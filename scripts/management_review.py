"""Management view over human/Skill-labelled evidence; no keyword judgments.

This optional extension keeps the original 1.0 input and renderer compatible.
Dates use the explicitly declared source clock. No network or browser APIs.
"""
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
import json


def dt(value):
    return datetime.fromisoformat(value) if value else None


def validate(data, api, source=None):
    req = api.require
    m = data['management']
    thresholds = m.get('alert_thresholds_hours')
    req(thresholds is None or (isinstance(thresholds, list) and len(thresholds) == 3 and
        all(type(x) in (int, float) and 0 < x < float('inf') for x in thresholds) and
        thresholds[0] < thresholds[1] < thresholds[2]), 'management.alert_thresholds_hours',
        '预警阈值须为null或黄橙红递增的三个有限正数')
    req(m.get('version') == '1.0', 'management.version', '只支持1.0')
    try:
        start, end, cutoff = (dt(m[k]) for k in ('week_start', 'week_end', 'cutoff'))
        req(start is not None and start <= end <= cutoff, 'management', '统计起止及资料截止时间顺序错误')
    except (ValueError, TypeError, KeyError):
        req(False, 'management', '时间必须是同一时区口径的ISO日期时间')
    api.string(m.get('time_basis'), 'management.time_basis')
    req(isinstance(m.get('summary'), list) and len(m['summary']) <= 3, 'management.summary', '最多三个有证据的核心判断')
    req(isinstance(m.get('read_case_ids'), list), 'management.read_case_ids', '需要阅读覆盖记录')
    req(len(m['read_case_ids']) == len(set(m['read_case_ids'])), 'management.read_case_ids', '阅读案例重复')
    req(set(m['read_case_ids']) == {c['id'] for c in data['cases']}, 'management.read_case_ids', '阅读覆盖与输出案例不一致')
    req(type(m.get('read_message_count')) is int, 'management.read_message_count', '需要阅读消息数')
    receipt_ids, order_ids, receipt_proofs = set(), set(), set()
    week_ids = set()
    for c in data['cases']:
        p = c['id'] + '.management'
        cm = api.obj(c.get('management'), p)
        week = api.obj(cm.get('week'), p + '.week')
        req(type(week.get('included')) is bool, p, '需要明确是否纳入本周')
        if c['included'] and week['included']:
            week_ids.add(c['id'])
        if not c['included']:
            continue
        if 'assessment' in c['validity']:
            try:
                req(dt(c['validity']['assessment']['as_of']) == cutoff, p + '.validity.assessment.as_of',
                    '有效性判断时点必须与管理报告资料截止一致')
            except (ValueError, TypeError, KeyError):
                req(False, p + '.validity.assessment.as_of', '判断与管理报告的时间格式或时区口径不一致')
        messages = {x['id']: x for x in c['source_messages']}

        def refs(value, path, needed=False, week_only=False):
            req(isinstance(value, list), path, '应为本案引用数组')
            req(not needed or bool(value), path, '需要原话依据')
            req(len(value) == len(set(value)), path, '引用重复')
            for ref in value:
                req(ref in messages, path, '引用不存在或跨案')
                msg = messages[ref]
                req(not msg.get('sensitive') and bool(msg['text'].strip()), path, '敏感/空白信息不得引用')
                if week_only:
                    try:
                        req(dt(msg['time']) <= end, path, '不能用截止周之后的消息倒填本周阶段')
                    except (ValueError, TypeError):
                        req(False, path, '阶段证据时间不能与本周截止比较')

        req(week.get('new_customer') is None or type(week.get('new_customer')) is bool, p, '新增客户必须true/false/null')
        refs(week.get('new_refs'), p + '.week.new_refs', week.get('new_customer') is True, week['included'])
        week_validity = api.obj(week.get('validity'), p + '.week.validity')
        api.choice(week_validity.get('status'), api.VALIDITY, p + '.week.validity.status')
        api.string(week_validity.get('reason'), p + '.week.validity.reason')
        refs(week_validity.get('refs'), p + '.week.validity.refs', week['included'], week['included'])
        if 'price_silence' in week_validity:
            import validity_evidence
            validity_evidence.validate_price_silence(week_validity, c['source_messages'], m['week_end'], api)
        phases = api.obj(week.get('phases'), p + '.week.phases')
        req(set(phases) == set(api.STAGES), p, '周阶段必须保留五列')
        for key, phase in phases.items():
            api.choice(phase.get('state'), ('done', 'gap', 'not_done', 'unknown'), p + '.' + key)
            api.string(phase.get('reason'), p + '.' + key)
            req(phase.get('applicable') is None or type(phase.get('applicable')) is bool, p, '适用性必须true/false/null')
            req(not (phase.get('applicable') is False and phase['state'] in ('done', 'gap')), p, '无需经过的阶段不能记已完成')
            refs(phase.get('refs'), p + '.' + key, phase['state'] in ('done', 'gap'), True)
        issue = api.obj(cm.get('issue'), p + '.issue')
        req(issue.get('stage') is None or issue.get('stage') in api.STAGES, p, '问题阶段只能用五列或null')
        api.choice(issue.get('kind'), ('gap', 'in_progress', 'constraint', 'unknown', 'none'), p + '.issue.kind')
        api.string(issue.get('label'), p + '.issue.label')
        refs(issue.get('refs'), p + '.issue.refs', issue['kind'] == 'gap')
        trial = api.obj(cm.get('trial'), p + '.trial')
        req(trial.get('paid') is None or type(trial.get('paid')) is bool, p, '试听付款必须true/false/null')
        req(type(trial.get('completed')) is bool, p, '缺上课记录按本次口径统计false并说明')
        refs(trial.get('payment_refs'), p + '.trial.payment_refs', trial['paid'] is True)
        refs(trial.get('completion_refs'), p + '.trial.completion_refs', trial['completed'])
        api.string(trial.get('completion_note'), p + '.trial.completion_note')
        api.string(trial.get('time_note'), p + '.trial.time_note')
        for key in ('payment_at', 'ended_from', 'ended_to'):
            req(key in trial, p, '试听时间未知须显式null')
            try:
                value = dt(trial[key])
                req(value is None or value <= cutoff, p + '.' + key, '已发生事件不能晚于资料截止')
            except (ValueError, TypeError):
                req(False, p + '.' + key, '试听时间格式/时区不一致')
        if trial['ended_from'] and trial['ended_to']:
            req(dt(trial['ended_from']) <= dt(trial['ended_to']), p, '结束时间区间颠倒')
        req(trial['completed'] or not (trial['ended_from'] or trial['ended_to']), p, '未正式完课不能启动完课时钟')
        formal = api.obj(cm.get('formal'), p + '.formal')
        req(type(formal.get('confirmed')) is bool, p, '正式购买必须显式true/false')
        req(formal['confirmed'] == (c['order']['formal'] == 'confirmed'), p, '正式购买与原订单状态不一致')
        refs(formal.get('refs'), p + '.formal.refs', formal['confirmed'])
        req(isinstance(formal.get('orders'), list), p, '正式订单必须为数组')
        try:
            at = dt(formal.get('confirmed_at'))
            req(at is None or at <= cutoff, p, '正式确认时间不能晚于资料截止')
        except (ValueError, TypeError):
            req(False, p, '正式确认时间格式/时区错误')
        for order in formal['orders']:
            oid = order.get('id')
            req(isinstance(oid, str) and oid and oid not in order_ids, p, '正式订单编号缺失或重复')
            order_ids.add(oid)
            req(formal['confirmed'], p, '未确认正式购买不能填写正式订单')
            refs(order.get('refs'), p + '.formal.orders.refs', True)
            req(isinstance(order.get('receipts'), list), p, '收款必须按实际到账逐笔记录')
            try:
                at = dt(order.get('confirmed_at'))
                req(at is None or at <= cutoff, p, '订单时间不能晚于资料截止')
            except (ValueError, TypeError):
                req(False, p, '订单时间格式/时区错误')
            for receipt in order['receipts']:
                rid = receipt.get('id')
                req(isinstance(rid, str) and rid and rid not in receipt_ids, p, '到账编号缺失或重复')
                receipt_ids.add(rid)
                api.number(receipt.get('amount'), p + '.receipt.amount')
                api.string(receipt.get('currency'), p + '.receipt.currency')
                refs(receipt.get('refs'), p + '.receipt.refs', True)
                proof = tuple(sorted(receipt['refs']))
                req(proof not in receipt_proofs, p, '相同收款证据不能重复计多笔到账')
                receipt_proofs.add(proof)
                try:
                    at = dt(receipt.get('at'))
                    req(at is None or at <= cutoff, p, '到账时间不能晚于资料截止')
                except (ValueError, TypeError):
                    req(False, p, '到账时间格式/时区错误')
        follow = api.obj(cm.get('must_follow'), p + '.must_follow')
        req(type(follow.get('needed')) is bool, p, '必须跟回需要明确判断')
        req(follow.get('priority') in (1, 2, 3), p, '优先级为1/2/3')
        for key in ('reason', 'action', 'when'):
            api.string(follow.get(key), p + '.must_follow.' + key)
        refs(follow.get('refs'), p + '.must_follow.refs', follow['needed'])
        if follow['needed']:
            req(not formal['confirmed'], p, '已正式成交不混入首次追单名单')
            req(c['recovery']['possibility'] in ('recoverable', 'conditional'), p, '已过期/不可触达不能列必须跟回')
            api.string(c['recovery']['script'], p + '.recovery.script')
    for finding in m['summary']:
        for key in ('claim', 'action', 'limit'):
            api.string(finding.get(key), 'management.summary.' + key)
        ids = finding.get('case_ids')
        req(isinstance(ids, list) and ids and len(ids) == len(set(ids)), 'management.summary', '结论需要不重复的案例依据')
        req(set(ids) <= week_ids, 'management.summary', '核心结论只能引用本周纳入案例')
    if source is not None:
        raw = source.get('cases') if isinstance(source, dict) else source
        req({x['id'] for x in raw} == {x['id'] for x in data['cases']}, 'management.coverage', '全量复盘不能遗漏源案例')
        req(sum(len(x['messages']) for x in raw) == m['read_message_count'], 'management.coverage', '阅读消息数与源不一致')
        raw_by_id = {x['id']: x for x in raw}
        for c in data['cases']:
            actual = any(start <= dt(x['time']) <= end for x in raw_by_id[c['id']]['messages'])
            req(actual == c['management']['week']['included'], c['id'], '上周范围与原始消息不一致')
    if 'coaching' in m:
        import coaching_review
        coaching_review.validate(data, api)
    import longitudinal_review
    longitudinal_review.validate_input(data, api)
    return data


