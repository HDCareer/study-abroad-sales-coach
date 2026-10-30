"""Lifecycle contracts and period counts; semantic decisions remain with the Skill."""
from collections import Counter
from datetime import datetime
import json
import review_integrity as integrity

CONTEXTS = {'initial':'首次评定', 'continuing':'连续跟进', 'returning':'断联后回流',
            'post_purchase':'成交后沟通', 'unknown':'续接关系待核'}
EVENTS = {'contact_returned':'恢复联系', 'demand_resumed':'原需求恢复', 'new_demand':'新需求',
          'customer_question':'客户有待回应的问题', 'correction':'历史补证或纠错'}


def info(case):
    return case.get('management', {}).get('lifecycle') or case.get('lifecycle')


def sales_applicable(case):
    meta = info(case)
    return meta is None or meta['sales_applicable'] is True


def customer_key(case):
    meta = info(case)
    if meta and meta.get('customer_key'):
        return ('company', meta['customer_key'])
    identity = case.get('identity') or case.get('validity', {}).get('assessment', {}).get('identity', {})
    if identity.get('basis') == 'source_id' and identity.get('account_id') and identity.get('customer_id'):
        return ('account', identity['account_id'], identity['customer_id'])
    return None


def period_customer_count(cases):
    # Unknown identities are not silently merged; exact totals are provided separately.
    return len({customer_key(c) or ('unmatched', c.get('id', c.get('case_id'))) for c in cases})


