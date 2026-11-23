# 变更与审查说明

## 2026-11-23

把可运行的获客引擎并入 `skills/creator-lead/`，并做安全审查与整改。原有 `prompts/`、`platforms/`、`data/`、`COMPLIANCE.md` 和 MIT 许可保持不变。

用户在本地用 Codex 升级后的 19 个附件中，审查时盒子上实际读到并采用的是主程序 `creator_lead.py`、冒烟测试和工程合规说明。其余配置、Docker 与操作文档按主程序的字段约定和测试期望补齐，示例一律标明【示例】，不含密钥。

### 发现的问题与处理

| 严重程度 | 问题 | 处理 |
| --- | --- | --- |
| 高 | Webhook 对 `CREATOR_LEAD_WEBHOOK_URL` 没有校验，`urlopen` 还会跟随跳转，存在 SSRF 风险（可打到本机、内网或云元数据地址） | 只允许 http/https；默认解析并拒绝回环/内网/链路本地等地址；禁止跟随跳转。本地调试需显式设置 `CREATOR_LEAD_WEBHOOK_ALLOW_PRIVATE=1` |
| 高 | 若按常见方式编写 Dockerfile 并以 root 运行，容器失陷后权限过大 | 提供的 Dockerfile 使用 `python:3.13-slim-bookworm`，以 uid 1000 的非 root 用户运行；compose 把主机端口绑在 `127.0.0.1:8787` |
| 中 | 退订令牌以明文存入数据库，库文件泄露即可伪造退订链接 | 数据库只保存 SHA-256 摘要；邮件正文仍使用随机 `token_urlsafe(24)`；查找时用 `hmac.compare_digest` |
| 中 | 跨站页面可能向 `/api/leads` 发 POST，造成垃圾线索或对他人邮箱发起确认信 | 若请求带 `Origin` 或 `Referer`，必须与 `public_base_url` 同源，否则返回 403。无这两种头的本地脚本仍可用 |
| 中 | 落地页接口在缺少邮箱和微信号时，只要有留言仍可能写入线索 | `source_type=landing_form` 时必须提供联系方式 |
| 中 | 数据目录和 SQLite 文件权限跟随默认 umask，可能被同机其他用户读取 | 初始化后尝试将目录设为 `0700`、数据库文件设为 `0600` |
| 中 | `export` 默认写出完整邮箱和姓名，容易误提交到公开仓库 | 默认脱敏联系方式和姓名；`--anonymize` 再清空留言、评分理由和负责人；完整导出必须加 `--include-pii` |
| 低 | 限流器按 IP 记时间戳，极端情况下字典会变大 | 超过 4096 个键时清理过期项 |
| 低 | 日志可能带上退订 URL 中的 token | 已有脱敏，测试确认访问记录为 `token=[redacted]` |

审查中确认仍保持的设计：

- 没有硬编码密码、Token 或 API 密钥；密钥只通过环境变量读取，仓库只提供 `.env.example`。
- SQL 使用参数绑定；状态更新里拼接的字段名是代码常量，不是用户输入。
- 落地页对配置文案做了 `html.escape`，同意勾选默认未选中，并有蜜罐字段。
- 提交有请求体大小限制和按 IP 的频率限制。
- 评论/私信导入关闭自动外发（`allow_automation=False`）；worker 必须加 `--send` 才会发信或调用 webhook。
- 示例数据带【示例】或 `is_sample: true`，不编造成交数字。

### 测试

在盒子上运行：

```bash
python skills/creator-lead/scripts/test_creator_lead.py
```

结果：`Smoke test passed: consent, capture, dedupe, score, queue, unsubscribe, report, security checks.`

覆盖：拒绝无同意、拒绝落地页无联系方式、拒绝跨源 Origin、去重、高/中意向评分、确认信主题不含 `《《`、退订令牌只在邮件中出现且数据库为哈希、退订后取消队列、漏斗报表、默认导出脱敏、webhook URL 校验。

### 仍需你本人完成的事项

- 把 `public_base_url` 换成带 HTTPS 的真实域名。
- 配置 SMTP，并确认退订页可从公网打开。
- 配置 webhook / CRM 地址（必须是公网 https，不要指向内网）。
- 替换示例中的资料链接和隐私说明，确保路径真实可走通后再对外收集信息。
- GitHub Topics 仍需在仓库 About 中手动添加（连接器无法写入）。
