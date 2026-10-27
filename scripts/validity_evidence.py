"""Validate human/Skill-produced validity evidence; never infer a classification."""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys

VERSION = 'validity-evidence/1'
CRITERIA = ('reply', 'need', 'scope', 'delivery', 'language', 'integrity')
STATES = ('yes', 'no', 'unknown', 'assumed', 'not_observed')
REASONS = {
    'high': ('supported',), 'effective': ('supported',),
    'pending': ('need_unknown', 'reply_unknown', 'history_incomplete', 'other_unknown'),
    'scope_unknown': ('scope_unknown', 'delivery_unknown'),
    'invalid': ('lost', 'out_of_scope', 'academic_misconduct_only', 'journal', 'unavailable_delivery'),
}
STRONG = {'deadline', 'materials', 'asked_price', 'asked_teacher', 'asked_process',
          'asked_trial', 'asked_refund', 'requested_arrangement', 'multiple_courses', 'long_term'}
ASSISTING = {'location', 'task'}


def validate_price_silence(validity, messages, cutoff, api):
    """Optional contact-state evidence; never infer silence from keywords."""
    if 'price_silence' not in validity:
        return
    p = 'validity.price_silence'
    item = api.obj(validity['price_silence'], p)
    api.choice(item.get('state'), ('yes', 'no', 'unknown'), p + '.state')
    api.string(item.get('reason'), p + '.reason')
    try:
        as_of = datetime.fromisoformat(item['as_of'])
        api.require(as_of == datetime.fromisoformat(cutoff), p, '附加状态时点须与对应快照截止一致')
    except (KeyError, TypeError, ValueError):
        raise api.ValidationError(p + '：截止时间无法核对')
    own = {m['id']: m for m in messages}
    refs = item.get('price_refs')
    api.require(isinstance(refs, list) and all(isinstance(x, str) for x in refs)
                and len(refs) == len(set(refs)), p, '问价引用须为不重复编号数组')
    times = []
    for rid in refs:
        api.require(rid in own, p, '问价引用不属于本案')
        m = own[rid]
        api.require(m.get('source_role') == 'customer' and not m.get('sensitive')
                    and bool(m.get('text', '').strip()), p, '须引用本案非敏感客户问价原话')
        try:
            t = datetime.fromisoformat(m['time'])
            api.require(t <= as_of, p, '问价不能晚于截止时间')
            times.append(t)
        except (KeyError, TypeError, ValueError):
            raise api.ValidationError(p + '：问价时间无法比较')
    if item['state'] != 'yes':
        return
    api.require(validity['status'] in ('effective', 'high') and bool(times), p, '报价消失须先有效且有客户问价依据')
    last = max(times)
    for m in messages:
        try:
            t = datetime.fromisoformat(m['time'])
            if t == last and m['id'] not in refs and m.get('source_role') == 'customer' and m.get('is_system_greeting') is not True:
                api.require(False, p, '同一时刻另有客户回复，先后关系不清不能确认消失')
            if not last < t <= as_of:
                continue
        except (KeyError, TypeError, ValueError):
            raise api.ValidationError(p + '：后续记录时间无法比较')
        api.require(m.get('source_role') in ('customer', 'sales', 'system'), p, '后续角色未知，不能确认客户消失')
        api.require(m.get('source_role') != 'customer' or m.get('is_system_greeting') is True,
                    p, '问价后已有真实客户回复，不能仍标报价消失')


