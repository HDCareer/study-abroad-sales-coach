"""Cross-snapshot invariants; facts, period scope and actions are distinct."""
from datetime import datetime
import json


def same(a, b):
    return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)


def period_sales_scope(case, management):
    week = case.get('management', {}).get('week', case.get('week', {}))
    if 'sales_scope' in week:
        return week['sales_scope']['sales_applicable']
    life = case.get('management', {}).get('lifecycle') or case.get('lifecycle')
    if life is None:
        return True  # Legacy reports without lifecycle retain their declared scope.
    if datetime.fromisoformat(management['cutoff']) > datetime.fromisoformat(management['week_end']):
        return None  # Never backfill the earlier period with today's communication type.
    return life['sales_applicable']


def validate(data, api):
    m = data['management']
    strict = 'reliability_version' in m
    if strict:
        api.require(m['reliability_version'] == '1.0' and m.get('lifecycle_version') == '1.0',
                    'reliability_version', '公司新分析使用1.0并提供lifecycle_version=1.0')
    for c in data['cases']:
        if not c['included']:
            continue
        cm = c['management']; life = cm.get('lifecycle') or {}
        own = {x['id']: x for x in c['source_messages']}
        def refs(items, at, required=True):
            api.require(isinstance(items, list) and (bool(items) or not required)
                        and all(isinstance(x, str) for x in items) and len(items) == len(set(items)),
                        c['id']+'.integrity.refs', '需要不重复的证据数组')
            for rid in items:
                api.require(rid in own and not own[rid].get('sensitive') and own[rid]['text'].strip(),
                            c['id']+'.integrity.refs', '证据不存在、跨案、敏感或为空')
                try:
                    api.require(datetime.fromisoformat(own[rid]['time']) <= datetime.fromisoformat(at),
                                c['id']+'.integrity.refs', '不能用后续消息证明此前状态')
                except (TypeError, ValueError):
                    raise api.ValidationError(c['id']+'：证据时间无法比较')
        scope = cm['week'].get('sales_scope')
        api.require(not strict or scope is not None, c['id']+'.week.sales_scope', '公司新分析须提供独立的统计期销售适用性')
        if scope is not None:
            api.obj(scope, 'week.sales_scope')
            api.require(type(scope.get('sales_applicable')) is bool or scope.get('sales_applicable') is None,
                        'week.sales_scope', '销售适用性须true/false/null')
            api.require(scope.get('as_of') == m['week_end'], 'week.sales_scope', '适用性时点须为统计期末')
            api.string(scope.get('reason'), 'week.sales_scope.reason')
            refs(scope.get('refs'), m['week_end'], scope['sales_applicable'] is not None)
        if strict and life.get('sales_applicable') is True:
            api.require('assessment' in c['validity'], c['id']+'.validity', '公司销售分析须保留逐项有效性证据')
        meta = cm.get('cohort')
        if meta is not None:
            api.require(not strict or 'entry' in meta, 'cohort.entry', '入组快照未知须显式null，不每日重建资格')
            entry = meta.get('entry')
            if entry is not None:
                api.obj(entry, 'cohort.entry')
                api.choice(entry.get('validity'), ('effective','high'), 'cohort.entry.validity')
                api.choice(entry.get('purchase_kind'), ('first','repeat'), 'cohort.entry.purchase_kind')
                api.string(entry.get('policy_version'), 'cohort.entry.policy_version')
                api.string(entry.get('reason'), 'cohort.entry.reason')
                try:
                    at = datetime.fromisoformat(entry['at'])
                    api.require(at <= datetime.fromisoformat(m['cutoff']), 'cohort.entry.at', '入组判断不能晚于资料截止')
                    if meta.get('first_contact_at'):
                        api.require(at >= datetime.fromisoformat(meta['first_contact_at']), 'cohort.entry.at', '不能在首次接触前确认入组')
                except (KeyError,TypeError,ValueError):
                    raise api.ValidationError('cohort.entry.at：需要可比较时间')
                refs(entry.get('refs'), entry['at'])
        actions = {a['id']: a for a in cm.get('actions', [])}
        for ev in life.get('events', []):
            if ev['kind'] == 'correction' and 'changes' in ev:
                api.string(ev.get('baseline_analysis_id'), 'correction.baseline_analysis_id')
                api.require(isinstance(ev['changes'], list) and ev['changes'], 'correction.changes', '需逐字段记录改动')
                fields = set()
                for change in ev['changes']:
                    api.obj(change, 'correction.change')
                    field = api.string(change.get('field'), 'correction.field')
                    api.require(field not in fields and 'before' in change and 'after' in change,
                                'correction.change', '字段不重复且需保留前后值')
                    fields.add(field)
                    api.require(not same(change['before'], change['after']), 'correction.change', '前后值相同不算纠错')
            if ev['kind'] != 'customer_question':
                continue
            links = ev.get('action_ids')
            api.require(not strict or links is not None, 'customer_question.action_ids', '客户问题须明确关联处理动作')
            if links is None:
                continue
            api.require(isinstance(links, list) and links and all(isinstance(x,str) for x in links)
                        and len(links)==len(set(links)), 'customer_question.action_ids', '需不重复的动作编号')
            for aid in links:
                api.require(aid in actions, 'customer_question.action_ids', '关联动作必须属于本案并回传状态')
                a = actions[aid]
                if a['status'] in ('resolved','cancelled','executed_waiting_customer'):
                    api.require(datetime.fromisoformat(a['updated_at']) >= datetime.fromisoformat(ev['at']),
                                'customer_question.action_ids', '不能用问题发生前的旧执行核销新问题')
                    api.require(bool(a.get('confirmation_source')) or any(
                        datetime.fromisoformat(own[r]['time']) >= datetime.fromisoformat(ev['at'])
                        for r in a['refs']), 'customer_question.action_ids', '核销须有问题发生之后的依据或明确裁决')
        for a in actions.values():
            change = a.get('change')
            if change is None:
                continue
            api.obj(change, 'action.change')
            for key in ('baseline_analysis_id','previous_updated_at','reason','confirmation_source'):
                api.string(change.get(key), 'action.change.'+key)
            api.require(isinstance(change.get('before'), dict) and bool(change['before']),
                        'action.change.before', '须保存本次改动字段的原值')
            refs(change.get('refs'), a['updated_at'], False)


