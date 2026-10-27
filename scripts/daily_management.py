"""Daily changes and action states over labelled evidence; no automatic sales judgment."""
from collections import Counter
from datetime import datetime

STATES = ('proposed', 'assigned', 'executed_waiting_customer', 'blocked_internal', 'resolved', 'cancelled')
LABELS = {'proposed':'建议待安排', 'assigned':'待执行', 'executed_waiting_customer':'已执行 等待客户',
          'blocked_internal':'内部协作受阻', 'resolved':'已解决', 'cancelled':'已不适用'}
TERMINAL = ('resolved', 'cancelled')


def identity(case):
    item = case.get('identity') or case.get('validity', {}).get('assessment', {}).get('identity', {})
    if item.get('basis') != 'source_id' or not item.get('account_id') or not item.get('customer_id'):
        return None
    tracking=case.get('tracking') or case.get('management',{}).get('tracking') or {}
    return item['account_id'], item['customer_id'], tracking.get('opportunity_id')


def actions(case):
    return case.get('actions') or case.get('management', {}).get('actions', [])


def validate(data, api):
    m=data['management']
    api.choice(m.get('cadence', 'weekly'), ('daily','weekly','period'), 'management.cadence')
    if m.get('cadence') == 'daily':
        cfg=api.obj(m.get('daily'), 'management.daily')
        api.choice(cfg.get('source_health'), ('complete','partial','delayed'), 'daily.source_health')
        api.string(cfg.get('source_note'), 'daily.source_note')
        cap=cfg.get('priority_limit',5)
        api.require(type(cap) is int and 1<=cap<=50, 'daily.priority_limit', '优先显示容量须为1至50的整数，剩余事项仍保留')
        api.require(datetime.fromisoformat(m['week_start']).date()==datetime.fromisoformat(m['week_end']).date(), 'daily.period', 'Daily统计范围须落在同一来源日期')
    cutoff=datetime.fromisoformat(m['cutoff'])
    for c in data['cases']:
        if not c['included']:continue
        values=c['management'].get('actions', [])
        api.require(isinstance(values,list),c['id']+'.actions','动作须为数组')
        own={x['id']:x for x in c['source_messages']}
        signals=c['management'].get('daily_signals',[])
        api.require(isinstance(signals,list),'daily_signals','重要变化须为数组')
        signal_ids=set()
        for s in signals:
            for key in ('id','reason'):api.string(s.get(key),'daily_signal.'+key)
            api.require(s['id'] not in signal_ids,'daily_signal.id','同案信号重复')
            signal_ids.add(s['id'])
            api.choice(s.get('kind'),('new_blocker','customer_commitment','manager_needed','evidence_correction'),'daily_signal.kind')
            refs=s.get('refs')
            api.require(isinstance(refs,list) and refs and all(isinstance(r,str) for r in refs) and len(refs)==len(set(refs)),'daily_signal.refs','重要变化需有原话依据')
            for r in refs:api.require(r in own and not own[r].get('sensitive') and bool(own[r]['text'].strip()),'daily_signal.refs','信号引用不能跨案、敏感或为空')
            if s['kind']=='evidence_correction':api.string(s.get('confirmation_source'),'daily_signal.confirmation_source')
        seen=set()
        for a in values:
            for key in ('id','issue_key','owner','action','status','updated_at'):
                api.string(a.get(key),'action.'+key)
            api.require(a['id'] not in seen,'action.id','同案动作ID重复')
            seen.add(a['id'])
            api.choice(a['status'],STATES,'action.status')
            api.choice(a.get('kind'),('sales_followup','trial_conversion','manager_decision','service','verify'),'action.kind')
            api.require(type(a.get('priority')) is int and a['priority'] in (1,2,3),'action.priority','优先级为1至3')
            for key in ('due_at','next_check_at','acknowledged_at','escalate_at'):
                api.require(key in a,'action.'+key,'时间未知须显式null')
                if a[key] is not None:
                    try: datetime.fromisoformat(a[key])-cutoff
                    except (TypeError,ValueError):raise api.ValidationError('action.'+key+'：时间格式不正确')
            try:
                api.require(datetime.fromisoformat(a['updated_at'])<=cutoff,'action.updated_at','状态不能在资料截止之后发生')
                api.require(a['acknowledged_at'] is None or datetime.fromisoformat(a['acknowledged_at'])<=cutoff,'action.acknowledged_at','不能预填未来主管确认')
            except (TypeError,ValueError):raise api.ValidationError('action：时区或日期无法比较')
            refs=a.get('refs')
            api.require(isinstance(refs,list) and all(isinstance(x,str) for x in refs) and len(refs)==len(set(refs)),'action.refs','需要不重复引用数组')
            for rid in refs:
                api.require(rid in own and not own[rid].get('sensitive') and bool(own[rid]['text'].strip()),'action.refs','引用不存在、跨案、敏感或为空')
                try: api.require(datetime.fromisoformat(own[rid]['time'])<=datetime.fromisoformat(a['updated_at']),'action.refs','不能用后续消息证明先前已执行')
                except (TypeError,ValueError):raise api.ValidationError('action.refs：消息与执行时间无法比较')
            if a['status']=='executed_waiting_customer':
                api.require(any(own[r].get('source_role')=='sales' for r in refs),'action.status','已执行须有实际销售动作，不以AI草稿证明')
            if a['status'] in ('assigned','blocked_internal'):
                api.string(a.get('confirmation_source'),'action.confirmation_source')
            if a['status'] in TERMINAL:
                api.string(a.get('resolution'),'action.resolution')
                api.require(bool(refs) or bool(a.get('confirmation_source')),'action.resolution','解决或取消须有实际依据')
            if c['recovery']['possibility']=='no_contact' and a['kind'] in ('sales_followup','trial_conversion'):
                api.require(a['status'] in TERMINAL,'action','明确拒收联系时不能继续推销任务，服务事项另列')