def warning(case, cutoff, thresholds=None):
    cm = case['management']
    t = cm['trial']
    if cm['formal']['confirmed']:
        return {'code': 'converted', 'label': '已正式购买', 'hours': None}
    if not t['completed']:
        return {'code': 'not_completed', 'label': '未正式完课', 'hours': None}
    if not t['ended_to']:
        return {'code': 'time_unknown', 'label': '已完课 · 计时待核', 'hours': None}
    minimum = max(0, (dt(cutoff) - dt(t['ended_to'])).total_seconds() / 3600)
    maximum = (dt(cutoff) - dt(t['ended_from'])).total_seconds() / 3600 if t['ended_from'] else None
    if thresholds is None:
        code, label = 'policy_unknown', '已完课 · 预警阈值待设'
    else:
        yellow, orange, red = thresholds
        index = 3 if minimum >= red else 2 if minimum >= orange else 1 if minimum >= yellow else 0
        code = ('window', 'yellow', 'orange', 'red')[index]
        label = (f'未确认达到首档{yellow:g}h', f'黄色预警 ≥{yellow:g}h',
                 f'橙色预警 ≥{orange:g}h', f'红色高风险 ≥{red:g}h')[index]
    exact = maximum is not None and abs(maximum - minimum) < 0.001
    text = f'{minimum:.1f}小时' if exact else f'至少{minimum:.1f}小时'
    if maximum is not None and not exact:
        text = f'{minimum:.1f}—{maximum:.1f}小时'
    return {'code': code, 'label': label, 'hours': minimum, 'elapsed': text}


