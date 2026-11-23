# creator-lead-skill

面向创作者的开源获客技能与可运行引擎：把内容引流到**你自己的落地页**，在用户明确同意后完成去重、意向评分、高意向 webhook 队列、邮件确认 / 培育、一键退订、漏斗报告和脱敏导出。

本仓库按 [MIT License](LICENSE) 发布，Copyright 2026 CooraRl。合规硬性规则见 [COMPLIANCE.md](COMPLIANCE.md)。给 Agent 用的技能说明是 [SKILL.md](SKILL.md)。

它**不会**自动发私信、自动评论、自动发布内容，也不会替你登录社交平台。社交平台文案始终是草稿，由你在官方客户端手动发出。

## 流程

```text
内容吸引
  -> 自有落地页提交（默认未勾选的同意）
  -> 去重
  -> 意向评分
  -> 高意向 webhook / CRM 队列
  -> 邮件确认与分层培育（outbox，默认可预览）
  -> 一键退订
  -> 漏斗报告与导出
```

## 快速开始

需要 Python 3.12+（本机测试使用 3.13）。无第三方 PyPI 依赖。

```bash
cp assets/campaign.example.json campaign.json
cp assets/env.example .env
# 按需编辑 campaign.json 里的活动名、资料链接、隐私政策地址
# 不要提交 .env、campaign.json 或数据目录

python3 scripts/creator_lead.py init \
  --config campaign.json \
  --data-dir .creator-lead-data

python3 scripts/creator_lead.py serve \
  --config campaign.json \
  --data-dir .creator-lead-data
# 默认只监听 127.0.0.1:8787
```

浏览器打开落地页，勾选同意后提交。然后：

```bash
# 只预览到期的邮件 / webhook，不外发
python3 scripts/creator_lead.py worker \
  --config campaign.json \
  --data-dir .creator-lead-data

# 确认 SMTP 与 webhook 后才真正发送
python3 scripts/creator_lead.py worker \
  --config campaign.json \
  --data-dir .creator-lead-data \
  --send

python3 scripts/creator_lead.py report \
  --config campaign.json \
  --data-dir .creator-lead-data

python3 scripts/creator_lead.py export \
  --config campaign.json \
  --data-dir .creator-lead-data \
  --output /tmp/leads-masked.csv
```

导入评论或私信前，先由你本人从有权查看的后台导出或粘贴，并保持【示例】标记不被当成真实用户：

```bash
python3 scripts/creator_lead.py ingest \
  --config campaign.json \
  --data-dir .creator-lead-data \
  --file assets/lead-import.example.json
```

运维细节见 [references/operations.md](references/operations.md)。

## Docker

示例文件在 `assets/docker-compose.example.yml` 与 `assets/Dockerfile`。镜像以非 root 用户（uid 10001）运行，健康检查访问容器内 `/health`。

```bash
cp assets/campaign.example.json campaign.json
cp assets/env.example .env
docker compose -f assets/docker-compose.example.yml up --build
```

示例把主机端口绑在 `127.0.0.1:8787`，worker 默认 dry-run。确认后再自行改 command 加 `--send`。

注意：编写本说明的环境里没有安装 Docker / Podman，因此 **compose 没有在本机实际拉起**。请在你的机器上先跑 `python3 scripts/smoke_test.py`，再启动容器。

## 测试

```bash
python3 scripts/smoke_test.py
```

覆盖：未同意拒绝、缺少联系方式拒绝、跨域 Origin 拒绝、采集、去重、评分、队列、哈希退订令牌、报告、脱敏导出，以及 webhook URL 的本机 / 私网拒绝。

一次完整闭环（落地页提交 → 去重 → 评分 → webhook 投递 → 邮件 outbox 并 `--send` → 退订 → 报告 / 导出）可在本机用落地页服务 + worker 直接验证。本地 webhook 需要 `CREATOR_LEAD_WEBHOOK_ALLOW_PRIVATE=1`；本地无 TLS 的测试 SMTP 需要 `CREATOR_LEAD_SMTP_STARTTLS=0`。生产环境不要打开这两项。

## 配置要点

- `assets/campaign.example.json` 是示例：活动 id 为 `ai-career-starter`，资料名为《AI 职场入门清单》，`webhook.enabled` 为 true，`email.enabled` 默认为 false。`offer.delivery_url` 与 `privacy_url` 指向 `example.com`，上线前必须改成你自己的地址。
- SMTP 通过环境变量 `CREATOR_LEAD_SMTP_*` 配置，不要写入仓库。
- 高意向 webhook URL 只能是 http(s)，默认拒绝回环和私网地址。
- 示例导入文件已标记【示例】。

## 目录

```text
SKILL.md                      Agent Skill 入口
COMPLIANCE.md                 中文合规硬性规则
LICENSE                       MIT
agents/openai.yaml            技能元数据
assets/campaign.example.json  示例活动配置
assets/lead-import.example.json
assets/env.example
assets/Dockerfile
assets/docker-compose.example.yml
scripts/creator_lead.py       可运行引擎（标准库）
scripts/smoke_test.py
references/                   运营、合规、数据契约等说明
```

## 你还需要自己完成的事项

- 配置真实域名、HTTPS、SMTP 和 webhook 终点。
- 把隐私政策、资料交付链接改成可访问的真实页面。
- 在 GitHub 仓库 About 中自行添加 Topics（例如 `agent-skills`、`lead-generation`）。接口侧无法代为设置。
