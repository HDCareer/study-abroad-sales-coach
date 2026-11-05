# 主管与团队输出规范 v1.0

随 留学辅导销售助手 0.7.35 内部版提供，0.7.36增加可选联系状态，0.7.37分离完整目标周与截至观察范围并接入业务进度基准。判断依据与生成顺序以 [主管管理规则](supervisor-management.md) 为准；本页定义接入格式。所有示例身份、路径均为占位，不得写入实际客户正文到 Skill 安装目录。

## 1. 输入与职责

单顾问继续使用原 `report.html / results.json / run.json / DELIVERY.json` 四件套。多个成员必须通过原独立校验，源消息核验为 matched，销售编号唯一、周期和规则一致；provenance中的实际运行文件指纹也必须完整且跨成员相同，不能只凭版本文字相同就拼接。`standards` 应是全批共用口径，个别客户的判断放入案例字段，不用不同规则标题混拼。

运行 `team_management.py prepare` 生成 `skill3-supervisor-request/1.0`，其中 `request_id` 绑定成员分析编号及结果字节；`members[].result` 提供完整标准分析。报告期 `reporting_window` 包含 `week_start / week_end / cutoff / time_basis` 四个字符串，采用原报告日期时间格式。截止日期可以晚于周末：当前关注用截止状态，周培训只用周内发生的行为。

### 1.1 周中日更：完整考核周与截至观察范围分开

每日刷新当前周看板时，使用周内累计（`cadence=weekly`，表示统计粒度，不表示每周才运行一次）。单顾问 `management.target_period` 显式提供完整自然周 `{start,end}`，周一00:00:00至周日23:59:59；`management.week_start/week_end` 与 `period.start/end` 仍表示实际已观察范围，不能填未来消息。最新事实截至 `cutoff`。例如周三早会：

```json
{
  "cadence":"weekly",
  "week_start":"2026-11-02 00:00:00",
  "week_end":"2026-11-04 09:00:00",
  "cutoff":"2026-11-04 09:00:00",
  "target_period":{"start":"2026-11-02 00:00:00","end":"2026-11-08 23:59:59"}
}
```

以上为management的部分字段。原 `period` 同时填写实际start/end/cutoff；原规则、案例、来源、时间口径等必填项不省略。观察起点必须等于完整目标周起点；观察终点不晚于目标周末和资料截止。完整周目标保持原金额，不乘已经过天数。原 `cadence=daily` 单日日报仍按原合同运行；不能把单日指标当成本周累计。

单顾问结果、主管request、团队结果新增同名 `target_period`，供页面显示完整考核周，`reporting_window`保留实际范围。所有顾问须提供相同值；不能一部分提供、一部分省略。业务输入也提供相同 `target_period`，实际统计窗口与成员保持一致。历史输入未提供时输出null，沿用旧语义，不猜自然周。

周一、周中、周日均可逐日更新实际观察终点；周后复盘可保持实际统计终点为周日、最新cutoff晚于周末。周培训和统计只能使用已观察范围内的证据，当前关注可使用截止时的新状态。完整目标周从不授予使用截止后消息的权限；新格式会拒绝这种提前输入。月度期间需覆盖完整目标周；月度累计独立提供。

模型读取全部成员、全部纳入案，生成第2节的审阅结果；不由展示程序猜问题。业务系统另供第3节数据。`build` 拒绝过期输入、错期/重复成员、错误引用及不符合源事实的状态。修改单顾问源分析后，必须重新 prepare 和审阅。

## 2. 模型输出：主管审阅

顶层字段必须齐全，不接受额外字段：

```json
{
  "schema_version": "skill3-supervisor-review/1.0",
  "request_id": "由prepare返回，不手写",
  "producer": {"kind": "model", "name": "实际模型或生成方名称"},
  "human_approval": "not_provided",
  "cases": [],
  "team_topics": [],
  "advisor_focus": []
}
```

### 每案管理决定 `cases`

必须恰好覆盖成员结果中所有 included 案例，每个销售编号＋案例编号一次。