def action_view(a, cutoff):
    now=datetime.fromisoformat(cutoff)
    due=lambda key: a.get(key) is not None and datetime.fromisoformat(a[key])<=now
    status=a['status']
    if status in TERMINAL:return {'code':status,'label':LABELS[status],'attention':False}
    if due('escalate_at'):
        handled=(a.get('acknowledged_at') is not None and datetime.fromisoformat(a['acknowledged_at'])>=datetime.fromisoformat(a['escalate_at']) and a.get('next_check_at') is not None and not due('next_check_at'))
        return {'code':'escalated_acknowledged' if handled else 'escalated','label':'升级事项 已知晓待复查' if handled else '已到升级处理节点','attention':not handled}
    if status=='executed_waiting_customer':
        return {'code':'followup_due' if due('next_check_at') else 'waiting_customer',
                'label':'已执行 回访节点已到' if due('next_check_at') else LABELS[status], 'attention':due('next_check_at')}
    if a.get('acknowledged_at') and due('next_check_at'):
        return {'code':'review_due','label':'主管约定复查节点已到','attention':True}
    if due('due_at'):
        muted=a.get('acknowledged_at') is not None and a.get('next_check_at') is not None and not due('next_check_at')
        return {'code':'overdue_acknowledged' if muted else 'overdue','label':'逾期 已知晓待复查' if muted else '逾期未落实','attention':not muted}
    if status=='blocked_internal':return {'code':'blocked_internal','label':LABELS[status],'attention':True}
    return {'code':status,'label':LABELS[status],'attention':False}