def metrics(data):
    m = data['management']
    start, end = dt(m['week_start']), dt(m['week_end'])
    def in_week(value):
        return bool(value) and start <= dt(value) <= end
    all_cases = [c for c in data['cases'] if c['included']]
    week = [c for c in all_cases if c['management']['week']['included']]
    valid = [c for c in week if c['management']['week']['validity']['status'] in ('effective', 'high')]
    paid = [c for c in week if c['management']['trial']['paid'] is True and in_week(c['management']['trial']['payment_at'])]
    formal = [c for c in week if c['management']['formal']['confirmed'] and (
        in_week(c['management']['formal']['confirmed_at']) or
        any(in_week(o['confirmed_at']) for o in c['management']['formal']['orders']))]
    order_rows = [(c, o) for c in all_cases for o in c['management']['formal']['orders'] if in_week(o['confirmed_at'])]
    known_total = sum((Decimal(str(r['amount'])) for _, o in order_rows for r in o['receipts'] if r['currency'] in ('CNY', 'RMB', '人民币')), Decimal(0))
    complete = bool(order_rows) and data['scope']['orders_complete'] and all(o['receipts'] and all(r['currency'] in ('CNY', 'RMB', '人民币') for r in o['receipts']) for _, o in order_rows)
    complete = complete and all(any(c['id'] == owner['id'] for owner, _ in order_rows) for c in formal)
    mean = known_total / len(order_rows) if complete else None
    follow = sorted([c for c in all_cases if c['management']['must_follow']['needed']], key=lambda c: (c['management']['must_follow']['priority'], - (warning(c, m['cutoff'], m.get('alert_thresholds_hours')).get('hours') or 0), c['id']))
    alerts = [(c, warning(c, m['cutoff'], m.get('alert_thresholds_hours'))) for c in all_cases if c['management']['trial']['completed'] and not c['management']['formal']['confirmed']]
    return {'week': week, 'valid': valid, 'trial_paid': paid, 'formal': formal, 'mean': mean,
            'current_formal': sum(c['management']['formal']['confirmed'] for c in all_cases),
            'undated_formal': sum(c['management']['formal']['confirmed'] and not c['management']['formal']['confirmed_at'] for c in all_cases),
            'undated_trial': sum(c['management']['trial']['paid'] is True and not c['management']['trial']['payment_at'] for c in all_cases),
            'must_follow': follow, 'alerts': alerts, 'known_total': known_total,
            'new_confirmed': sum(c['management']['week']['new_customer'] is True for c in week),
            'new_unknown': sum(c['management']['week']['new_customer'] is None for c in week)}