| 字段 | 规则 |
| --- | --- |
| sales_id, case_id | 标准结果中的固定编号 |
| attention | manager / advisor / historical / none |
| trigger | trial_followup / trial_preparation / course_verify / service_followup / customer_blocker / commitment_due / order_verify / scope_verify / none |
| priority | manager/advisor 为 1、2、3；historical/none 为 null |
| title, why | 简短管理标题、为何现在关注或不关注；不得新增无证事实 |
| refs | 本案标准 evidence 中消息编号数组；活动关注和历史训练需有证据；不能晚于资料截止 |
| action_index | 选择本案 recovery.actions 的从0起编号；manager/advisor必填有效编号，其他可null |
| trial_preparation | null，或下表五字段对象 |

活动关注不能使用 trigger=none。正式已购客户不能列首次转正、试听准备、原成交阻碍或首次成交承诺追回。`service_followup` 专用于已确认正式购买后的课程服务核查，沿用源 recovery 的动作；不得据此重新计为首次成交。`order_verify` 不用于已经确认正式购买的旧需求；`course_verify` 不把已完整完课的原试听再次标成未完。

准备检查对象固定为：

```json
{
  "course_state": "paid_schedule_unknown",
  "student_goal": "继承已知目标；缺失则写待核",
  "teacher_alignment": "已知教师确认或尚需核实的事实",
  "preparation": "本次需准备或核实什么",
  "refs": ["本案消息编号"]
}
```

course_state 只取 `unknown / not_confirmed_paid / paid_schedule_unknown / scheduled / partial / completed`。状态须与源付款/完课事实一致；已完整完课不能标待上课，部分上课不能当完整完课。unknown之外的状态须有引用。

主管一问**直接取源** `recovery.coaching_question`，下一动作**直接取源** `recovery.actions[action_index]`。审阅中不得另写一套字段替换它们。源动作错误先走源复核，重新生成单顾问交付。

### 团队培训 `team_topics`

最多3项。每项固定字段：

| 字段 | 规则 |
| --- | --- |
| id, title | 本批稳定主题编号与清晰行为标题 |
| opportunity_definition | 哪些销售机会适用；什么具体动作算缺口 |
| layer | judgment / expression / execution / mixed |
| stage | 固定枚举 reception / diagnosis / proposal / objection / close，分别展示为承接、诊断、方案报价、异议处理、Close |
| exercise, pass_criteria | 本次训练怎么做、怎样算通过 |
| source | `{path, quote}`；引用成员 coaching_review.source_text 已有的培训原文，quote至少8字符 |
| members | 逐案例归并证据，结构如下 |

member 固定字段：`sales_id / case_id / layer / basis / status / refs / why_same`。

- layer：judgment、expression、execution，保留该案实际层次。
- basis：layer 或 issue；分别核对源 layers 的相应层，或源 issue。
- status：gap / sound / unknown。不得把源已正常的行为变成缺口；反例可明确列sound。
- refs：本案证据；gap/sound不能空，需与对应源判断证据相交。任何引用不能晚于周末；gap至少一条发生在统计周内。
- why_same：这案为什么符合该主题的具体行为定义；含不同层次时解释共同点。

至少两位不同顾问有gap才能称团队共性。mixed须实际存在至少两个缺口层次。一个客户的不同问题不能仅因都带“价格”合成一类。程序检查字段与引用，**语义是否真同类仍由模型及主管复核**。

程序在 `team_topics[].counts` 内输出 `case_count / advisor_count / gap_case_count / gap_advisor_count / unique_customer_count / gap_rate`。含反例时案例总数与缺口举证数不同，界面优先标“缺口举证×案、涉及×位顾问”。独立客户数和发生率固定null：本模块没有逐个适用机会的完整问题分母，也没有自动跨账号去重。

### 个人重点 `advisor_focus`

每位成员恰好一条，固定字段：`sales_id / plan_id / reason / case_ids`。plan_id 必须来自本人的 `coaching.plans`；所选case_ids必须属于该计划。没有可选重点时plan_id=null、case_ids=[]并说明原因。程序保留源计划的练习、通过标准和proposed状态，不生成训练已完成或效果提升的结论。

## 3. 业务系统输入

可省略；省略时显示未接入，不能用聊天估净营收。输入范式：