def build(data, api, previous=None):
    import management_review as mr
    m=data['management']; cutoff=m['cutoff']; cfg=m.get('daily',{})
    prior={}
    if previous is not None:
        api.require(previous.get('schema_version')=='skill3-management-results/1.0','previous-results','需要统一管理结果，不是分析草稿')
        for field in ('sales','reporting_window'):api.obj(previous.get(field),'previous-results.'+field)
        api.string(previous.get('analysis_id'),'previous-results.analysis_id')
        api.require(isinstance(previous.get('cases'),list),'previous-results.cases','需要历史案例数组')
        api.require(previous['sales']['id']==data['sales']['id'],'previous-results','不能把其他销售结果当本人的昨日基线')
        api.require(previous['reporting_window']['time_basis']==m['time_basis'],'previous-results','时间口径不同不能直接对照')
        try:api.require(datetime.fromisoformat(previous['reporting_window']['cutoff'])<=datetime.fromisoformat(cutoff),'previous-results','不能使用未来基线')
        except (KeyError,TypeError,ValueError):raise api.ValidationError('previous-results：资料截止日期或时区无法比较')
        for c in previous['cases']:
            key=identity(c)
            if c['included'] and key:
                api.require(key not in prior,'previous-results','同客户多个需求未分清，暂不自动对照')
                prior[key]=c
    queue=[]; progress=[]; observed=[]; action_rows=[]; counts=Counter(); seen=set(); current_keys=set()
    def add(c,label,reason,priority=2,kind='change',action_id=None):
        signature=(c['id'],kind,action_id,label)
        if signature in seen:return
        seen.add(signature)
        queue.append({'case_id':c['id'],'name':c['name'],'label':label,'reason':reason,'priority':priority,'kind':kind,'action_id':action_id})
    for c in data['cases']:
        if not c['included']:continue
        key=identity(c); old=prior.get(key) if key else None
        if key:
            api.require(key not in current_keys,'daily.identity','本批同客户多项需求须先分清稳定机会ID，不能重复续接')
            current_keys.add(key)
        cm=c['management']; current_warning=mr.warning(c,cutoff,m.get('alert_thresholds_hours'))
        old_warning=old.get('trial_warning') if old else None
        baseline=old is not None
        if not baseline:observed.append(c['id'])
        old_signals={s['id'] for s in old.get('daily_signals',[])} if old else set()
        own={x['id']:x for x in c['source_messages']}
        for signal in cm.get('daily_signals',[]):
            if signal['id'] in old_signals:continue
            if old and signal['kind']!='evidence_correction':
                api.require(any(datetime.fromisoformat(own[r]['time'])>datetime.fromisoformat(previous['reporting_window']['cutoff']) for r in signal['refs']), 'daily_signal','新的重要变化须有上一时点之后的依据；旧证据纠错单列')
            labels={'new_blocker':'客户出现新阻碍','customer_commitment':'客户有新的推进承诺','manager_needed':'需要主管介入','evidence_correction':'已有判断经确认更正'}
            add(c,labels[signal['kind']],signal['reason'],1 if signal['kind']=='manager_needed' else 2,'signal',signal['id'])
        if baseline:
            delta=[]
            if c['validity']['status']!=old['validity']['status']:delta.append('有效等级变化')
            if cm['trial']['paid']!=old['trial']['paid']:delta.append('试听付款状态变化')
            if cm['trial']['completed']!=old['trial']['completed']:delta.append('实际完课状态变化')
            if cm['formal']['confirmed']!=old['formal']['confirmed']:delta.append('正式购买状态变化')
            if any(c['phases'][s]['state']!=old['current_phases'][s]['state'] for s in api.STAGES):delta.append('主线阶段变化')
            if delta:
                target=progress if cm['formal']['confirmed'] else queue
                target.append({'case_id':c['id'],'name':c['name'],'label':'、'.join(delta),'reason':c['headline'],'priority':2,'kind':'change','action_id':None})
        ranks={'window':0,'yellow':1,'orange':2,'red':3}
        rank=ranks.get(current_warning['code'],-1);prev_rank=ranks.get(old_warning['code'],-1) if old_warning else -1
        if rank>0 and rank>prev_rank:
            add(c,current_warning['label'],'依据已确认完课和本次资料截止；新进入或升级预警',1,'warning')
        old_actions={a['id']:a for a in actions(old)} if old else {}
        for a in actions(c):
            v=action_view(a,cutoff)
            row={**a,'case_id':c['id'],'name':c['name'],'effective':v}
            if cm['formal']['confirmed'] and a['kind'] in ('sales_followup','trial_conversion') and a['status'] not in TERMINAL:
                row['effective']={'code':'closed_by_purchase','label':'已正式购买 首次追单结束','attention':False}
                if not old or not old['formal']['confirmed']:
                    progress.append({'case_id':c['id'],'name':c['name'],'label':row['effective']['label'],'reason':a['action'],'priority':3,'kind':'closed','action_id':a['id']})
                action_rows.append(row);continue
            action_rows.append(row)
            oa=old_actions.get(a['id']);ov=action_view(oa,previous['reporting_window']['cutoff']) if oa else None
            changed=oa is None or any(a.get(k)!=oa.get(k) for k in ('status','issue_key','due_at','next_check_at','escalate_at'))
            if a['status'] in TERMINAL and changed:
                progress.append({'case_id':c['id'],'name':c['name'],'label':LABELS[a['status']],'reason':a['resolution'],'priority':3,'kind':'closed','action_id':a['id']})
            elif v['attention'] and (changed or not ov or ov['code']!=v['code'] or v['code'] in ('overdue','escalated','followup_due','review_due')):
                add(c,v['label'],a['action'],1 if v['code'] in ('overdue','escalated') else a['priority'],'action',a['id'])
            elif changed and a['status'] in ('proposed','assigned'):
                add(c,LABELS[a['status']],a['action'],a['priority'],'action',a['id'])
            elif changed and a['status']=='executed_waiting_customer':
                progress.append({'case_id':c['id'],'name':c['name'],'label':v['label'],'reason':a['action'],'priority':3,'kind':'progress','action_id':a['id']})
        if not actions(c) and cm['must_follow']['needed']:
            add(c,'需落实跟回动作状态',cm['must_follow']['action'],cm['must_follow']['priority'],'followup')
    def group_by_case(items):
        grouped={}
        for x in items:grouped.setdefault(x['case_id'],[]).append(x)
        return [{**v[0],'label':'；'.join(dict.fromkeys(x['label'] for x in v)),
                 'reason':'；'.join(dict.fromkeys(x['reason'] for x in v)),
                 'priority':min(x['priority'] for x in v),'events':v} for v in grouped.values()]
    queue=group_by_case(queue)
    progress=group_by_case(progress)
    queue.sort(key=lambda x:(x['priority'],x['case_id'],x['kind']))
    counts=Counter(a['effective']['code'] for a in action_rows)
    limit=cfg.get('priority_limit',5)
    return {'version':'skill3-daily/1','as_of':cutoff,'baseline_as_of':previous['reporting_window']['cutoff'] if previous else None,
            'source_health':cfg.get('source_health','partial'),'source_note':cfg.get('source_note',data['scope']['coverage']),
            'priority':queue[:limit],'other_attention':queue[limit:],'progress':progress,'first_observed_case_ids':observed,
            'action_counts':dict(counts),'actions':action_rows,
            'note':'首次观察不等于新增客户。未列入首页不等于问题已解决；全部待办与完整证据仍可展开。时间仅推进到已声明的资料截止，不使用系统当前时间补造客户状态。'}


