# 两层销售复盘、话术映射与改进记录

主管批量复盘采用以下默认标准：批量复盘与Skill评估使用相同两层，作为主管批量报告的默认组成。先判断销售选的方向是否合理，再检查客户可见表达是否完成该方向；不是将所有未成交归为话术没背熟。

## 两层与证据

第一层检查需求、客户当前决定、真实阻碍、方案选择和下一动作。依据销售实际发言/动作判断其表现，不声称读到内心。第二层检查针对合理判断组织的理由、顺序、具体性、针对性和必要回答。方向错误时先纠正第一层；另有独立表达缺口才同时标第二层，不能把同一个问题换名字扣两次。

每层分为可见缺口、未见明显缺口、证据不足、本案不适用。另保留执行标签，记录付款入口、回传、约定等兑现情况；它不是新增培训阶段。主问题可为判断、表达、两层、执行、无明确缺口或证据不足。成交案也可有过程缺口，未成交案也可有良好判断；结果不反推唯一原因。

## 对应到原库

按本案事实选择实际读过的培训规则或原话术，保留来源文件、场景/标题、原Word段落定位（若有）、逐字短摘录和本案引用。生成器检查摘录确实存在于对应材料。原库引文与后加运行规则明确分开标注；不能把运行说明冒充原话术逐字摘录。来源须直接支持所标缺口，例如响应超时对应响应规则，不用师资匹配规则代替。来源适用性由Skill判断，不能仅按关键词匹配。

采用状态：未体现、只做了部分、时机/条件用错、已恰当体现、证据不足、不适用。这里评价可观察的使用结果，不能据此断言没有学习、懒惰或拒绝执行。表达不同但完成同一论证可算采用；照抄但不适用不能算掌握。一般课后跟进不能机械套“试听好但正式贵”，直接询价也不自动成为价格异议。

训练动作按问题决定：第一层练读案、辨阻碍和方案选择；第二层在正确判断下练原段逻辑与本案改写；执行缺口练具体任务和回报节点。背诵可作为准备，验收须看是否在适用情境完成正确动作。每人最多三个本期重点，给案例、练习、通过标准和下一批的观察项。训练状态默认为建议，未发生的培训、员工反馈或效果不能写成已完成。

## 同类问题与关键节点

新批次默认在主管首页归纳最多三个有依据的同类问题；按同一个可观察机会定义分母，例如“客户问价后销售有机会解释费用和方案”，不把所有客户当成机会。列出有缺口、未见该缺口及待核案例；每案每项至多一次，待核不计入可判断分母。有实际对照才展示，不能制造对照或把比例当作成交原因。样本少或客户条件不同不作人员排名，结果只作为带教优先级线索。

对有明确缺口的关键案例，逐节点说明：当时客户正决定什么、有何实际阻碍；销售做了什么；属于判断、表达还是执行的哪个具体缺口；可能影响客户购买依据的哪一部分（明确是推断）；当时更合理的动作；基于最新资料现在如何跟进；对应的培训规则或原话术。分别引用客户与销售当时的原话，展开可查时间、来源和行号。话术库只映射适用段落，不因为没逐字照搬就判未掌握。

当时的判断只能用当时可见信息；后续反馈独立标注，不能倒填当时已知事实。销售确有可观察动作可评价；未看到某动作时注明缺失的电话、群聊或附件及记录范围，不能断言现实中未发生。未成交可能与预算、交付、时间或客户选择有关；不要凭结果把原因全归给销售，亦不可推断销售是否参加培训、是否背诵、动机或岗位适配。两层的缺口要各自有不同的实际问题，不能同一问题重复扣分；无法判断就标待核。

### 数据扩展

为保证旧报告兼容，扩展字段可省略；新批次默认为关键缺口提供节点与可比较的机会，确无适用机会时`patterns`为空。每个纳入案例的`management.layers.diagnostic_nodes`数组，每项包含：