```json
{
  "schema_version": "skill3-supervisor-business/1.0",
  "reporting_window": {"week_start":"2026-10-19 00:00:00","week_end":"2026-10-25 23:59:59","cutoff":"2026-10-25 23:59:59","time_basis":"与主管输入相同口径"},
  "currency": "CNY",
  "scope_note": "明确纳入团队及排除范围",
  "definitions": {"revenue":"net_after_refunds","conversion":"period_first_formal_over_effective","average_order":"first_formal_order"},
  "targets": {"effective_conversion":null,"first_formal_order_rmb":null},
  "advisors": [{"sales_id":"顾问编号","net_revenue":0,"target":null,"effective_leads":0,"first_formal_purchases":0,"first_formal_order_total":null,"first_formal_order_count":null,"source":"可回查的业务表位置或业务查询标识"}]
}
```

可额外提供 `business_month:"YYYY-MM"`，由公司按整周归月规则指定；未提供不推算。advisors须与团队成员完全一致，无多余、缺员或重复。业务日期起止与聊天统计周相同，业务截止不得晚于资料截止，时间口径相同。

- targets：两项目标分别由使用机构提供，未知显式null；缺失不影响已知经营结果，不能借作者机构目标填补。
- net_revenue：人民币净营收，已扣退款，允许负数。
- target：正数或null；缺任一个人的目标，团队目标与目标达成率不凭空相加。
- effective_leads：本周有效承接人数；first_formal_purchases：本周首次正式购课人数，排除试听与续费。允许跨周客户本周成交，因此该经营比率可超过100%，不是固定获客批次最终转化率。
- first_formal_order_total/count：本周首购客户的首次正式订单金额合计与已有金额的人数；两者同时缺失用null。只覆盖部分首购客户时显示资料不全，客单价不计算。正式首购数为0时也不显示0元客单价。
- JSON金额须为数字，不接受数值字符串；人数必须非负整数，拒绝布尔值及NaN/Infinity。续费不能补成首次客单金额。

公式：净营收求和；目标达成率=净营收÷目标；有效转化率=本周正式首购人数÷本周有效承接人数；首单客单价=完整首单金额合计÷首次正式购买人数。零分母及缺失均为null，不填0；不采用每人比率的简单平均。目标完成比例不是时间进度，后者按下述可选pace接入，不擅自假定每日平均。

### 截至时点的业务进度 `pace`

每个advisors项可增加 `pace`，省略或null表示尚未提供目标日历基准：

```json
{"expected_net_revenue":18000,"as_of":"2026-11-04 09:00:00","source":"业务系统目标日历或已批准的阶段目标查询标识"}
```

`expected_net_revenue` 是业务系统按实际目标安排给出的截至应达人民币净营收，非负有限数值；可以为0。`as_of`必须与该业务实际营收的 `reporting_window.cutoff` 是同一时刻；不同截止、缺来源或无效值拒收。数据部门负责日历和应达值，Skill不按星期比例推断。

输出位于 `business.advisors[].pace`，保留上述三字段，增加 `actual_net_revenue / gap / status / expected_attainment`。gap=实际净营收−截至应达净营收；status是behind（负）、on_track（零）、ahead（正）；expected_attainment=应达净营收÷完整目标，未知目标时为null。这里的进度状态只是经营比较，不归因于顾问能力，也不预测成交。

只有全体纳入顾问都有同截止基准时，`business.team.pace`才合计实际与应达值，并在sources保留每位基准出处。任一顾问缺失则团队pace=null，已有个人基准仍保留。零基准不等于缺失；退款后的实际净营收可为负。不从目标达成率或经过天数补齐缺失基准。

### 可选的团队月累计 `monthly`

在上述业务输入顶层增加monthly；省略或null表示月数据未接，不用单周数据填补。提供时有下列六个必填字段，可另带pace：

```json
{
  "business_month":"2026-11",
  "period":{"start":"2026-10-26 00:00:00","end":"2026-11-29 23:59:59","cutoff":"2026-11-02 12:00:00","time_basis":"与主管输入相同口径"},
  "sales_ids":["本报告全部顾问编号"],
  "net_revenue":0,
  "target":null,
  "source":"业务系统截至该时点的整月累计及月目标出处"
}
```

