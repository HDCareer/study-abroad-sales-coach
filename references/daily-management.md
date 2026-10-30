# Daily管理：变化、动作与可比结果

0.7.34公司Daily按[分析追溯与完整交付](analysis-trace-and-delivery.md)生成不可变交付目录，上期基线读取该目录results.json；本页原两文件命令仍兼容，不作为完整交付检查通过。模型资料覆盖与业务判断正确分别说明。

本页是Daily模式及其数据扩展的唯一运行规则。它延续[管理首页](chat-review-management.md)、[两层带教](chat-review-coaching.md)、[申诉复核](appeals-and-review.md)和[连续观察](longitudinal-review.md)，不改变有效流量定义、固定STEP或本机构已确认的预警时限。实时带单仍由销售决定实际发送。

## 最佳使用节奏与首页

四类客户场景、需求关联及销售统计适用性统一按[客户连续管理](customer-lifecycle.md)。新公司批次填写lifecycle_version、reliability_version与逐案lifecycle、week.sales_scope；本次服务/闲聊不作销售能力评价，但不能删除过去销售期间或固定入组资格。历史保护、任务变更与问题核销统一按[可靠性合同](review-integrity.md)。跨日同客活跃不等于新增，历史结论与本次新增分析分别展示。

公司持续使用时默认按销售每天生成Daily；用户明确要周报或指定期间时按要求生成。每天覆盖应检查的在途客户，分析读取新增消息和有关历史；不能只读最后一句，也不要求无变化旧案每天全文重做。到期、升级、补证与已批准规则变化同样会触发复查，无新消息不等于不用检查时间节点。本地工具仅在运行时出快照，定时导入与触发由数据部门安排。

Daily首页依次给：本日确认数量和数据状态；今天先处理的客户；新进展及已关闭事项；折叠的全部动作状态、同批成熟期及人工复核、完整统计/阶段图/两层证据、全部客户索引和必须跟回。当前仍需跟回的完整名单继续保留，不能因为首页去重而删除。首页优先事项按客户合卡，保留卡内多项原因；最多优先显示5位，其余需关注事项折叠可见，不能截断后丢弃。主管展开任一客户都应能直接看到对应原话、时间、行号和判断链。

置顶条件：新出现的关键阻碍/真实推进承诺；需主管介入；客户等级、付款、完课、正式购买或阶段变化；已到动作/回访/复查节点；进入或升级试听预警。普通寒暄、重复导入及未改变决定的信息不造“新问题”。已执行且尚在约定等待期不记未跟进；已知晓旧问题按约定节点再提示；未确认落实的持续逾期仍保留为原待办，不每天新增一次失误。

首触日、当日会话、当日付款是不同数。首次观察不等于新增客户；当天正式购买人数不能除以当天新接人数作为销售转化率。订单不全、日期不明、身份未核各自列待核，不补0。所有时钟只推进到本次声明的资料截止，不拿系统时间假定客户导出后仍未付款。

## Daily输入与基线

有已确认公司customer_key时优先使用该键+需求ID。昨日未出现的回流客户可重复传`--history-results`读取相关获准旧统一结果，逐案选择最新基线并展示来源。历史参数只提供对照，模型分析前也须读对应旧事实和实际动作，不是生成器替代语义理解。新扩展字段、计数及兼容见客户连续管理；下方来源账号匹配是旧数据兼容路径，不能冒充公司跨账号去重。

沿用原分析结构；新增分析默认填写 `management.cadence:"daily"`。旧数据不带cadence仍按历史weekly兼容；另支持weekly/period。为了兼容，`management.week_start/week_end`、每案`management.week`及JSON的`week_*`名称保留，Daily时它们表示**本日统计范围和当日快照**。Daily起止必须属于同一来源日期；`cutoff`是最新资料时点，可与统计期末不同，不倒填期末事实。只有相关原消息在当日，才将该案纳入当日会话；无新消息但到期的旧案仍保留在当前案例集合。

`management.daily`必需：

| 字段 | 含义 |
| --- | --- |
| source_health | complete/partial/delayed，描述本批声明覆盖状态，程序不认证平台完整性 |
| source_note | 具体覆盖、延迟/缺失及受影响结论 |
| priority_limit | 可选整数1至50，默认5；不改变应处理事项总数 |

有获准保留的上期统一结果时传`--previous-results`，以来源账号+来源客户ID+已知稳定需求ID续接；不按昵称、当批case编号猜。多需求未分清则停止自动匹配；没有稳定身份仍可单批分析，但不称成功续接。基线必须为同一销售、相同时间口径、资料截止不晚于本期；同一时点的修正版要保留更正来源，不能说成新进展。`analysis_id`同时包含基线编号，HTML和JSON共用结果。

