---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001-20261021-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001
tested_sha: 6e1f2489007b085b5a02d0aff2df6f4d2f86c44e
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001-20261021-R01.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows, Node 24.19.0, Chrome headless, local Next production build with intercepted synthetic API
created_at: 2026-10-21T03:09:31Z
updated_at: 2026-10-21T03:09:31Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

前端测试位于 `src/tests/frontend/` 集中布局；浏览器拦截 `/v1/`，使用合成订单，无真实 TikTok 调用、消息外发、退款或发券。用户截图只是预期 UI 资料，不是新版本现场验收。

# 命令和逐项结果

- `npm ci --no-audit --no-fund`：390 包安装成功。
- 首先将浏览器用例改为无需点“详情”即看到承运商，针对原源码运行失败：30 秒等待 `Carrier A` 超时；修复后该用例通过。
- `npm run lint`：0 error、4 个既有 warning；`npm run typecheck`：通过；`npm run test`：47/47 通过。
- `npm run build`：修订后的生产构建通过。
- `npm run test:ui` 对开发服务器：43 passed、1 skipped、1 failed；唯一失败是 HTML 缓存用例要求生产缓存头，不是此次订单卡问题。切换本地生产构建并设 `UI_CACHE_EXPECT_PRODUCTION=1` 后，45/45 通过。
- 收紧已完成订单物流状态映射后，生产构建再次通过，受影响两条浏览器用例 2/2 通过；未重跑无关的全部浏览器用例。
- `git diff --check`：通过。未运行 GitHub Actions。

# REQ/AC 或门禁与证据映射

- AC-01：自动载入用例在点击详情前等待承运商，且详情调用数为 1、消息发送数为 0；实现使用视口观察器，屏外不主动加载。
- AC-02：同一浏览器用例断言六项标签及实际值；状态用例验证 `IN_TRANSIT→运送中`、`DELIVERED→已送达`、`COMPLETED→空值`。
- AC-03：上述前端静态、契约、生产构建与隔离浏览器结果。
- AC-04：尚未发布 staging 或完成真实页面核对，需后续现场 TR 补充。

# 缺陷、未执行项与残余风险

当前只有合成浏览器证据；真实店铺订单若无承运商或轨迹，字段显示空值。自动请求可能增加可见卡片的 TikTok 只读调用，平台错误通过原有失败提示和重试呈现。无后端/数据库变更，因此没有运行后端或 PostgreSQL 集成回归。

# 结论和复测条件

本地前端行为和构建通过；整体任务仍因 staging 发布与真实订单只读核对未完成而为 `PARTIAL`。production 放行不在本任务范围。