以上日期与目标仅为结构示例。period为公司完整经营月边界，须包含当前统计周；cutoff不得早于当前周开始、不得晚于报告资料截止。月末可以晚于cutoff；月累计仍仅取业务系统截至该时点的实际数。sales_ids须与本报告成员完全相同且不重复；如顶层business_month也存在，两处须一致。净营收允许扣退款后为负，目标正数或null；程序只算 `target_attainment=net_revenue/target`，不从周数据外推或累计重复快照。输出为 `business.monthly`，保留原字段及达成率；当前月度合同仅团队级，不能把团队月累计当个人值。

月累计可另提供同结构 `monthly.pace`，其as_of须匹配 `monthly.period.cutoff`，输出使用当月累计净营收和月目标计算。周与月的截止和进度分别显示；不得用本周进度代替整月进度，未提供月基准时保持null。

## 4. 团队标准交付

`build` 生成一个新目录，内含：

- `team-results.json`：`skill3-supervisor-results/1.0`。包含来源绑定、完整cases、queue、advisor_queue、decision_log、source_must_follow、team_topics、advisor_focus、business、limitations、provenance、team_analysis_id。
- `report.html`：本地参考页面，经营总览与顾问带教两页；案例由卡片展开。引用片段不等于聊天全文。
- `run.json`：运行版本、来源分析、输入摘要及产物完整性记录。
- `TEAM-DELIVERY.json`：完成凭证与文件校验值；独立verify通过才消费。

`queue` 是全部主管关注，`advisor_queue` 是顾问自行执行；两者均有rank，从1起。`homepage_limit=3`仅限制首屏展示，不截断结果。`decision_log`保留全部案例的纳入或排除原因。`source_must_follow`保留原Skill全部必须跟回名单，不能把它误当主管必须逐案细读名单。

0.7.36在上述队列形成时读取可选源contact_status：已确认暂时失联的普通追单另列暂停清单，不挤当前重点首屏；已付课程责任或明确核查仍保留并说明原因。全量cases、decision_log、source_must_follow及未结商机不删除。具体轮次输入、时间边界及恢复依据见[联系状态规范](followup-contact.md)；没有评定不冒充“联系正常”。

每个cases项保留source原案例、decision管理选择、manager_question原主管问题、action原下一动作。业务指标在business分区，不反写源AI判断。个人训练保留source计划，主题成员按销售＋案例＋源analysis_id可定位。

`source_skill_version`是成员报告的版本；`runtime.skill_version`是团队模块实际版本。模型生成方写真实name；当前模块不验上游API调用日志，`model_coverage=not_checked`、`human_approval=not_provided`不能改成已通过。此状态不否认公司已有接口，只表示这一份结果没有真实调用/认可证据。

不同结果使用新目录；同内容可重试。发布前暂存校验失败不能留下完成凭证，不覆盖不同内容的既有成功目录。verify核对交付文件完整性、输入和来源摘要的内部一致性、运行记录绑定及页面分析编号；不会重开上游成员或逐条解析页面文字证明语义正确。文件校验值不是外部API签名或人工认可。

输出不得位于任一源成员交付目录内部，避免破坏原四件套。CLI会自动保护来源；如直接用Python接口，prepare/build返回对象保留内存中的来源绑定，重新从JSON读取后调用publish/write_request须显式传入member_deliveries，不能丢失源目录保护。团队运行记录同时固定新模块脚本、Skill入口及两份主管规范的指纹。

## 5. 数据部门页面映射与验收

| 页面区域 | 读取来源 |
| --- | --- |
| 经营总览数字 | business.monthly展示团队月累计；business.team / business.advisors / targets展示明确标注的周数据；空值显示待补 |
| 今日关注 | queue前3条及完整展开入口；不以原must_follow总数替代 |
| 带教提示 | advisor_focus中的原plan及管理选择原因 |
| 个人指标图 | business.advisors；按各自目标达成比例绘图，实际金额/比率与目标明示 |
| 全团队培训 | team_topics，分别显示缺口举证数与涉及顾问数 |
| 每位顾问模块 | advisor_focus；其余原计划保留在源单顾问报告，BI需另接该入口 |
| 案例与聊天 | cases.source.evidence、原source成员分析；详情按需展开layers（含diagnostic_nodes/training/library）、recovery话术/条件/推进信号、trial_warning；完整聊天另接原始消息查询接口 |
| 暂停普通追单清单 | 本期paused_contact与opportunity_pool.entries中contact_routing.paused的未结项联合去重；身份待核是并列信息，不能遗漏 |

