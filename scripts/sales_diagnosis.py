"""Checks and renders traceable sales diagnosis; no automated business judgment."""
from collections import Counter
from datetime import datetime


def validate(data, api):
    cases = {c['id']: c for c in data['cases'] if c['included']}
    nodes_by_case = {}
    for cid, case in cases.items():
        layers = case['management']['layers']
        nodes = layers.get('diagnostic_nodes', [])
        api.require(isinstance(nodes, list), cid, '诊断节点须为数组')
        messages = {m['id']: m for m in case['source_messages']}
        seen = {}
        for node in nodes:
            p = cid + '.diagnostic_nodes'
            api.obj(node, p)
            nid = api.string(node.get('id'), p + '.id')
            api.require(nid not in seen, p, '本案节点编号重复')
            api.choice(node.get('layer'), ('judgment', 'expression', 'execution'), p + '.layer')
            api.choice(node.get('stage'), api.STAGES, p + '.stage')
            api.require(layers[node['layer']]['status'] == 'gap', p, '节点所属层须有可见缺口')
            for key in ('customer_decision', 'sales_action', 'gap', 'possible_effect', 'better_action', 'current_action', 'limit'):
                api.string(node.get(key), p + '.' + key)
            api.choice(node.get('sales_action_evidence'), ('observed', 'not_observed'), p + '.sales_action_evidence')
            if node['sales_action_evidence'] == 'not_observed':
                api.string(node.get('coverage_limit'), p + '.coverage_limit')
            try:
                at = datetime.fromisoformat(node['observed_at'])
                cutoff = datetime.fromisoformat(data['management']['cutoff'])
                api.require(at <= cutoff, p, '节点时间不能晚于报告截止时间')
            except (KeyError, TypeError, ValueError):
                raise api.ValidationError(p + '：节点或截止时间无法比较')
            def check_refs(key, roles, required, later=False):
                refs = node.get(key)
                api.require(isinstance(refs, list) and all(isinstance(x, str) for x in refs)
                            and len(refs) == len(set(refs)), p + '.' + key, '引用须为不重复的编号数组')
                api.require(not required or bool(refs), p + '.' + key, '需要本案证据')
                for rid in refs:
                    api.require(rid in messages, p + '.' + key, '引用不属于本案')
                    m = messages[rid]
                    api.require(not m.get('sensitive') and bool(m.get('text', '').strip()), p, '敏感或空消息不可引用')
                    api.require(m.get('source_role') in roles, p, '消息角色不符或无法确认')
                    try:
                        t = datetime.fromisoformat(m['time'])
                        api.require((at < t <= cutoff) if later else t <= at, p, '引用时间与节点或截止时间不符')
                    except (KeyError, TypeError, ValueError):
                        raise api.ValidationError(p + '：消息与节点时间无法比较')
            check_refs('customer_refs', ('customer',), True)
            check_refs('sales_refs', ('sales',), node['sales_action_evidence'] == 'observed')
            check_refs('later_feedback_refs', ('customer', 'sales'), False, later=True)
            index = node.get('library_index')
            api.require(type(index) is int and 0 <= index < len(layers['library']), p, '需对应本案已核验的培训来源')
            api.require(layers['library'][index]['layer'] == node['layer'], p, '培训来源与问题层次不一致')
            seen[nid] = node
        nodes_by_case[cid] = seen
    patterns = data['management']['coaching'].get('patterns', [])
    api.require(isinstance(patterns, list) and len(patterns) <= 3, 'coaching.patterns', '最多三个同类重点')
    for pattern in patterns:
        p = 'coaching.patterns'
        api.obj(pattern, p)
        for k in ('name', 'opportunity_definition'):
            api.string(pattern.get(k), p + '.' + k)
        api.choice(pattern.get('layer'), ('judgment', 'expression', 'execution'), p + '.layer')
        api.choice(pattern.get('stage'), api.STAGES, p + '.stage')
        opportunities = pattern.get('opportunities')
        api.require(isinstance(opportunities, list) and bool(opportunities), p, '至少列出一项适用机会')
        used = set()
        for item in opportunities:
            api.obj(item, p + '.opportunities')
            cid = item.get('case_id')
            api.require(cid in cases and cid not in used, p, '机会须来自本销售本批不同案例')
            used.add(cid)
            api.choice(item.get('status'), ('gap', 'sound', 'unknown'), p + '.status')
            refs = item.get('refs')
            messages = {m['id']: m for m in cases[cid]['source_messages']}
            api.require(isinstance(refs, list) and all(isinstance(x, str) for x in refs)
                        and len(refs) == len(set(refs)), p, '机会引用须为不重复的编号数组')
            api.require(item['status'] == 'unknown' or bool(refs), p, '有结论的机会需要本案证据')
            for rid in refs:
                api.require(rid in messages and not messages[rid].get('sensitive')
                            and bool(messages[rid].get('text', '').strip()), p, '机会引用不存在、敏感或为空')
            if item['status'] == 'gap':
                node = nodes_by_case[cid].get(item.get('node_id'))
                api.require(node is not None and node['layer'] == pattern['layer'] and node['stage'] == pattern['stage'], p, '缺口须对应同一层和阶段的本案节点')
            if item['status'] == 'sound':
                api.require(cases[cid]['management']['layers'][pattern['layer']]['status'] in ('sound', 'gap'), p, '对照须有本层可判定依据')