CSS = """
:root{color-scheme:light dark;--bg:light-dark(#f5f7f6,#1b1e21);--surface:light-dark(#fff,#24282c);--ink:light-dark(#25332e,#e5ece8);--muted:light-dark(#5b6c63,#b2c0b8);--line:light-dark(#dce5de,#46534b);--soft:light-dark(#edf3ef,#303b34);--green:light-dark(#34735b,#8dc5aa);--warn:light-dark(#8a5c18,#e7ba72)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 system-ui,'Microsoft YaHei',sans-serif}main{max-width:1100px;margin:auto;padding:28px}h1{font-size:28px;font-weight:600;margin:0 0 4px}h2{font-size:19px;margin:0 0 12px}h3{font-size:16px;margin:12px 0 8px}p{margin:7px 0}button,a{font:inherit;color:inherit}button{cursor:pointer}button:focus-visible,a:focus-visible{outline:3px solid var(--green);outline-offset:3px}button{border:1px solid var(--line);border-radius:6px;background:var(--surface);padding:7px 11px;text-align:left}a{text-underline-offset:3px}.muted,small{color:var(--muted);font-size:12px}.panel{background:var(--surface);padding:24px;border:1px solid var(--line);border-radius:10px;margin:18px 0}.metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:15px;margin:23px 0}.metric small{display:block}.metric b{font-size:27px;font-weight:550;display:block;font-variant-numeric:tabular-nums}.finding{display:block;width:100%;background:var(--soft);margin:8px 0;padding:12px 16px}.finding small{display:block}.flow-row{display:grid;grid-template-columns:100px 1fr 140px;gap:14px;align-items:center;margin:12px 0}.track{height:16px;background:var(--soft);border-radius:3px}.bar{height:100%;background:var(--green);border-radius:3px}.flow-value{text-align:right}.gap-link{margin:0 0 9px 114px;font-size:13px}.legend{display:flex;gap:16px;flex-wrap:wrap}.reason-box{margin-top:14px;padding-top:10px;border-top:1px solid var(--line)}.case-links{display:grid;gap:6px}.case-links button{display:flex;justify-content:space-between;gap:12px}.case-links small{max-width:65%;text-align:right}.alert-grid{display:flex;gap:8px;flex-wrap:wrap}.badge{display:inline-block;padding:2px 7px;border-radius:4px;background:var(--soft);font-size:12px}.yellow{background:light-dark(#fff2cb,#4b3d14)}.orange{background:light-dark(#ffe4c6,#52371c)}.red{background:light-dark(#f9dddd,#502e2e)}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:10px 8px;text-align:left;vertical-align:top}th{font-weight:550}.table-scroll{overflow-x:auto}.quote{padding:11px 14px;margin:9px 0;background:var(--soft);border-radius:5px}.quote-meta{display:flex;gap:12px;justify-content:space-between;font-size:12px}blockquote{margin:5px 0;overflow-wrap:anywhere;white-space:pre-wrap}.quote small{font-size:11px}.case-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.case-head h2{margin:0}.analysis-node{margin-top:18px;border-top:1px solid var(--line);padding-top:10px}.reason{padding:10px 14px;background:var(--soft);border-radius:5px}.draft{white-space:pre-wrap;background:var(--soft);padding:14px;border-radius:5px}summary{cursor:pointer}.phase-mini{margin:7px 0}details>summary{padding:6px 0}.case-detail{scroll-margin-top:16px}.follow-count{white-space:nowrap}.facts{display:flex;gap:10px;flex-wrap:wrap}.footer{margin:18px 0;color:var(--muted);font-size:12px}[hidden]{display:none!important}@media(max-width:700px){main{padding:12px}.panel{padding:16px}.metrics{grid-template-columns:repeat(3,1fr);gap:12px}.metric b{font-size:22px}.flow-row{grid-template-columns:83px 1fr 105px;gap:8px}.gap-link{margin-left:91px}.case-links button{display:block}.case-links small{display:block;text-align:left;max-width:none}.case-head{display:block}.table-scroll table{min-width:590px}}@media print{body{background:#fff;color:#111}main{max-width:none;padding:0}.panel{break-inside:avoid;border-color:#aaa}button{border:0}#evidence-panel[hidden],.case-detail[hidden]{display:none}.table-scroll{overflow:visible}.footer{color:#555}}
"""


