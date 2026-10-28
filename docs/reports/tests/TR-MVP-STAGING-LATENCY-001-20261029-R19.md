---
record_id: TR-MVP-STAGING-LATENCY-001-20261029-R19
record_type: test
revision: R19
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: 053ebc9f625042e6c38c3c3c10df6e4c9e0284ba
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R15.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
environment: local frontend dev and production build; synthetic browser responses only
created_at: 2026-10-29T06:58:00+08:00
updated_at: 2026-10-29T06:58:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R18.md
---

# 看板局部回显验证

新增浏览器用例让店铺名称响应保持未返回，授权当前用户与看板指标正常返回。旧实现 `node --test --test-name-pattern='dashboard shows authorized metrics before store names return' ../tests/frontend/browser/ui-regressions.test.mjs` 在约 4.7 秒内以 2 秒指标可见超时失败；改动后同一用例通过，看板指标先于店铺名称显示。名称响应包含未授权店铺时，最终选择器仅保留授权店铺。

本次源码 `053ebc9f`：四条看板浏览器用例通过；前端契约 `npm test` 51/51；开发模式全浏览器 132 通过、1 个仅生产构建执行的用例跳过；`npm run build`、`npm run typecheck` 通过，`npm run lint` 0 error、8 个既有 warning；生产构建在 PowerShell 设置 `UI_CACHE_EXPECT_PRODUCTION=1` 后运行 `npm run test:ui`，133/133。`git diff --check` 通过。浏览器数据全部为合成响应，无真实平台调用和写入。

这些结果证明浏览器端不再把店铺名称作为看板指标前置条件，不能证明 staging 或公网实际快了多少。本次未发布；真实冷/热、跨店、并发 401、平台 429/失败和首次内容回显计时未在此次验证。网络抖动期间公网 p50/p95 仍只作诊断。整体任务状态 `PARTIAL`、`VERIFYING`。