def overview(data, api):
    cases = {c['id']: c for c in data['cases'] if c['included']}
    rows = []
    for p in data['management']['coaching'].get('patterns', []):
        counts = Counter(x['status'] for x in p['opportunities'])
        buttons = ''.join(f'<button type="button" data-case="{api.e(x["case_id"])}"><span>{api.e(cases[x["case_id"]]["name"])} · {api.e(x["case_id"])}</span><small>{api.e({"gap":"有缺口", "sound":"未见该缺口", "unknown":"待核"}[x["status"]])} →</small></button>' for x in p['opportunities'])
        rows.append(f'<details><summary><b>{api.e(p["name"])}</b>：{counts["gap"]}案有缺口 / {counts["gap"] + counts["sound"]}案可判断，另{counts["unknown"]}案待核</summary><p>观察机会：{api.e(p["opportunity_definition"])}</p><div class="case-links">{buttons}</div></details>')
    return ('<h3>同类问题集中在哪</h3><p class="muted">按可比较机会计数；待核不计入可判断分母。比例不等于成交原因。</p>' + ''.join(rows)) if rows else ''


def detail(case, api):
    rows = []
    for n in case['management']['layers'].get('diagnostic_nodes', []):
        quote_groups = []
        for key, label in (('customer_refs', '当时客户原话'), ('sales_refs', '当时销售原话'), ('later_feedback_refs', '后续反馈（不代表当时已知）')):
            if n[key]:
                quote_groups.append(f'<p><b>{label}：</b></p>' + ''.join(api.quote(case, ref) for ref in n[key]))
        quotes = ''.join(quote_groups)
        source = case['management']['layers']['library'][n['library_index']]
        coverage = f'<p><b>记录范围：</b>{api.e(n["coverage_limit"])}</p>' if n['sales_action_evidence'] == 'not_observed' else ''
        rows.append(f'<details><summary>{api.e(api.STAGES[n["stage"]])} · {api.e(n["gap"])}</summary><p><b>当时客户要解决：</b>{api.e(n["customer_decision"])}</p><p><b>销售当时的动作：</b>{api.e(n["sales_action"])}</p>{coverage}<p><b>可能影响：</b>{api.e(n["possible_effect"])}（分析推断）</p><p><b>当时更合理的动作：</b>{api.e(n["better_action"])}</p><p><b>现在如何跟进：</b>{api.e(n["current_action"])}</p><p><b>对应培训：</b>{api.e(source["locator"])}</p><p class="muted">{api.e(n["limit"])}</p>{quotes}</details>')
    return '<h4>逐节点核对</h4>' + ''.join(rows) if rows else ''
