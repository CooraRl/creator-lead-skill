# 更新日志

## 2026-11-23

将可运行的创作者获客引擎（落地页、同意记录、去重、意向评分、webhook 队列、邮件确认 / 培育 outbox、一键退订、漏斗报告与脱敏导出）作为本仓库的主体，替换此前仅含流程提示词与示例数据的版本。

源码以作者提供的完整程序包目录为准，并做了安全与运维修正：

- 退订令牌在数据库中改为 SHA-256 存储，邮件正文仍使用一次性明文令牌。
- 落地页提交校验 `Origin` / `Referer`（若请求携带这些头），并要求至少填写邮箱或微信号。
- 默认导出脱敏；完整个人信息需显式 `--include-pii`。
- Webhook 仅允许 http(s)，默认拒绝回环 / 私网地址，并禁止跟随重定向，降低 SSRF 风险。
- 数据目录与 SQLite 文件尽量使用较严格权限（0700 / 0600）。
- `assets/docker-compose.example.yml`：主机端口绑定 `127.0.0.1`，修正 worker 与 `ENTRYPOINT` 冲突，默认不带 `--send`。
- 增加 `CREATOR_LEAD_WEBHOOK_ALLOW_PRIVATE` 与 `CREATOR_LEAD_SMTP_STARTTLS` 供本地调试。
- `purge --dry-run` 与文档对齐（默认仍是检查、不加 `--apply` 不删除）。
- 导入示例标记为【示例】并带 `is_sample: true`。

已知限制：本环境没有 Docker / Podman，compose 示例已按文件审查修正，但未在容器中实际启动。生产域名、真实 SMTP、HTTPS 与隐私政策地址需由仓库所有者自行配置，不要把密钥提交进 Git。
