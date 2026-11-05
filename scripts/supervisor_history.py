"""Retain supplied opportunity snapshots without inventing refreshed judgments."""
import copy
from datetime import datetime
import hashlib
import json

SCHEMA = 'skill3-opportunity-pool/1.0'
OPEN = {'open', 'waiting', 'dormant', 'unknown'}
TEMPORARY_UNREACHABLE = 'temporary_unreachable'


def require(ok, message):
    if not ok:
        raise ValueError('往期商机：' + message)


def _id(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def _time(value):
    require(isinstance(value, str), '时间须为明确字符串')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('往期商机：时间须为ISO格式') from exc


def stable_key(source):
    life = source.get('lifecycle') or {}
    oid = (source.get('tracking') or {}).get('opportunity_id')
    if not isinstance(oid, str) or not oid.strip():
        return None
    company = life.get('customer_key')
    if isinstance(company, str) and company.strip():
        return {'kind': 'company', 'customer_key': company, 'opportunity_id': oid}
    identity = source.get('identity') or {}
    if identity.get('basis') == 'source_id' and all(
            isinstance(identity.get(k), str) and identity[k].strip()
            for k in ('account_id', 'customer_id')):
        return {'kind': 'account', 'account_id': identity['account_id'],
                'customer_id': identity['customer_id'], 'opportunity_id': oid}
    return None


def _status(source):
    life = source.get('lifecycle') or {}
    if (source.get('formal') or {}).get('confirmed') is True:
        return 'won'
    status = life.get('opportunity_status', 'unknown')
    require(status in OPEN | {'won', 'closed', 'none'}, '源需求状态无效')
    require(status != 'won', '源won须有本需求正式购买确认')
    if status == 'closed':
        refs = life.get('refs') or []
        evidence = {e['id'] for e in source.get('evidence', [])}
        require(bool(life.get('reason')) and bool(refs) and set(refs) <= evidence,
                '结束需求须保留源状态理由和本案证据')
    return status


def _snapshot(row):
    return copy.deepcopy({k: row.get(k) for k in (
        'sales_id', 'sales_name', 'case_id', 'name', 'source', 'decision',
        'manager_question', 'action')})


def _contact(source, cutoff):
    value = source.get('contact_status')
    if isinstance(value, dict):
        return copy.deepcopy(value)
    return {'status': 'not_assessed', 'label': '联系状态未评定', 'as_of': cutoff,
            'why': '此份标准结果未提供联系状态扩展；不能据此推定失联或恢复。'}


def protected_contact_work(row):
    """Pausing ordinary outreach must not hide paid-course or explicit verification duties."""
    source = row.get('source') or {}
    trial = source.get('trial') or {}
    trigger = (row.get('decision') or {}).get('trigger')
    if trial.get('paid') is True or trial.get('completed') is True:
        return '已付或已完课事项仍需核查；暂时失联不解除课程责任及原试听预警。'
    if trigger == 'service_followup' and (source.get('formal') or {}).get('confirmed') is True:
        return '已正式购买的服务事项仍需处理；暂时失联不等于服务结束。'
    if ((source.get('must_follow') or {}).get('needed') is True and
            trigger in ('order_verify', 'course_verify', 'scope_verify')):
        return '源必须跟回包含订单、课况或范围核查，保留核查入口。'
    return None


def contact_routing(row, contact):
    temporary = (contact or {}).get('status') == TEMPORARY_UNREACHABLE
    protection = protected_contact_work(row) if temporary else None
    return {'paused': temporary and protection is None, 'protected': protection is not None,
            'reason': protection or ('暂时失联：暂停普通追单提醒，保留未结记录；有新回复或有据的等待约定后再更新。'
                                     if temporary else '未因联系状态暂停本次管理建议。')}


def _continued_contact(source, cutoff, previous_entry):
    incoming = _contact(source, cutoff)
    prior = (previous_entry or {}).get('contact_status')
    if prior is None and previous_entry:
        prior = (previous_entry.get('snapshot') or {}).get('source', {}).get('contact_status')
    if not isinstance(prior, dict) or prior.get('status') != TEMPORARY_UNREACHABLE:
        return incoming, 'current'
    if incoming.get('status') in (TEMPORARY_UNREACHABLE, 'waiting'):
        return incoming, 'current'
    if (incoming.get('status') == 'wait_unknown' and
            incoming.get('coverage') == 'complete' and incoming.get('evidence') and
            incoming.get('as_of') and _time(incoming['as_of']) == _time(cutoff)):
        # A corrected, source-checked waiting agreement may predate the pause.
        # It does not need a new reply to undo the incorrect silence routing.
        incoming['previous_contact'] = {
            key: copy.deepcopy(prior.get(key))
            for key in ('status', 'as_of', 'first_unanswered_at', 'evidence')}
        incoming['review_note'] = '本期完整联系评定补出有据的等待约定；恢复时点待核，撤回原普通追单暂停，不等同客户已有新回复。'
        return incoming, 'revised_from_wait'
    # A newly supplied result alone does not undo a prior pause. A concrete genuine
    # customer reply after the stopped cycle does; the single-case checker owns role/ref validation.
    replied_at = incoming.get('last_customer_reply_at')
    replied_ref = incoming.get('last_customer_reply_ref')
    stopped_at = prior.get('first_unanswered_at') or prior.get('as_of')
    if replied_at and replied_ref and stopped_at:
        try:
            recovered = _time(replied_at) > _time(stopped_at) and _time(replied_at) <= _time(cutoff)
        except TypeError as exc:
            raise ValueError('往期商机：恢复联系与原暂停时间口径不一致') from exc
        if recovered:
            value = copy.deepcopy(incoming)
            value.update(status='reengaged', label='客户已恢复回复', resumed_at=replied_at,
                         why='新标准结果提供了原暂停周期之后的真实客户回复，恢复正常跟进；不代表已成交。')
            return value, 'recovered_from_reply'
    retained = copy.deepcopy(prior)
    if replied_at and not replied_ref:
        retained['review_note'] = '上次暂时失联；本期有客户回复时间，但可核引用未提供，回复依据待核。本次没有重新判定失联。'
    else:
        retained['review_note'] = '本期未补齐原暂停周期之后的联系复核，保留上次标记；本次没有重新判定失联。'
    return retained, 'retained_unverified'


def _source(row, members):
    member = members.get(row['sales_id'])
    require(member is not None and member.get('analysis_id'), '本期案例缺成员分析出处')
    return {'analysis_id': member['analysis_id'], 'sales_id': row['sales_id'], 'case_id': row['case_id']}


def _validate_entry(entry, cutoff):
    require(isinstance(entry, dict) and isinstance(entry.get('snapshot'), dict), '历史池项缺快照')
    require(entry.get('status') in OPEN | {'won', 'closed', 'none'}, '历史池状态无效')
    require(type(entry.get('is_open')) is bool and entry['is_open'] == (entry['status'] in OPEN), '历史池终态矛盾')
    require(isinstance(entry.get('pool_id'), str) and entry['pool_id'], '历史池项缺编号')
    require(_time(entry['last_observed_cutoff']) <= _time(cutoff), '历史池快照不能来自未来')
    require(_time(entry['first_tracked_week']) <= _time(cutoff), '首次管理基线不能来自未来')
    require(entry['snapshot'].get('sales_id') == entry.get('sales_id'), '历史池归属与快照矛盾')
    require(entry.get('last_source', {}).get('sales_id') == entry.get('sales_id'), '历史池出处归属矛盾')
    if entry.get('identity_status') in ('company', 'account'):
        require(entry.get('identity_key') == stable_key(entry['snapshot'].get('source') or {}), '历史池固定身份与来源矛盾')
        require(entry['pool_id'] == 'op-' + _id(entry['identity_key']), '历史池固定编号与身份矛盾')


def build(rows, reporting_window, source_members, previous=None):
    """Only supplied history is carried; absence never proves zero past opportunities."""
    require(isinstance(rows, list), '本期案例须为数组')
    start, cutoff = reporting_window['week_start'], reporting_window['cutoff']
    members = {m['sales_id']: m for m in source_members}
    baseline = start
    coverage = 'not_provided'
    old_entries = []
    if previous is not None:
        prior_window = previous['reporting_window']
        require(prior_window['time_basis'] == reporting_window['time_basis'], '历史与本期时间口径不同')
        try:
            require(_time(prior_window['cutoff']) <= _time(cutoff) and
                    _time(prior_window['week_start']) <= _time(start), '不能使用未来历史快照')
        except TypeError as exc:
            raise ValueError('往期商机：历史与当前时区口径不一致') from exc
        old_pool = previous.get('opportunity_pool')
        if old_pool is None:
            old_pool = build(previous['cases'], prior_window, previous['source_members'])['opportunity_pool']
            coverage = 'previous_snapshot_only'
        else:
            require(old_pool.get('schema_version') == SCHEMA, '历史商机池版本不支持')
            coverage = 'provided_chain'
        baseline = old_pool['baseline_start']
        old_entries = copy.deepcopy(old_pool['entries'])
    entries = {}
    canonical = {}
    for entry in old_entries:
        _validate_entry(entry, cutoff)
        require(entry['pool_id'] not in entries, '历史池编号重复')
        entry['refresh_status'] = 'unrefreshed'
        if 'contact_status' not in entry:
            entry['contact_status'] = _contact(entry['snapshot'].get('source') or {}, entry['last_observed_cutoff'])
        entry['contact_refresh_status'] = 'retained_unverified'
        entry['is_prior'] = _time(entry['first_tracked_week']) < _time(start)
        entry['state_note'] = '本期未复核，保留上次判断；不表示已确认当前订单或客户状态。' if entry['is_open'] else '保留已结束需求的来源记录。'
        entry['contact_routing'] = contact_routing(entry['snapshot'], entry['contact_status'])
        entries[entry['pool_id']] = entry
        if entry.get('identity_status') in ('company', 'account'):
            require(entry['pool_id'] not in canonical, '历史池同需求重复')
            canonical[entry['pool_id']] = entry
    row_keys = {}
    for row in rows:
        key = stable_key(row['source'])
        if key:
            row_keys.setdefault('op-' + _id(key), []).append(row)
    closed_ids = []
    for row in sorted(rows, key=lambda r: (r['sales_id'], r['case_id'])):
        source = row['source']; key = stable_key(source); source_ref = _source(row, members)
        pid = 'op-' + _id(key) if key else None
        previous_entry = canonical.get(pid)
        status = _status(source)
        if status == 'none' and previous_entry is None:
            continue
        identity_status = key['kind'] if key else 'pending'
        note = ''
        if pid and (len(row_keys[pid]) > 1 or (previous_entry and previous_entry['sales_id'] != row['sales_id'])):
            identity_status = 'ownership_pending'
            note = '同一需求出现重复或跨顾问归属，本轮不自动转派、不关闭原负责人的商机。'
            previous_entry = None
        if identity_status in ('pending', 'ownership_pending'):
            pid = 'pending-' + _id(source_ref)
            note = note or '缺少稳定客户或需求编号，不按昵称或本批案例编号跨期合并。'
        old_open = previous_entry['is_open'] if previous_entry else False
        first_week = previous_entry['first_tracked_week'] if previous_entry else start
        snap = _snapshot(row)
        contact, contact_refresh = _continued_contact(source, cutoff, previous_entry)
        if contact_refresh == 'retained_unverified':
            note = (note + ' ' if note else '') + '本期未补齐暂停后的联系复核，保留上次暂时失联标记及其原时点。'
        if previous_entry and old_open and status == 'none':
            status = previous_entry['status']
            note = (note + ' ' if note else '') + '本次标无销售需求不能证明原商机已结束；保留原未结状态，需核实。'
            # Keep the latest observation, but retain the exact prior state basis separately.
            retained = {'status': previous_entry['status'], 'last_source': copy.deepcopy(previous_entry['last_source']),
                        'last_observed_cutoff': previous_entry['last_observed_cutoff']}
        else:
            retained = None
        if previous_entry and not old_open and status in OPEN:
            events = (source.get('lifecycle') or {}).get('events', [])
            resumed = previous_entry['status'] == 'closed' and any(e.get('kind') == 'demand_resumed' for e in events)
            require(resumed, '已结束的同一需求不能无恢复依据重开；独立新需求使用新编号')
        entry = {'pool_id': pid, 'identity_key': key, 'identity_status': identity_status,
                 'sales_id': row['sales_id'], 'sales_name': row.get('sales_name'),
                 'case_id': row['case_id'], 'name': row.get('name'),
                 'first_tracked_week': first_week, 'last_observed_cutoff': cutoff,
                 'last_source': source_ref, 'status': status, 'is_open': status in OPEN,
                 'refresh_status': 'current', 'is_prior': _time(first_week) < _time(start),
                 'state_note': note, 'retained_status_basis': retained, 'snapshot': snap}
        entry.update(contact_status=contact, contact_refresh_status=contact_refresh,
                     contact_routing=contact_routing(row, contact))
        entries[pid] = entry
        if previous_entry and old_open and not entry['is_open']:
            closed_ids.append(pid)
    ordered = sorted(entries.values(), key=lambda e: (e['first_tracked_week'], e['sales_id'], e['pool_id']))
    followup = {'current': [], 'unrefreshed': [], 'waiting': [],
                'closed_this_run': sorted(closed_ids), 'identity_pending': [],
                'temporary_unreachable': []}
    for entry in ordered:
        pid = entry['pool_id']
        if entry['identity_status'] == 'ownership_pending' or (entry['identity_status'] == 'pending' and entry['is_open']):
            followup['identity_pending'].append(pid)
            continue
        if entry['is_open'] and entry.get('contact_status', {}).get('status') == TEMPORARY_UNREACHABLE:
            followup['temporary_unreachable'].append(pid)
            if entry['contact_routing']['paused']:
                continue
        if entry['is_open'] and entry['is_prior'] and entry.get('contact_status', {}).get('status') in ('waiting', 'wait_unknown'):
            followup['waiting'].append(pid)
            continue
        if entry['is_open'] and entry['is_prior']:
            if entry['refresh_status'] == 'unrefreshed':
                snapshot = entry['snapshot']; source = snapshot.get('source') or {}
                worthwhile = ((snapshot.get('decision') or {}).get('attention') in ('manager', 'advisor') or
                              (source.get('must_follow') or {}).get('needed') is True or
                              (source.get('trial') or {}).get('paid') is True)
                followup['unrefreshed' if worthwhile else 'waiting'].append(pid)
            elif (entry['snapshot'].get('decision') or {}).get('attention') in ('manager', 'advisor'):
                followup['current'].append(pid)
            else:
                followup['waiting'].append(pid)
    return {'opportunity_pool': {'schema_version': SCHEMA, 'as_of': cutoff,
                                'baseline_only': previous is None, 'history_coverage': coverage,
                                'baseline_start': baseline, 'entries': ordered},
            'history_followup': followup}
