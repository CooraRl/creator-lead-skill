# Creator Lead Skill

**一套可在 Claude Code、Cursor、Codex、Grok Build 里直接调用的自媒体获客技能：按 6 步漏斗，帮你从定位、选题、写稿到整理线索，覆盖抖音、X 和微信公众号。**

它只做「内容和线索整理」，**不自动私信、不自动评论、不自动关注或取关、不自动发布**。所有回复草稿都由你本人核对后手动发出。选题和文案必须基于真实新闻或你提供的真实素材，不能编造事实、证言或数据。

本仓库的组织方式参考了 [patch-gg/pixelfx](https://github.com/patch-gg/pixelfx) 和 [CooraRl/ai-content-miniapps](https://github.com/CooraRl/ai-content-miniapps)：先给出能直接用的流程、提示词和示例数据，再用一个便携的 Agent Skill，让别人（和未来的你）按同一套规范继续做下去。

选题默认对接 [CooraRl/daily-ai-news](https://github.com/CooraRl/daily-ai-news) 的新闻 JSON 与吸睛 / 焦虑 / 相关评分。免费资料（lead magnet）可以复用 [CooraRl/ai-content-miniapps](https://github.com/CooraRl/ai-content-miniapps) 里的清单、测验和小程序模板。

## 6 步获客漏斗

| 步骤 | 目录与提示词 | 输入 | 输出 |
| --- | --- | --- | --- |
| 1. 定位与用户画像 | `prompts/01-positioning.md` | 你的领域、想提供的产品或服务、目标用户 | 用户画像、痛点、搜索词、平台选择 |
| 2. 选题 | `prompts/02-topics.md` | daily-ai-news 的真实新闻 JSON，或你粘贴的热榜 / 趋势 | 按评分排序的选题清单和内容角度 |
| 3. 内容生成 | `prompts/03-content.md` | 已选定的真实选题 | 抖音口播脚本 + 标题 + 封面文案；X 帖或串帖；公众号文章大纲。每条结尾都带领取钩子 |
| 4. 引流设计 | `prompts/04-funnel.md` | 你的免费资料、主页和私域入口 | 资料包装、简介、置顶、从公域到公众号 / 私域的路径 |
| 5. 线索整理 | `prompts/05-leads.md` | 你导出或粘贴的评论、私信（不要让 Agent 去爬取） | 意向分级表（高 / 中 / 低 / 无）和**供你手动发送**的回复草稿 |
| 6. 复盘 | `prompts/06-review.md` | 各条内容带来的线索数量和备注 | 哪条内容最有效，以及下一轮选题建议 |

完整工作流、检查清单和两个走通示例写在 [`skills/creator-lead/SKILL.md`](skills/creator-lead/SKILL.md)。平台字数、钩子写法和合规要点见 `platforms/`。硬性规则见 [`COMPLIANCE.md`](COMPLIANCE.md)。数据格式见 [`data/schema.md`](data/schema.md)。

## 快速开始

不需要安装依赖，也不需要任何 API 密钥。

1. 克隆本仓库，先读 `COMPLIANCE.md` 和 `skills/creator-lead/SKILL.md`。
2. 把技能目录放到你使用的 Agent 工具里，或直接在本仓库中对 Agent 说「请遵循 `skills/creator-lead/SKILL.md`」。
3. 按 6 步依次运行对应提示词。第 2 步优先使用 daily-ai-news 已抓取的新闻；没有接口时，也可以粘贴你确认过的真实标题和出处。
4. 把生成的文案当作草稿：先核对事实，再由你在各平台手动发布或回复。
5. 第 5 步只处理你主动提供的评论和私信。输出里的回复必须经你修改后，由你本人发出。

## 在各工具中使用这个 Skill

`skills/creator-lead/SKILL.md` 使用通用 Agent Skills 格式（YAML frontmatter 含 `name` 与 `description`），兼容 Claude Code、Cursor、Codex、Grok Build 等会读取 `SKILL.md` 的工具。

```bash
# Claude Code
cp -R skills/creator-lead ~/.claude/skills/

# 其他工具：把该目录放到对应的 skills 文件夹，
# 或直接在本仓库里对 Agent 说「请遵循 skills/creator-lead/SKILL.md」
```

然后用一句话说清当前步骤，例如：

- 「我做 AI 新闻和 AI 焦虑内容，想卖入门陪跑，先帮我做第 1 步定位。」
- 「这里是 daily-ai-news 今天的 JSON，按技能第 2 步挑 3 个选题。」
- 「按第 3 步，给这条选题分别写抖音口播、X 串帖和公众号大纲，结尾带领取钩子。」
- 「我把今天的评论粘贴在下面，按第 5 步分级，并给每条草拟我可以手动发送的回复。」

## 与另外两个仓库的联动

1. **选题来源**：[daily-ai-news](https://github.com/CooraRl/daily-ai-news) 负责抓取 AI 新闻，并规划了吸睛度 / 焦虑感 / 相关度评分与标题钩子。本技能第 2 步读取同一套 JSON 字段（见 `data/schema.md`），排序建议仍为 `hook * 0.4 + anxiety * 0.3 + relevance * 0.3`。现在可以粘贴已生成的 Markdown / JSON；以后接口就绪后再自动读取。
2. **领取资料**：[ai-content-miniapps](https://github.com/CooraRl/ai-content-miniapps) 提供可导入的内容类小程序模板，例如 AI 焦虑指数测试、职业辅助风险测试、每日名词、发布清单。第 4 步可以把这些模板包装成免费资料，而不是另起一套空洞的「电子书」。
3. **示例数据**是虚构的结构演示，标题和姓名带「【示例】」，`is_sample` 为 `true`。不能把示例当成真实新闻、真实用户或真实转化数据对外宣传。

## 内容与安全约定

更完整的条款在 [`COMPLIANCE.md`](COMPLIANCE.md)。这里是必须遵守的底线：

- 不在仓库或对话里存放密钥、密码、Token 或真实 `.env`。
- 不自动私信、不自动评论、不批量关注或取关、不爬取他人未公开数据。
- 内容与回复都只生成草稿，**不自动发布**；每条回复都由人发出。
- 不编造事实、不编造成交证言、不编造阅读量或转化数字、不制造虚假紧迫感。
- 处理评论和私信时遵守《个人信息保护法》：尽量脱敏，不要把真实姓名、手机号、微信号提交进公开仓库。

## 仓库结构

```
creator-lead-skill/
  skills/creator-lead/SKILL.md   # 便携技能正文
  prompts/                       # 6 步提示词，可单独复制使用
  platforms/                     # 抖音、X、公众号的格式与合规要点
  data/schema.md                 # 选题、内容和线索的 JSON 约定
  data/sample-content.json       # 【示例】内容草稿
  data/sample-leads.json         # 【示例】线索分级
  COMPLIANCE.md                  # 硬性合规规则
```

## 推荐的 GitHub Topics

本仓库的 GitHub 连接器暂时不能写入 Topics。你可以在仓库主页右侧 **About** 里手动添加：

`agent-skills` `content-creation` `lead-generation` `douyin` `wechat` `claude-code-skill` `grok` `ai`

## 许可

[MIT](LICENSE)。欢迎直接使用、改作，以及基于这套流程开源你自己的获客技能。

作者：[Coora](https://github.com/CooraRl)（X [@XxCoora](https://x.com/XxCoora)）。
