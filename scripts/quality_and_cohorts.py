"""Comparable observation windows and recorded human reviews, not AI self-scoring."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import copy
import json


def formal_time(case):
    f=case['management']['formal']
    values=[f.get('confirmed_at')]+[o.get('confirmed_at') for o in f['orders']]
    return min((datetime.fromisoformat(x) for x in values if x),default=None) if f['confirmed'] else None


def validate(data,api):
    m=data['management']; cutoff=datetime.fromisoformat(m['cutoff'])
    seen_new=set()
    horizons=m.get('cohort_settings',{}).get('horizons_days',[1,3,7])
    api.require(isinstance(horizons,list) and horizons and all(type(x) is int and x>0 for x in horizons) and len(horizons)==len(set(horizons)), 'cohort.horizons_days','观察窗口须为不重复的正整数天数')
    for c in data['cases']:
        if not c['included'] or 'cohort' not in c['management']:continue
        meta=api.obj(c['management']['cohort'],'cohort')
        api.choice(meta.get('first_contact_basis'),('source_history','confirmed_metadata','unknown'),'cohort.first_contact_basis')
        api.require(meta.get('is_new_customer') is None or type(meta.get('is_new_customer')) is bool,'cohort.is_new_customer','新增身份须true/false/null')
        api.choice(meta.get('outcome_coverage'),('complete','partial','unknown'),'cohort.outcome_coverage')
        if meta['outcome_coverage']=='complete':api.string(meta.get('coverage_source'),'cohort.coverage_source')
        refs=meta.get('first_contact_refs')
        own={x['id']:x for x in c['source_messages']}
        api.require(isinstance(refs,list) and all(isinstance(x,str) for x in refs) and len(refs)==len(set(refs)),'cohort.first_contact_refs','需要不重复引用数组')
        for rid in refs:
            api.require(rid in own and not own[rid].get('sensitive') and bool(own[rid]['text'].strip()),'cohort.first_contact_refs','引用不存在、跨案、敏感或为空')
        if meta['first_contact_basis']=='unknown':
            api.require(meta.get('first_contact_at') is None,'cohort.first_contact_at','真实首触未知不能填成首条可见消息')
        else:
            try:
                started=datetime.fromisoformat(meta['first_contact_at'])
                api.require(started<=cutoff,'cohort.first_contact_at','首触不能晚于资料截止')
                if meta['first_contact_basis']=='source_history':
                    api.require(bool(refs) and started==min(datetime.fromisoformat(own[r]['time']) for r in refs),'cohort.first_contact_at','首触需对应已核实的来源时间，不能凭空提前')
                else:api.string(meta.get('confirmation_source'),'cohort.confirmation_source')
            except (KeyError,ValueError,TypeError):raise api.ValidationError('cohort.first_contact_at：日期或来源无法核对')
        identity=c['validity'].get('assessment',{}).get('identity',{})
        if meta.get('is_new_customer') is True and identity.get('basis')=='source_id':
            key=(identity['account_id'],identity['customer_id'])
            api.require(key not in seen_new,'cohort','同一新客重复进入获客队列，应先核对客户与需求归属')
            seen_new.add(key)
    evaluation=m.get('evaluation')
    if evaluation is None:return
    api.obj(evaluation,'evaluation')
    try:recorded=datetime.fromisoformat(evaluation['recorded_at'])
    except (KeyError,ValueError,TypeError):raise api.ValidationError('evaluation.recorded_at：需要实际复核登记时间')
    reviews=evaluation.get('reviews');api.require(isinstance(reviews,list),'evaluation.reviews','需要实际人工复核数组')
    cases={c['id']:c for c in data['cases'] if c['included']}; seen=set()
    for r in reviews:
        for key in ('id','original_analysis_id','reviewer','confirmation_source','reason','reviewed_at'):
            api.string(r.get(key),'evaluation.'+key)
        api.require(r['id'] not in seen,'evaluation.id','复核编号重复')
        seen.add(r['id'])
        api.require(r.get('case_id') in cases,'evaluation.case_id','复核必须对应本批纳入案例')
        api.choice(r.get('sample_type'),('appeal','spot_check','benchmark'),'evaluation.sample_type')
        api.choice(r.get('kind'),('correction','upheld','insufficient','new_progress','policy_change'),'evaluation.kind')
        api.choice(r.get('target'),('validity','sales_judgment','expression','followup','evidence','fact'),'evaluation.target')
        api.require('ai_value' in r and 'human_value' in r,'evaluation.values','须保留原AI与人工结果；未知用null')
        if r['target']=='validity':
            api.choice(r['ai_value'],api.VALIDITY,'evaluation.ai_value')
            if r['human_value'] is not None:api.choice(r['human_value'],api.VALIDITY,'evaluation.human_value')
        api.require(r['kind']!='insufficient' or r['human_value'] is None,'evaluation','证据不足不能冒充确定人工答案')
        equal=json.dumps(r['ai_value'],sort_keys=True)==json.dumps(r['human_value'],sort_keys=True)
        if r['kind'] in ('correction','upheld'):
            api.require(r['human_value'] is not None,'evaluation','更正或维持原判须有确定人工结论')
            api.require(equal==(r['kind']=='upheld'),'evaluation','维持/更正类型须与原AI和人工值一致')
        try:api.require(datetime.fromisoformat(r['reviewed_at'])<=recorded,'evaluation.reviewed_at','不能预填未来复核')
        except (ValueError,TypeError):raise api.ValidationError('evaluation.reviewed_at：日期无法比较')
        refs=r.get('refs');own={x['id']:x for x in cases[r['case_id']]['source_messages']}
        api.require(isinstance(refs,list) and refs and all(isinstance(x,str) for x in refs) and len(refs)==len(set(refs)),'evaluation.refs','复核须有本案非重复引用')
        for ref in refs:
            api.require(ref in own and not own[ref].get('sensitive') and bool(own[ref]['text'].strip()),'evaluation.refs','复核引用不存在、跨案或敏感/为空')
            try:api.require(datetime.fromisoformat(own[ref]['time'])<=datetime.fromisoformat(r['reviewed_at']),'evaluation.refs','不能用复核之后的消息证明此前的人工裁决')
            except (TypeError,ValueError):raise api.ValidationError('evaluation.refs：复核与消息时区无法比较')


def build(data):
    m=data['management']; cutoff=datetime.fromisoformat(m['cutoff'])
    horizons=sorted(m.get('cohort_settings',{}).get('horizons_days',[1,3,7]))
    groups=defaultdict(list); ungrouped=Counter()
    for c in data['cases']:
        if not c['included']:continue
        cm=c['management'];meta=cm.get('cohort');policy=c['validity'].get('assessment',{}).get('policy_version','unknown')
        if c['validity']['status'] not in ('high','effective'):
            ungrouped['有效性未确定或无效']+=1;continue
        if c['validity'].get('assessment',{}).get('identity',{}).get('basis')!='source_id':
            ungrouped['稳定客户身份待核 不给精确转化率']+=1;continue
        acquired=None
        if meta and meta.get('is_new_customer') is True and meta.get('first_contact_at'):
            acquired=datetime.fromisoformat(meta['first_contact_at'])
            groups[('new_effective',acquired.date().isoformat(),policy)].append((c,acquired,meta))
        else:ungrouped['新增身份或真实首触待核']+=1
        t=cm['trial']
        if t['completed'] and t['ended_from'] and t['ended_from']==t['ended_to']:
            end=datetime.fromisoformat(t['ended_to']); purchased=formal_time(c)
            if purchased and purchased<end:
                ungrouped['完课前已正式购买 单列']+=1
            else:groups[('completed_trial',end.date().isoformat(),policy)].append((c,end,meta or {}))
        elif t['completed']:ungrouped['完课具体时间待核 不造精确转正窗口']+=1
    rows=[]
    for (kind,date,policy),members in sorted(groups.items()):
        for days in horizons:
            mature=[];converted=0;unknown=0
            for c,started,meta in members:
                end=started+timedelta(days=days)
                if cutoff<end:continue
                mature.append(c['id']);paid=formal_time(c)
                if paid is not None and started<=paid<=end:converted+=1
                elif c['management']['formal']['confirmed'] and paid is None:unknown+=1
                elif paid is not None and paid<started:unknown+=1
                elif meta.get('outcome_coverage')!='complete':unknown+=1
            rows.append({'kind':kind,'contact_or_completion_date':date,'policy_version':policy,'horizon_days':days,
                         'cohort_size':len(members),'mature_count':len(mature),'not_yet_mature':len(members)-len(mature),
                         'confirmed_within_window':converted,'outcome_unknown':unknown,
                         'rate':converted/len(mature) if mature and unknown==0 else None,'mature_case_ids':mature})
    reviews=m.get('evaluation',{}).get('reviews',[]); evals=[]
    for sample in ('appeal','spot_check','benchmark'):
        items=[r for r in reviews if r['sample_type']==sample]
        if not items:continue
        decidable=[r for r in items if r['kind'] in ('upheld','correction') and r['human_value'] is not None]
        agree=sum(json.dumps(r['ai_value'],sort_keys=True)==json.dumps(r['human_value'],sort_keys=True) for r in decidable)
        invalid=[r for r in decidable if r['target']=='validity' and r['ai_value']=='invalid']
        wrong_invalid=sum(r['human_value'] in ('high','effective') for r in invalid)
        evals.append({'sample_type':sample,'review_items':len(items),'unique_cases':len({r['case_id'] for r in items}),
                      'decidable_items':len(decidable),'agreed_items':agree,'agreement_on_reviewed_items':agree/len(decidable) if decidable else None,
                      'insufficient_items':sum(r['kind']=='insufficient' for r in items),'reviewed_ai_invalid':len(invalid),'corrected_invalid_to_effective':wrong_invalid,
                      'limit':'仅描述此来源已复核项目；申诉、抽查与基准样本分开，不外推整体准确率。'})
    return {'version':'skill3-quality-cohorts/1','as_of':m['cutoff'],'cohorts':rows,'ungrouped_reasons':dict(ungrouped),
            'human_review':evals,'review_records':copy.deepcopy(reviews),
            'review_status':'已登记人工复核记录；登记字段不等于程序认证人员或结论' if reviews else '尚无实际人工复核记录，不生成准确率',
            'note':'按同一接入/完课日及相同经过时长观察；未成熟、缺日期和订单覆盖不全分别列出，不将今天成交除以今天新客。比例变化不证明AI带来因果改善。'}


def render(result,api):
    items=[]
    for x in result['cohorts']:
        rate=f'{x["rate"]:.1%}' if x['rate'] is not None else '待核或未成熟'
        items.append(f'<tr><td>{api.e("新增有效客户" if x["kind"]=="new_effective" else "完课后待转正客户")}<small>{api.e(x["contact_or_completion_date"])}</small></td><td>{x["horizon_days"]}天</td><td>{x["mature_count"]}/{x["cohort_size"]}</td><td>{x["confirmed_within_window"]}</td><td>{x["outcome_unknown"]}</td><td>{rate}</td></tr>')
    rows=''.join(items)
    reviews=''.join(f'<p>{api.e(x["sample_type"])}：复核{x["review_items"]}项，可判{x["decidable_items"]}项，一致{x["agreed_items"]}项；AI判无效的复核项{x["reviewed_ai_invalid"]}，更正为有效{x["corrected_invalid_to_effective"]}。{api.e(x["limit"])}</p>' for x in result['human_review'])
    return f'<section class="panel" id="quality-cohorts"><details><summary>同批客户的成熟期表现与人工复核</summary><p>{api.e(result["note"])}</p><div class="table-scroll"><table><tr><th>客户批次</th><th>观察窗</th><th>已成熟/批次</th><th>窗内正式购买</th><th>结果待核</th><th>成熟部分观察率</th></tr>{rows}</table></div><p>未纳入精确窗口：{api.e(result["ungrouped_reasons"])}</p><p>{api.e(result["review_status"])}</p>{reviews}</details></section>'
