# 安装与第一次检查

## Gemini：有 Skills／技能入口

1. 下载 Release 中的 `study-abroad-sales-coach-public-v0.7.15-public.2.zip`。不要只下载单个SKILL.md，否则参考资料不完整。
2. 在自己的浏览器打开 https://gemini.google.com 。侧栏找到 Customize／自定义；没有时查看 More／更多，再进入 Skills。
3. 点 Upload／上传。选“文件”时上传这个ZIP；如果窗口标题是“选择要上传的文件夹”，先把ZIP解压到一个文件夹，再选择直接包含SKILL.md和references的那层文件夹，不能把ZIP当作文件夹选择。预览名称 `study-abroad-sales-coach`，保留资料后点 Create／创建，不使用自动重写来缩短规则。
4. 新开聊天，输入 `/`（新版可能为 `@`）选择这个Skill，再输入“开始体验”。
5. 应出现内置澳洲本科经济学案例的简短背景、销售建议和客户回复；示例为三小时共420澳元，全部是虚构测试条件。

Google要求账号满18岁、登录并开启Keep Activity。账号、地区及更新状态可能影响入口；请以自己的界面为准，不为了安装盲目修改隐私选项。更新资料时需重新上传完整包。

## Gemini：只有 Gems 入口

下载并解压 Gem 备用资料包。新建Gem，名称填“留学辅导销售助手”，把`粘贴到Gem指令框.txt`全文放进指令框，把`00-core.md`和8个场景MD上传到Knowledge／知识，共9个文件；LICENSE无需上传。保存后新开Gem对话，输入“开始体验”。

Gem是备用适配，读取方式与原生Skill不同，须同样做下面的检查。分享Gem会让获授权的人查看其指令和知识文件；不要在公开Gem里放真实内部资料。

## Codex 桌面端

将Skill安装包解压成`study-abroad-sales-coach`文件夹，放入自己用户目录下的`.agents/skills/`，确认该文件夹直接包含SKILL.md和references。重新打开任务，选择或输入`$study-abroad-sales-coach`。不同版本界面的安装入口可能不同，手动目录方式见官方说明。不要把客户案例放在公共仓库。

## 不只看“上传成功”

按顺序输入以下消息，保留原回复，不反复重试挑选好答案：

1. “使用 study-abroad-sales-coach 开始体验。” 看是否能用内置案例，并给实际可发送的话术。
2. “客户说：我现在最多只有300澳元，不能再加。老师还没有确认缩课是否可行。” 看是否记得原方案420澳元，不虚构300已获批或缩课已可交付。
3. “换一个客户：英国本科，只问你们每小时多少钱，没有提供我们机构价表。” 看是否把澳洲案例金额带入新客户；正确做法是指出缺少适用价格，同时帮销售承接询价。

若出现缺文件、乱报价或不读取资料，停止将其回复直接发给客户，把去身份化的结果反馈到Issues。此检查只验证基本调用、连续事实和新案隔离，不证明所有场景的销售效果。

## 官方依据与验证状态

- [Google：创建与管理Skills](https://support.google.com/gemini/answer/17094296?hl=en)
- [Google：创建Gems](https://support.google.com/gemini/answer/15146780?hl=en)
- [OpenAI：Skills](https://learn.chatgpt.com/docs/build-skills)

此版本的文件结构、引用和公开资料边界已做本地检查。Gemini账号内安装与模型效果应按上述步骤实测；文档支持上传，不等于所有账号均已完成兼容性验证。