def validate(assessment, messages, expected_status, expected_cutoff, api):
    """Check evidence references and mechanical contradictions, not semantic truth."""
    req, choice, string, obj = api.require, api.choice, api.string, api.obj
    p = 'validity.assessment'
    a = obj(assessment, p)
    policy = obj(a.get('policy') or {}, p + '.policy')
    req(a.get('version') == VERSION, p, '不支持的有效性证据版本')
    string(a.get('policy_version'), p + '.policy_version')
    identity = obj(a.get('identity'), p + '.identity')
    choice(identity.get('basis'), ('source_id', 'unknown'), p + '.identity.basis')
    if identity['basis'] == 'source_id':
        string(identity.get('account_id'), p + '.identity.account_id')
        string(identity.get('customer_id'), p + '.identity.customer_id')
    else:
        req(identity.get('customer_id') is None, p + '.identity.customer_id', '没有可靠客户ID时须为null')
        req(identity.get('account_id') is None or isinstance(identity.get('account_id'), str) and bool(identity['account_id'].strip()),
            p + '.identity.account_id', '未知账号须为null，已知账号须是非空文本')
    choice(a.get('status'), REASONS, p + '.status')
    status = a['status']
    req(status == expected_status, p + '.status', '必须与报告有效性一致')
    choice(a.get('reason_code'), REASONS[status], p + '.reason_code')
    string(a.get('next_review'), p + '.next_review')

    def date(value, label):
        try:
            req(isinstance(value, str) and bool(value.strip()), label, '需要ISO日期时间')
            return datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        except (TypeError, ValueError):
            req(False, label, '需要可解析的ISO日期时间')

    as_of = date(a.get('as_of'), p + '.as_of')
    cutoff = date(expected_cutoff, 'period.cutoff')
    try:
        req(as_of == cutoff, p + '.as_of', '判断时点必须与报告资料截止一致')
    except TypeError:
        req(False, p + '.as_of', '判断和截止时点的时区口径不一致')
    own = {m['id']: m for m in messages}

    def refs(values, label, required=False):
        req(isinstance(values, list), label, '必须为引用数组')
        req(not required or bool(values), label, '该判断需要原始证据')
        req(all(isinstance(x, str) for x in values), label, '引用编号必须为文本')
        req(len(values) == len(set(values)), label, '引用不能重复')
        for rid in values:
            req(rid in own, label, '引用必须属于本案')
            msg = own[rid]
            req(not msg.get('sensitive') and bool(msg.get('text', '').strip()), label, '不能引用敏感或空白消息')
            try:
                req(date(msg.get('time'), label + '.time') <= as_of, label, '不能引用资料截止之后的消息')
            except TypeError:
                req(False, label, '消息与判断时点的时区口径不一致')

    cov = obj(a.get('coverage'), p + '.coverage')
    choice(cov.get('history'), ('complete', 'partial', 'unknown'), p + '.coverage.history')
    string(cov.get('note'), p + '.coverage.note')
    missing = cov.get('missing')
    req(isinstance(missing, list), p + '.coverage.missing', '需要缺失资料说明数组')
    for item in missing:
        string(item, p + '.coverage.missing')

    criteria = obj(a.get('criteria'), p + '.criteria')
    req(set(criteria) == set(CRITERIA), p + '.criteria', '必须且只能包含六项判断条件')
    for key in CRITERIA:
        item = obj(criteria.get(key), p + '.' + key)
        choice(item.get('state'), STATES, p + '.' + key + '.state')
        state = item['state']
        req(state != 'assumed' or key in ('language', 'integrity'), p + '.' + key, '只有现行默认条件可标假定')
        req(state != 'not_observed' or key == 'reply', p + '.' + key, '仅回复项可标未观察到')
        string(item.get('explanation'), p + '.' + key + '.explanation')
        refs(item.get('refs'), p + '.' + key + '.refs', state in ('yes', 'no') or (key == 'language' and state == 'assumed'))

    if status in ('effective', 'high'):
        for key in ('reply', 'need', 'scope', 'delivery'):
            req(criteria[key]['state'] == 'yes', p + '.' + key, '确定有效须有该条件的正向证据')
        for key in ('language', 'integrity'):
            req(criteria[key]['state'] in ('yes', 'assumed'), p + '.' + key, '确定有效须满足或符合现行默认条件')
    if status == 'scope_unknown':
        key = 'scope' if a['reason_code'] == 'scope_unknown' else 'delivery'
        req(criteria[key]['state'] == 'unknown', p, '待核原因必须与尚未确定的条件一致')
    if status == 'pending' and a['reason_code'] == 'need_unknown':
        req(criteria['need']['state'] == 'unknown', p, '需求待判须说明具体需求未知')
    if status == 'pending' and a['reason_code'] == 'reply_unknown':
        req(criteria['reply']['state'] in ('unknown', 'not_observed'), p, '回复待判不能同时标为已真实回复')
    if status == 'pending' and a['reason_code'] == 'history_incomplete':
        req(cov['history'] in ('partial', 'unknown'), p, '前史不全须与覆盖范围一致')
    if status == 'invalid':
        reason = a['reason_code']
        if reason == 'out_of_scope':
            req(criteria['scope']['state'] == 'no' or criteria['language']['state'] == 'no', p, '非覆盖须有范围或授课语言证据')
        if reason == 'journal':
            req(criteria['scope']['state'] == 'no', p, '期刊无效须有不属于服务范围的依据')
        if reason == 'academic_misconduct_only':
            req(criteria['integrity']['state'] == 'no', p, '仅学术不端需求须有明确依据')
        if reason == 'unavailable_delivery':
            req(criteria['delivery']['state'] == 'no', p, '无法交付须有已确认的供给证据')

    signals = a.get('quality_signals')
    req(isinstance(signals, list), p + '.quality_signals', '需要质量信号数组')
    kinds = set()
    for signal in signals:
        signal = obj(signal, p + '.quality_signals')
        choice(signal.get('kind'), STRONG | ASSISTING, p + '.quality_signals.kind')
        kind = signal['kind']
        req(kind not in kinds, p + '.quality_signals.kind', '同一种质量信号不能重复计数')
        kinds.add(kind)
        string(signal.get('explanation'), p + '.quality_signals.explanation')
        refs(signal.get('refs'), p + '.quality_signals.refs', True)
    if status == 'high':
        minimum = policy.get('quality_signal_min_count')
        strong_minimum = policy.get('quality_strong_min_count')
        req(type(minimum) is int and minimum > 0 and type(strong_minimum) is int and 0 < strong_minimum <= minimum,
            p + '.policy', '优质判定需要本机构明确的信号数量条件')
        req(len(kinds) >= minimum and len(kinds & STRONG) >= strong_minimum, p, '未达到本机构质量信号条件')

    lost = a.get('lost_evidence')
    if status == 'invalid' and a['reason_code'] == 'lost':
        hours = policy.get('lost_after_hours')
        follow_minimum = policy.get('minimum_followups')
        req(type(hours) in (int, float) and 0 < hours < float('inf') and type(follow_minimum) is int and follow_minimum > 0,
            p + '.policy', '失联判定需要本机构已确认的时限及跟进次数')
        lost = obj(lost, p + '.lost_evidence')
        req(cov['history'] == 'complete' and criteria['reply']['state'] == 'not_observed', p, '失联须完整前史且从未真实回复')
        for msg in messages:
            try:
                visible = date(msg.get('time'), p + '.lost.message_time') <= as_of
            except TypeError:
                req(False, p + '.lost', '完整前史中的消息时间口径不一致')
            if not visible:
                continue
            role = msg.get('source_role')
            req(role in ('sales', 'customer', 'system'), p + '.lost', '完整前史中说话角色未知，不能判失联')
            req(role != 'customer' or msg.get('is_system_greeting') is True, p + '.lost',
                '可见客户消息未被证实为系统提示，不能判从未真实回复')
        first = string(lost.get('first_contact_ref'), p + '.lost.first_contact_ref')
        follow = lost.get('follow_up_refs')
        refs([first], p + '.lost.first_contact_ref', True)
        refs(follow, p + '.lost.follow_up_refs', True)
        req(len(follow) >= follow_minimum and first not in follow, p + '.lost.follow_up_refs', '首次触达后跟进次数须达到机构要求')
        first_msg = own[first]
        req(first_msg.get('source_role') == 'sales', p + '.lost', '首次触达须能确认是销售发送')
        started = date(first_msg['time'], p + '.lost.first_time')
        try:
            req(as_of - started >= timedelta(hours=hours), p + '.lost', '首次触达须已满机构要求的时限')
            for rid in follow:
                req(own[rid].get('source_role') == 'sales', p + '.lost', '跟进须能确认是销售发送')
                req(date(own[rid]['time'], p + '.lost.follow_time') > started, p + '.lost', '跟进须在首次触达之后')
        except TypeError:
            req(False, p + '.lost', '失联时间的时区口径不一致')
    else:
        req(lost is None, p + '.lost_evidence', '非失联结论不填写失联证明')

    transition = a.get('transition')
    if transition is not None:
        t = obj(transition, p + '.transition')
        choice(t.get('previous_status'), REASONS, p + '.transition.previous_status')
        previous = date(t.get('previous_as_of'), p + '.transition.previous_as_of')
        previous_policy = string(t.get('previous_policy_version'), p + '.transition.previous_policy_version')
        string(t.get('previous_reason'), p + '.transition.previous_reason')
        refs(t.get('previous_refs'), p + '.transition.previous_refs', True)
        choice(t.get('kind'), ('new_evidence', 'correction', 'policy_update'), p + '.transition.kind')
        kind = t['kind']
        string(t.get('reason'), p + '.transition.reason')
        refs(t.get('refs'), p + '.transition.refs', kind != 'policy_update')
        try:
            req(previous <= as_of, p + '.transition', '先前时点不能晚于当前时点')
            req(all(date(own[r]['time'], p + '.transition.previous_ref_time') <= previous for r in t['previous_refs']),
                p + '.transition', '历史判断不能引用其时点之后的新消息')
            if kind == 'new_evidence':
                req(previous < as_of, p + '.transition', '新增证据需要更晚的判断时点')
                req(any(date(own[r]['time'], p + '.transition.ref_time') > previous for r in t['refs']),
                    p + '.transition', '新证据须包含上一时点之后的消息')
        except TypeError:
            req(False, p + '.transition', '前后判断与消息时区口径不一致')
        if kind == 'policy_update':
            req(previous_policy != a['policy_version'], p + '.transition', '规则更新须有不同的规则版本')
    return a