上一结果仍含客户证据，使用前须确认原始保留起算和期限。Daily对照器不自动认证留存授权；到期结果不能再传入，不通过重导出或刷新编号续期。较长期趋势用已有可配置快照流程；授权未明确前不改变原获准保留期限。纯汇总、可关联摘要和完整聊天的保存范围不能混用。

```text
python scripts/render_chat_review.py <本期分析.json> --previous-results <上期统一结果.json> --output <日报.html> --results-output <本期统一结果.json> --source <本期独立导入.json>
```

首次无历史省略previous-results。source仅在有独立导入源时提供；不从分析稿反造独立源。check-only不写文件。新产物放授权私有目录，原基线不得被结果输出覆盖。

## 动作状态，不能把建议当作执行

每案`management.actions`为数组。动作ID和`issue_key`跨批沿用；同一问题改写描述不新建任务。没有真实执行记录就保持建议，不能为了关闭提醒而标成完成。下一次输入应带回仍有关的动作及实际新状态；本地生成器不是任务数据库，不自行记忆、持久化更新或通知销售。

| 字段 | 规则 |
| --- | --- |
| id、issue_key | 稳定动作编号、所针对问题编号 |
| kind | sales_followup/trial_conversion/manager_decision/service/verify |
| owner、action | 实际执行人、具体要完成的动作 |
| status | proposed建议待安排；assigned已确认待执行；executed_waiting_customer已执行等客户；blocked_internal内部协作受阻；resolved已解决；cancelled已不适用 |
| priority | 1/2/3，1优先 |
| updated_at | 实际状态登记所依据的时点，不晚于资料截止 |
| due_at、next_check_at、acknowledged_at、escalate_at | 执行截止、下次回访/复查、主管确认知晓、约定升级节点；未知显式null，不编时限 |
| refs | 本案非敏感原消息ID；引用时间不能晚于所证明的状态 |
| confirmation_source | assigned/blocked_internal必填，记录实际安排/协作确认来源 |
| resolution | resolved/cancelled必填，另有原话或实际确认来源 |

executed_waiting_customer必须有**实际销售发出的动作**的引用，AI草稿、仅客户发言不能证明。具体动作是否完成原建议的目的仍须Skill结合语义判断，角色校验不是充分证明。合理等待没有下一节点时列节点待核，不自行认定逾期。回访/复查已到或升级未落实时持续保留原短待办，不因昨日已经出现便消失；必须跟回而无执行状态也提示落实，不每天增加新失误数。主管确认知晓后须有真实复查节点才暂缓旧逾期提示，不能仅凭点“知道了”永久隐藏。任何活跃状态到明确升级节点均需提醒，包括等客户；确认时间须在该升级节点之后，才可按新的约定复查暂缓。已解决/不适用保留处理原因和历史，不当新问题。

首次正式购买后，未终结的首次追单/试听转正动作派生为`closed_by_purchase`，保留原任务状态作为历史；服务、退款及内部协作不自动关闭。普通拒绝仍可合理推进；明确拒收联系后不保留活跃推销动作，必要服务任务另列。

可选`management.daily_signals`为`{id,kind,reason,refs}`数组：kind为new_blocker/customer_commitment/manager_needed/evidence_correction。信号ID稳定；非纠错的新信号相对上期须有截止之后的新证据，不能以改编号复用旧消息。evidence_correction须有confirmation_source，单列更正，不说成客户新发生的事实。重要性由Skill读上下文判断，程序不做关键词命中。

## 同批客户、相同成熟期

目的：辨认销售承接和转正表现，不把今天刚接、尚无合理成交时间的客户算成失败。`management.cohort_settings.horizons_days`为观察窗正整数数组，默认[1,3,7]天；这是比较时长，不替代本机构已确认时限的业务预警，也不意味着过窗自动放弃。

每案可选`management.cohort`：

| 字段 | 含义 |
| --- | --- |
| first_contact_basis | source_history已核来源历史；confirmed_metadata已确认源元数据；unknown |
| first_contact_at | 实际首次接入时刻；未知null，不以首条可见代替 |
| first_contact_refs | 来源历史依据；source_history须有匹配时刻引用 |
| is_new_customer | 真实新客true/false/null；稳定同一客户不能重复当两个新客 |
| confirmation_source | confirmed_metadata必填，记录核实来源 |
| outcome_coverage | complete/partial/unknown，针对本需求正式购买结果截至本批cutoff是否核齐 |
| coverage_source | complete必填；聊天完整不能自动证明订单完整 |

