# 历史事实、期间统计与动作核销｜0.7.33

本页是六组修复的运行合同，叠加[客户连续管理](customer-lifecycle.md)、[Daily](daily-management.md)和[基础数据合同](chat-review-data.md)。不修改流量有效性定义、授课语言要求、优质覆盖基础或本机构已确认的预警时限。数据部门保存和传入状态，Skill依据实际材料判断，程序校验结构与前后关系。

## 公司新分析入口与兼容

公司新分析明确设置`management.reliability_version:"1.0"`和`management.lifecycle_version:"1.0"`；每个纳入案例均有lifecycle和下方week.sales_scope。当前销售适用为true时必须提供validity.assessment逐项证据，不能只交一个有效标签。非销售案继续按已有不适用规则处理。

旧文件不含reliability_version仍能读取，但不因此通过公司新分析验收。出现历史保护需要前后比较时，必须通过Daily命令传入实际相关统一结果；只有本期切片无法证明昨日状态未被覆盖。没有匹配基线标no_available_baseline，不声称已核对连续性。当前生成器的previous/history参数用于Daily，Weekly/period的期间快照同样生效，但不支持以这些参数执行历史状态比较。

## 1. 已确认事实与具体纠错

匹配历史后，已确认的trial.paid、trial.completed、formal.confirmed及已知付款/完课/正式确认时间不能被省略、改成false/null或换日重置。固定首次添加日期及来源同样保护。未见完课记录统计未完成的规则，只适用于授权可用记录中从未确认完课的情况；不能将昨日已确认的事实当作今天没有。

原判断确实错误时，新增correction事件，保留实际确认来源、原因和引用，并增加：

```json
{
  "id": "CORRECTION-稳定编号",
  "kind": "correction",
  "at": "2026-10-21 10:00:00",
  "reason": "纯合成示意：复核发现原完课记录误读",
  "refs": ["本案实际证据ID"],
  "confirmation_source": "实际授权复核记录位置",
  "baseline_analysis_id": "本次实际采用的旧analysis_id",
  "changes": [
    {"field": "trial.completed", "before": true, "after": false},
    {"field": "trial.ended_from", "before": "2026-10-20 09:05:00", "after": null},
    {"field": "trial.ended_to", "before": "2026-10-20 09:05:00", "after": null}
  ]
}
```

这是字段示意，不能原样伪填。每个改动都须与真实前后值对应；事件必须是相对基线新增、发生不早于该基线截止，且引用不晚于纠错时刻。旧纠错、错基线或其他字段的纠错没有全局豁免效力。原格式不含changes的历史纠错仍可保留说明，不能据此改写受保护事实。有效等级正常变化须有对应真实上一状态/时点的assessment.transition，个案裁决也可用定向纠错。

已完课且未转正仍需保留风险时钟。不能用none、dormant或闲聊标签消除预警；明确结束用closed并提供真实依据、终结销售动作。正式购买可关闭本需求的销售追单，服务任务另列。程序不认证复核人的权限或来源真伪，也不证明订单账本已完整实现。

## 2. 聊天、成交和到账各按自己的日期

- 本期活跃：由本期是否发生消息确定。
- 本期新增：按已确认公司首次添加日期去重，不取首次被AI看到的日期。
- 本期首课付款：纳入集合中付款日期在本期的需求数。
- 本期正式购买：纳入集合中正式确认或其订单确认日期在本期的需求数；同需求多订单不当多位客户。
- 正式均单：本期新确认订单，截至资料截止的已知累计人民币实收除以订单数。订单/金额不完整则待核；这不是本期现金流、退款后净收入或合同总额。

交易统计读取全部纳入案例，不限于本期有聊天的案例。21日无聊天，22日证据确认21日成交，修订21日报时仍须计入；不记为22日新成交。旧订单今日追加到账不新增今日成交，也不进入今日新订单均单。分期沿用订单ID、每笔独立收款ID；相同ID/相同证据重复填报会被拒绝。跨报告去重仍由上游按ID和修订关系实现，不把日报数直接累加。

## 3. 固定入组资格与当前有效性分开

需要成熟期比较时，management.cohort除原字段外提供entry。公司新格式有cohort就必须有entry键，未知为null。没有cohort或entry未知：显示固定入组快照待补，不反推精确分母和转化率。

```json
{
  "entry": {
    "at": "2026-10-20 09:10:00",
    "validity": "effective",
    "purchase_kind": "first",
    "policy_version": "实际入组判定规则版本",
    "reason": "纯合成示意：首次确认具备有效需求",
    "refs": ["入组时已存在的本案证据ID"]
  }
}
```

