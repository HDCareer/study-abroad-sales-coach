# 有效性逐项证据与更新

公开版不包含作者机构的业务分类标准。使用者先在私下提供本机构有效、优质、无效、覆盖、授课语言、可交付、质量信号、失联及报价后沉默的定义，缺少关键标准时保持相应待核。不能从示例、脚本或作者机构补默认门槛。

## 逐项判断与结论

沿用high/effective/pending/scope_unknown/invalid五状态；逐项记录真实回复、具体需求、覆盖、交付、授课语言和学术诚信的yes/no/unknown等状态、理由与本案refs。优质的强/辅助信号按机构确认的实际定义取用；不把未成交、嫌贵或报价后沉默自动判为无效。系统提示与真实用户回复分开；看不到图片/语音内容不能猜，但真实发送行为不能当从未回复。

新分析在validity.assessment保留version="validity-evidence/1"、policy_version、identity、as_of、status、reason_code、coverage、criteria、quality_signals、lost_evidence、transition、next_review。identity含basis和来源account_id/customer_id；缺稳定身份basis=unknown、customer_id=null，不冒充跨批关联。coverage含history、note、missing；criteria恰好reply/need/scope/delivery/language/integrity，每项state/explanation/refs。quality_signals每项kind/explanation/refs；同事实不重复当多个信号，程序仅检查数量/引用，不能证明语义。

如机构确认采用优质等级，在assessment.policy明确quality_signal_min_count和quality_strong_min_count（正整数）；没有配置不得输出high。如机构确认从未回复的失联规则，policy提供lost_after_hours（有限正数）、minimum_followups（正整数），lost_evidence提供first_contact_ref和follow_up_refs；历史、角色与时间都需支持。此处无作者机构默认值。

可选validity.price_silence含state（yes/no/unknown）、as_of、price_refs和reason；仅在本机构定义成立且客户已有效时组合显示等级与报价消失，强等级优先、不重复计数。报价后已真实回复或资料不足时不强判消失，程序不自行设沉默时限。

## 机器可读结果（可与管理报告共同使用）

同一份分析生成报告和[统一结果](review-results.md)。统计期末与最新资料截止分别保留。transition有可追溯旧快照时才填previous_status/previous_as_of/previous_policy_version/previous_reason/previous_refs/kind/refs/reason；kind为new_evidence/correction/policy_update。新消息不倒填旧时点，政策更新须明确新版本。新情况不自动计原AI误判，人工纠错按[复核规则](appeals-and-review.md)执行。

独立源核对使用报告生成器的source选项；未提供源只能声称结构与引用检查。所有原话、身份、报告与跨周档案按本机构授权范围和保留期限保存在私有位置，不进入GitHub。代码不连接平台或认证复核权限，不用结构通过冒充准确率。
