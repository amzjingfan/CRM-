---
record_id: TR-MVP-STAGING-LATENCY-001-20261029-R11
record_type: test
revision: R11
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: eab7e2c207308fde34be1ca50f25d32be1670cfa
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R10.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
environment: Windows local isolated worktree, Node frontend, Next 16.4.2 production build, Chromium mocked API
created_at: 2026-10-29T02:18:00+08:00
updated_at: 2026-10-29T02:18:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R10.md
---

# 范围与结果

`TEST_LAYOUT=centralized`；新增契约及浏览器测试均位于 `src/tests/frontend/`。先添加并发刷新浏览器测试，旧实现失败为 2 次刷新；再添加迟到只读 POST 契约测试，初版修复仍失败为 2 次刷新，补白名单后通过。测试使用合成响应，无真实凭证、平台调用或消息发送。

- `npm run test`：51/51；覆盖并发 401 只刷新一次、迟到 GET 与订单详情 POST 复用新 Cookie、原幂等键不变、刷新失败后两请求均拒绝。
- `npm run typecheck`：通过。
- `npm run lint`：0 error、8 条既有 warning，未新增违规。
- `npm run build`：Next 16.4.2 生产构建通过。
- `UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui`，在本地生产构建服务器运行：129/129；包含已过期门店并发请求恢复及全站现有浏览器回归。
- `git diff --check`：通过。

本次前端专用改动未运行后端测试、迁移或真实 TikTok API；其契约和服务端权限未改变。当前结论仅为本地应用回归通过，staging 尚未部署本次修复，现场端到端耗时、全站冷热、跨店、故障与限流验收仍缺。WAN/隧道抖动期间公网 p50/p95 仅作诊断，不作为该应用改动的绝对阈值，整体任务保持 PARTIAL/VERIFYING。
