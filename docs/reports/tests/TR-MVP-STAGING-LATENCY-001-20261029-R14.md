---
record_id: TR-MVP-STAGING-LATENCY-001-20261029-R14
record_type: test
revision: R14
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: 40f39665b03a67712384dec13fec06c0c25ba2bf
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R12.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-03, AC-06]
environment: Windows isolated source and release worktrees, Next 16.4.2 production browser with synthetic API, staging Rootless Docker and public gateway
created_at: 2026-10-29T05:20:00+08:00
updated_at: 2026-10-29T05:20:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R13.md
---

# 测试范围与结果

`TEST_LAYOUT=centralized`。先用浏览器用例复现详情 429 后没有重试按钮，再修复组件。主线代码提交 `56c8c86d` 在生产构建服务器运行 `node --test ../tests/frontend/browser/workspace-experience.test.mjs` 50/50，`npm run test` 51/51，`npm run typecheck` 和 `npm run build` 通过，`npm run lint` 为 0 error/8 条既有 warning；最终 PR head `40f39665` 仅额外修改产品文档，组件 blob 未变，`git diff --check` 通过。

性能专用 release `eb0eedc7` 再次运行同组 50/50 浏览器、51/51 契约、typecheck、build、lint 0 error/8 warning 和 diff check。合成 429 用例证实详情和物流失败时订单号仍在、点击重试后各增加一次只读请求并恢复字段，测试中发送调用数为 0；没有触发真实 TikTok 限流或真实买家消息。

PR #612 的最终 head 对应 CI run `40767804440`：Backend job `123096571658`、Frontend job `123096572270` 均 runner 空、0 steps 且标为 failure；**CI 未运行**。按项目已批准的零步骤本地替代门禁记录，不计 CI 通过。后端套件、迁移与 AI eval 不适用于此次纯前端详情重试；接口和安全配置未修改。

# Staging 现场

原运行前端为 `sha256:f2294806…5a83d`。私有备份权限和 PostgreSQL/MinIO 可读性、精确镜像摘要与 OCI revision、源目录干净及两文件 release diff 通过；`ValidateOnly=validated`、`Deploy=passed`。部署后 12 容器运行，后端与前端健康，迁移头已应用，单店人工发送及各安全开关未变。公网 `/healthz`、`/v1/health`、`/v1/health/ready`、`/workspace` 均 200；四条非配对单样本 TTFB 为 1.411、1.560、1.596、1.705 秒，只作诊断。证据见 [机器记录](../../../release/evidence/staging/crm-staging-order-detail-retry-20261029.json)。

# 未完成与复测条件

已登录 in-app browser 的 `getTab` 在 30 秒超时，故本次真实订单画面为 `UI_UNAVAILABLE`，不冒充已验收。真实并发 401、跨店和买家身份的全站精确回显、匹配的冷热用户可见耗时、真实失败/429 与 WAN 改善仍缺；公网 p50/p95 在已证实的链路抖动期间仅作诊断，不作为应用改动的绝对阈值。结论为局部修复和部署通过，整体 `PARTIAL / VERIFYING`。