仅稳定客户身份且具有固定入组快照cohort.entry的客户进入精确比较，按真实首触日及入组规则版本分组；公司新格式有cohort就必须提供entry或显式null。entry的at、validity、purchase_kind、policy_version、reason、refs及迁移规则见[可靠性合同](review-integrity.md)。当前成交、失联、闲聊或等级变化不重建原资格；优质覆盖基础，只算一位。缺快照不推精确率。完课后转正另按已确认的准确完课日建立队列；只有时间区间时继续做保守预警，但不制造精确成熟期。已在完课前正式购买单列。多项独立需求须有稳定标识及不同的真实完课事件，重复导入同一完课事件不作为新样本。

每窗分别列：批次人数、已成熟、未成熟、窗内已确认购买、结果待核、可计算的观察率。只有已走完整个观察窗才进入成熟分母；窗内已确认购买可计确定正结果；未见购买且订单覆盖不全、购买日期未知等留待核。已成熟但仍有结果待核时不生成单一精确率；零分母显示未成熟/待核。首触前已购买者不当新获客转化。比较同销售前后或不同销售时须核对规则、观察时长、订单覆盖、需求组合与样本数量；不能把不同批次表面高低说成能力因果，更不能单凭此给淘汰结论。

## 真实人工复核与质量验证

维持用户确定的先投入使用、AI先判断、开放申诉后人工复核路线；不要求上线前逐案人工对照。申诉能找错，但不能估计所有未申诉结果的质量。试用时建议主管另主动抽查部分AI判有效、无效和待核的案例，特别核看误判无效导致的漏跟；抽查是管理质量建议，不新增上线审批门槛。

`management.evaluation:{recorded_at,reviews}`可登记实际复核。每项须有：`id,original_analysis_id,case_id,reviewer,confirmation_source,reason,reviewed_at,sample_type,kind,target,ai_value,human_value,refs`。样本来源sample_type为appeal/spot_check/benchmark；kind为correction/upheld/insufficient/new_progress/policy_change；target为validity/sales_judgment/expression/followup/evidence/fact。原结果及人工结果保留原字段值，不能以解释改写伪装一致；证据不足human_value=null，维持须与原值一致，更正须不同。按人工真实确认登记，不让AI自填为人工结论。

复核时间可晚于原聊天资料截止，不能被误改成客户消息日期；但不能晚于实际登记时点。refs指本案证据，新增补证应先归入正确来源；original_analysis_id指被复核的实际原版本而非修正版。程序校验字段和本案引用，不能认证复核人身份、确认来源真实性或原分析编号真实性，须由现有人工复核流程核验。

申诉、主动抽查、事先冻结的基准样本分别报告复核项数、可判断项、一致项、证据不足及AI判无效被更正有效的项目数；同一客户可有多个判断项目，项数和客户数分列。新增进展/规则变化不计原判断错误。当前工具保留逐项登记和引用便于追溯，不把“几次申诉改了几次”外推全量准确率。不无依据填写目标准确率、置信度或宣称通过；无真实人工记录直接写尚无实际复核，不生成准确率。

每次规则修改后，先用已确认边界例和反例检查原有规则是否退步，再在冻结版本的真实记录上观察：有效性误判/待核、问题定位是否获复核支持、提醒是否真有行动价值、建议是否执行、主管核查与销售改写成本。用于修改的案例不能同时当作独立验证；合成检查只证明特定结构和边界逻辑，不能证明销售判断能力、转化提升或训练效果。同类标准更新继续按申诉复核规则由负责人确认，再版本化更改。

## 交付和实现边界

同一分析生成Daily HTML和统一JSON：`cadence`、`daily`、`quality_and_cohorts`；每案保留actions/daily_signals/cohort。JSON含动作派生状态、去重变化和全部需关注事项，以及分组统计和逐项复核记录。原证据按已有授权引用输出，不新增第二次AI分析。

这三项是本地Skill及生成器能力；公司API接入、定时任务、状态回传存储、权限、看板和提醒投递由数据部门实现。它们接入前不能宣称已形成后台自动监控。日报是管理入口，完整证据和周期复盘按需展开，长期带教观察继续使用独立快照，不每天把整份历史报告推给主管。

## 公开版所需配置

预警使用management.alert_thresholds_hours，未设只显示时长与阈值待设；Daily、报告和统一结果共用相同配置。有效性、授课条件、目标与留存须先私下提供本机构规则，不沿用作者机构默认值。观察窗是分析时长，不是资料保存授权。
