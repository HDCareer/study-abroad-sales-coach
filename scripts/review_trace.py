"""Locally observed provenance and explicitly attributed upstream model records."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
import re

SCHEMA = 'skill3-run-provenance/1.0'
RECORD_SCHEMA = 'skill3-analysis-run/1.0'


def stamp_report(html, provenance, escape):
    coverage = provenance['coverage']; upstream = provenance['upstream']
    labels = {'complete':'已登记的成功完整调用覆盖了所给来源', 'partial':'所给来源尚有未被完整调用覆盖的消息',
              'not_checked':'模型资料覆盖未核验'}
    model = upstream.get('model')
    model_label = model['provider']+' / '+model['name'] if model else '未提供实际模型运行记录'
    count = lambda value: '未知' if value is None else str(value)
    note = ('<details class="panel"><summary>分析过程与资料覆盖</summary><p>'+escape(labels[coverage['status']])+
            '</p><p>来源消息 '+count(coverage['source_message_count'])+'；已登记送入 '+count(coverage['supplied_message_count'])+
            '；成功完整调用覆盖 '+count(coverage['completed_call_message_count'])+'；分析中可核对消息 '+str(coverage['analysis_reference_count'])+
            '；媒体受限 '+str(len(coverage['media_limited_message_keys']))+' 条。</p><p>模型：'+escape(model_label)+
            '</p><p>资料覆盖完整不代表模型理解全文或判断正确；未记录的信息不推测补齐。</p></details>')
    return html.replace('</main>',note+'</main>',1)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def fingerprint(root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    paths = [root/'SKILL.md']
    for directory in ('references', 'scripts', 'assets', 'agents'):
        paths.extend(p for p in (root/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    files = {p.relative_to(root).as_posix(): digest(p.read_bytes()) for p in sorted(paths)}
    return {'sha256': digest(canonical(files)), 'files': files}


def descriptor(raw):
    return {'sha256': digest(raw), 'bytes': len(raw)}


def inventory(source, api):
    cases = source.get('cases') if isinstance(source, dict) else source
    api.require(isinstance(cases, list), 'trace.cases', '需要来源案例数组')
    rows = {}; seen = set()
    for case in cases:
        api.obj(case, 'trace.case')
        cid = api.string(case.get('id'), 'trace.case.id')
        api.require(cid not in seen, 'trace.case', '来源案例编号重复'); seen.add(cid)
        api.require(isinstance(case.get('messages'), list), 'trace.messages', '需要消息数组')
        for msg in case['messages']:
            api.obj(msg, 'trace.message')
            sid = msg.get('source_message_id')
            if sid is not None:
                locator = ['id', api.string(sid, 'trace.source_message_id')]
            else:
                row = msg.get('source_row', msg.get('row'))
                sheet = msg.get('source_sheet', msg.get('sheet', ''))
                api.require(type(row) is int and row >= 1 and isinstance(sheet, str), 'trace.locator', '没有稳定消息ID时须有工作表与正整数行号')
                locator = ['row', sheet, row]
            key = canonical([cid, locator]).decode('utf-8')
            api.require(key not in rows, 'trace.message', '同案来源消息编号/位置重复')
            for field in ('time', 'text'):
                api.string(msg.get(field), 'trace.'+field, empty=field=='text')
            role = msg.get('role', msg.get('speaker'))
            api.string(role, 'trace.role')
            # Media unavailable is retained as a limit, never inferred as no reply.
            media = msg.get('media_status', 'not_declared')
            api.choice(media, ('not_declared', 'not_applicable', 'readable', 'unreadable', 'partial'), 'trace.media_status')
            rows[key] = {'case_id': cid, 'content_sha256': digest(canonical({
                'time': msg['time'], 'text': msg['text'], 'role': role,
                'is_system_greeting': msg.get('is_system_greeting'), 'media_status': media})),
                'media_status': media}
    return rows


def build(data, api, inputs, source=None, run_record=None, record_root=None):
    """inputs contains exact bytes read by the CLI, not paths re-read later."""
    runtime = fingerprint()
    artifacts = {('history:'+digest(raw) if key.startswith('history:') else key): descriptor(raw)
                 for key, raw in sorted(inputs.items())}
    source_rows = inventory(source, api) if source is not None else None
    supplied, complete = set(), set()
    supplied_rows = {}
    reported = {'status': 'not_recorded', 'calls': []}
    attachments = {}
    if run_record is not None:
        api.obj(run_record, 'run-record')
        api.require(run_record.get('schema_version') == RECORD_SCHEMA, 'run-record.schema_version', '不支持的运行记录格式')
        for field in ('run_id', 'producer', 'recorded_at'):
            api.string(run_record.get(field), 'run-record.'+field)
        try:
            recorded = datetime.fromisoformat(run_record['recorded_at'])
            api.require(recorded.utcoffset() is not None, 'run-record.recorded_at', '运行日志使用带时区时间')
        except (ValueError, TypeError):
            raise api.ValidationError('run-record.recorded_at：需要带时区时间')
        api.require(run_record.get('analysis_sha256') == artifacts['analysis']['sha256'], 'run-record.analysis_sha256', '运行记录与本次分析文件不一致')
        api.require(run_record.get('skill_runtime_sha256') == runtime['sha256'], 'run-record.skill_runtime_sha256', '模型运行记录与当前Skill运行文件不一致；请使用对应冻结版本')
        model = api.obj(run_record.get('model'), 'run-record.model')
        for field in ('provider', 'name'):
            api.string(model.get(field), 'run-record.model.'+field)
        api.require('revision' in model and (model['revision'] is None or isinstance(model['revision'], str) and bool(model['revision'].strip())), 'run-record.model.revision', '模型修订未知须null')
        api.require(record_root is not None, 'run-record', '需运行附件基准目录')
        base = Path(record_root).resolve()
        def artifact(item, label):
            api.obj(item, label)
            relative = api.string(item.get('path'), label+'.path')
            path = (base/relative).resolve()
            api.require(not Path(relative).is_absolute() and path.is_relative_to(base) and path.is_file(), label, '运行附件须在运行记录目录内且真实存在')
            raw = path.read_bytes()
            api.require(item.get('sha256') == digest(raw), label, '运行附件摘要不符，不能证明记录指向此文件')
            attachments[label] = descriptor(raw)
            return raw
        artifact(run_record.get('prompt'), 'prompt')
        artifact(run_record.get('settings'), 'settings')
        calls = run_record.get('calls')
        api.require(isinstance(calls, list) and calls, 'run-record.calls', '需实际调用记录，无日志不伪造')
        seen = set(); reported_calls = []
        for call in calls:
            api.obj(call, 'run-record.call')
            cid = api.string(call.get('id'), 'run-record.call.id')
            api.require(bool(re.fullmatch(r'[A-Za-z0-9_-]{1,100}', cid)) and cid not in seen, 'run-record.call.id', '调用编号需唯一且仅字母数字下划线连字符'); seen.add(cid)
            api.choice(call.get('status'), ('success', 'failed', 'cancelled'), 'run-record.call.status')
            api.require(type(call.get('truncated')) is bool or call.get('truncated') is None, 'run-record.call.truncated', '截断状态须true/false/null')
            api.require('truncated' in call, 'run-record.call.truncated', '未知截断须显式null')
            try:
                start = datetime.fromisoformat(call['started_at']); end = datetime.fromisoformat(call['ended_at'])
                api.require(start.utcoffset() is not None and end.utcoffset() is not None and start <= end <= recorded, 'run-record.call.time', '调用起止须带时区且不晚于日志登记')
            except (ValueError, TypeError, KeyError):
                raise api.ValidationError('run-record.call.time：无法比较调用时间')
            packet = json.loads(artifact(call.get('input'), cid+'.input').decode('utf-8-sig'))
            api.require(isinstance(packet, dict) and packet.get('schema_version') == 'skill3-model-packet/1.0', 'run-record.input', '需要归档的实际模型资料包')
            rows = inventory(packet, api)
            api.require(all(k not in supplied_rows or supplied_rows[k] == v for k,v in rows.items()), 'run-record.input', '同一消息在多次调用中的内容不一致')
            supplied_rows.update(rows)
            if source_rows is not None:
                api.require(set(rows) <= set(source_rows), 'run-record.input', '模型资料包含本次独立源之外的消息，须提供完整授权源')
                api.require(all(rows[k] == source_rows[k] for k in rows), 'run-record.input', '送入记录的消息与独立源的角色/时间/原文/媒体状态不一致')
            artifact(call.get('response'), cid+'.response')
            media = call.get('attachments', [])
            api.require(isinstance(media, list), 'run-record.call.attachments', '附加图片/语音/文件需为数组')
            media_ids = set()
            for item in media:
                api.obj(item, 'run-record.call.attachment')
                mid = api.string(item.get('id'), 'run-record.call.attachment.id')
                api.require(bool(re.fullmatch(r'[A-Za-z0-9_-]{1,100}',mid)) and mid not in media_ids,
                            'run-record.call.attachment.id', '附件编号须唯一且仅字母数字下划线连字符')
                media_ids.add(mid); artifact(item, cid+'.attachment.'+mid)
            supplied.update(rows)
            if call['status'] == 'success' and call['truncated'] is False:
                complete.update(rows)
            reported_calls.append({'id': cid, 'status': call['status'], 'truncated': call['truncated'],
                                   'started_at': call['started_at'], 'ended_at': call['ended_at'],
                                   'message_count': len(rows), 'message_keys': sorted(rows), 'attachment_ids': sorted(media_ids)})
        reported = {'status': 'recorded_by_upstream', 'run_id': run_record['run_id'], 'producer': run_record['producer'],
                    'recorded_at': run_record['recorded_at'], 'model': {k: model[k] for k in ('provider','name','revision')},
                    'calls': reported_calls, 'artifacts': attachments}
    unknown_media = [k for k,v in (source_rows or {}).items() if v['media_status'] in ('unreadable','partial')]
    missing = sorted(set(source_rows)-complete) if source_rows is not None else None
    coverage = 'not_checked' if source_rows is None or run_record is None else 'complete' if not missing else 'partial'
    identity = {'inputs': artifacts, 'runtime_sha256': runtime['sha256'], 'upstream_artifacts': attachments,
                'python_version': platform.python_version()}
    return {'schema_version': SCHEMA, 'identity': identity, 'runtime': runtime, 'upstream': reported,
            'coverage': {'status': coverage, 'source_message_count': len(source_rows) if source_rows is not None else None,
                         'analysis_reference_count': sum(len(c['source_messages']) for c in data['cases']),
                         'claimed_read_message_count': data.get('management',{}).get('read_message_count'),
                         'supplied_message_count': len(supplied) if run_record is not None else None,
                         'completed_call_message_count': len(complete) if run_record is not None else None,
                         'missing_from_completed_calls': missing if run_record is not None else None,
                         'media_limited_message_keys': unknown_media},
            'limits': ['调用状态及模型身份由上游登记，程序只核对本地文件与一致性，不认证平台日志真伪。',
                       '完整资料覆盖不证明模型理解全文或判断正确；媒体不可读限制另列。',
                       '哈希用于检查变化，不是匿名化、权限认证或长期留存授权。']}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='读取当前冻结Skill运行文件指纹，不调用模型')
    parser.add_argument('--fingerprint', action='store_true', required=True)
    parser.parse_args()
    print(json.dumps(fingerprint(), ensure_ascii=False, indent=2))
