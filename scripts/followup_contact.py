"""Evidence-based contact cadence; never change validity, demand state, or trial risk.

The Skill groups separate contact occasions and declares source coverage. This
module checks references, roles, timestamps, replies, and the agreed waiting
window; those checks do not prove semantic independence or source completeness.
"""
from datetime import datetime, timedelta
import math

LABELS = {
    'policy_unknown': '机构联系阈值待设',
    'not_assessed': '跟进轮次未评定',
    'incomplete': '联系资料不全，暂不判失联',
    'not_applicable': '从未真实回复，使用原新客规则',
    'waiting': '按客户约定等待',
    'wait_unknown': '约定等待节点待核',
    'active': '当前可继续沟通',
    'monitoring': '跟进观察中',
    'temporary_unreachable': '暂时失联，可恢复',
    'reengaged': '客户已重新回复',
}


def require(ok, message):
    if not ok:
        raise ValueError('联系状态：' + message)


def instant(value):
    require(isinstance(value, str) and value.strip(), '时间须为ISO字符串')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('联系状态：时间须为ISO格式') from exc


def stamp(value):
    return value.isoformat(sep=' ') if value is not None else None


def exact(value, keys, label):
    require(isinstance(value, dict) and set(value) == set(keys), label + '字段缺失或不支持')


def text(value, label):
    require(isinstance(value, str) and value.strip(), label + '须为非空文字')


def real_reply(message):
    return message.get('source_role') == 'customer' and message.get('is_system_greeting') is not True