- `id`、`layer`（judgment/expression/execution）、`stage`（reception/diagnosis/proposal/objection/close）、`observed_at`。
- `customer_decision`、`sales_action`、`gap`、`possible_effect`、`better_action`、`current_action`、`limit`：均为具体文字。`possible_effect`是推断，不可当成已证明因果；`better_action`只能依据节点当时事实，`current_action`可依据后续真实情况。
- `sales_action_evidence`为observed/not_observed；后者需`coverage_limit`说明未见范围，不能断言现实未做。
- `customer_refs`须引用本案客户当时消息，`sales_refs`在observed时须引用本案销售当时消息；`later_feedback_refs`仅引用节点之后、截止前消息，可为空。角色或时间无法确定时不伪造节点。
- `library_index`为本案`library`数组从0开始的索引，对应同一问题层次，来源逐字核验规则不变。

`management.coaching.patterns`最多三项，含`name`、`opportunity_definition`、`layer`、`stage`和`opportunities`。每个机会含本批`case_id`、`status`（gap/sound/unknown）和`refs`；gap另给本案`node_id`且阶段、层次一致。sound须有本案证据，unknown可无引用。生成器只核对引用、类型、时间与分母，不验证语义、完整性或因果；节点是否真正反映本案和培训方法仍须主管申诉复核。

## 批次校正与连续观察

跨周状态续接、同类机会去重和实际训练前后观察按[跨周规则](longitudinal-review.md)执行。旧缺口持续未解决不每周新增一次；已确认人工纠错替换原观察，版本不同的机会定义分段。缺档案或缺训练执行记录只说明缺口，不用模型记忆补齐。

有人对缺口、两层归因或原库采用提出异议时，先用[申诉与复核规则](appeals-and-review.md)核对完整上下文和原时点。待复核的问题不计作已确认能力缺陷；被撤销的缺口同步退出个人重复问题、同类机会缺口计数和对应训练依据，保留更正记录，不把修正版算新的失败。其余独立成立的判断不受影响。

用户明确更换混入其他记录的源文件时，新源为唯一事实依据。旧批标为被替代，不并入长期趋势；同一批的修正版不是第二次失败或第二周。重新导入和核对新行号、客户身份及截止时间，不能拿被移除消息补缺证。

本地观察记录只保存在授权私有客户目录，记录批次、销售、时间口径、源指纹、逐案两层结论和训练建议。每天重复出现的同一客户应按稳定来源身份匹配并去重；批次内案例编号会变化，昵称不能当稳定身份。未来比较需同时看同类适用机会、问题出现比例、已确认训练执行、后续实际表现和观察周期，不能只比问题绝对数。

单批校正数据只建立基线，不能据此断言长期能力、学习态度、改进速度或岗位不适配。可为负责人提供可核查的岗位表现与复核建议，不根据聊天自动作辞退决定或人格评价。岗位评估还需负责人核验岗位要求、支持条件、员工说明及足够的可比记录。

本机制是读取已保存的资料，不是模型自动学习或保证永久记忆。遵守现有客户资料保留期限；本轮不扩大长期存储授权。保留期外的个体管理档案须另行明确范围与期限，不能隐蔽复制客户正文延长保留。

## 数据扩展

保留management 1.0。启用本模式时顶层management.coaching包含version="1.0"、basis="corrected_baseline"或"baseline"、previous_batch_status="superseded"或"none"、assessment、strengths数组（claim/case_ids），以及最多三项plans。每项计划含id、layer（judgment/expression/execution）、skill、case_ids、source_paths、action、exercise、pass_criteria、next_review、status="proposed"。已有实施结果需在后续独立记录，不改写原建议的发生时间。

每个纳入case.management.layers包含：

- primary：judgment/expression/both/execution/none/unknown。
- judgment、expression：各含status（gap/sound/unknown/not_applicable）、finding、expected、refs；execution同结构但不要求expected。
- causal_limit：事实与归因限制。
- library数组：source_kind（scene/training_rule）、path（相对Skill根的MD）、locator、quote、layer、application（not_used/partial/misapplied/appropriate/unknown/not_applicable）、rationale、refs。
- training：kind（judgment/expression/combined/execution/none/verify）、action、exercise、pass_criteria、status="proposed"。

有明确缺口时需要相关来源；quote须能在来源中逐字定位（忽略Markdown引用符和空白排版）。路径只允许Skill入口或references内MD。所有客户refs仍必须来自当前案、当前源。两层统计按案例计算，同案可两层有缺口而不相加。报告显示建议而非已完成训练，不能把覆盖校验称为专业判断已获认可。
