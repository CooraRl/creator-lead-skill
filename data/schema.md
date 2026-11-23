# 数据格式约定

这份文档定义本技能在选题、内容草稿和线索整理时使用的 JSON 形状。字段尽量与 [CooraRl/daily-ai-news](https://github.com/CooraRl/daily-ai-news) 以及 [CooraRl/ai-content-miniapps](https://github.com/CooraRl/ai-content-miniapps) 的新闻对象对齐，便于以后直接读取日报接口。

时区默认 `Asia/Shanghai`（北京时间）。`published` 是给人看的字符串，`published_iso` 便于排序。

## 总原则

- 所有将要发布的选题、文案、评分解释都必须基于真实新闻或用户提供的真实素材，**不捏造事实**。
- 仓库里的演示数据必须带 `source: "local-sample"`（或同等说明），并且每条记录 `is_sample` 为 `true`，标题、姓名或正文带「【示例】」。
- 分数使用 1–10，可保留一位小数。
- 不把 API 密钥、Cookie 或未脱敏的真实个人信息写入任何 JSON。
- 内容对象的 `status` 只能表示草稿状态；线索对象的 `do_not_auto_send` 必须为 `true`。

## 新闻 / 选题输入（与 daily-ai-news 对齐）

根对象：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `generated_at` | string | 是 | 生成时间，ISO 8601，建议带 `+08:00` |
| `timezone` | string | 是 | 默认 `Asia/Shanghai` |
| `schema_version` | string | 建议 | 当前为 `"1.0"` |
| `source` | string | 是 | `local-sample` 或 `daily-ai-news`，或用户注明的其他真实来源名 |
| `note` | string | 示例必填 | 示例数据需说明「非真实新闻」 |
| `items` | array | 是 | 新闻数组，可以为空 |

`items[]` 一条新闻：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 稳定唯一 ID |
| `title` | string | 是 | 标题 |
| `link` | string | 是 | 原文链接 |
| `source` | string | 是 | 来源名称 |
| `published` | string | 是 | 可读时间，例如 `2026-11-22 09:30` |
| `published_iso` | string | 建议 | ISO 8601 |
| `summary` | string | 建议 | 中文摘要；尚未生成时可为空字符串 |
| `is_sample` | boolean | 示例必填 | 示例必须为 `true` |
| `scores` | object | 建议 | `hook`、`anxiety`、`relevance`，均为 1–10 |
| `score_reasons` | object | 可选 | 三项分数的一句理由 |
| `hook_titles` | string[] | 建议 | 标题钩子，至少包含焦虑型、反转型各一条 |

选题排序：

```
overall = hook * 0.4 + anxiety * 0.3 + relevance * 0.3
```

完整新闻示例也可参考 ai-content-miniapps 的 `data/sample-news.json`。本仓库的 `sample-content.json` 在 `topic` 字段中嵌入了精简后的同类对象。

## 内容草稿根对象（`sample-content.json`）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `generated_at` | string | 是 | ISO 8601 |
| `timezone` | string | 是 | 默认 `Asia/Shanghai` |
| `schema_version` | string | 建议 | `"1.0"` |
| `source` | string | 是 | 示例为 `local-sample` |
| `note` | string | 示例必填 | 说明这些是虚构演示，不可当真实新闻或已发布内容 |
| `items` | array | 是 | 内容草稿数组 |

### `items[]` 一条内容草稿

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 例如 `sample-content-20261123-01` |
| `is_sample` | boolean | 示例必填 | 示例必须为 `true` |
| `status` | string | 是 | 只允许 `draft`（待人工核对后发布） |
| `platform` | string | 是 | `douyin`、`x` 或 `wechat-mp` |
| `topic` | object | 是 | 对应的新闻选题，字段与上表新闻对象一致 |
| `title_options` | string[] | 是 | 备选标题 |
| `cover_copy` | string | 可选 | 封面叠字，主要用于抖音 |
| `body` | string | 是 | 口播脚本、帖文或文章大纲 |
| `cta` | string | 是 | 领取钩子，必须是可兑现的写法 |
| `redeem_path` | string | 建议 | 真正的领取步骤 |
| `estimated_duration` | string | 可选 | 口播或阅读的大致时长 |
| `word_count` | number | 可选 | 正文大约字数 |
| `overall_score` | number | 可选 | 选题综合分 |
| `notes` | string | 可选 | 待核对项或其他提醒 |

## 线索根对象（`sample-leads.json`）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `generated_at` | string | 是 | ISO 8601 |
| `timezone` | string | 是 | 默认 `Asia/Shanghai` |
| `schema_version` | string | 建议 | `"1.0"` |
| `source` | string | 是 | 示例为 `local-sample` |
| `note` | string | 示例必填 | 说明为虚构评论 / 私信，不是真实用户 |
| `disclaimer` | string | 是 | 必须声明回复仅供人工发送 |
| `items` | array | 是 | 线索数组 |

### `items[]` 一条线索

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 例如 `sample-lead-01` |
| `is_sample` | boolean | 示例必填 | 示例必须为 `true` |
| `platform` | string | 是 | `douyin`、`x` 或 `wechat-mp` |
| `source_type` | string | 是 | `comment`、`dm` 或 `keyword_reply` |
| `display_name` | string | 建议 | 公开显示名；示例用化名并加「【示例】」 |
| `raw_text` | string | 是 | 用户粘贴的原文；公开示例必须是虚构句子 |
| `intent` | string | 是 | 仅允许 `高`、`中`、`低`、`无` |
| `intent_reason` | string | 是 | 一句判断理由 |
| `draft_reply` | string | 是 | 供用户修改后手动发送的回复；无需回复时用空字符串并在 `notes` 说明 |
| `do_not_auto_send` | boolean | 是 | 必须为 `true` |
| `related_content_id` | string | 可选 | 对应内容草稿 id |
| `suggested_next_step` | string | 建议 | 例如「发送资料路径」「人工介绍报名方式」「不必回复」 |
| `created_at` | string | 建议 | ISO 8601 |
| `notes` | string | 可选 | 脱敏说明或其他提醒 |

## 以后如何对接真实数据

- 第 2 步：当 daily-ai-news 提供 `GET /news/today` 时，把响应根对象直接作为选题输入。在此之前，由用户粘贴已生成的 JSON 或 Markdown。
- 第 5 步：**始终**由用户导出或粘贴评论和私信，不规划登录爬取接口。
- 第 6 步：复盘表可以在本地扩展一个 `metrics` 对象（播放、领取数、高意向数）。真实统计不要提交到公共仓库。
