# 留学辅导销售助手

为留学课程辅导销售提供下一步建议、客户参考话术和聊天记录复盘。实时带单一客一对话，销售审核后发送；不会自动联系客户或收款。

**当前公开试用版：0.7.34-public.1，对应内部规则0.7.34。** 本轮固定版本投入实际使用，依据真实反馈继续观察，不宣称已证明成交提升或能够替代成熟顾问。

## 下载与使用

- [完整Skill安装包](https://github.com/HDCareer/study-abroad-sales-coach/releases/download/v0.7.34-public.1/study-abroad-sales-coach-public-v0.7.34-public.1.zip)：保留全部目录，不要只复制SKILL.md。
- [Gem知识备用包](https://github.com/HDCareer/study-abroad-sales-coach/releases/download/v0.7.34-public.1/study-abroad-sales-coach-public-Gem-v0.7.34-public.1.zip)：先解压，再按所用界面上传文本知识文件；不要把ZIP直接当聊天附件使用。
- [安装与升级说明](docs/INSTALL.md)
- [团队试用与反馈记录](docs/TEAM-TRIAL.md)
- [发布记录](https://github.com/HDCareer/study-abroad-sales-coach/releases/tag/v0.7.34-public.1)

公开版包含五阶段、三性五定、48个场景及301段参考话术，保留单客带单和按销售分别复盘的能力。真实价表、内部客户分类标准、业绩目标、供应商及客户记录不在公开包中。实际使用时私下补充[本机构业务信息](references/organization-policy.example.md)，只补当前决定需要的项目。

## 本次更新

- 连续客户管理：首次添加只计一次，连续跟进、断联回流、原订单服务及独立新需求分别判断，历史结果和未结动作接续。
- 可靠性修复：保护已确认付款、完课和成交事实；按事件日期统计交易；固定批次与期末状态分离；改期改派留痕，已解决客户问题核销。
- 分析追溯：记录实际输入和运行规则指纹，可核对上游真实模型日志与资料覆盖；没有日志如实标未知。
- 完整交付：同一目录生成 report.html、results.json、run.json、DELIVERY.json，支持独立校验、同内容重试和失败隔离。
- 保留Daily、两层带教、申诉复核、必须跟回名单及48场景、301段话术方法。

公开版不含作者机构价格、截图、分类门槛、绩效目标、客户资料或内部留存/预警默认值，需使用者配置本机构规则。API采集、模型调用、持久状态、通知及标签回写需由使用方接入；文件与合成检查不代表真实判断准确率或平台已上线。

## 开始带单或复盘

已有客户材料时，提供最新对话及必要业务回传，输入“接下来怎么回”。没有材料时，可以输入“开始体验”使用内置虚构例子；示例金额和服务不能用于真实报价。

批量复盘：上传经授权、去掉无关身份信息的聊天记录，说明“按销售分别复盘，优先找补救单”。首次补充本机构统计口径，不把缺失信息补成成交或无效客户。

自动导入XLSX需要Python和openpyxl；固定HTML报告需要本地Python执行与文件权限。纯文本知识方式可输出文字/表格，不代表执行了脚本。平台安装和读取能力须在实际环境确认。

## 旧版本与资料保护

历史Release和原下载链接保留，旧包内容不改写。升级需要更新使用中的资料并新开客户对话，旧下载副本不会自动变新。

客户聊天、联系方式、订单、真实价格和内部文件应保存在机构授权的私有位置，勿上传GitHub或公开Issue。公开反馈只提交可公开的改写例子，并区分模拟与真实观察。[反馈入口](https://github.com/HDCareer/study-abroad-sales-coach/issues/new?template=feedback.yml)

本版检查文件结构、引用、打包一致性与公开资料边界；不宣称已完成各平台安装验收或真实销售验证。使用许可见[LICENSE](LICENSE.md)。