def render(data, api, view):
    import management_review as mr
    import quality_and_cohorts
    base=mr.render(data,api)
    prefix,rest=base.split('</header>',1)
    archived,evidence=rest.split('<section class="panel" id="evidence-panel"',1)
    evidence_body,tail=evidence.split('</section>',1)
    indexes,footer=tail.split('<footer',1)
    def cards(items):
        return ''.join(f'<div class="reason"><button type="button" data-case="{api.e(x["case_id"])}">{api.e(x["name"])} · {api.e(x["label"])}</button><p>{api.e(x["reason"])}</p></div>' for x in items) or '<p>本次没有符合此类条件的新事项。</p>'
    rows=''.join(f'<tr><td>{api.e(a["name"])}</td><td>{api.e(a["owner"])}</td><td>{api.e(a["action"])}</td><td>{api.e(a["effective"]["label"])}</td><td>{api.e(a.get("next_check_at") or a.get("due_at") or "节点待核")}</td></tr>' for a in view['actions'])
    baseline=api.e(view['baseline_as_of'] or '无可用基线，本次为首次观察')
    metrics=mr.metrics(data)
    formal=str(len(metrics['formal'])) if metrics['formal'] or data['scope']['orders_complete'] else '待核'
    mean=f'¥{metrics["mean"]:,.0f}' if metrics['mean'] is not None else '待核'
    findings=''.join('<div class="reason"><b>'+api.e(f['claim'])+'</b><p>'+api.e(f['action'])+'</p>'+''.join('<button type="button" data-case="'+api.e(cid)+'">查看 '+api.e(cid)+' 原话</button>' for cid in f['case_ids'])+'<p class="muted">'+api.e(f['limit'])+'</p></div>' for f in data['management']['summary'])
    numbers=f'<section class="panel"><div class="metrics" style="grid-template-columns:repeat(3,minmax(0,1fr))"><div class="metric"><b>{len(metrics["week"])}</b><small>当日有记录的会话</small></div><div class="metric"><b>{metrics["new_confirmed"]}</b><small>确认当日新接客户</small></div><div class="metric"><b>{len(metrics["valid"])}</b><small>当日会话中确定有效</small></div><div class="metric"><b>{len(metrics["trial_paid"])}</b><small>当日确认试听付款</small></div><div class="metric"><b>{formal}</b><small>当日确认正式购买</small></div><div class="metric"><b>{mean}</b><small>当日正式订单均单实收</small></div></div><p class="muted">会话不等于新客；新增归属待核{metrics["new_unknown"]}位。付款日期不明和订单覆盖不足不补成0。这里不计算“当天成交/当天新增”的伪转化率。</p>{findings}</section>'
    panel=f'''<section class="panel" id="daily-priority"><h2>今天先处理什么 · {len(view['priority'])}项</h2><p class="muted">对照截至：{baseline}；本次资料截至：{api.e(view['as_of'])}</p><p><b>数据状态：{api.e(view['source_health'])}</b> · {api.e(view['source_note'])}</p>{cards(view['priority'])}<details><summary>其他需关注事项 · {len(view['other_attention'])}项</summary>{cards(view['other_attention'])}</details><details><summary>新进展和已关闭事项 · {len(view['progress'])}项</summary>{cards(view['progress'])}</details><p class="muted">{api.e(view['note'])}</p></section><section class="panel"><details><summary>全部动作状态 · {len(view['actions'])}项</summary><div class="table-scroll"><table><tr><th>客户</th><th>负责人</th><th>动作</th><th>当前状态</th><th>节点</th></tr>{rows}</table></div></details></section>'''
    quality=quality_and_cohorts.render(quality_and_cohorts.build(data),api)
    return prefix+'</header>'+numbers+panel+quality+'<details class="panel" id="daily-full-analysis"><summary>完整统计 主线图 预警与带教依据</summary>'+archived+'</details><section class="panel" id="evidence-panel"'+evidence_body+'</section><details class="panel"><summary>全部客户索引和当前跟回依据</summary>'+indexes+'</details><footer'+footer
