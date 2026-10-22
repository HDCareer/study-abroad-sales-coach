# 留学辅导销售助手

为留学课程辅导销售提供下一步建议、客户参考话术和聊天记录复盘。实时带单一客一对话，销售审核后发送；不会自动联系客户或收款。

**当前公开试用版：0.7.22-public.1，对应内部规则0.7.22。** 本轮固定版本投入实际使用，依据真实反馈继续观察，不宣称已证明成交提升或能够替代成熟顾问。

## 下载与使用

- [完整Skill安装包](https://github.com/HDCareer/study-abroad-sales-coach/releases/download/v0.7.22-public.1/study-abroad-sales-coach-public-v0.7.22-public.1.zip)：保留全部目录，不要只复制SKILL.md。
- [Gem知识备用包](https://github.com/HDCareer/study-abroad-sales-coach/releases/download/v0.7.22-public.1/study-abroad-sales-coach-public-Gem-v0.7.22-public.1.zip)：先解压，再按所用界面上传文本知识文件；不要把ZIP直接当聊天附件使用。
- [安装与升级说明](docs/INSTALL.md)
- [团队试用与反馈记录](docs/TEAM-TRIAL.md)
- [发布记录](https://github.com/HDCareer/study-abroad-sales-coach/releases/tag/v0.7.22-public.1)

公开版包含五阶段、三性五定、48个场景及301段参考话术，保留单客带单和按销售分别复盘的能力。真实价表、内部客户分类标准、业绩目标、供应商及客户记录不在公开包中。实际使用时私下补充[本机构业务信息](references/organization-policy.example.md)，只补当前决定需要的项目。

## 本次更新

- 同步0.7.17至0.7.21的表达调整：日常客户稿最多200个非空白字符、最多三段，完整综合方案保留例外；强调信息取舍、自然衔接、具体帮助与避免重复。
- 同步0.7.22的业务协作：回传逐项对应承诺，具体服务按范围和权限协商，有真实师资资料时提醒销售主动发送。
- Gem核心知识包含当前全部非场景参考，包括微信表达和聊天复盘文件，避免上传旧核心漏掉新规则。

销售判断框架保持。简短、流畅或模拟客户认可，都不等于实际销售效果；复杂价值异议、推荐稳定性和人工改写负担仍需观察。

## 开始带单或复盘

已有客户材料时，提供最新对话及必要业务回传，输入“接下来怎么回”。没有材料时，可以输入“开始体验”使用内置虚构例子；示例金额和服务不能用于真实报价。

批量复盘：上传经授权、去掉无关身份信息的聊天记录，说明“按销售分别复盘，优先找补救单”。首次补充本机构统计口径，不把缺失信息补成成交或无效客户。

自动导入XLSX需要Python和openpyxl；固定HTML报告需要本地Python执行与文件权限。纯文本知识方式可输出文字/表格，不代表执行了脚本。平台安装和读取能力须在实际环境确认。

## 旧版本与资料保护

历史Release和原下载链接保留，旧包内容不改写。升级需要更新使用中的资料并新开客户对话，旧下载副本不会自动变新。

客户聊天、联系方式、订单、真实价格和内部文件应保存在机构授权的私有位置，勿上传GitHub或公开Issue。公开反馈只提交可公开的改写例子，并区分模拟与真实观察。[反馈入口](https://github.com/HDCareer/study-abroad-sales-coach/issues/new?template=feedback.yml)

本版检查文件结构、引用、打包一致性与公开资料边界；不宣称已完成各平台安装验收或真实销售验证。使用许可见[LICENSE](LICENSE.md)。
