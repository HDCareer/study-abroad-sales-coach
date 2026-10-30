"""Private, expiring cross-period snapshots. No CRM, automatic judgment or deletion."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import hashlib
import html
import json
from pathlib import Path

VERSION = 'skill3-longitudinal/1'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def validate_input(data, api):
    """Check optional annotations created by the Skill, not their semantic accuracy."""
    cfg = data['management'].get('longitudinal')
    if cfg is None:
        api.require(not any(c.get('management', {}).get('tracking', {}).get('events') for c in data['cases']), 'tracking', '带教观察事件需要同批longitudinal定义；仅需求编号可独立使用')
        cfg={'definitions':[], 'training_events':[]}
    api.obj(cfg, 'longitudinal')
    definitions = cfg.get('definitions')
    api.require(isinstance(definitions, list), 'longitudinal.definitions', '需要同类机会定义数组')
    keys = set()
    for definition in definitions:
        for key in ('key', 'version', 'policy_version', 'label', 'opportunity_definition'):
            api.string(definition.get(key), 'longitudinal.definition.' + key)
        identity = (definition['key'], definition['version'], definition['policy_version'])
        api.require(identity not in keys, 'longitudinal.definitions', '机会定义重复')
        keys.add(identity)
        api.choice(definition.get('layer'), ('judgment', 'expression', 'execution'), 'longitudinal.layer')
        api.choice(definition.get('stage'), api.STAGES, 'longitudinal.stage')
    cutoff = datetime.fromisoformat(data['management']['cutoff'])
    for c in data['cases']:
        tracking = c.get('management', {}).get('tracking')
        if tracking is None or not c['included']:
            continue
        api.obj(tracking, c['id'] + '.tracking')
        opportunity = tracking.get('opportunity_id')
        api.require(opportunity is None or isinstance(opportunity, str) and opportunity.strip(), 'tracking.opportunity_id', '需求ID未知用null，不用昵称替代')
        events = tracking.get('events')
        api.require(isinstance(events, list), 'tracking.events', '需要可观察机会数组')
        messages = {m['id']: m for m in c['source_messages']}
        anchors = set()
        for event in events:
            identity = tuple(event.get(k) for k in ('key', 'version', 'policy_version'))
            api.require(identity in keys, 'tracking.event', '观察必须对应已声明的同类机会定义')
            api.choice(event.get('state'), ('gap', 'sound', 'unknown'), 'tracking.state')
            api.choice(event.get('review'), ('unreviewed', 'confirmed', 'contested', 'withdrawn'), 'tracking.review')
            api.choice(event.get('change_kind'), ('observation', 'correction'), 'tracking.change_kind')
            if event['review'] in ('confirmed', 'withdrawn') or event['change_kind'] == 'correction':
                api.string(event.get('confirmation_source'), 'tracking.confirmation_source')
            if event['change_kind'] == 'correction':
                api.require(event['review'] in ('confirmed', 'withdrawn'), 'tracking.correction', '正式纠错需要实际人工确认')
            ref = event.get('anchor_ref')
            api.require(isinstance(ref, str) and ref in messages, 'tracking.anchor_ref', '观察锚点须来自本案原话')
            m = messages[ref]
            api.require(not m.get('sensitive') and bool(m.get('text', '').strip()), 'tracking.anchor_ref', '敏感或空原话不能作为观察锚点')
            api.require(m.get('source_role') in ('sales', 'customer'), 'tracking.anchor_ref', '锚点须有可确认的说话角色')
            try:
                at = datetime.fromisoformat(event['observed_at'])
                api.require(datetime.fromisoformat(m['time']) <= at <= cutoff, 'tracking.observed_at', '观察时间须在锚点之后且不晚于截止')
            except (KeyError, ValueError, TypeError):
                raise api.ValidationError('tracking.observed_at：时间或时区无法比较')
            anchor = m.get('source_message_id') or digest([m['time'], m['source_role'], m['text']])
            if not m.get('source_message_id'):
                api.require(sum((x['time'], x.get('source_role'), x['text']) == (m['time'], m['source_role'], m['text']) for x in messages.values()) == 1,
                            'tracking.anchor_ref', '无稳定消息ID且相同原话同时间重复，不能自动确定同一机会')
            api.require((identity, anchor) not in anchors, 'tracking.events', '同一机会重复记录')
            anchors.add((identity, anchor))
    training = cfg.get('training_events', [])
    api.require(isinstance(training, list), 'longitudinal.training_events', '培训执行记录须为数组')
    ids = set()
    for event in training:
        for key in ('id', 'plan_id', 'key', 'version', 'policy_version', 'at', 'confirmation_source'):
            api.string(event.get(key), 'training_event.' + key)
        api.require(event['id'] not in ids, 'training_events', '执行事件ID重复')
        ids.add(event['id'])
        api.require(tuple(event[k] for k in ('key', 'version', 'policy_version')) in keys, 'training_events', '执行记录未对应机会定义')
        api.choice(event.get('kind'), ('assigned', 'completed', 'verified'), 'training_event.kind')
        try:
            api.require(datetime.fromisoformat(event['at']) <= cutoff, 'training_event.at', '实际培训不能发生于资料截止之后')
        except (TypeError, ValueError):
            raise api.ValidationError('training_event.at：时间无法比较')


def make_snapshot(results, recorded_at, retention_days=None, retention_basis=None, supersedes=None, retention_start_at=None):
    if results.get('schema_version') != 'skill3-management-results/1.0':
        raise ValueError('需要由报告生成器输出的统一管理结果')
    if type(retention_days) is not int or retention_days <= 0:
        raise ValueError('保留天数必须是正整数')
    if not retention_basis:
        raise ValueError('结构化档案保留需要明确授权依据；参数本身不证明授权')
    created = datetime.fromisoformat(recorded_at)
    start = datetime.fromisoformat(retention_start_at or recorded_at)
    if start > created:
        raise ValueError('保留期起算时间不能晚于登记时间')
    cutoff = datetime.fromisoformat(results['reporting_window']['cutoff'])
    if created < cutoff:
        raise ValueError('档案登记时间不能早于资料截止')
    cfg = results.get('longitudinal') or {'definitions': [], 'training_events': []}
    records, unmatched, seen_relations = [], [], set()
    for c in results['cases']:
        if not c['included']:
            continue
        identity = c['identity']
        if identity.get('basis') != 'source_id':
            unmatched.append(c['case_id'])
            continue
        relation = digest([identity['account_id'], identity['customer_id']])
        tracking = c.get('tracking') or {'opportunity_id': None, 'events': []}
        episode = digest([relation, tracking['opportunity_id']]) if tracking['opportunity_id'] else None
        if (relation, episode) in seen_relations:
            raise ValueError('同一客户的多条记录未区分需求ID，不能自动合并')
        seen_relations.add((relation, episode))
        own = {m['id']: m for m in c['evidence']}
        events = []
        for event in tracking['events']:
            anchor = own[event['anchor_ref']]
            anchor_key = anchor.get('source_message_id') or digest([anchor['time'], anchor['source_role'], anchor['text']])
            event_id = digest([relation, episode, event['key'], event['version'], event['policy_version'], anchor_key])
            events.append({**{k: event[k] for k in ('key', 'version', 'policy_version', 'state', 'review', 'change_kind', 'observed_at')},
                           'event_id': event_id, 'anchor_key': digest(anchor_key),
                           'human_confirmation_recorded': bool(event.get('confirmation_source'))})
        records.append({'relationship_key': relation, 'opportunity_key': episode, 'case_id': c['case_id'],
                        'identity_verified_against_source': results['source_verification']['status'] == 'matched',
                        'validity': c['validity']['status'], 'label': c['validity']['label'],
                        'stages': {key: value['state'] for key, value in c['current_phases'].items()},
                        'trial_paid': c['trial']['paid'], 'trial_completed': c['trial']['completed'],
                        'formal_confirmed': c['formal']['confirmed'], 'must_follow': c['must_follow']['needed'],
                        'events': events})
    training = [{k: e[k] for k in ('id', 'plan_id', 'key', 'version', 'policy_version', 'kind', 'at')}
                for e in cfg.get('training_events', [])]
    return {'schema_version': VERSION, 'analysis_id': results['analysis_id'], 'supersedes_analysis_id': supersedes,
            'skill_version': results['skill_version'], 'sales': results['sales'],
            'window': results['reporting_window'], 'recorded_at': recorded_at,
            'retention_start_at': start.isoformat(' '),
            'expires_at': (start + timedelta(days=retention_days)).isoformat(' '),
            'retention_days': retention_days, 'retention_basis': retention_basis or '须配置本机构授权依据',
            'definitions': cfg.get('definitions', []), 'training_events': training,
            'cases': records, 'unmatched_case_ids': unmatched,
            'evidence_notice': '不含客户原话、姓名或原始身份ID；哈希标识仍属私有可关联资料，不是匿名证明。原证据是否仍可回查另按源资料保留情况核实。'}


def compare(snapshots, view_at):
    now = datetime.fromisoformat(view_at)
    valid, expired, unique = [], [], {}
    for s in snapshots:
        if s.get('schema_version') != VERSION:
            raise ValueError('不支持的跨周快照格式')
        if datetime.fromisoformat(s['recorded_at']) > now:
            raise ValueError('不能使用查看时点之后登记的档案')
        if datetime.fromisoformat(s['expires_at']) <= now:
            expired.append(s['analysis_id'])
            continue
        if s['analysis_id'] in unique:
            if digest(unique[s['analysis_id']]) != digest(s):
                raise ValueError('相同分析编号的快照不一致，不能静默覆盖')
            continue
        unique[s['analysis_id']] = s
    groups = defaultdict(list)
    for s in unique.values():
        key = (s['sales']['id'], s['window']['week_start'], s['window']['week_end'])
        groups[key].append(s)
    for items in groups.values():
        items.sort(key=lambda s: (datetime.fromisoformat(s['window']['cutoff']), datetime.fromisoformat(s['recorded_at'])))
        for prev, nxt in zip(items, items[1:]):
            if datetime.fromisoformat(prev['window']['cutoff']) == datetime.fromisoformat(nxt['window']['cutoff']) and nxt.get('supersedes_analysis_id') != prev['analysis_id']:
                raise ValueError('同一截止时点的修正版需要明确替代哪个分析编号')
        valid.append(items[-1])
    valid.sort(key=lambda s: (datetime.fromisoformat(s['window']['cutoff']), datetime.fromisoformat(s['recorded_at'])))
    customers, events, conflicts, definitions, trainings = {}, {}, set(), {}, {}
    for s in valid:
        sid = s['sales']['id']
        for d in s['definitions']:
            key = (sid, d['key'], d['version'], d['policy_version'], s['window']['time_basis'])
            if key in definitions and definitions[key] != d:
                raise ValueError('同一机会版本的定义改变，需升版本后分段观察')
            definitions[key] = d
        for t in s['training_events']:
            key = (sid, t['id'], s['window']['time_basis'])
            training_item = {**t, 'time_basis': s['window']['time_basis']}
            if key in trainings and trainings[key] != training_item:
                raise ValueError('相同培训执行事件被改写，需保留独立纠错记录')
            trainings[key] = training_item
        for c in s['cases']:
            case_key = (sid, c['relationship_key'], c['opportunity_key'])
            old = customers.get(case_key)
            delta = [k for k in ('validity', 'label', 'trial_paid', 'trial_completed', 'formal_confirmed', 'must_follow', 'stages') if old and old[k] != c[k]]
            customers[case_key] = {**c, 'sales_id': sid, 'as_of': s['window']['cutoff'], 'changed_fields': delta,
                                   'first_observed': old['first_observed'] if old else s['window']['cutoff'],
                                   'latest_analysis_id': s['analysis_id']}
            for e in c['events']:
                ek = (sid, e['event_id'])
                item = {**e, 'sales_id': sid, 'time_basis': s['window']['time_basis']}
                old_event = events.get(ek)
                changed = old_event and any(old_event[k] != item[k] for k in ('state', 'review', 'observed_at'))
                if changed and not (e['change_kind'] == 'correction' and e['human_confirmation_recorded']):
                    conflicts.add(ek)
                    continue
                if e['change_kind'] == 'correction':
                    conflicts.discard(ek)
                events[ek] = item
    rows = defaultdict(Counter)
    for ek, e in events.items():
        week = datetime.fromisoformat(e['observed_at']).date().isocalendar()
        key = (e['sales_id'], e['key'], e['version'], e['policy_version'], e['time_basis'], f'{week.year}-W{week.week:02d}')
        state = 'contested' if ek in conflicts or e['review'] == 'contested' else 'withdrawn' if e['review'] == 'withdrawn' else e['state']
        rows[key][state] += 1
        rows[key]['unreviewed'] += e['review'] == 'unreviewed'
    patterns = []
    for key, counts in sorted(rows.items()):
        definition = definitions.get(key[:5])
        patterns.append({'sales_id': key[0], 'key': key[1], 'version': key[2], 'policy_version': key[3],
                         'time_basis': key[4], 'week': key[5], 'label': definition['label'] if definition else key[1],
                         'counts': dict(counts), 'assessable': counts['gap'] + counts['sound'],
                         'gap': counts['gap'], 'provisional_unreviewed': counts['unreviewed']})
    training_views = []
    for (sid, _, _), t in trainings.items():
        if t['kind'] not in ('completed', 'verified'):
            continue
        before, after = Counter(), Counter()
        for ek, e in events.items():
            if e['sales_id'] != sid or e['time_basis'] != t['time_basis'] or tuple(e[k] for k in ('key', 'version', 'policy_version')) != tuple(t[k] for k in ('key', 'version', 'policy_version')):
                continue
            target = after if datetime.fromisoformat(e['observed_at']) > datetime.fromisoformat(t['at']) else before
            if ek in conflicts or e['review'] in ('contested', 'withdrawn'):
                target[e['review'] if ek not in conflicts else 'contested'] += 1
            else:
                target[e['state']] += 1
        training_views.append({**t, 'sales_id': sid, 'before': dict(before), 'after': dict(after),
                               'interpretation': '仅描述同版本机会中训练前后的已见表现；没有新机会不判改善，比例变化不证明训练因果。'})
    latest_by_sales = {}
    for s in valid:
        sid = s['sales']['id']
        latest_by_sales[sid] = max(latest_by_sales.get(sid, s['window']['cutoff']), s['window']['cutoff'], key=datetime.fromisoformat)
    for c in customers.values():
        fresh = datetime.fromisoformat(c['as_of']) == datetime.fromisoformat(latest_by_sales[c['sales_id']])
        c['seen_in_latest_batch'] = fresh
        c['follow_status'] = ('本期跟回建议' if fresh else '仅旧快照待办，需新证据核实') if c['must_follow'] else '最近可见快照未列跟回'
    return {'schema_version': 'skill3-longitudinal-view/1', 'view_at': view_at,
            'active_analysis_ids': [s['analysis_id'] for s in valid], 'expired_analysis_ids': expired,
            'customers': list(customers.values()), 'patterns': patterns, 'training': training_views,
            'conflicting_event_count': len(conflicts), 'unmatched_case_count': sum(len(s['unmatched_case_ids']) for s in valid),
            'limits': '首次观察不等于实际新加；无需求ID仅跟踪销售与客户关系，转接和新需求不自动合并。不同规则/机会版本分段，申诉待核不计可判分母。到期只停止使用并列出，不自动删除。'}


def render(view):
    e = lambda x: html.escape(str(x), quote=True)
    rows = ''.join(f'<tr><td>{e(p["sales_id"])}</td><td>{e(p["week"])}</td><td>{e(p["label"])}<small>{e(p["version"])} / {e(p["policy_version"])}</small></td><td>{p["gap"]}/{p["assessable"]}</td><td>{e(p["counts"])}</td></tr>' for p in view['patterns'])
    customers = ''.join(f'<tr><td>{e(c["sales_id"])}</td><td>{e(c["relationship_key"][:12])}</td><td>{e(c["label"])}<small>{e(c["follow_status"])}</small></td><td>{e(c["changed_fields"])}</td><td>{e(c["as_of"])}</td></tr>' for c in view['customers'])
    training = ''.join(f'<p>{e(t["plan_id"])} · {e(t["kind"])}：训练前 {e(t["before"])}；训练后 {e(t["after"])}</p>' for t in view['training'])
    return f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>跨周销售观察</title><style>body{{font:15px/1.7 system-ui;max-width:1100px;margin:30px auto;padding:16px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}small{{display:block;color:#666}}.scroll{{overflow:auto}}</style><h1>跨周销售观察</h1><p>{e(view["limits"])}</p><p>有效批次{len(view["active_analysis_ids"])}；到期待处理{len(view["expired_analysis_ids"])}；身份未能续接{view["unmatched_case_count"]}；观察冲突{view["conflicting_event_count"]}。</p><h2>同类机会 · 缺口数/可判断机会</h2><p>重复问题仅计一次。未人工复核的观察单独列数，不作为已确认的岗位能力结论。</p><div class="scroll"><table><tr><th>销售</th><th>发生周</th><th>同类问题/版本</th><th>缺口/可判</th><th>完整计数</th></tr>{rows}</table></div><h2>训练后的新机会</h2>{training or "<p>尚无实际训练完成记录。</p>"}<h2>客户当前状态续接</h2><p>只显示私有标识摘要；完整聊天与客户姓名未写入本档案。原案仍须在授权来源中回查。</p><div class="scroll"><table><tr><th>销售</th><th>客户标识</th><th>最新等级</th><th>变化项</th><th>资料截止</th></tr>{customers}</table></div></html>'


def main(argv=None):
    p = argparse.ArgumentParser(description='从同一分析生成私有跨周快照和观察表，不读取平台、不自动判断或删除')
    p.add_argument('--results', required=True, type=Path)
    p.add_argument('--history', nargs='*', type=Path, default=[])
    p.add_argument('--snapshot-output', required=True, type=Path)
    p.add_argument('--summary-output', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--recorded-at', required=True)
    p.add_argument('--retention-days', type=int)
    p.add_argument('--retention-basis')
    p.add_argument('--retention-start-at', help='首次交付/获准起算时点；重导入或更正不顺延')
    p.add_argument('--supersedes')
    args = p.parse_args(argv)
    import render_chat_review as api
    try:
        results = json.loads(args.results.read_text(encoding='utf-8-sig'))
        current = make_snapshot(results, args.recorded_at, args.retention_days, args.retention_basis, args.supersedes, args.retention_start_at)
        history = [json.loads(path.read_text(encoding='utf-8-sig')) for path in args.history]
        view = compare(history + [current], args.recorded_at)
        outputs = {args.snapshot_output: json.dumps(current, ensure_ascii=False, indent=2),
                   args.summary_output: json.dumps(view, ensure_ascii=False, indent=2), args.output: render(view)}
        if len({x.resolve() for x in outputs}) != 3 or any(x.resolve() in {v.resolve() for v in [args.results] + args.history} for x in outputs):
            raise ValueError('三个输出必须不同且不能覆盖任何输入')
        for path in outputs:
            api.private_output(path)
            if path.exists():
                raise ValueError('已有文件默认不覆盖：' + str(path))
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('x', encoding='utf-8') as handle:
                handle.write(content)
        print(json.dumps({'snapshot': str(args.snapshot_output), 'view': str(args.output), 'active_batches': len(view['active_analysis_ids']), 'source_authorization': '须由使用者确认，程序不能认证'}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, api.ValidationError) as exc:
        print('无法生成跨周观察：' + str(exc))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
