# 聊天记录复盘数据合同与本地生成

公司0.7.34交付同时按[分析追溯与完整交付](analysis-trace-and-delivery.md)采用delivery-dir，记录实际输入/规则版本，有真实模型日志才核对送入覆盖；独立检查成功后消费。下文旧输出参数仅保留兼容。

公司0.7.33新分析同时使用[可靠性合同](review-integrity.md)：reliability_version=1.0、期间销售用途快照、固定入组资格、具体字段纠错、任务变更与问题动作关联。历史格式兼容不等于公司新分析验收通过。

公司新连续批次在本合同上增加[客户连续管理扩展](customer-lifecycle.md)：`management.lifecycle_version`和逐案`management.lifecycle`，以客户/需求稳定编号区分新客、连续、回流与成交后沟通。`validity.status:not_applicable`仅用于本次非销售且没有可核历史有效性；不是无效类别，不能用于销售咨询逃避判定。其余旧字段保持兼容。

本文件只定义复盘数据怎样存入固定模板。批量销售复盘的判断方法使用[聊天记录分析与拿单复盘](chat-review.md)及入口固定阶段；不要将其缩成普通单案 AI 建议短评。生成器不分析销售能力、不创造因果，也不替代负责人验收。先由 Skill 读原始记录并完成专业判断，再运行校验；不因模板有字段就编造事实填满。

