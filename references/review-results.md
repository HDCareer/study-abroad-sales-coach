# 统一管理结果：同一分析供报告和数据部门使用

新批次默认由同一份已校验的复盘数据同时生成HTML和固定格式JSON，不能为两种交付分别作第二次判断。输入继续使用[现有数据合同](chat-review-data.md)、management、两层带教和有效性证据扩展；本页规定交付结果，不要求平台接入、写标签或建立新系统。

## 生成

```text
python scripts/render_chat_review.py <复盘数据.json> --output <报告.html> --results-output <统一结果.json> --source <独立导入的cases.json>
```

所有文件都放授权私有客户目录；有独立导入源时必须传source，没有时不伪造，结果显示not_checked。check-only只检查，不写任何输出；已有文件默认拒绝覆盖。旧版仅HTML命令继续兼容，但新批次默认同时交付两份。没有management的旧输入须先按当前规范分析，不能猜补字段后导出。

## 字段与含义

| 字段 | 含义 |
| --- | --- |
| schema_version | 固定skill3-management-results/1.0，表示交付格式版本 |
| analysis_id | 对本次分析输入和Skill版本计算的版本编号；相同输入在相同版本下得到相同编号。HTML显示相同编号 |
| skill_version、rules | 实际Skill版本和本批采用口径；逐案assessment另有业务policy_version |
| sales | 本报告唯一销售的ID与显示名 |
| period、reporting_window | 统计范围、资料截止、消息时间口径；历史周末快照与最新状态分开 |
| scope | 材料覆盖、客户队列和订单是否核齐；不能据聊天完整推订单完整 |
| source_verification | matched表示程序已逐字比对提供的独立导入源；not_checked表示未提供。该状态不证明源完整、语义判断正确或身份在原平台已核验 |
| metrics | 与管理报告相同函数计算的本周会话、有效、已确认试听付款、正式购买人数及正式均单。未知金额为null，不填0 |
| summary、coaching | 本批最多三个主管核心结论、两层带教、同类机会及建议，直接复用原分析 |
| must_follow_case_ids | 与报告末尾相同顺序的必须跟回案例编号 |
| cases | 每案结果，排除项保留原因，不混入纳入数 |
| longitudinal | 可选跨周机会定义和实际培训事件；没有时为null |
| cadence、daily | daily/weekly/period；Daily保留基线截止、优先/其他需关注、新进展、全部动作与派生状态。历史输入缺cadence按weekly兼容 |
| quality_and_cohorts | 同批成熟期、未纳入原因、按来源分开的人工复核汇总及逐项登记；无真实复核不报准确率 |

每个纳入案例包括以下字段：

- `case_id`是本批定位编号；跨批匹配使用`identity`中的来源账号与客户ID。未知客户ID为null，显示名不能冒充稳定身份。来源ID尚未独立核对时不得声称已在原平台核实。
- `validity`为当前等级、组合显示label、reason、refs、price_silence与assessment。high覆盖effective，不重复计数；price_silence=yes分别显示“优质有效—报价消失”或“基础有效—报价消失”。仅问价但需求未知仍pending。新批次明确填写附加状态，旧数据缺字段导出unknown，不从reason文字反猜。
- `week`保留截至统计期末的有效性与阶段；`current_phases`、`position`和`issue`保留最新五列、最远进展、当前阶段与主要卡点。不能用更新后的状态重写周末。
- `layers`逐案区分判断、表达、执行、对应培训与训练；旧记录无两层数据为null，不冒充未见缺口。
- `tracking`为可选的稳定需求ID与观察事件，按[跨周规则](longitudinal-review.md)填写；旧数据缺失为null，不猜补。
- `actions`、`daily_signals`、`cohort`按[Daily规则](daily-management.md)保留实际状态与来源，缺失不猜补。Daily仍保留week和metrics.week_*兼容名称，实际表示声明的本日统计期；日新增与当天购买不能直接相除。
- `trial`、`formal`、`order`分别保留已知付款、完课、正式购买、订单实收与报价。`trial_warning`复用报告预警函数，不另起计时。
- `must_follow`、`recovery`保留依据、优先级、责任动作、时点、补救草稿及适用条件。已正式购买或不宜触达不混入首次追单。
- `report_anchor`为当前管理HTML中对应case位置。`evidence`只收录上述结果实际引用的本案非敏感原话，保留消息ID、来源、时间、说话人、工作表行号或来源消息ID；不复制全量聊天。它仍属于客户资料，遵守同一授权和保留规则。

## 一致性与复核

生成器使用同一等级显示函数、周统计函数、预警函数和跟回排序，先校验再输出；不读关键词重新分类、不改AI归因。analysis_id表示同一分析版本，原始输入仍是可再生成报告的完整记录，交付JSON不是另一个可随意手改的真源。发现错误先回到对应案例和证据，记录人工复核及修改原因，再从修正分析重新生成两份结果；不只改其中一份文件。

具体执行[销售申诉与人工复核规则](appeals-and-review.md)：复核记录单独存本批私有目录，相关待核/更正说明同步写入分析现有的理由与限制字段，再统一生成。当前生成器不认证复核权限、不自动办理申诉，也不将AI草稿标成人工确认；标准变更须有具体确认依据及生效范围。

本次只固定Skill的本地输出。数据部门如何传入原始记录、接收JSON、打开后台证据位置或回写标签，仍由数据部门实现。

Daily可传`--previous-results <上期统一结果.json>`，HTML与JSON采用同一基线，analysis_id同时包含基线编号。输入前核对该历史资料仍在授权保留期内；结果JSON含引用证据，不是可以无限保存的匿名汇总。上期完整结果是日常对照输入，长期结构化趋势使用已有快照流程。人工复核和新动作须回到专业分析统一登记后重生成，不能手改交付JSON制造完成状态。