SCRIPT = """
(()=>{const root=document.getElementById('review-root');
function openCase(id){const item=document.getElementById('case-'+id);if(!item)return;const panel=document.getElementById('evidence-panel');panel.hidden=false;root.querySelectorAll('.case-detail').forEach(x=>x.hidden=x!==item);panel.scrollIntoView({behavior:'auto',block:'start'});window.location.hash='case-'+id;}
root.addEventListener('click',ev=>{const b=ev.target.closest('button');if(!b)return;if(b.dataset.case)openCase(b.dataset.case);if(b.dataset.reason){const box=document.getElementById(b.dataset.reason);root.querySelectorAll('.reason-box').forEach(x=>x.hidden=x!==box);box.hidden=false;box.open=true;box.scrollIntoView({behavior:'auto',block:'start'});}if(b.id==='hide-evidence')document.getElementById('evidence-panel').hidden=true;});
function fromHash(){const id=window.location.hash.slice(1);if(id.startsWith('case-'))openCase(id.slice(5));}window.addEventListener('hashchange',()=>{const id=window.location.hash.slice(1);if(id.startsWith('case-')){const item=document.getElementById(id);if(item&&item.hidden)openCase(id.slice(5));}});fromHash();})();
"""


def render(data, api):
    e = api.e
    s = metrics(data)
    m = data['management']
    all_cases = [c for c in data['cases'] if c['included']]
    coaching = None
    if 'coaching' in m:
        import coaching_review as coaching
    byid = {c['id']: c for c in all_cases}
    def case_button(c, note=None):
        return f'<button type="button" data-case="{e(c["id"])}"><span>{e(c["name"])} · {e(c["id"])}</span><small>{e(note or c["headline"])} →</small></button>'
    def case_list(cases):
        return '<div class="case-links">' + ''.join(case_button(c) for c in cases) + '</div>'
    metrics_html = ''.join(f'<div class="metric"><small>{e(label)}</small><b>{e(value)}</b></div>' for label, value in [
        ('上周纳入会话', len(s['week'])), ('确定有效', len(s['valid'])), ('上周确认首课付款', len(s['trial_paid'])),
        ('上周确认正式购买', len(s['formal']) if len(s['formal']) or data['scope']['orders_complete'] else '待核'),
        ('正式订单均单实收', '¥' + format(s['mean'], ',.0f') if s['mean'] is not None else '待核')])
    summary_html, reason_html = [], []
    for i, finding in enumerate(m['summary']):
        summary_html.append(f'<button type="button" class="finding" data-reason="finding-{i}"><b>{e(finding["claim"])}</b><small>{len(finding["case_ids"])}个对应案例 · {e(finding["action"])} · 点击看依据 →</small></button>')
        reason_html.append(f'<details class="reason-box" id="finding-{i}" hidden><summary>{e(finding["claim"])} · {len(finding["case_ids"])}案</summary><p class="muted">{e(finding["limit"])}</p>{case_list([byid[x] for x in finding["case_ids"]])}</details>')
    flow = []
    valid = s['valid']
    flow_cases = s['week']
    valid_ids = {c['id'] for c in valid}
    for i, (key, label) in enumerate(api.STAGES.items()):
        def phase(c): return c['management']['week']['phases'][key]
        done = [c for c in flow_cases if phase(c)['state'] in ('done', 'gap')]
        weak = sum(phase(c)['state'] == 'gap' for c in done)
        skipped = [c for c in flow_cases if phase(c).get('applicable') is False]
        unknown = [c for c in flow_cases if phase(c)['state'] == 'unknown']
        pending = [c for c in flow_cases if phase(c)['state'] not in ('done', 'gap') and phase(c).get('applicable') is not False]
        width = 100 * len(done) / max(1, len(flow_cases))
        valid_done = sum(c['id'] in valid_ids for c in done)
        flow.append(f'<div class="flow-row"><span>{e(label)}</span><div class="track" role="img" aria-label="{e(label)}已完成{len(done)}位，基于上周{len(flow_cases)}位客户"><div class="bar" style="width:{width:.3f}%"></div></div><button type="button" class="flow-value" data-reason="done-{key}">{len(done)}位完成 →</button></div>')
        reason_html.append(f'<details class="reason-box" id="done-{key}" hidden><summary>{e(label)} · {len(done)}位完成（含不足）</summary>{case_list(done) or "<p>无可确认完成案例。</p>"}</details>')
        detail_note = '；'.join(text for count, text in [(weak, f'其中{weak}位完成但不足'), (len(unknown), f'{len(unknown)}位待核'), (len(skipped), f'{len(skipped)}位无需经过')] if count)
        flow.append(f'<div class="muted gap-link">完成者中确定有效{valid_done}位' + ('；' + e(detail_note) if detail_note else '') + '</div>')
        previous = list(api.STAGES)[i-1] if i else None
        def eligible(c):
            phases = c['management']['week']['phases']
            if previous is None:
                return True
            if key == 'close' and phases['objection'].get('applicable') is False:
                return phases['proposal']['state'] in ('done', 'gap')
            return phases[previous]['state'] in ('done', 'gap')
        transition = [c for c in pending if eligible(c)]
        if transition:
            link_label = '本环节未完成／待核' if i == 0 else '已完成前序、本环节未推进'
            flow.append(f'<button type="button" class="gap-link" data-reason="stage-{key}">{link_label} {len(transition)}位 · 看原因</button>')
            groups = defaultdict(list)
            for c in transition:
                issue = c['management']['issue']
                kind = {'gap': '推进缺口', 'in_progress': '正常在途', 'constraint': '现实约束', 'unknown': '证据不足', 'none': '未发现明确缺口'}[issue['kind']]
                groups[kind + ' · ' + issue['label']].append(c)
            body = ''.join(f'<h3>{e(reason)} · {len(cases)}位</h3>{case_list(cases)}' for reason, cases in groups.items())
            reason_html.append(f'<details class="reason-box" id="stage-{key}" hidden><summary>前序 → {e(label)}未推进 · {len(transition)}位</summary><p class="muted">上周阶段人数；原因与补救采用资料截止时点的最新记录，可能起于更早环节。缺证和在途不算已流失。</p>{body}</details>')
    close_branches = Counter(c['management']['week']['phases']['close']['branch'] for c in flow_cases if c['management']['week']['phases']['close']['state'] in ('done', 'gap'))
    flow.append('<p class="muted">Close支线：' + '；'.join(e(api.BRANCH[k] or '范围未分') + f' {v}位' for k, v in close_branches.items()) + '。首课Close不等于正式购买。</p>')
    warnings = []
    alert_counts = Counter(w['code'] for _, w in s['alerts'])
    for code, name in [('red','红色高风险'), ('orange','橙色预警'), ('yellow','黄色预警'), ('window','首档时限内'), ('time_unknown','完课时间待核'), ('policy_unknown','预警阈值待设')]:
        subset = [(c,w) for c,w in s['alerts'] if w['code'] == code]
        if subset:
            warnings.append(f'<details><summary><span class="badge {code}">{e(name)} · {len(subset)}位</span></summary><div class="case-links">' + ''.join(case_button(c, w['label'] + ' · ' + w.get('elapsed', c['management']['trial']['time_note']) + ' · ' + api.POSSIBILITY[c['recovery']['possibility']]) for c,w in subset) + '</div></details>')
    follow_rows = []
    for c in s['must_follow']:
        f = c['management']['must_follow']
        w = warning(c, m['cutoff'], m.get('alert_thresholds_hours'))
        flag = f'<span class="badge {w["code"]}">{e(w["label"])}</span>' if w['code'] not in ('not_completed','converted') else ''
        priority_label = {1: '优先处理', 2: '备齐方案再接续', 3: '按节点跟进'}[f['priority']]
        follow_rows.append(f'<tr><td><small>{priority_label}</small>{case_button(c, "查看原话")}{flag}</td><td>{e(f["reason"])}</td><td>{e(f["action"])}</td><td>{e(data["sales"]["name"])}<br>{e(f["when"])}</td></tr>')
    details = []
    for c in all_cases:
        cm = c['management']; t = cm['trial']; w = warning(c, m['cutoff'], m.get('alert_thresholds_hours'))
        nodes = []
        for node in c['evidence_nodes']:
            quotes = ''.join(api.quote(c, ref) for ref in node['refs'])
            nodes.append(f'<div class="analysis-node">{quotes}<div class="reason"><b>未完成的动作：</b>{e(node["missed"])}<br><b>为什么影响购买：</b>{e(node["impact"])}</div><p><b>当时更好的接法：</b>{e(node["better"])}</p><p class="muted">可商榷之处：{e(node["limit"])}</p></div>')
        if not nodes:
            nodes = [''.join(api.quote(c, ref) for ref in c['summary_refs'])]
        phase_html = ''.join(f'<p class="phase-mini"><b>{e(label)}：</b>{e({"done":"已完成","gap":"完成但不足","not_done":"未完成／无需","unknown":"待核"}[c["phases"][key]["state"]])} · {e(c["phases"][key]["reason"])}</p>' for key,label in api.STAGES.items())
        action_html = ''.join(f'<li><b>{e(a["owner"])} · {e(a["when"])}</b>：{e(a["action"])}<br><small>推进信号：{e(a["signal"])}</small></li>' for a in c['recovery']['actions'])
        trial_pay = '试听已付款' if t['paid'] is True else '试听付款性质待核' if t['paid'] is None else '未见试听付款记录'
        completion = '已正式完成试听' if t['completed'] else '按记录未完成试听'
        refs = list(dict.fromkeys(c['validity']['refs'] + c['order']['refs'] + t['completion_refs'] + t['payment_refs'] + cm['formal']['refs'] + [r for phase in c['phases'].values() for r in phase['refs']]))
        morequotes = ''.join(api.quote(c, ref) for ref in refs)
        formal = '已正式购买' if cm['formal']['confirmed'] else '未见正式购买／结果待核'
        layer_detail = coaching.detail(c, api) if coaching else ''
        if 'assessment' in c['validity']:
            import validity_evidence
            layer_detail = validity_evidence.detail(c, api) + layer_detail
        details.append(f'''<article class="case-detail" id="case-{e(c['id'])}" hidden>
<div class="case-head"><div><h2>{e(c['name'])} · {e(c['id'])}</h2><p>{e(c['headline'])}</p></div><span class="badge">{e(api.validity_label(c['validity']))}</span></div>
<div class="facts"><span>{e(trial_pay)}</span><span>{e(completion)}</span><span>{e(formal)}</span><span class="badge {w['code']}">{e(w['label'])} {e(w.get('elapsed',''))}</span></div>
<p class="muted">{e(t['completion_note'])}；{e(t['time_note'])}</p>
<p><b>当前判断：</b>{e(c['current_problem'])}</p><p class="muted">{e(c['attribution'])}</p>{layer_detail}
{''.join(nodes)}<h3>现在先做什么</h3><ul>{action_html}</ul>
<div class="draft">{e(c['recovery']['script']) or '本案不生成推销稿；按上述内部动作处理。'}</div><p class="muted">使用前提：{e(c['recovery']['script_conditions'])}</p>
<details><summary>更多依据：有效性、五环节、付款与完课</summary><p>{e(c['validity']['reason'])}</p>{phase_html}<p>{e(c['order']['summary'])}</p>{morequotes}</details>
<p><b>面谈重点：</b>{e(c['recovery']['coaching_question'])}</p></article>''')
    allrows = ''.join(f'<tr><td>{case_button(c, "看证据")}</td><td>{e(api.validity_label(c["validity"]))}</td><td>{e(c["headline"])}</td><td>{"本周" if c["management"]["week"]["included"] else "仅截止后更新"}</td></tr>' for c in all_cases)
    caution = f'上周确认新增{ s["new_confirmed"] }位，新增归属待核{ s["new_unknown"] }位；会话数不冒充新增流量。正式购买当前可确认{s["current_formal"]}位，其中{s["undated_formal"]}位确认日期不明；另有{s["undated_trial"]}位首课付款日期不明，均未强填本周收款。'
    known_receipts = f'已能确认金额的正式订单人民币到账合计：¥{s["known_total"]:,.2f}，不代表全部实际收入。' if s['known_total'] else '正式订单实收金额未能从记录中核清，不记为零收入。'
    exclusions = ''.join(f'<li>{e(c["id"])} · {e(c["name"])}：{e(c["exclusion_reason"])}</li>' for c in data['cases'] if not c['included'])
    criteria = '<details><summary>有效性与付款判定标准</summary><ul>' + ''.join(f'<li>{e(x)}</li>' for x in data['standards']) + '</ul></details>'
    if exclusions:
        criteria += '<details><summary>排除项与理由</summary><ul>' + exclusions + '</ul></details>'
    coaching_html = coaching.overview(data, api) if coaching else ''
    correction = '<p class="reason"><b>校正数据版</b> · 本报告仅依据最新上传文件，替代此前混入其他聊天的报告；旧批不计入历史趋势。</p>' if coaching and m['coaching']['basis'] == 'corrected_baseline' else ''
    html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'"><title>{e(data['sales']['name'])} · 销售周复盘</title><style>{CSS}</style></head><body><main id="review-root">
