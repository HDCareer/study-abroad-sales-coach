"""Verified member deliveries -> evidence-bound supervisor review -> local team view.

This adapter does not classify chat text, call a model, or change member results.
The supervisor review is a separately versioned model-produced input, not a source
of replacement payment, validity, phase, or action facts.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid

import coaching_review
import management_review
import render_chat_review as api
import review_delivery

REQUEST_SCHEMA = 'skill3-supervisor-request/1.0'
REVIEW_SCHEMA = 'skill3-supervisor-review/1.0'
RESULT_SCHEMA = 'skill3-supervisor-results/1.0'
RUN_SCHEMA = 'skill3-supervisor-run/1.0'
DELIVERY_SCHEMA = 'skill3-supervisor-delivery/1.0'
PAYLOADS = ('team-results.json', 'report.html', 'run.json')
ATTENTION = {'manager', 'advisor', 'historical', 'none'}
TRIGGERS = {'trial_followup', 'trial_preparation', 'course_verify', 'customer_blocker',
            'commitment_due', 'order_verify', 'scope_verify', 'service_followup', 'none'}
LAYERS = {'judgment', 'expression', 'execution'}
STAGES = {'reception', 'diagnosis', 'proposal', 'objection', 'close'}
COURSE_STATES = {'unknown', 'not_confirmed_paid', 'paid_schedule_unknown', 'scheduled', 'partial', 'completed'}
WINDOW_KEYS = ('week_start', 'week_end', 'cutoff', 'time_basis')


class BoundData(dict):
    """Keep local read-only input roots in memory, never in serialized output."""
    def __init__(self, value, member_deliveries):
        super().__init__(value)
        self.member_deliveries = tuple(Path(p).resolve() for p in member_deliveries)


def protect_output(path, member_deliveries, *, directory=False, input_paths=()):
    target = Path(path).resolve()
    require(bool(member_deliveries), '写入前须保留来源成员目录绑定')
    for value in member_deliveries:
        source = Path(value).resolve()
        require(target != source and source not in target.parents,
                '输出不能位于来源成员交付目录内：' + str(source))
        if directory:
            require(target not in source.parents, '输出目录不能包含来源成员交付目录')
    for value in input_paths:
        source = Path(value).resolve()
        require(target != source and (not directory or target not in source.parents),
                '输出不能覆盖或包含本次输入文件：' + str(source))


def source_runtime(result):
    provenance = result.get('provenance') or {}
    runtime = provenance.get('runtime') or {}
    identity = provenance.get('identity') or {}
    digest = runtime.get('sha256')
    files = runtime.get('files')
    require(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest),
            '成员缺少可校验的Skill运行指纹')
    require(isinstance(files, dict) and bool(files) and all(
        isinstance(p, str) and isinstance(v, str) and re.fullmatch(r'[0-9a-f]{64}', v)
        for p, v in files.items()), '成员Skill运行文件摘要无效')
    require(digest == identity.get('runtime_sha256') == sha(canonical(files)),
            '成员Skill运行指纹内部不一致')
    return digest


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def text(value, name, empty=False):
    require(isinstance(value, str) and (empty or bool(value.strip())), name + '须为非空文字')
    return value


def exact(value, keys, name):
    require(isinstance(value, dict) and set(value) == set(keys), name + '字段缺失或含不支持的字段')


def dt(value):
    text(value, '时间')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('时间须为ISO格式：' + value) from exc


def not_after(value, cutoff):
    try:
        return dt(value) <= dt(cutoff)
    except TypeError as exc:
        raise ValueError('引用与截止的时区口径不一致') from exc


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _runtime():
    root = Path(__file__).resolve().parents[1]
    match = re.search(r'^版本：([^。\s]+)', (root/'SKILL.md').read_text(encoding='utf-8-sig'), re.MULTILINE)
    require(match is not None, '无法取得当前运行Skill版本')
    paths = [Path(__file__).with_name(name) for name in (
        'team_management.py', 'team_management_render.py', 'supervisor_business.py',
        'supervisor_history.py', 'followup_contact.py', 'review_delivery.py', 'coaching_review.py',
        'management_review.py')]
    paths += [root/'SKILL.md', root/'references/supervisor-management.md',
              root/'references/supervisor-output-contract.md']
    return {'skill_version': match.group(1),
            'files': {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in paths}}


def request_id(binding, previous_team=None):
    return sha(canonical(binding if previous_team is None else
                         {'members': binding, 'previous_team': previous_team}))


def prepare(member_deliveries, previous_team_delivery=None):
    """Read only independently verified, source-matched immutable member bundles."""
    require(isinstance(member_deliveries, (list, tuple)) and member_deliveries, '至少需要一个成员交付目录')
    members = []; seen = set(); window = rules = version = runtime_digest = target_period = None
    for directory in member_deliveries:
        manifest = review_delivery.verify(directory)
        path = Path(directory)/'results.json'
        raw = path.read_bytes()
        require(manifest['files']['results.json'] == {'sha256': sha(raw), 'bytes': len(raw)}, '读取过程中成员结果发生变化')
        result = json.loads(raw.decode('utf-8'))
        require(result.get('source_verification', {}).get('status') == 'matched', '成员必须通过独立来源匹配校验')
        sid = text(result.get('sales', {}).get('id'), '成员sales.id')
        require(sid not in seen, '同一销售重复输入：' + sid); seen.add(sid)
        rw = result.get('reporting_window')
        exact(rw, WINDOW_KEYS, 'reporting_window')
        for key in WINDOW_KEYS:
            text(rw[key], 'reporting_window.' + key)
        require(not_after(rw['week_start'], rw['week_end']) and not_after(rw['week_end'], rw['cutoff']), '统计期与截止顺序错误')
        member_target = management_review.validate_target_period(result.get('target_period'), rw)
        require(result.get('period', {}).get('start') == rw['week_start'] and
                result.get('period', {}).get('end') == rw['week_end'] and
                result.get('period', {}).get('cutoff') == rw['cutoff'], '成员period与reporting_window不一致')
        require(isinstance(result.get('rules'), list), '成员rules必须为数组')
        member_runtime = source_runtime(result)
        if window is None:
            window, rules, version = copy.deepcopy(rw), copy.deepcopy(result['rules']), result['skill_version']
            runtime_digest = member_runtime
            target_period = copy.deepcopy(member_target)
        else:
            require(rw == window, '成员统计期、资料截止或time_basis不一致')
            require(member_target == target_period, '成员完整考核周不一致，不能混拼截至期间与目标期间')
            require(result['rules'] == rules, '成员采用的业务规则不一致')
            require(result['skill_version'] == version, '成员Skill版本不一致')
            require(member_runtime == runtime_digest, '成员实际Skill运行规则文件不一致，不能只凭相同版本号合并')
        require(isinstance(result.get('cases'), list), '成员cases必须为数组')
        ids = set()
        for case in result['cases']:
            cid = text(case.get('case_id'), '成员case_id')
            require(cid not in ids and case.get('sales_id') == sid, '成员case重复或销售归属错误')
            ids.add(cid)
            require(type(case.get('included')) is bool, '成员included须明确布尔值')
        require(isinstance(result.get('must_follow_case_ids'), list) and
                len(set(result['must_follow_case_ids'])) == len(result['must_follow_case_ids']) and
                set(result['must_follow_case_ids']) <= ids, '成员必须跟回清单无效')
        members.append({'sales_id': sid, 'analysis_id': result['analysis_id'],
                        'results_sha256': sha(raw), 'result': result})
    members.sort(key=lambda m: m['sales_id'])
    binding = [{'sales_id': m['sales_id'], 'analysis_id': m['analysis_id'],
                'results_sha256': m['results_sha256']} for m in members]
    previous_team = previous_result = None
    protected = list(member_deliveries)
    if previous_team_delivery is not None:
        import supervisor_history
        manifest = verify(previous_team_delivery)
        raw = (Path(previous_team_delivery)/'team-results.json').read_bytes()
        require(manifest['files']['team-results.json'] == {'sha256': sha(raw), 'bytes': len(raw)},
                '读取过程中上一团队结果发生变化')
        previous_result = json.loads(raw.decode('utf-8'))
        supervisor_history.build([], window, [], previous_result)
        previous_team = {'team_analysis_id': previous_result['team_analysis_id'], 'results_sha256': sha(raw)}
        protected.append(previous_team_delivery)
    return BoundData({'schema_version': REQUEST_SCHEMA, 'request_id': request_id(binding, previous_team),
            'reporting_window': window, 'target_period': target_period, 'source_skill_version': version, 'rules': rules,
            'model_coverage': 'not_checked', 'members': members,
            'previous_team': previous_team, 'previous_result': previous_result}, protected)


def _source_maps(request):
    sources = {}; plans = {}; names = {}
    for member in request['members']:
        sid = member['sales_id']; result = member['result']
        names[sid] = result['sales'].get('name', sid)
        current = (result.get('coaching') or {}).get('plans', [])
        plans[sid] = {p['id']: p for p in current}
        require(len(plans[sid]) == len(current), '源带教计划ID重复')
        for case in result['cases']:
            if case['included']:
                sources[(sid, case['case_id'])] = case
    return sources, plans, names


def _refs(values, case, cutoff, needed=False):
    require(isinstance(values, list) and all(isinstance(r, str) for r in values), 'refs必须为消息ID数组')
    require(len(values) == len(set(values)) and (values or not needed), 'refs重复或缺少必要证据')
    evidence = {m['id']: m for m in case.get('evidence', [])}
    require(len(evidence) == len(case.get('evidence', [])), '源evidence消息ID重复')
    for rid in values:
        require(rid in evidence, '引用不在本案标准结果evidence中：' + rid)
        msg = evidence[rid]
        require(not msg.get('sensitive') and isinstance(msg.get('text'), str) and msg['text'].strip(), '引用为敏感或空白消息')
        require(not_after(msg['time'], cutoff), '引用晚于相应截止：' + rid)


def _validate_preparation(value, source, cutoff):
    if value is None:
        return
    exact(value, ('course_state', 'student_goal', 'teacher_alignment', 'preparation', 'refs'), 'trial_preparation')
    state = value['course_state']
    require(state in COURSE_STATES, 'course_state不支持')
    for key in ('student_goal', 'teacher_alignment', 'preparation'):
        text(value[key], 'trial_preparation.' + key)
    _refs(value['refs'], source, cutoff, needed=state != 'unknown')
    trial = source.get('trial') or {}
    paid, completed = trial.get('paid'), trial.get('completed')
    require((state == 'completed') == (completed is True), 'course_state与已确认完课事实不一致')
    if state == 'not_confirmed_paid':
        require(paid is not True, '已确认试听付款不能重标未确认付款')
    if state in ('paid_schedule_unknown', 'scheduled', 'partial'):
        require(paid is True and completed is not True, '课前/部分完课状态需要已付且未确认完整完课')


def validate_review(request, review):
    exact(review, ('schema_version', 'request_id', 'producer', 'human_approval', 'cases', 'team_topics', 'advisor_focus'), 'supervisor review')
    require(review['schema_version'] == REVIEW_SCHEMA and review['request_id'] == request['request_id'], '主管审阅版本或request_id不匹配')
    exact(review['producer'], ('kind', 'name'), 'producer')
    require(review['producer']['kind'] == 'model', 'producer.kind须为model；声明不等于实际API日志')
    text(review['producer']['name'], 'producer.name')
    require(review['human_approval'] == 'not_provided', '本模块不认证主管批准，禁止模型代填人工确认')
    sources, plans, _ = _source_maps(request)
    cutoff = request['reporting_window']['cutoff']; end = request['reporting_window']['week_end']
    require(isinstance(review['cases'], list), 'cases须为数组')
    decisions = {}
    keys = ('sales_id', 'case_id', 'attention', 'trigger', 'priority', 'title', 'why', 'refs', 'action_index', 'trial_preparation')
    first_sale = {'trial_followup', 'trial_preparation', 'customer_blocker', 'commitment_due'}
    for decision in review['cases']:
        exact(decision, keys, 'case review')
        key = (text(decision['sales_id'], 'sales_id'), text(decision['case_id'], 'case_id'))
        require(key in sources and key not in decisions, '主管决策引用串案、排除案或重复案例')
        source = sources[key]; decisions[key] = decision
        attention, trigger, priority = decision['attention'], decision['trigger'], decision['priority']
        require(attention in ATTENTION and trigger in TRIGGERS, 'attention或trigger不支持')
        text(decision['title'], 'title'); text(decision['why'], 'why')
        active = attention in ('manager', 'advisor')
        if active:
            require(type(priority) is int and priority in (1, 2, 3) and trigger != 'none', '需处理事项必须有priority与实际trigger')
        else:
            require(priority is None, 'none/historical的priority必须为null')
        if attention == 'none':
            require(trigger == 'none', 'none不允许保留活跃触发')
        _refs(decision['refs'], source, cutoff, needed=active or attention == 'historical')
        index = decision['action_index']; actions = (source.get('recovery') or {}).get('actions', [])
        require(index is None or (type(index) is int and 0 <= index < len(actions)), 'action_index必须定位源recovery.actions')
        require(not active or index is not None, '需处理事项必须选择现有下一动作')
        formal = source.get('formal', {}).get('confirmed') is True
        completed = source.get('trial', {}).get('completed') is True
        possibility = source.get('recovery', {}).get('possibility')
        if active and trigger in first_sale:
            require(not formal and possibility not in ('not_now', 'no_contact'), '已正式购买/不宜再推/拒收联系不得重启首次追单')
        if active and trigger == 'trial_followup':
            require(completed and not formal, '试听转正跟进须有完整完课且未确认正式购买')
        if active and trigger == 'trial_preparation':
            require(not completed, '已完整完课不能再作试听准备')
            require(decision['trial_preparation'] is not None, '试听准备须提供准备检查')
        if active and trigger == 'order_verify':
            require(not formal, '已确认正式购买不能重启订单是否购买核实')
        if active and trigger == 'course_verify':
            require(not completed, '已确认完整完课不能重启是否完课核实')
        if active and trigger == 'service_followup':
            require(formal, '正式购课后的服务核查须有源formal.confirmed=true；不能代替首次转正')
        if active and trigger == 'scope_verify':
            criteria = source.get('validity', {}).get('assessment', {}).get('criteria', {})
            require(not (criteria.get('scope', {}).get('state') == 'yes' and criteria.get('delivery', {}).get('state') == 'yes'), '覆盖及交付均已确认，不能重启范围核实')
        _validate_preparation(decision['trial_preparation'], source, cutoff)
    require(set(decisions) == set(sources), '主管决策必须覆盖全部included案例，不能只提供首屏案例')
    require(isinstance(review['team_topics'], list) and len(review['team_topics']) <= 3, '团队主题最多3项')
    topic_ids = set()
    for topic in review['team_topics']:
        exact(topic, ('id', 'title', 'opportunity_definition', 'layer', 'stage', 'exercise', 'pass_criteria', 'source', 'members'), 'team topic')
        tid = text(topic['id'], 'topic.id')
        require(tid not in topic_ids, '团队主题ID重复'); topic_ids.add(tid)
        for field in ('title', 'opportunity_definition', 'exercise', 'pass_criteria'):
            text(topic[field], 'topic.' + field)
        require(topic['layer'] in LAYERS | {'mixed'} and topic['stage'] in STAGES, '主题层次/阶段无效')
        exact(topic['source'], ('path', 'quote'), 'topic.source')
        quote = text(topic['source']['quote'], 'source.quote')
        original = coaching_review.source_text(topic['source']['path'], api)
        require(len(coaching_review.canonical(quote)) >= 8 and coaching_review.canonical(quote) in coaching_review.canonical(original), '团队训练引文不在所指Skill原文或过短')
        require(isinstance(topic['members'], list) and topic['members'], '团队主题需要成员证据')
        member_keys = set(); gap_sales = set(); gap_layers = set()
        for member in topic['members']:
            exact(member, ('sales_id', 'case_id', 'layer', 'basis', 'status', 'refs', 'why_same'), 'topic member')
            key = (text(member['sales_id'], 'member.sales_id'), text(member['case_id'], 'member.case_id'))
            require(key in sources and key not in member_keys, '同主题案例重复或不存在'); member_keys.add(key)
            source = sources[key]; layer = member['layer']; status = member['status']
            require(layer in LAYERS and member['basis'] in ('layer', 'issue') and status in ('gap', 'sound', 'unknown'), '主题成员依据类型无效')
            require(topic['layer'] == 'mixed' or topic['layer'] == layer, '主题层次须与成员一致或用mixed')
            text(member['why_same'], 'why_same')
            _refs(member['refs'], source, end, needed=status != 'unknown')
            basis = (source.get('layers') or {}).get(layer, {}) if member['basis'] == 'layer' else source.get('issue', {})
            observed = basis.get('status') if member['basis'] == 'layer' else basis.get('kind')
            expected = status if member['basis'] == 'layer' else {'gap': 'gap', 'sound': 'none', 'unknown': 'unknown'}[status]
            if status != 'unknown':
                require(observed == expected, '团队成员状态与源层次/问题结论冲突')
                require(bool(set(member['refs']) & set(basis.get('refs', []))), '团队成员须引用对应源判断的证据')
            if status == 'gap':
                evidence = {m['id']: m for m in source['evidence']}
                start = request['reporting_window']['week_start']
                require(any(not_after(start, evidence[rid]['time']) for rid in member['refs']),
                        '团队缺口成员至少需要一条统计周内证据，不能只用旧历史')
                gap_sales.add(key[0])
                gap_layers.add(layer)
        require(len(gap_sales) >= 2, '团队共性须至少两位顾问存在已举证缺口')
        require(topic['layer'] != 'mixed' or len(gap_layers) >= 2, 'mixed主题须实际包含多个缺口层次')
    require(isinstance(review['advisor_focus'], list), 'advisor_focus须为数组')
    focus_sales = set()
    for focus in review['advisor_focus']:
        exact(focus, ('sales_id', 'plan_id', 'reason', 'case_ids'), 'advisor_focus')
        sid = text(focus['sales_id'], 'focus.sales_id')
        require(sid in plans and sid not in focus_sales, '顾问焦点销售重复或不存在'); focus_sales.add(sid)
        text(focus['reason'], 'focus.reason'); ids = focus['case_ids']; pid = focus['plan_id']
        require(isinstance(ids, list) and all(isinstance(cid, str) for cid in ids) and len(ids) == len(set(ids)), '焦点case_ids须唯一')
        if pid is None:
            require(not ids, '没有计划时不能虚构焦点案例')
        else:
            require(pid in plans[sid] and ids and set(ids) <= set(plans[sid][pid]['case_ids']), '焦点须引用源计划和其中案例')
    require(focus_sales == set(plans), 'advisor_focus须覆盖全部顾问')
    return decisions


def build_business(payload, sales_ids, reporting_window, target_period=None):
    import supervisor_business
    return supervisor_business.build(payload, sales_ids, reporting_window, target_period)


def _warning_rank(source):
    code = source.get('trial_warning', {}).get('code', '')
    return {'red': 0, 'orange': 1, 'yellow': 2}.get(code, 3)


def _result_id(result):
    return sha(canonical({k: v for k, v in result.items() if k not in ('team_analysis_id', 'provenance')}))


def build(member_deliveries, review, business=None, previous_team_delivery=None):
    request = prepare(member_deliveries, previous_team_delivery)
    decisions = validate_review(request, review)
    sources, plans, names = _source_maps(request)
    source_members = []
    for member in request['members']:
        result = member['result']
        source_members.append({k: member[k] for k in ('sales_id', 'analysis_id', 'results_sha256')} |
                              {'sales_name': names[member['sales_id']], 'skill_version': result['skill_version'],
                               'source_verification': copy.deepcopy(result['source_verification']),
                               'model_coverage': copy.deepcopy((result.get('provenance') or {}).get('coverage', {'status': 'not_checked'}))})
    rows = []; log = []; must = []
    for key in sorted(sources):
        source, decision = sources[key], decisions[key]
        action = None if decision['action_index'] is None else copy.deepcopy(source['recovery']['actions'][decision['action_index']])
        row = {'sales_id': key[0], 'sales_name': names[key[0]], 'case_id': key[1], 'name': source['name'],
               'source': copy.deepcopy(source), 'decision': copy.deepcopy(decision),
               'manager_question': source.get('recovery', {}).get('coaching_question', ''), 'action': action}
        rows.append(row)
        log.append({'sales_id': key[0], 'case_id': key[1], 'attention': decision['attention'], 'trigger': decision['trigger'],
                    'priority': decision['priority'], 'why': decision['why'], 'refs': copy.deepcopy(decision['refs'])})
    bykey = {(r['sales_id'], r['case_id']): r for r in rows}
    for member in request['members']:
        for cid in member['result']['must_follow_case_ids']:
            key = (member['sales_id'], cid)
            require(key in sources, '源必须跟回清单含排除案例')
            must.append({'sales_id': key[0], 'case_id': cid, 'must_follow': copy.deepcopy(sources[key]['must_follow']),
                         'supervisor_attention': decisions[key]['attention'], 'decision_reason': decisions[key]['why']})
    sort_key = lambda row: (row['decision']['priority'], _warning_rank(row['source']), row['sales_id'], row['case_id'])
    queue = [dict(row, rank=i + 1) for i, row in enumerate(sorted(
        [r for r in rows if r['decision']['attention'] == 'manager'], key=sort_key))]
    advisor_queue = [dict(row, rank=i + 1) for i, row in enumerate(sorted(
        [r for r in rows if r['decision']['attention'] == 'advisor'], key=sort_key))]
    topics = []
    for item in review['team_topics']:
        topic = copy.deepcopy(item)
        topic['counts'] = {'case_count': len(topic['members']), 'advisor_count': len({m['sales_id'] for m in topic['members']}),
                           'gap_case_count': sum(m['status'] == 'gap' for m in topic['members']),
                           'gap_advisor_count': len({m['sales_id'] for m in topic['members'] if m['status'] == 'gap'}),
                           'unique_customer_count': None, 'gap_rate': None}
        topic['count_note'] = '仅统计已举证案例和顾问；未建立全量可比较机会分母，不计算发生率或独立客户数。'
        topics.append(topic)
    focuses = []
    for focus in sorted(review['advisor_focus'], key=lambda x: x['sales_id']):
        focuses.append(copy.deepcopy(focus) | {'sales_name': names[focus['sales_id']],
                       'plan': None if focus['plan_id'] is None else copy.deepcopy(plans[focus['sales_id']][focus['plan_id']])})
    result = {'schema_version': RESULT_SCHEMA, 'request_id': request['request_id'],
              'previous_team': copy.deepcopy(request['previous_team']),
              'source_skill_version': request['source_skill_version'], 'reporting_window': request['reporting_window'],
              'target_period': copy.deepcopy(request['target_period']),
              'source_members': source_members, 'rules': copy.deepcopy(request['rules']),
              'producer': copy.deepcopy(review['producer']), 'human_approval': review['human_approval'],
              'model_coverage': 'not_checked', 'homepage_limit': 3,
              'cases': rows, 'queue': queue, 'advisor_queue': advisor_queue, 'decision_log': log,
              'source_must_follow': must, 'team_topics': topics, 'advisor_focus': focuses,
              'business': build_business(business, sorted(names), request['reporting_window'], request['target_period']),
              'input_hashes': {'review_sha256': sha(canonical(review)),
                               'business_sha256': None if business is None else sha(canonical(business))},
              'limitations': ['主管摘要与团队归并为模型声明，未登记实际模型API覆盖或人工批准。',
                              '标准结果只含引用证据，不含完整聊天；未选入主管首页不等于原跟进任务已完成。',
                              '团队案例数不等于去重客户数；共同问题不能直接解释全部业绩差距。']}
    import supervisor_history
    result.update(supervisor_history.build(rows, request['reporting_window'], source_members, request['previous_result']))
    current_pool = {(e['sales_id'], e['case_id']): e for e in result['opportunity_pool']['entries']
                    if e['refresh_status'] == 'current'}
    for row in rows:
        entry = current_pool.get((row['sales_id'], row['case_id']))
        row['contact_status'] = copy.deepcopy(entry['contact_status'] if entry else
                                             supervisor_history._contact(row['source'], request['reporting_window']['cutoff']))
        row['contact_refresh_status'] = entry['contact_refresh_status'] if entry else 'current'
        row['contact_routing'] = supervisor_history.contact_routing(row, row['contact_status'])
    result['queue'] = [dict(row, rank=i + 1) for i, row in enumerate(sorted(
        [r for r in rows if r['decision']['attention'] == 'manager' and not r['contact_routing']['paused']], key=sort_key))]
    result['advisor_queue'] = [dict(row, rank=i + 1) for i, row in enumerate(sorted(
        [r for r in rows if r['decision']['attention'] == 'advisor' and not r['contact_routing']['paused']], key=sort_key))]
    result['paused_contact'] = [copy.deepcopy(row) for row in rows if row['contact_routing']['paused']]
    for item in result['decision_log']:
        row = bykey[(item['sales_id'], item['case_id'])]
        item['contact_routing'] = copy.deepcopy(row['contact_routing'])
    for item in result['source_must_follow']:
        row = bykey[(item['sales_id'], item['case_id'])]
        item['contact_routing'] = copy.deepcopy(row['contact_routing'])
    runtime = _runtime()
    result['runtime'] = runtime
    result['team_analysis_id'] = _result_id(result)
    result['provenance'] = {'schema_version': RUN_SCHEMA, 'team_analysis_id': result['team_analysis_id'],
                            'request_id': request['request_id'], **result['input_hashes'],
                             'previous_team': copy.deepcopy(request['previous_team']),
                            'sources': [{k: m[k] for k in ('sales_id', 'analysis_id', 'results_sha256')} for m in source_members],
                            'runtime': runtime, 'producer': copy.deepcopy(review['producer']),
                            'model_coverage': 'not_checked', 'human_approval': 'not_provided'}
    return BoundData(result, request.member_deliveries)


def verify(directory):
    root = Path(directory)
    require(root.is_dir() and not root.is_symlink(), '团队交付目录不存在或为链接')
    require({p.name for p in root.iterdir()} == set(PAYLOADS) | {'TEAM-DELIVERY.json'}, '团队交付不完整或混入其他文件')
    for name in (*PAYLOADS, 'TEAM-DELIVERY.json'):
        require((root/name).is_file() and not (root/name).is_symlink(), '团队交付文件须为普通文件')
    manifest = _json(root/'TEAM-DELIVERY.json')
    require(isinstance(manifest, dict) and manifest.get('schema_version') == DELIVERY_SCHEMA and manifest.get('status') == 'complete', '团队完成标记无效')
    aid = manifest.get('team_analysis_id')
    require(isinstance(aid, str) and re.fullmatch(r'[0-9a-f]{64}', aid), '团队分析编号格式无效')
    require(isinstance(manifest.get('files'), dict) and set(manifest['files']) == set(PAYLOADS), '团队完成清单文件范围错误')
    for name in PAYLOADS:
        raw = (root/name).read_bytes()
        require(manifest['files'][name] == {'sha256': sha(raw), 'bytes': len(raw)}, '团队交付文件摘要不一致：' + name)
    result = _json(root/'team-results.json'); run = _json(root/'run.json')
    require(isinstance(result, dict) and isinstance(run, dict), '团队结果与运行记录须为对象')
    require(result.get('schema_version') == RESULT_SCHEMA and result.get('team_analysis_id') == aid and _result_id(result) == aid, '团队结果内容或编号不一致')
    require(result.get('provenance') == run and run.get('schema_version') == RUN_SCHEMA and run.get('team_analysis_id') == aid, '团队运行记录不一致')
    require(run.get('request_id') == result.get('request_id'), '团队请求绑定不一致')
    require(all(run.get(k) == v for k, v in result.get('input_hashes', {}).items()) and
            set(result.get('input_hashes', {})) == {'review_sha256', 'business_sha256'}, '团队上游输入摘要不一致')
    require(run.get('runtime') == result.get('runtime') and run.get('producer') == result.get('producer') and
            run.get('model_coverage') == result.get('model_coverage') == 'not_checked' and
            run.get('human_approval') == result.get('human_approval') == 'not_provided', '团队运行来源或核验边界不一致')
    binding = [{k: m[k] for k in ('sales_id', 'analysis_id', 'results_sha256')} for m in result['source_members']]
    previous_team = result.get('previous_team')
    if previous_team is not None:
        exact(previous_team, ('team_analysis_id', 'results_sha256'), 'previous_team')
        require(all(isinstance(v, str) and re.fullmatch(r'[0-9a-f]{64}', v) for v in previous_team.values()), '上一团队绑定摘要无效')
    require(run.get('previous_team') == previous_team and binding == run.get('sources') and
            request_id(binding, previous_team) == result['request_id'], '团队来源绑定不一致')
    html = (root/'report.html').read_text(encoding='utf-8')
    require(re.findall(r'<main\b[^>]*\bdata-team-analysis-id="([^"]+)"', html) == [aid], '团队HTML分析编号缺失或重复')
    require(manifest.get('source_skill_version') == result.get('source_skill_version'), '团队源Skill版本不一致')
    return manifest


def _write(path, raw):
    with path.open('xb') as handle:
        handle.write(raw); handle.flush(); os.fsync(handle.fileno())


def publish(directory, result, *, member_deliveries=(), input_paths=()):
    import team_management_render
    require(not Path(directory).is_symlink(), '交付目标不能为链接')
    protect_output(directory, member_deliveries or getattr(result, 'member_deliveries', ()),
                   directory=True, input_paths=input_paths)
    target = Path(directory).resolve(); api.private_output(target)
    require(result.get('team_analysis_id') == _result_id(result), '待交付结果内容已改变')
    html = team_management_render.render(result)
    payload = {'team-results.json': json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8'),
               'report.html': html.encode('utf-8'),
               'run.json': json.dumps(result['provenance'], ensure_ascii=False, indent=2).encode('utf-8')}
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.parent/('.' + target.name + '.team-delivery.lock')
    token = uuid.uuid4().hex; stage = None; acquired = False
    try:
        with lock.open('xb') as handle:
            acquired = True; handle.write(token.encode('ascii')); handle.flush(); os.fsync(handle.fileno())
        if target.exists():
            manifest = verify(target)
            require(manifest['team_analysis_id'] == result['team_analysis_id'] and all(
                manifest['files'][name] == {'sha256': sha(raw), 'bytes': len(raw)} for name, raw in payload.items()),
                '目标已有不同或损坏交付；请使用新修订目录')
            return {'status': 'reused', 'directory': str(target), 'team_analysis_id': result['team_analysis_id']}
        stage = Path(tempfile.mkdtemp(prefix='.' + target.name + '.staging-', dir=target.parent))
        require(stage.resolve().parent == target.parent, '暂存目录不在目标父目录')
        for name, raw in payload.items():
            _write(stage/name, raw)
        manifest = {'schema_version': DELIVERY_SCHEMA, 'status': 'complete', 'team_analysis_id': result['team_analysis_id'],
                    'source_skill_version': result['source_skill_version'], 'created_at': datetime.now(timezone.utc).isoformat(),
                    'files': {name: {'sha256': sha(raw), 'bytes': len(raw)} for name, raw in payload.items()}}
        _write(stage/'TEAM-DELIVERY.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'))
        verify(stage)
        require(not target.exists(), '提交前目标已出现，请检查并发交付')
        os.rename(stage, target); stage = None
        return {'status': 'complete', 'directory': str(target), 'team_analysis_id': result['team_analysis_id']}
    finally:
        # Remove only this attempt's known files, never recursively delete user data.
        if stage is not None:
            require(stage.resolve().parent == target.parent, '拒绝清理目标之外的暂存目录')
            for name in (*PAYLOADS, 'TEAM-DELIVERY.json'):
                path = stage/name
                if path.is_file() and not path.is_symlink():
                    path.unlink()
            stage.rmdir()
        if acquired and lock.is_file() and not lock.is_symlink() and lock.read_text(encoding='ascii') == token:
            lock.unlink()


def write_request(path, request, *, member_deliveries=()):
    path = Path(path)
    protect_output(path, member_deliveries or getattr(request, 'member_deliveries', ()))
    require(not path.is_symlink(), '请求输出不能为链接')
    api.private_output(path)
    raw = json.dumps(request, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
    if path.exists():
        require(path.is_file() and path.read_bytes() == raw, '请求输出已存在不同内容，请用新文件')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(path, raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description='仅从已验证的单顾问交付生成主管管理与团队汇总；不调用模型或外网')
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare', help='核验成员交付并生成供模型读取的统一请求')
    prep.add_argument('--member-delivery', action='append', required=True, type=Path)
    prep.add_argument('--output', required=True, type=Path)
    prep.add_argument('--previous-team-delivery', type=Path)
    prep.add_argument('--require-history', action='store_true', help='连续运行守卫：缺上一完整团队交付则拒收')
    create = sub.add_parser('build', help='验证主管review后生成不可覆盖的完整团队交付')
    create.add_argument('--member-delivery', action='append', required=True, type=Path)
    create.add_argument('--review', required=True, type=Path)
    create.add_argument('--business', type=Path)
    create.add_argument('--delivery-dir', required=True, type=Path)
    create.add_argument('--previous-team-delivery', type=Path)
    create.add_argument('--require-history', action='store_true', help='连续运行守卫：缺上一完整团队交付则拒收')
    check = sub.add_parser('verify', help='独立检查团队交付完整性')
    check.add_argument('directory', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command in ('prepare', 'build'):
            require(not args.require_history or args.previous_team_delivery is not None,
                    '已要求历史续接，必须提供--previous-team-delivery；不能默默重建管理基线')
        if args.command == 'prepare':
            protected = args.member_delivery + ([args.previous_team_delivery] if args.previous_team_delivery else [])
            protect_output(args.output, protected)
            request = prepare(args.member_delivery, args.previous_team_delivery); write_request(args.output, request)
            output = {'request_id': request['request_id'], 'members': len(request['members']), 'output': str(args.output)}
        elif args.command == 'build':
            inputs = [args.review] + ([args.business] if args.business else [])
            protected = args.member_delivery + ([args.previous_team_delivery] if args.previous_team_delivery else [])
            protect_output(args.delivery_dir, protected, directory=True, input_paths=inputs)
            output = publish(args.delivery_dir, build(args.member_delivery, _json(args.review), _json(args.business) if args.business else None, args.previous_team_delivery), input_paths=inputs)
        else:
            output = {'valid': True, **verify(args.directory)}
        print(json.dumps(output, ensure_ascii=False)); return 0
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        print('团队管理检查失败：' + str(exc), file=sys.stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())
