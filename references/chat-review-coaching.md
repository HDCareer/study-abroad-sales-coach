# 两层销售复盘、话术映射与改进记录

主管批量复盘采用以下默认标准：批量复盘与Skill评估使用相同两层，作为主管批量报告的默认组成。先判断销售选的方向是否合理，再检查客户可见表达是否完成该方向；不是将所有未成交归为话术没背熟。

## 两层与证据

第一层检查需求、客户当前决定、真实阻碍、方案选择和下一动作。依据销售实际发言/动作判断其表现，不声称读到内心。第二层检查针对合理判断组织的理由、顺序、具体性、针对性和必要回答。方向错误时先纠正第一层；另有独立表达缺口才同时标第二层，不能把同一个问题换名字扣两次。

每层分为可见缺口、未见明显缺口、证据不足、本案不适用。另保留执行标签，记录付款入口、回传、约定等兑现情况；它不是新增培训阶段。主问题可为判断、表达、两层、执行、无明确缺口或证据不足。成交案也可有过程缺口，未成交案也可有良好判断；结果不反推唯一原因。

## 对应到原库

按本案事实选择实际读过的培训规则或原话术，保留来源文件、场景/标题、原Word段落定位（若有）、逐字短摘录和本案引用。生成器检查摘录确实存在于对应材料。原库引文与后加运行规则明确分开标注；不能把运行说明冒充原话术逐字摘录。来源须直接支持所标缺口，例如响应超时对应响应规则，不用师资匹配规则代替。来源适用性由Skill判断，不能仅按关键词匹配。

采用状态：未体现、只做了部分、时机/条件用错、已恰当体现、证据不足、不适用。这里评价可观察的使用结果，不能据此断言没有学习、懒惰或拒绝执行。表达不同但完成同一论证可算采用；照抄但不适用不能算掌握。一般课后跟进不能机械套“试听好但正式贵”，直接询价也不自动成为价格异议。

训练动作按问题决定：第一层练读案、辨阻碍和方案选择；第二层在正确判断下练原段逻辑与本案改写；执行缺口练具体任务和回报节点。背诵可作为准备，验收须看是否在适用情境完成正确动作。每人最多三个本期重点，给案例、练习、通过标准和下一批的观察项。训练状态默认为建议，未发生的培训、员工反馈或效果不能写成已完成。

## 批次校正与连续观察

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