主管的一问用于定位工作是否做实，不等于客户需要重新答题。对外客户消息、老师协调、主管指派由人确认执行。本模块没有自动发送、定时任务、数据库、授权管理或BI部署；数据部门负责接入与状态保存。

验收分别记录：文件/计算检查、这批已知聊天回放、实际DeepSeek端到端运行、主管语义复核、后续执行效果。前两项通过不能代替后三项。新周不要复制旧客户名单或训练结论；重新产生并保存request与review后再build。

## 6. 跨周未结商机输入与结果

首次建立基线可不提供历史。后续每日/每周的prepare和build同时传入 `--previous-team-delivery <上次成功团队目录> --require-history`。require-history启用时缺前期目录即拒收，防止周一误建新基线；它不会自动寻找公司数据库。数据部门负责保存并传入最新成功快照，缺失时恢复历史，不能自行去掉守卫重跑。

prepare中的previous_team为null或 `{team_analysis_id, results_sha256}`，previous_result提供已核的上一份团队结果，供本轮阅读。成员与上期摘要共同绑定request_id；更换前期基线须重新prepare和review。上一期不会被当作“本周成员报告”混拼，旧统计周的数字也不会自动加进本周。旧来源不能晚于当前截止，时间口径须一致。输出目录同样不能侵入前期交付目录。

新增两个团队结果分区，均与当期cases/decision_log分开：

- `opportunity_pool`：`schema_version=skill3-opportunity-pool/1.0`；包含as_of、baseline_only、history_coverage、baseline_start、entries。history_coverage可为not_provided、previous_snapshot_only、provided_chain；最后一种只表示接上已给快照链，不认证公司全部历史已经齐全。
- `history_followup`：current、unrefreshed、waiting、temporary_unreachable、closed_this_run、identity_pending六个数组；数组值是pool_id，可在entries定位。current是本期有新标准判断且值得主管/顾问处理的往期未结案；unrefreshed是本期未提供新快照且原有管理/付款/必须跟回依据的旧案；其余未结等待折叠，纯欢迎语不自动挤上提醒首屏。temporary_unreachable分组不能独自代替完整暂停清单，因为身份待核项还需按联系状态并列展示。

每个entries项保留 `pool_id / identity_key / identity_status / sales_id / sales_name / case_id / name / first_tracked_week / last_observed_cutoff / last_source / status / is_open / refresh_status / is_prior / state_note / retained_status_basis / snapshot`。last_source包含原analysis_id、sales_id、case_id；snapshot是该需求最近的标准案例与管理决定，包含source、decision、manager_question和action，不递归嵌套全部旧团队报告。

first_tracked_week是首次纳入管理的周，不能重命名为真实添加日期。稳定键优先公司customer_key+opportunity_id，其次真实账号account_id+customer_id+opportunity_id；每次导出不得重建需求编号。身份不全、重复归属或未确认转派列待核，不凭昵称合并。pool_id只是稳定键摘要，不是公司新增订单编号。

open/waiting/dormant/unknown保持未结；明确同需求正式购买为won，有源理由与证据的结束为closed。首次none不入池；已有未结变none不自动关闭，state_note与retained_status_basis保留需核实的旧状态依据。attention=historical仅训练分类，不是商机状态。已结束同需求不得无恢复依据重开；独立新需求应另编号。

本期缺案保留原快照并标refresh_status=unrefreshed，不伪造新分析或将旧预警时长冒充今天重算。若本期有新数据，需要先由原Skill和已有历史接口更新逐案事实、订单/完课与下一动作，再进入本团队层。真实来源不足时，先核订单和课况，不能继续声称一定未付款或一定仍有希望。

首次无前期输入时页面明确“建立本期基线／上期清单未接入”；这不是往期机会为零。往期模块允许展开全部保留项和结束依据，主屏保持简短。每日保存最新成功完整团队目录，周一、月初不清空；客户的成交仍按实际时间进入周/月业绩，不按入池周挪回过去。
