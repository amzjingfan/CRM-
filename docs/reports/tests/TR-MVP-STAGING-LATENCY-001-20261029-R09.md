---
record_id: TR-MVP-STAGING-LATENCY-001-20261029-R09
record_type: test
revision: R09
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: c1fcc1c74dbb073b2d560c178499b2ac5ec99f2e
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R09.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-05, AC-06]
environment: local production Next.js and backend full suite; isolated staging linux/amd64 release and authenticated browser
created_at: 2026-10-29T01:25:00+08:00
updated_at: 2026-10-29T01:25:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R08.md
---

# 源码与本地门禁

`TEST_LAYOUT=centralized`。源码 subject `c1fcc1c7`：前端类型、构建、48/48 契约、128/128 生产浏览器通过；lint 0 error、8 个既有 warning。后端 `uv lock --check`、全量 Ruff、466 文件格式、mypy 252 源文件通过，`uv run pytest` 为 2325 passed、55 skipped（平台/PostgreSQL 前置条件）、2 个弃用警告。专用 release `18cea7f2` 的前端 48/48 契约、124/124 生产浏览器、类型/构建通过，后端授权安全 17/17 和目标静态检查通过。旧实现对慢双请求、失败刷新、成功删除即时移除的回归先失败，修复后通过。PR #599 和 #600 的 GitHub CI 两作业均 runner 空、0 steps 失败，**未计为 CI 测试通过**；本地等价结果记录在 PR #599。

# staging 发布和只读验证

前后端镜像 linux/amd64、revision `18cea7f2`、本地/远端 RepoDigest 匹配。Git bundle 两端 SHA 核对、远端 checkout 干净。私有备份环境、PostgreSQL、MinIO 文件均 `0600`、目录 `0700`，备份可读。`ValidateOnly=validated`、`Deploy=passed`，迁移头仍为 `034_agent_debug_runs`，12 容器运行，三个公网健康接口 200。实际 backend/frontend 为新摘要；检索、解析摘要及原单店人工发送、Webhook 读取、翻译、Agent 调试、自动回复关闭、高风险写入关闭保持。公网 `/settings/stores`、`/workspace`、`/dashboard` 为 200；未认证新 API 为 401。已登录浏览器门店页显示一条授权行；只读刷新后浏览器工具 60 秒超时，现场刷新结果 `UI_UNAVAILABLE`。未发送消息、退款或部署 production。

部署前未认证门店 HTML：业务机回环 30/30 200，TTFB p50/p95 0.005/0.013 秒；入口隧道 29/30 200，1 条 20 秒超时，p50/p95 1.694/7.341 秒；公网 4/5 200，成功样本 2.059–8.968 秒，另 1 条 15 秒超时。部署后公网同路由 5/5 200，TTFB 1.212、1.408、1.496、1.848、1.927 秒。样本少、未配对，且不是认证 API；不能将其推断为已登录用户的普遍提速。

# 结论

本次隔离发布和安全门禁通过，已登录首次门店表回显可见。本地回归证实慢请求/503/403、旧响应与成功写入的行为；现场刷新、同条件冷/热、跨店、故障/限流全站验收仍缺，WAN/隧道抖动未解决。按用户修订，公网 p50/p95 在网络异常期间仅作诊断。整体任务仍 `VERIFYING / PARTIAL`。全部低敏发布证据见 [JSON](../../../release/evidence/staging/crm-staging-stores-progressive-20261029.json)。