def compare(current, old, api, baseline_id, baseline_at=None):
    cm = current['management']; life = cm.get('lifecycle') or {}; past_life = old.get('lifecycle') or {}
    previous_events = {e['id'] for e in past_life.get('events', [])}
    def corrected(field, before, after):
        return any(bool(baseline_id) and e['kind']=='correction' and e['id'] not in previous_events
                   and e.get('baseline_analysis_id')==baseline_id
                   and (baseline_at is None or datetime.fromisoformat(e['at']) >= datetime.fromisoformat(baseline_at))
                   and any(x.get('field')==field and same(x.get('before'),before) and same(x.get('after'),after)
                           for x in e.get('changes', [])) for e in life.get('events', []))
    def preserve(field, before, after):
        api.require(same(before,after) or corrected(field,before,after), field,
                    '已确认历史不可无依据改变；须绑定本次基线、具体字段及前后值的新增纠错')
    for key in ('first_added_at','first_added_source'):
        if past_life.get(key) is not None:
            preserve('lifecycle.'+key, past_life[key], life.get(key))
    for group, flags, dates in (
        ('trial', ('completed','paid'), ('payment_at','ended_from','ended_to')),
        ('formal', ('confirmed',), ('confirmed_at',))):
        prior = old.get(group) or {}; now = cm[group]
        for key in flags:
            if prior.get(key) is True:
                preserve(group+'.'+key, True, now.get(key))
        for key in dates:
            if prior.get(key) is not None:
                preserve(group+'.'+key, prior[key], now.get(key))
    if current['validity']['status'] != old['validity']['status']:
        transition = current['validity'].get('assessment', {}).get('transition')
        valid_transition = bool(transition) and transition.get('previous_status')==old['validity']['status']
        previous_as_of = old['validity'].get('assessment', {}).get('as_of')
        if valid_transition and previous_as_of:
            valid_transition = transition.get('previous_as_of')==previous_as_of
        api.require(valid_transition or corrected('validity.status',old['validity']['status'],current['validity']['status']),
                    'lifecycle.validity', '等级变化须对应实际上一判断或具体字段纠错')
    before_cohort = old.get('cohort') or {}; now_cohort = cm.get('cohort') or {}
    for key in ('entry','first_contact_at','is_new_customer'):
        if before_cohort.get(key) is not None:
            preserve('cohort.'+key, before_cohort[key], now_cohort.get(key))
    # A frozen period classification is independent of today's communication.
    before_scope = old.get('week', {}).get('sales_scope')
    after_scope = cm['week'].get('sales_scope')
    if before_scope and after_scope and before_scope['as_of']==after_scope['as_of']:
        preserve('week.sales_scope', before_scope, after_scope)
    old_actions = {a['id']:a for a in old.get('actions', [])}
    current_actions = {a['id']:a for a in cm.get('actions', [])}
    for aid, before in old_actions.items():
        if before['status'] not in ('resolved','cancelled'):
            api.require(aid in current_actions, 'actions', '未结动作必须回传，不能凭省略消失')
        if aid not in current_actions:
            continue
        after = current_actions[aid]
        api.require(datetime.fromisoformat(after['updated_at']) >= datetime.fromisoformat(before['updated_at']),
                    'action.updated_at', '同一动作更新时间不能倒退')
        protected = [k for k in ('kind','owner','issue_key','action') if not same(before.get(k),after.get(k))]
        protected += [k for k in ('due_at','next_check_at','escalate_at')
                      if before.get(k) is not None and not same(before.get(k),after.get(k))]
        if before['status'] in ('resolved','cancelled') and after['status'] not in ('resolved','cancelled'):
            protected.append('status')
        if not protected:
            continue
        change = after.get('change') or {}
        api.require(change.get('baseline_analysis_id')==baseline_id
                    and change.get('previous_updated_at')==before['updated_at']
                    and change.get('reason') and change.get('confirmation_source')
                    and all(k in change.get('before',{}) and same(change['before'][k],before.get(k)) for k in protected),
                    'action.change', '改期、改派、改写或重开须保留本次基线和实际变更依据')


def question_state(event, actions):
    links = event.get('action_ids')
    if not links:
        return 'unknown'
    by_id = {a['id']:a for a in actions}
    if any(x not in by_id for x in links):
        return 'unknown'
    if all(by_id[x]['status'] in ('resolved','cancelled') for x in links):
        return 'closed'
    if all(by_id[x]['status'] in ('resolved','cancelled','executed_waiting_customer') for x in links):
        return 'waiting'
    return 'open'