def validate(data, api):
    m = data['management']
    strict = 'lifecycle_version' in m
    if strict: api.require(m['lifecycle_version'] == '1.0', 'lifecycle_version', '只支持1.0')
    start, end, cutoff = (datetime.fromisoformat(m[k]) for k in ('week_start','week_end','cutoff'))
    identities, demands = {}, set()
    for c in data['cases']:
        if not c['included']: continue
        x = info(c); p = c['id'] + '.lifecycle'
        api.require(not strict or x is not None, p, '新连续管理模式须逐案提供lifecycle；旧输入仍兼容')
        if x is None: continue
        api.require(x.get('version') == '1.0', p, '只支持1.0')
        api.choice(x.get('context'), CONTEXTS, p+'.context')
        api.choice(x.get('communication'), ('sales','service','social','mixed','unknown'), p+'.communication')
        api.choice(x.get('demand_relation'), ('initial','same','new','none','unknown'), p+'.demand_relation')
        api.choice(x.get('purchase_kind'), ('first','repeat','none','unknown'), p+'.purchase_kind')
        api.choice(x.get('opportunity_status'), ('open','waiting','dormant','won','closed','none','unknown'), p+'.opportunity_status')
        api.require(type(x.get('sales_applicable')) is bool or x.get('sales_applicable') is None, p, 'sales_applicable须true/false/null')
        api.string(x.get('reason'), p+'.reason')
        for key in ('customer_key','first_added_at','first_added_source'):
            api.require(key in x, p, key+'未知须显式null')
        if x['customer_key'] is not None: api.string(x['customer_key'], p+'.customer_key')
        own = {v['id']:v for v in c['source_messages']}
        def refs(values, at=None):
            api.require(isinstance(values,list) and values and all(isinstance(v,str) for v in values) and len(values)==len(set(values)), p+'.refs', '需不重复的本案证据')
            for rid in values:
                api.require(rid in own and not own[rid].get('sensitive') and bool(own[rid]['text'].strip()), p+'.refs', '引用不存在、跨案或敏感/空白')
                try: api.require(datetime.fromisoformat(own[rid]['time']) <= (at or cutoff), p+'.refs', '证据晚于所证明事件')
                except (TypeError,ValueError): raise api.ValidationError(p+'：证据时钟无法比较')
        refs(x.get('refs'))
        try:
            added = datetime.fromisoformat(x['first_added_at']) if x['first_added_at'] else None
            api.require(added is None or added <= cutoff, p+'.first_added_at', '首次添加不能在未来')
        except (TypeError,ValueError): raise api.ValidationError(p+'：首次添加日期无法比较')
        if added:
            api.string(x['first_added_source'],p+'.first_added_source')
        else: api.require(x['first_added_source'] is None, p, '未知首次添加时间不冒充已核实')
        new = c['management']['week']['new_customer']
        if added and x['customer_key']:
            api.require(new == (start <= added <= end), p, '新增标记须按固定公司首次添加时间，不能按今天是否聊天')
        else: api.require(new is None, p, '公司身份/首次添加待核时不能猜新增或非新增')
        if x['context']=='initial': api.require(added is None or start<=added<=end, p, '已过首次添加日应使用连续/回流等场景')
        if x['context'] in ('returning','post_purchase'):
            api.require(new is not True,p,'回流/已购客户不是当天新接客户')
        if x['customer_key']:
            signature=(x['first_added_at'],x['first_added_source'])
            api.require(x['customer_key'] not in identities or identities[x['customer_key']]==signature,p,'同一公司客户首次添加依据冲突')
            identities[x['customer_key']]=signature
        oid=c['management'].get('tracking',{}).get('opportunity_id')
        if customer_key(c) and oid:
            key=customer_key(c)+(oid,)
            api.require(key not in demands,p,'同一客户同一需求在本批重复，先归并')
            demands.add(key)
        if x['demand_relation'] in ('initial','same','new') and x['sales_applicable'] is True:
            api.string(oid,p+'.opportunity_id')
        if x['communication'] in ('service','social'):
            api.require(x['sales_applicable'] is False,p,'纯服务/闲聊不能进入当期销售分母；有销售内容用mixed')
        if x['communication']=='sales': api.require(x['sales_applicable'] is True,p,'销售咨询须纳入销售适用判断')
        if c['validity']['status']=='not_applicable':
            api.require(x['sales_applicable'] is False,p,'不适用只用于本次无销售需求，不增加无效原因')
            api.require('assessment' not in c['validity'],p,'不适用不伪造六项有效性判断')
        if x['sales_applicable'] is not True:
            api.require(not c['management']['must_follow']['needed'],p,'非销售/用途待核不能列为必须追单')
            api.require(c['management']['issue']['kind']!='gap',p,'非销售沟通不能记咨询流程缺口')
            for layer in ('judgment','expression','execution'):
                if 'layers' in c['management']:
                    api.require(c['management']['layers'][layer]['status'] in ('not_applicable','unknown'),p,'非销售沟通不进入销售能力评价')
            api.require(not c['management'].get('tracking',{}).get('events'),p,'非销售沟通不能新增销售带教观察')
            for action in c['management'].get('actions',[]):
                api.require(action['kind'] not in ('sales_followup','trial_conversion') or action['status'] in ('resolved','cancelled'),p,'非销售沟通的追单须有实际终结依据；未决追单应标mixed')
        if x['opportunity_status']=='won': api.require(c['management']['formal']['confirmed'],p,'需求成交须有本需求正式购买依据')
        if c['management']['formal']['confirmed']:
            api.require(x['opportunity_status'] in ('won','none'),p,'本需求成交不能同时记未成交；复购另立需求')
        if x['opportunity_status']=='none':
            api.require(x['sales_applicable'] is not True,p,'仍有销售咨询需求时不能标无需求来关闭预警')
        if c['management']['trial']['completed'] and not c['management']['formal']['confirmed'] and x['opportunity_status']!='closed':
            api.require(x['sales_applicable'] is True and x['opportunity_status'] not in ('none','dormant'),
                        p,'已完课未转正须保留销售预警；明确终结须使用closed并提供依据')
        if x['opportunity_status'] in ('dormant','closed'):
            api.require(not c['management']['must_follow']['needed'],p,'未落实追单不能靠暂存或结束隐藏')
            for a in c['management'].get('actions',[]):
                api.require(a['kind'] not in ('sales_followup','trial_conversion') or a['status'] in ('resolved','cancelled'),p,'暂存/结束前须处理活跃销售动作')
            if x['opportunity_status']=='dormant':
                api.require(not c['management']['trial']['completed'] or c['management']['formal']['confirmed'],p,'已完课未转正风险不能仅靠暂存隐藏；明确结束另记录依据')
        events=x.get('events');api.require(isinstance(events,list),p+'.events','需要事件数组，无事件为空')
        seen=set()
        for event in events:
            eid=api.string(event.get('id'),p+'.event.id')
            api.require(eid not in seen,p,'事件编号重复');seen.add(eid)
            api.choice(event.get('kind'),EVENTS,p+'.event.kind')
            api.string(event.get('reason'),p+'.event.reason')
            try:
                at=datetime.fromisoformat(event['at']);api.require(at<=cutoff,p,'事件不能晚于资料截止')
            except (KeyError,TypeError,ValueError): raise api.ValidationError(p+'：事件时间无法比较')
            refs(event.get('refs'),at)
            if event['kind']=='correction':api.string(event.get('confirmation_source'),p+'.event.confirmation_source')
            else:
                api.require(any(own[r].get('source_role')=='customer' and not own[r].get('is_system_greeting') and datetime.fromisoformat(own[r]['time'])==at for r in event['refs']),p,'客户事件须锚定发生时的真实客户消息，不能用导入日或销售群发代替')
            if event['kind'] in ('new_demand','demand_resumed'):
                api.require(x['sales_applicable'] is True and bool(oid),p,'需求事件须对应可辨识销售需求')
                if start<=at<=end:
                    api.require(x['demand_relation']==('new' if event['kind']=='new_demand' else 'same'),p,'新需求和原需求恢复不能混用')