def build(case, as_of):
    """Derive contact_status from an optional, explicitly annotated contact_review."""
    cutoff = instant(as_of)
    messages = case.get('source_messages', [])
    require(isinstance(messages, list), 'source_messages须为数组')
    own = {m.get('id'): m for m in messages}
    visible = []
    bad_times = []
    for m in messages:
        try:
            at = instant(m.get('time'))
            if at <= cutoff:
                visible.append((at, m))
        except (ValueError, TypeError):
            bad_times.append(m.get('id'))
    # Preserve legacy inputs without making a new silence conclusion.
    replies = sorted(((at, m) for at, m in visible if real_reply(m)), key=lambda p: (p[0], p[1]['id']))
    latest = replies[-1] if replies else None
    out = {'status': 'not_assessed', 'label': LABELS['not_assessed'], 'as_of': as_of,
           'coverage': 'not_assessed', 'first_unanswered_at': None, 'window_end': None,
           'attempt_count': 0, 'total_unanswered_attempts': 0, 'attempts': [],
           'evidence': [], 'why': '未提供contact_review，不把未评定当正常或失联。',
           'last_customer_reply_at': stamp(latest[0]) if latest else None,
           'last_customer_reply_ref': latest[1]['id'] if latest and not latest[1].get('sensitive') else None,
           'resumed_at': None, 'pause_eligible_at': None,
           'grouping_basis': '独立联系轮次由Skill分组；程序只检查可核时间、角色、引用及回复。'}
    if out['last_customer_reply_ref']:
        out['evidence'].append(out['last_customer_reply_ref'])
    review = case.get('management', {}).get('contact_review')
    if 'contact_review' not in case.get('management', {}):
        return out
    exact(review, ('coverage', 'attempts', 'wait') + (('policy',) if 'policy' in review else ()), 'contact_review')
    policy = review.get('policy')
    hours = minimum = None
    if policy is not None:
        exact(policy, ('version', 'unanswered_hours', 'minimum_attempts'), 'contact_review.policy')
        text(policy['version'], 'contact_review.policy.version')
        hours, minimum = policy['unanswered_hours'], policy['minimum_attempts']
        require(type(hours) in (int, float) and math.isfinite(hours) and hours > 0,
                'policy.unanswered_hours须为正有限小时数，不能借用默认值')
        require(type(minimum) is int and minimum > 0, 'policy.minimum_attempts须为正整数')
    out['policy'] = dict(policy) if policy is not None else None
    require(review['coverage'] in ('complete', 'partial', 'unknown'), 'coverage取complete/partial/unknown')
    out['coverage'] = review['coverage']
    require(isinstance(review['attempts'], list), 'attempts须为数组')
    require(len(own) == len(messages) and None not in own, '消息编号缺失或重复')

    def refs(values, label):
        require(isinstance(values, list) and values and all(isinstance(x, str) for x in values)
                and len(values) == len(set(values)), label + '须为不重复的本案消息编号')
        result = []
        for ref in values:
            require(ref in own, label + '不能引用其他案例或未知消息')
            msg = own[ref]
            require(not msg.get('sensitive') and isinstance(msg.get('text'), str) and msg['text'].strip(),
                    label + '不能引用敏感或空白正文')
            at = instant(msg.get('time'))
            try:
                require(at <= cutoff, label + '不能使用资料截止后的消息')
            except TypeError as exc:
                raise ValueError('联系状态：引用与资料截止时区口径不一致') from exc
            result.append((at, msg))
        out['evidence'].extend(values)
        return sorted(result, key=lambda p: (p[0], p[1]['id']))

    rounds, seen = [], set()
    for item in review['attempts']:
        exact(item, ('refs', 'reason'), 'attempt')
        text(item['reason'], 'attempt.reason')
        used = refs(item['refs'], 'attempt.refs')
        require(not set(item['refs']) & seen, '同一销售消息不能重复计入多个跟进轮次')
        seen.update(item['refs'])
        require(all(m.get('source_role') == 'sales' and m.get('is_system_greeting') is not True for _, m in used),
                '主动跟进须是实际销售发送，系统提示或客户消息不计轮次')
        begin, end = used[0][0], used[-1][0]
        require(not any(begin <= at <= end for at, _ in replies),
                '一轮主动跟进引用之间有客户回复，不能合成未获回复的一次跟进')
        rounds.append({'start': begin, 'end': end, 'refs': [m['id'] for _, m in used], 'reason': item['reason']})
    rounds.sort(key=lambda a: (a['start'], a['end'], a['refs']))
    require(all(rounds[i - 1]['end'] < rounds[i]['start'] for i in range(1, len(rounds))),
            '不同轮次不能重叠或同一时刻拆分计数；连续多条微信应由Skill归为一次联系')

    wait = review['wait']
    until = None
    if wait is not None:
        exact(wait, ('until', 'reason', 'refs'), 'wait')
        text(wait['reason'], 'wait.reason')
        agreed = refs(wait['refs'], 'wait.refs')
        require(any(real_reply(m) for _, m in agreed), '合理等待须有客户约定依据，不能只用顾问单方提议')
        if wait['until'] is not None:
            until = instant(wait['until'])
            try:
                require(until >= max(at for at, _ in agreed), '等待节点不能早于约定依据')
                until <= cutoff
            except TypeError as exc:
                raise ValueError('联系状态：等待节点与来源时间口径不一致') from exc
    out['evidence'] = list(dict.fromkeys(out['evidence']))

    def finish(status, why):
        out.update(status=status, label=LABELS[status], why=why)
        return out

    unknown_roles = [m for _, m in visible if m.get('source_role') not in ('sales', 'customer', 'system')]
    if review['coverage'] != 'complete' or bad_times or unknown_roles:
        return finish('incomplete', '来源覆盖不完整、时间或说话角色不能核清，不能证明期间持续没有客户回复。')
    if wait is not None and until is None:
        return finish('wait_unknown', '客户已有合理等待约定，但恢复联系时点未核清，暂不按观察时限判失联。')
    if until is not None and until > cutoff:
        return finish('waiting', '尚在客户已约定的等待期内；期间发送的信息不累计成失联跟进次数。')
    if not replies:
        return finish('not_applicable', '可见记录中客户从未真实回复；本规则只处理曾回复后沉默，原新客失联规则保持。')

    if policy is None:
        current = [a for a in rounds if a['start'] > replies[-1][0]
                   and (until is None or a['start'] >= until)]
        if not current:
            return finish('active', '当前没有未获回复的主动跟进序列；不据此推断购买意向。')
        out.update(first_unanswered_at=stamp(current[0]['start']), attempt_count=None,
                   total_unanswered_attempts=len(current),
                   attempts=[{'started_at': stamp(a['start']), 'ended_at': stamp(a['end']),
                              'refs': a['refs'], 'reason': a['reason'], 'within_window': None} for a in current])
        return finish('policy_unknown', '已核对未回复轮次，但未配置本机构观察时限与独立轮次数；不新判暂时失联。')

    # A real customer message ends the previous unanswered sequence, including
    # an unreadable attachment, emoji, link, or file. System greetings do not.
    for index, (reply_at, reply_message) in enumerate(replies):
        if index == 0:
            continue
        prior_reply_at = replies[index - 1][0]
        old = [a for a in rounds if prior_reply_at < a['start'] and a['end'] < reply_at
               and (until is None or a['start'] >= until)]
        if old:
            end = old[0]['start'] + timedelta(hours=hours)
            in_window = [a for a in old if a['end'] <= end]
            if len(in_window) >= minimum and reply_at > end:
                out['resumed_at'] = stamp(reply_at)
                out['pause_eligible_at'] = stamp(end)

    last_reply_at = replies[-1][0]
    current = [a for a in rounds if a['start'] > last_reply_at and (until is None or a['start'] >= until)]
    if not current:
        if out['resumed_at'] is not None:
            return finish('reengaged', '此前满足暂时失联条件后，客户已有真实新回复；恢复沟通，不把回复等同付款承诺。')
        return finish('active', '当前没有未获回复的主动跟进序列；已有客户回复或尚未开始本轮跟进。')
    first = current[0]['start']
    end = first + timedelta(hours=hours)
    qualifying = [a for a in current if a['end'] <= end]
    out.update(first_unanswered_at=stamp(first), window_end=stamp(end), attempt_count=len(qualifying),
               total_unanswered_attempts=len(current),
               attempts=[{'started_at': stamp(a['start']), 'ended_at': stamp(a['end']),
                          'refs': a['refs'], 'reason': a['reason'], 'within_window': a['end'] <= end} for a in current])
    if cutoff >= end and len(qualifying) >= minimum:
        out['pause_eligible_at'] = stamp(end)
        return finish('temporary_unreachable', '曾有客户真实回复；从本轮第一次未获回复的主动跟进起已满本机构观察时限，窗内达到本机构规定的独立跟进轮次数，至截止仍无真实回复。可恢复暂时失联，不改有效性、需求终态或已付课程责任。')
    return finish('monitoring', '尚未同时满足本机构观察时限与独立跟进轮次数，保持观察；新跟进不重置本轮起点。')


def validate(data, api):
    """Optional extension gate used by the existing analysis validator."""
    for case in data['cases']:
        if case['included'] and 'contact_review' in case.get('management', {}):
            try:
                build(case, data['period']['cutoff'])
            except (ValueError, TypeError) as exc:
                api.require(False, case['id'] + '.management.contact_review', str(exc))