validity仅effective/high；purchase_kind为first/repeat，指入组时的购买链路。at不早于真实首触、不晚于资料截止，引用不晚于at。entry的规则版本固定，不因今天升级Skill而换成新版本。固定入组资格和cohort.first_contact_at、is_new_customer在匹配历史后不能静默改变；原资格误判用correction，field写cohort.entry（完整对象前后值）、cohort.first_contact_at或cohort.is_new_customer。

新客获客队列使用入组时first、真实首触及is_new_customer=true；同一稳定公司客户不重复作为两名新客。成交、失联、售后闲聊或当前有效性改变不删除原批次成员。完课队列仍需明确完课时刻，无法确定时不制造精确观察窗。只统计本次提供的队列成员；要查看完整固定批次，数据部门必须回传该批全部成员的有效状态，不只提交今天活跃者。局部输入不得宣称全批结果。

## 4. 统计期销售适用性与当前沟通分开

每案management.week增加：

```json
{
  "sales_scope": {
    "as_of": "与management.week_end完全相同",
    "sales_applicable": true,
    "reason": "纯合成示意：本期发生过该需求的销售咨询",
    "refs": ["统计期末之前已存在的本案证据ID"]
  }
}
```

该快照表示截至期末、本期是否有销售咨询适用内容，不能只看最后一句是闲聊还是销售。true进入本期销售分母；false非销售；null待核（此时可无引用，但须解释）。as_of必须等于week_end，引用不可来自统计期之后。它与week.validity及week.phases一起服务于历史统计；当前lifecycle和实际动作服务于现在的待办。

同一期间快照在匹配历史后不能静默改写；真实纠错用field=week.sales_scope，before/after保留完整对象。后续新闲聊不得改写过去咨询。晚到交易按真实发生日修订；如果迟到证据不足以重建当时销售用途，保留待核，不能以未来对话倒填。旧格式若cutoff晚于week_end且没有sales_scope，期间适用性为unknown；列出受影响case，不复制当前用途回历史。

## 5. 任务变化须保留原值

匹配历史后，同一任务updated_at不能倒退；未结任务不得省略。已知due_at/next_check_at/escalate_at的改动或清空、owner/kind/issue_key/action的改写、终结任务重开，均需action.change：

```json
{
  "change": {
    "baseline_analysis_id": "本次实际采用的旧analysis_id",
    "previous_updated_at": "该旧版本动作的实际更新时间",
    "before": {"due_at": "原截止时间"},
    "reason": "具体改期原因",
    "confirmation_source": "实际执行或确认来源",
    "refs": ["本案变更依据ID"]
  }
}
```

before必须覆盖所有受保护的实际改动字段；旧值须与基线相同，引用不能晚于任务updated_at。当前任务字段保存新值。没有原截止的新动作可正常排期；原逾期记录保留在原结果与变更before里，不因改期消失。状态为resolved/cancelled仍须原有解决说明和证据/明确裁决；建议不算执行。成交后服务通常创建独立service动作，不将原追单任务换名改类型冒充延续。

## 6. 问题发生记录与待办状态关联

公司新格式的customer_question事件须增加非空action_ids，明确关联本案处理动作。不能按标题相似猜关联。保留事件，同时派生提醒：全部resolved/cancelled则取消待回应；全部终结或executed_waiting_customer则不再催首次回应，后续复查依动作节点；还有未处理动作则保留待回应。

核销关联动作的updated_at不得早于问题；须有问题发生之后的执行证据或明确人工裁决。相关终结动作也随事件回传，不能只留一个已删除的动作编号。旧问题缺关联显示“处理状态待核”；允许在原事件其余内容不变的前提下一次性补action_ids。已关联事件不改写，重新提问另立真实事件和处理动作。其他无关任务完成不能核销这个问题。

## 接入边界

统一结果保留reliability_version、week.sales_scope、cohort.entry、correction及action.change/action_ids，历史比较依赖回传原统一结果，不能手工拼假基线。内部历史及原话继续遵守获准留存；新合同不授权长期保存。

逐字来源匹配只验证实际引用，不证明模型读完全部消息。0.7.34的[分析追溯与完整交付](analysis-trace-and-delivery.md)记录来源、模型资料包和调用/截断状态，并以delivery-dir输出完整目录与独立校验凭证；公司新交付按该页执行。旧output/results-output仍是分文件交付，不作为完整交付通过。平台权限、外部回写重试、跨销售归属、完整交易账本及真实语义准确率仍需独立建设和验证。
