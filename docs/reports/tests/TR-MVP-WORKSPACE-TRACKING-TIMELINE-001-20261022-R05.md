---
record_id: TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R05
record_type: test
revision: R05
status: PARTIAL
task_id: MVP-WORKSPACE-TRACKING-TIMELINE-001
tested_sha: 97c5d6bb6f7734e27eaafcf779df8f8a0ff74541
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R05.md
requirement_ids: [MVP-WORKSPACE-TRACKING-TIMELINE-001]
acceptance_ids: [AC-05]
environment: merged-main Linux amd64 staging Rootless Docker; synthetic Chrome intercepts all workspace API calls
created_at: 2026-10-22T04:24:00Z
updated_at: 2026-10-22T04:24:00Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R04.md
---

# staging 门禁与页面结果

R04 在 subject 上的完整后端 2233 passed/29 skipped、前端契约 47 passed、生产浏览器 27 passed、Ruff/格式/mypy/typecheck/build 通过。PR #509 的两个 GitHub Actions 作业均在执行步骤前失败，无测试日志，未计为 CI 通过。

从 `main=326b1d35` 的干净源码构建两个 `linux/amd64` 镜像，源码 bundle 与镜像归档在本机和 staging 的 SHA-256 一致，导入后镜像 ID 与 OCI revision 均匹配。GHCR 两份不可变摘要核对后，原三摘要、单店人工发送与翻译模式再核对；六角色预取 `passed`、配置验证 `validated`、私有 PostgreSQL 备份 `0600` 且 `pg_restore -l` 可读、部署 `passed`。运行前后端摘要匹配候选，检索摘要未改；迁移头、固定出口、11 个容器及 `/healthz`、`/v1/health`、`/v1/health/ready`、`/workspace` 公网 HTTP 200 均通过。门禁原件留在 staging 私有目录，其 SHA-256 与低敏摘要见[部署证据](../../../release/evidence/staging/crm-staging-workspace-native-card-20261022.json)。

已部署页面运行 `UI_BASE_URL=https://staging.overselfx.com node --test --test-name-pattern='tracking popover|cross border tracking|bulk tracking translation' ../tests/frontend/browser/workspace-experience.test.mjs`：3 passed。浏览器拦截全部 `/v1/` 请求并使用合成会话；卡片草稿、人工审阅、确认后卡片 POST 与消息“查看详情”已验证，不触及真实买家。

# AC 与剩余风险

部署和合成 UI 均通过；真实登录态卡片预览及详情仍待用户确认，Codex 应用内浏览器读取连续超时，记 `UI_UNAVAILABLE`，故本报告暂记 `PARTIAL`。未向真实 TikTok 买家发送原生卡片，不声称具体店铺/订单已获平台实际接收；production 仍未放行。