<header><h1>{e(data['sales']['name'])} · 销售周复盘</h1><p class="muted">统计：{e(m['week_start'])} — {e(m['week_end'])}<br>最新状态截至：{e(m['cutoff'])} · {e(m['time_basis'])}</p>{correction}</header>
<section class="panel"><div class="metrics">{metrics_html}</div><p class="muted">仅统计有证据且时间落在上周的付款；未知金额不填0，首课不混入正式均单。</p>{''.join(summary_html)}<p><a href="#must-follow">必须跟回 {len(s['must_follow'])}位 · 查看末尾名单 →</a></p><details><summary>统计范围与证据边界</summary><p>{e(caution)}</p><p>{e(data['scope']['coverage'])}</p><p>客户未见实际上课记录，不计入已完成试听，注明记录中未见；中途中断另作说明。预约到期不等于上过课。首课付款为已付人数，后续中断或退款见个案，不代表净留存订单。</p><p>{e(known_receipts)}</p>{criteria}</details></section>
<section class="panel"><h2>销售主线 · 五环节完成情况</h2><p class="muted">覆盖上周全部{len(flow_cases)}位纳入客户，其中确定有效{len(valid)}位。每列独立计数，不相加；无需异议可直接进入Close。缺证与正常在途不算流失。</p>{''.join(flow)}{''.join(reason_html)}</section>
<section class="panel"><h2>试听后转正预警</h2><p class="muted">截至最新资料；从已确认实际完课计算。区间只按可证明的最低超时分档，分档依据本机构已确认阈值，不把高风险当自动放弃条件。</p>{''.join(warnings) or '<p>本批没有可确认已完课且仍需转正的案例。</p>'}</section>
{coaching_html}
<section class="panel" id="evidence-panel" hidden aria-live="polite"><button type="button" id="hide-evidence">收起个案</button>{''.join(details)}</section>
<section class="panel"><details><summary>全部客户索引 · {len(all_cases)}位（含统计期后更新）</summary><div class="table-scroll"><table><thead><tr><th>客户</th><th>有效性</th><th>一句话判断</th><th>范围</th></tr></thead><tbody>{allrows}</tbody></table></div></details></section>
<section class="panel" id="must-follow"><h2>必须跟回的客户 · {len(s['must_follow'])}位</h2><p class="muted">必须采取行动，不代表必然成交。只列当前仍有窗口、有购买基础和具体推进动作的客户。</p><div class="table-scroll"><table><thead><tr><th>客户／证据</th><th>为什么必须跟回</th><th>现在先做什么</th><th>负责人／节点</th></tr></thead><tbody>{''.join(follow_rows) or '<tr><td colspan="4">当前没有足够证据列入必须跟回的客户。</td></tr>'}</tbody></table></div></section>
<footer class="footer">依据本次私聊导出；图片、语音和群聊未提供的内容不作已知事实。建议尚未发送，补救结果尚未发生。私有资料按本机构资料保留规则处理。</footer>
</main><script>{SCRIPT}</script></body></html>'''
    return html