def compare(current, old, api, baseline_id=None, baseline_at=None):
    integrity.compare(current, old, api, baseline_id, baseline_at)
    x,y=info(current),info(old)
    if not x or not y:return
    if y['customer_key'] and x['customer_key']:
        api.require(x['customer_key']==y['customer_key'],'lifecycle.history','不能把其他客户当历史')
    prior={e['id']:e for e in y['events']}
    for e in x['events']:
        if e['id'] in prior:
            old_event=prior[e['id']]
            enriched=e.get('kind')=='customer_question' and 'action_ids' not in old_event and {k:v for k,v in e.items() if k!='action_ids'}==old_event
            api.require(e==old_event or enriched,'lifecycle.event','同一事件不可改写；纠错另记事件并保留原判断')
        elif e['kind']=='demand_resumed':
            api.require(y['opportunity_status'] in ('dormant','closed'),'lifecycle.event','原需求恢复须有此前暂存/结束状态；连续对话不刷激活')


def baselines(data, api, reports, identity):
    """Select newest provided snapshot per demand, never manufacture a history."""
    prior, times, ids = {}, {}, {}
    m=data['management']
    for report in reports:
        api.require(report.get('schema_version')=='skill3-management-results/1.0','history-results','需要统一管理结果')
        api.require(report.get('sales',{}).get('id')==data['sales']['id'],'history-results','不能混入其他销售基线；转接须先核实上游归属')
        window=api.obj(report.get('reporting_window'),'history-results.reporting_window')
        api.require(window.get('time_basis')==m['time_basis'],'history-results','时间口径不同')
        try:
            at=datetime.fromisoformat(window['cutoff'])
            api.require(at<=datetime.fromisoformat(m['cutoff']),'history-results','不能使用未来基线')
        except (KeyError,TypeError,ValueError):raise api.ValidationError('history-results：基线时间无法比较')
        aid=api.string(report.get('analysis_id'),'history-results.analysis_id')
        api.require(isinstance(report.get('cases'),list),'history-results.cases','需要案例数组')
        seen=set()
        for case in report['cases']:
            if not case.get('included'):continue
            key=identity(case)
            if not key:continue
            api.require(key not in seen,'history-results','同客户多需求未分清，先处理重复')
            seen.add(key)
            if key in prior and times[key]==at:
                api.require(json.dumps(prior[key],sort_keys=True)==json.dumps(case,sort_keys=True),'history-results','同一时点存在冲突版本；仅提供已确认有效的修正版')
            if key not in prior or at>times[key]:prior[key]=case;times[key]=at;ids[key]=aid
    return prior,times,ids


def summary(data):
    if not any(info(c) for c in data['cases'] if c['included']):return None
    m=data['management'];start,end=(datetime.fromisoformat(m[k]) for k in ('week_start','week_end'))
    cases=[c for c in data['cases'] if c['included'] and c['management']['week']['included']]
    unknown=[c['id'] for c in cases if not info(c) or not info(c).get('customer_key')]
    known=[c for c in cases if info(c) and info(c).get('customer_key')]
    valid=[c for c in known if integrity.period_sales_scope(c,m) is True and c['management']['week']['validity']['status'] in ('high','effective')]
    new=[c for c in data['cases'] if c['included'] and info(c) and info(c).get('customer_key') and c['management']['week']['new_customer'] is True]
    seen=set();counts=Counter()
    for c in data['cases']:
        if not c['included']:continue
        for e in (info(c) or {}).get('events',[]):
            key=(customer_key(c),c['management'].get('tracking',{}).get('opportunity_id'),e['id'])
            if key not in seen and start<=datetime.fromisoformat(e['at'])<=end:counts[e['kind']]+=1;seen.add(key)
    return {'version':'skill3-lifecycle/1','known_active_customers':period_customer_count(known),
            'new_customers':period_customer_count(new),'active_effective_customers':period_customer_count(valid),
            'sales_cases':sum(integrity.period_sales_scope(c,m) is True for c in cases),
            'non_sales_cases':sum(integrity.period_sales_scope(c,m) is False for c in cases),
            'scope_unknown_cases':sum(integrity.period_sales_scope(c,m) is None for c in cases),
            'new_status_unknown_case_ids':[c['id'] for c in cases if c['management']['week']['new_customer'] is None],
            'identity_unknown_case_ids':unknown,'event_counts':dict(counts),
            'note':'客户、需求及事件分别计数；当日活跃人数不能逐日相加作累计客户。仅在本次输入范围内汇总，不代表公司完整存量。'}


def detail(case, api):
    x=info(case)
    if x is None:return ''
    scope={True:'销售咨询',False:'本次不进入销售流量与咨询质量统计',None:'沟通用途待核'}[x['sales_applicable']]
    text=f'{CONTEXTS[x["context"]]} · {scope}；首次添加：{x["first_added_at"] or "待核"}；需求：{case["management"].get("tracking",{}).get("opportunity_id") or "未建立/待核"}；状态：{x["opportunity_status"]}'
    events=''.join('<p>'+api.e(EVENTS[e['kind']]+' · '+e['at']+' · '+e['reason'])+'</p>'+''.join(api.quote(case,r) for r in e['refs']) for e in x['events'])
    return '<div class="reason"><b>'+api.e(text)+'</b><p>'+api.e(x['reason'])+'</p></div><details><summary>本案连续事件及依据</summary>'+events+'</details>'