主管新版在本合同上增加[management扩展](chat-review-management.md#管理数据扩展)，由相同生成器输出简明首页、阶段证据点击、试听时效与必须跟回名单。旧版无扩展的输入仍兼容。下文“不计算均单”等说明只描述旧版；管理版金额完整时按扩展中的订单口径计算。

新批次同时交付[统一管理结果](review-results.md)：由本输入一并生成HTML与JSON，等级、统计、预警和必须跟回顺序保持一致，JSON不再作第二次分析。`validity.price_silence`按[有效性规则](validity-assessment.md#逐项判断与结论)记录附加状态；优质有效优先，报价消失不改变有效等级。

## 用法与边界

持续使用的新增批次默认按[Daily管理扩展](daily-management.md)明确cadence=daily，并提供覆盖说明和实际动作状态；用户指定周报/期间时遵从。旧week字段在Daily表示本日快照，旧输入省略cadence仍按周兼容。首次没有历史不造变化趋势；实际人工复核、成熟期与上期对照参数也见该页。

生成器为 scripts/render_chat_review.py，样式为 assets/chat-review.css，均相对 Skill 根目录。仅依赖 Python 标准库；CSS 会内嵌到最终 HTML，成品不需要联网或另带样式文件。不安装服务、不上传、不自动联系客户。

~~~text
python scripts/render_chat_review.py <私有目录/复盘数据.json> --check-only
python scripts/render_chat_review.py <私有目录/复盘数据.json> --output <私有目录/销售姓名复盘.html>
~~~

Excel/CSV已有独立导入结果时，两步均须加 --source <私有目录/cases.json>。源可为案例数组或 {cases:[...]}；每案 id、account_id（若有）与每条消息 source_sheet/source_row/time/role/text 用来核对，兼容旧 sheet/row 字段。源消息必须先从文件独立提取，不允许从分析稿反造源以通过检查。同案同位置的原话、时间、角色逐字一致才通过；显示 speaker 与源 role 不同时可在消息加 source_role 明确原角色。截图没有独立源文件时，未传 --source 只能声称引用归属/结构检查，不能声称与外部原文已逐字核对。

输出已有文件时默认报错，只有覆盖已获得授权才使用 --overwrite。真实 JSON 与 HTML 只放项目指定的私有客户目录，不写进 Skill、Git、公共样例。生成器拒绝写入自身 Skill 目录或 Git 工作区。源码不含本机绝对路径。

每份输入只有一位销售，输出也只有一位销售。同一批多人分别生成；不能将多人放在一起后靠筛选当作独立报告。转接归属在分析阶段处理，排除项仍列明理由；同一源消息不重复计入两个案例。

默认只显示判断引用的原话，不把全量聊天嵌入成品。原文中的无关验证码、口令等可标 sensitive:true，保留输入原文但不能被引用，输出不含该正文。该标记不是自动脱敏器：生成前必须人工检查关键引用是否夹带无关敏感内容；不能为隐藏敏感内容把原话改写成另一句。

## 顶层字段

所有下列字段必填。unknown 是明确未知，不等于否、无问题或零；空数组仅表示没有已核实的该类条目。

| 字段 | 类型与含义 |
| --- | --- |
| schema_version | 固定 "1.0" |
| sales | {id,name}：销售标识与显示名 |
| period | {start,end,cutoff}：本次统计起止与资料截点，字符串，要注明适用时区 |
| scope | {cohort,coverage,orders_complete} |
| scope.cohort | new_clients 已核本期新客；active_conversations 本期出现的会话；unknown |
| scope.coverage | 阅读覆盖、缺图/语音/群聊/电话、旧客与新客边界的具体文字 |
| scope.orders_complete | 布尔值，正式订单结果是否在本批范围内核齐；不能把“聊天完整”当订单完整 |
| targets | {conversion_rate:null,average_order_rmb:null}，有本机构明确目标时填数值，未设置保持 null，生成器不补默认目标 |
| standards | 字符串数组，列本次负责人确认的有效客户、首课/正式单、响应/跟进等口径 |
| cases | 案例对象数组，含纳入和排除项 |

只在**已核本期新客 + 订单完整 + 没有待判/范围待核 + 有有效分母**时显示完整转化率。其他情形只显示已确认数量，不拿会话数冒充获客队列。订单覆盖不全且无确认正式单时，首屏显示“正式单待核”，不显示醒目的“0正式单”。

本版不计算平均实收：收款笔数不等于订单笔数，分期、首课、续购、外币报价需要订单口径。目标可以显示，实际均单待完整订单与人民币实收核对后另算。

## 每案身份、分组与原始消息

| 字段 | 类型与含义 |
| --- | --- |
| id | 全批唯一编号，字母开头，只用字母、数字、下划线、短横线 |
| sales_id | 必须等于顶层 sales.id |
| name, date | 微信显示名、该案起始日期 |
| included | 是否纳入客户会话计数，明确布尔值 |
| exclusion_reason | 纳入时允许空串；排除时必须写具体原因 |
| group | 下方互斥分组之一 |
| source_messages | 本案原始消息数组 |

分组固定顺序，也是导航与总表顺序：rescue 重点补救 → trial_followup 正常首课跟进 → order_check 仅订单核实 → routine 正常推进 → historical 历史复盘 → low_priority 暂不逐案详谈。excluded 为排除项，不进入上述分组计数。首屏各组由同一数组计算，加总必须等于纳入数，不接受手工总数。

“重点补救”须有具体销售缺口与当前争取动作；正常首课没有明显问题时放正常首课跟进；仅缺订单性质、不足以判断失单的放仅订单核实。历史期限已过等情况单列历史。不要把已付首课自动当遗憾单，也不要把正常首课藏到其他分组。

每条 source_messages：

~~~json
{"id":"C01-m01","source":"聊天导出.xlsx","sheet":"Sheet1","row":2,"time":"2026-10-19 10:00","speaker":"客户","text":"此处为原始完整消息","sensitive":false}
~~~

sensitive 可省略，其他必填。有效性扩展中的失联判断需保留可核查的`source_role`，必要时带独立源中的布尔`is_system_greeting`；不能自行把客户消息改成系统提示，使用`--source`会核对该标记。截图无工作表时 sheet:""；无行号时 row:null，source 写截图文件名及可定位页/区域。行号沿用原文件，不按排序后的消息重编号。若标准化数据来自非表格来源，可同时在报告与独立源消息中提供相同的`source_message_id`；无行号时以该来源ID定位，且检查同案原文、时间、角色及ID，不能杜撰平台ID或当作已接入平台。text 可以保留原始空字符串，但不能作为判断引用。id 全批唯一、建议案例前缀；所有 refs 只能引用**本案**消息，不能引用另一客户同名消息。相同 source+sheet+row 或同来源消息ID不能重复归属；先消除重复或处理转接归属。

排除项仅需本节字段及原始消息，不需要假填阶段与成交。纳入项还需要以下全部字段。

## 有效性与订单

validity:{status,reason,refs}：

- status 为 high 优质有效、effective 基础有效、pending 待判定、scope_unknown 范围待核、invalid 无效。
- reason 写符合哪些条件/缺什么证据；refs 至少一条本案消息。
- 无效不等于排除：真实无效线索仍在会话总数里；内部同事等才按归属排除。
- 新批次的`assessment`按[有效性逐项判断与更新](validity-assessment.md#机器可读结果可与管理报告共同使用)填写，逐项给可见证据、数据缺口、时点及必要的状态变化；`assessment.status`须与当前`status`一致。报告生成器发现该字段时自动检验，不含字段的历史数据保持兼容。`management.week.validity`仍保留统计期结束时的判断，不可用后来证据倒填。

order:{formal,first_lesson,summary,refs,actual_receipts,quotes}：

- formal：confirmed 已确认正式购买；not_confirmed 截至记录未确认正式购买；unknown 结果待核。not_confirmed 不主张现实中没有成交。
- first_lesson：paid 已付费、completed 已上、accepted 接受首课但付款待核、not_started 未进入、unknown 不足以判断。订单性质未证实不能猜固定金额的首课。
- summary：当前结果、责任人应核哪一步；refs 至少一条。
- actual_receipts：数组，每条 {amount,currency,kind,refs}。kind 为 formal|trial|unknown。没有实收依据写空数组，不拿报价、支付链接、付款意愿填入。
- quotes：数组，每条 {amount,currency,description,refs}，仅存报价证据。金额可以数字或数字字符串，不能隐式换汇。

## 五列完成度与培训当前位置

phases 必须恰好五个键：reception 承接、diagnosis 诊断、proposal 方案报价、objection 异议处理、close Close。

每列为 {state,reason,refs,branch}：

- state:done 完成且未见明显不足，显示 ✓；gap 已完成但不足，显示 ✓＋reason；not_done 没完成，显示空白；unknown 缺记录，显示待核。
- reason 必填，尤其说明完成/未完成依据。done/gap 必须有非空 refs；其余允许空数组但不能无理由。
- branch:formal|trial|transfer|none。仅 Close 可写非 none；首课/转接 Close 额外显示支线，不充作正式成交。
- 报价发出不等于方案共识、销售解释不等于异议解除、邀请付款不等于 Close完成。判断仍由专业分析负责，脚本不会按关键词打勾。

position：

~~~json
{
  "furthest":{"step":5,"branch":"trial","reason":"已完成首课","refs":["C01-m01"]},
  "current":{"step":3,"branch":"trial","reason":"首课效果顾虑仍未解决","refs":["C01-m02"]},
  "main_stage":"objection",
  "scene":"首课后",
  "reason":"已走到首课交付，现在需要回到异议处理补效果证据"
}
~~~

以上仅示意字段，不是可直接使用的客户事实。furthest/current.step 为培训 1..5，不足时 null；分别给支线、理由和本案依据，已知步骤必须有引用。main_stage 只能五列编号或 null；资料不足、正常推进没有明确缺口时用 null 并在 reason 写清。交付、排课、教师匹配只是 scene，不能冒充第六个谈单阶段。

## 个案判断、证据链与补救

以下字段为文字：

- headline：一句话结论。
- goal：本次拿单/复盘目标。
- current_problem：具体断点。
- attribution：销售缺口、客户约束、供给限制与未知原因怎样区分。
- opportunity：为什么值得争取，明确需求、购买信号与离成交还差什么；没有机会也写不适用原因。不能把“优质”当必然购买。
- other_constraints：真实预算/决策/供给等三性之外问题，可空但不能硬塞三性。

nature 恰好三个对象 {name,state,reason,refs}，name 分别为重要性、有效性、紧迫性；state 为 gap|established|unknown|not_applicable。gap/established 要有引用。已有重要性共识/真实期限不能因未成交就改判缺失。

summary_refs：1—3条关键本案原话，直接放总表聊天对照，不能只写抽象结论。

evidence_nodes：数组，每项 {refs,missed,impact,better,limit}。分别展示原话、“这段没完成什么”、“为什么影响购买”、“当时更好的接法”、“判断边界”。重点补救与历史复盘至少一处完整证据链；不能把改进建议写成原销售实际发送，也不能写“肯定能签”。

recovery：

| 字段 | 内容 |
| --- | --- |
| possibility | recoverable 当前可推进、conditional 有条件、not_now 当前原需求不宜再推、no_contact 停止该渠道触达、unknown 先核实 |
| reason | 为什么现在能/不能争取，剩余缺口与真实时间窗口 |
| actions | 至少一项 {owner,action,when,signal}；明确谁、干什么、何时、什么反馈算推进 |
| script | 建议客户稿；无可发送稿写空串，不能编造师资/审批/时限 |
| script_conditions | 该稿使用前提与尚须核实的承诺；可发补救稿必填 |
| coaching_question | 主管带销售过案时最重要的一问 |
| next_signal | 下一次须取得的可观察购买推进信号 |

rescue 且当前可/有条件推进时必须给 script 和前提。明确停止触达 no_contact 时稿必须为空，内部动作写入 actions。正常首课分组必须有 accepted/paid/completed 支线证据；仅订单核实至少有订单事实明确 unknown。

## 校验与验收

校验会阻止：跨销售混合、消息/行号重复归属、跨案例引用、敏感/空白引用、非五列主阶段、漏字段被当成零、已确认实收与订单状态冲突、救单缺证据链和动作、重复输出覆盖。

校验不能证明：读取了未包含的截图/语音、原始提取没有漏字、专业归因正确、未成交必由销售导致、补救会成交。交付前仍要对照原文件抽核引用、核对所有重点案，再检查HTML计数、五列标记、优先顺序和实际阅读。浏览器策略禁止预览时不得绕过；如实说明只完成结构/静态验证，不称浏览器已验收。