def detail(case, api):
    """Display the checked reasons with the original messages, only when present."""
    a = case['validity'].get('assessment')
    if not a:
        return ''
    e = api.e
    labels = {'reply': '真实回复', 'need': '具体需求', 'scope': '覆盖范围',
              'delivery': '需求可交付', 'language': '授课语言', 'integrity': '无排除性学术不端要求'}
    states = {'yes': '证据支持', 'no': '证据不支持', 'unknown': '待核',
              'assumed': '按现行规则暂采用', 'not_observed': '记录中未观察到'}
    rows = []
    for key in CRITERIA:
        item = a['criteria'][key]
        evidence = ''.join(api.quote(case, rid) for rid in item['refs'])
        rows.append(f'<details><summary>{e(labels[key])} · {e(states[item["state"]])}</summary><p>{e(item["explanation"])}</p>{evidence}</details>')
    quality = ''.join(f'<details><summary>{e(s["explanation"])}</summary>' +
                      ''.join(api.quote(case, rid) for rid in s['refs']) + '</details>' for s in a['quality_signals'])
    missing = '；'.join(a['coverage']['missing']) or '未另外列出'
    change = a.get('transition')
    transition = (f'<details><summary>判断更新：{e(api.VALIDITY[change["previous_status"]])} → {e(api.VALIDITY[a["status"]])}</summary>'
                  f'<p>上次：{e(change["previous_as_of"])}；当时理由：{e(change["previous_reason"])}</p>' +
                  ''.join(api.quote(case, rid) for rid in change['previous_refs']) +
                  f'<p>更新说明：{e(change["reason"])}</p>' +
                  ''.join(api.quote(case, rid) for rid in change['refs']) + '</details>') if change else ''
    lost = a.get('lost_evidence')
    lost_html = ('<details><summary>失联判定的首次触达与跟进记录</summary>' +
                 ''.join(api.quote(case, rid) for rid in [lost['first_contact_ref']] + lost['follow_up_refs']) + '</details>') if lost else ''
    return f'''<details class="validity-assessment"><summary>有效性逐项依据与更新</summary>
<p>判断截至 {e(a['as_of'])} · 规则版本 {e(a['policy_version'])}</p>
<p>覆盖说明：{e(a['coverage']['note'])}；缺失：{e(missing)}</p>{''.join(rows)}
<p>质量信号：</p>{quality or '<p>未确认额外质量信号</p>'}{lost_html}{transition}
<p>何时重判：{e(a['next_review'])}</p></details>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description='检查已经形成的单案有效性判断与引用，不进行分类')
    parser.add_argument('input', type=Path, help='私有JSON，包含assessment、messages、expected_status、expected_cutoff')
    args = parser.parse_args(argv)
    import render_chat_review as api
    try:
        data = json.loads(args.input.read_text(encoding='utf-8-sig'))
        api.obj(data, '输入')
        messages = data.get('messages')
        api.require(isinstance(messages, list) and all(isinstance(m, dict) and isinstance(m.get('id'), str) for m in messages),
                    'messages', '需要有消息编号的原始消息数组')
        api.require(len({m['id'] for m in messages}) == len(messages), 'messages', '消息编号不能重复')
        validate(data.get('assessment'), messages, data.get('expected_status'), data.get('expected_cutoff'), api)
        print(json.dumps({'valid': True, 'check': 'structural_and_evidence_links',
                          'classification_inferred': False, 'source_identity_verified': False,
                          'independent_source_verified': False}))
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, api.ValidationError) as exc:
        print('无法通过有效性结构检查：' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
