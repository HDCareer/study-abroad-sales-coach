# 安装与升级

下载Release中的 `study-abroad-sales-coach-public-v0.7.16-public.1.zip`，保留全部目录，不只复制SKILL.md。已安装用户将旧副本留存后，用新版完整包更新所用平台的Skill；新开对话使用新版。不要覆盖自己另外添加的私有业务资料，将其保存在独立私有位置。

## 支持完整Skill的环境

在所用平台的Skill上传/安装入口选择完整ZIP；若界面要求文件夹，先解压，再选直接包含SKILL.md、references、scripts和assets的那层目录。安装后以 `study-abroad-sales-coach` 选择Skill并说“开始体验”。不同平台入口以当前界面为准，本版未逐个平台重新安装验证。

有本地文件与Python执行能力时，聊天导入需要openpyxl，HTML生成只依赖Python标准库。运行说明见[导入规则](../references/chat-import.md)和[报告数据合同](../references/chat-review-data.md)。没有执行能力时按[复盘结构](../references/chat-review.md)输出文字或表格，不伪造脚本运行结果。

## 只有Gem知识附件入口

解压 `study-abroad-sales-coach-public-Gem-v0.7.16-public.1.zip`。指令框使用“粘贴到Gem指令框.txt”，知识中上传00-core.md及8个场景文件。该备用形式用于带单和文字复盘，不执行本地导入或HTML生成脚本；读取聊天表格/图片的范围需如实确认。

## 安装后检查

1. “开始体验”：应进入虚构案例并提供实际回复，不索取已给过的信息。
2. 换一个客户询价但不提供本机构价表：应说明缺适用价格，不继承演示金额。
3. 给一小批虚构聊天并说明机构统计口径：应按销售分开，分清首课/正式单、最远/当前阶段，引用原话并给补救动作。

保留首次输出，不能以“已上传”代替实际可用检查。用真实客户材料前去掉无关联系方式、账号和验证码；不要把内部规则上传公开仓库。
