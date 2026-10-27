"""One structured handoff from the validated report input; no second analysis."""
import copy
import hashlib
import json
from pathlib import Path
import re

VERSION = 'skill3-management-results/1.0'


def build(data, api, source_checked=None):
    import management_review as management
    api.require('management' in data, 'results', '统一管理结果需要management数据')
    api.require(data['period']['cutoff'] == data['management']['cutoff'], 'results', '报告与管理结果须采用同一资料截止时间')
    skill_text = (Path(__file__).resolve().parents[1] / 'SKILL.md').read_text(encoding='utf-8-sig')
    version = re.search(r'^版本：([^。\s]+)', skill_text, re.MULTILINE)
    api.require(version is not None, 'results', '无法取得Skill运行版本')
    digest_input = {'skill_version': version.group(1), 'analysis': data}
    digest = hashlib.sha256(json.dumps(digest_input, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    m = management.metrics(data)
    def snapshot(validity):
        result = copy.deepcopy(validity)
        result['label'] = api.validity_label(validity)
        result.setdefault('price_silence', {'state': 'unknown', 'reason': '旧数据未提供此项'})
        return result
    records = []
    for c in data['cases']:
        result = {'case_id': c['id'], 'included': c['included'], 'name': c['name'],
                  'sales_id': c['sales_id'], 'exclusion_reason': c['exclusion_reason']}
        if not c['included']:
            records.append(result)
            continue
        cm = c['management']
        assessment = c['validity'].get('assessment')
        result.update(identity=copy.deepcopy(assessment['identity']) if assessment else
                      {'basis': 'unknown', 'account_id': c['sales_id'], 'customer_id': None},
                      group=c['group'], headline=c['headline'], validity=snapshot(c['validity']),
                      diagnosis={key: copy.deepcopy(c[key]) for key in ('goal', 'current_problem', 'attribution', 'opportunity', 'other_constraints', 'nature', 'summary_refs', 'evidence_nodes')},
                      week=copy.deepcopy(cm['week']), current_phases=copy.deepcopy(c['phases']),
                      position=copy.deepcopy(c['position']), issue=copy.deepcopy(cm['issue']),
                      layers=copy.deepcopy(cm.get('layers')), trial=copy.deepcopy(cm['trial']),
                      tracking=copy.deepcopy(cm.get('tracking')),
                      formal=copy.deepcopy(cm['formal']), order=copy.deepcopy(c['order']),
                      trial_warning=management.warning(c, data['management']['cutoff'], data['management'].get('alert_thresholds_hours')),
                      must_follow=copy.deepcopy(cm['must_follow']), recovery=copy.deepcopy(c['recovery']),
                      report_anchor='case-' + c['id'])
        result['week']['validity'] = snapshot(cm['week']['validity'])
        own = {msg['id']: msg for msg in c['source_messages']}
        used = set()
        def collect(value):
            if isinstance(value, dict):
                for v in value.values(): collect(v)
            elif isinstance(value, list):
                for v in value: collect(v)
            elif isinstance(value, str) and value in own:
                used.add(value)
        collect(result)
        result['evidence'] = [copy.deepcopy(msg) for msg in c['source_messages'] if msg['id'] in used and not msg.get('sensitive')]
        records.append(result)
    mean = str(m['mean']) if m['mean'] is not None else None
    return {'schema_version': VERSION, 'analysis_id': digest, 'sales': copy.deepcopy(data['sales']),
            'skill_version': version.group(1),
            'period': copy.deepcopy(data['period']), 'scope': copy.deepcopy(data['scope']),
            'reporting_window': {key: data['management'][key] for key in ('week_start', 'week_end', 'cutoff', 'time_basis')},
            'rules': copy.deepcopy(data['standards']), 'source_verification':
            {'status': 'matched' if source_checked is not None else 'not_checked', 'message_count': source_checked},
            'summary': copy.deepcopy(data['management']['summary']),
            'metrics': {'week_cases': len(m['week']), 'week_effective': len(m['valid']),
                        'week_trial_paid': len(m['trial_paid']), 'week_formal_confirmed': len(m['formal']),
                        'average_formal_receipt_rmb': mean},
            'coaching': copy.deepcopy(data['management'].get('coaching')),
            'longitudinal': copy.deepcopy(data['management'].get('longitudinal')),
            'must_follow_case_ids': [c['id'] for c in m['must_follow']], 'cases': records}


def stamp_report(html, analysis_id):
    return html.replace('<main', '<main data-analysis-id="' + analysis_id + '"', 1).replace(
        '</main>', '<p class="muted">分析版本编号：' + analysis_id + '</p></main>', 1)
