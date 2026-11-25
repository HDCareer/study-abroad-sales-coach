# 留学辅导销售助手

为留学课程辅导销售提供下一步建议、客户参考话术和聊天记录复盘。实时带单一客一对话，销售审核后发送；不会自动联系客户或收款。

**当前公开完整版：0.8.3。** 本轮固定版本投入实际使用，依据真实反馈继续观察，不宣称已证明成交提升或能够替代成熟顾问。

## 下载与使用

- [完整Skill安装包](https://github.com/HDCareer/study-abroad-sales-coach/raw/refs/heads/main/dist/study-abroad-sales-coach-public.zip)：保留全部目录，不要只复制SKILL.md。
- [Gem知识备用包](https://github.com/HDCareer/study-abroad-sales-coach/raw/refs/heads/main/dist/study-abroad-sales-coach-public-Gem.zip)：先解压，再按所用界面上传文本知识文件；不要把ZIP直接当聊天附件使用。
- [安装与升级说明](docs/INSTALL.md)
- [团队试用与反馈记录](docs/TEAM-TRIAL.md)
- [版本清单](MANIFEST.json)

公开版包含五阶段、三性五定、48个场景及301段参考话术，保留单客带单和按销售分别复盘的能力。真实价表、内部客户分类标准、业绩目标、供应商及客户记录不在公开包中。实际使用时私下补充[本机构业务信息](references/organization-policy.example.md)，只补当前决定需要的项目。

## 本次更新

新增需求未落地状态、付款证据、同口径快照及无效合计。公开分发采用机构自配的判定门槛。

单客微信先给可发回复，再给两行备忘。新增会议场景的脱敏改写，用于需求诊断、教学分工、试听反馈、比价退出、家庭商量及交易交付。原场景库、程序交付和主管管理继续保留。

## 开始带单或复盘

已有客户材料时，提供最新对话及必要业务回传，输入“接下来怎么回”。没有材料时，可以输入“开始体验”使用内置虚构例子；示例金额和服务不能用于真实报价。

批量复盘：上传经授权、去掉无关身份信息的聊天记录，说明“按销售分别复盘，优先找补救单”。首次补充本机构统计口径，不把缺失信息补成成交或无效客户。

自动导入XLSX需要Python和openpyxl；固定HTML报告需要本地Python执行与文件权限。纯文本知识方式可输出文字/表格，不代表执行了脚本。平台安装和读取能力须在实际环境确认。

## 旧版本与资料保护

历史Release和原下载链接保留，旧包内容不改写。升级需要更新使用中的资料并新开客户对话，旧下载副本不会自动变新。

客户聊天、联系方式、订单、真实价格和内部文件应保存在机构授权的私有位置，勿上传GitHub或公开Issue。公开反馈只提交可公开的改写例子，并区分模拟与真实观察。[反馈入口](https://github.com/HDCareer/study-abroad-sales-coach/issues/new?template=feedback.yml)

本版检查文件结构、引用、打包一致性与公开资料边界；不宣称已完成各平台安装验收或真实销售验证。使用许可见[LICENSE](LICENSE.md)。
