---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-ORDERS-001-20261021-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-ORDERS-001
tested_sha: 6f8f6c05e8668e71d785e31e152d51b96d2bf6cf
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-ORDERS-001-20261021-R01.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-ORDERS-001]
acceptance_ids: [AC-01, AC-02]
environment: Windows 11; isolated Docker PostgreSQL test profile; local Next.js webpack production build; synthetic Chrome; staging official API read-only probe
created_at: 2026-10-20T16:20:00Z
updated_at: 2026-10-20T16:20:00Z
supersedes: null
---

# 本次结果

`TEST_LAYOUT: centralized`。从候选工作树运行 `src/scripts/run-postgres-integration-tests.ps1`：2232 passed、3 skipped（POSIX bash 专用），测试数据库容器已移除。`uv run ruff check` 和 `format --check` 相关文件通过；`uv run mypy app scripts` 188 个源文件通过。前端 `npm run typecheck`、契约 `npm run test` 47/47、`npm run lint` 0 errors/4 warnings，`npm run build -- --webpack` 成功；生产模式 `npm run test:ui` 42/42，通过本地临时依赖目录提供 `playwright-core`。

默认 Turbopack 构建因当前工作树 `node_modules` 是指向仓库其他位置的目录链接而失败；webpack 生产构建成功，正式容器构建将自行安装锁定依赖。首次浏览器测试缺 `playwright-core`；在忽略的 `src/tests/.artifacts/` 安装锁定版本后复测通过。

新增确定性用例核对官方单会话固定路径与订单查询 `buyer_user_id` 签名正文、买家 IM ID 不符先于订单请求拒绝、跨买家订单拒绝及非法金额拒绝。staging 旧版运行容器只读探针确认已知会话买家 IM ID 相符、订单域 ID 可用、官方返回 1 笔订单且金额/商品/物流存在；该探针尚未证明新代码已部署。未使用 GitHub Actions、未发送 TikTok 消息。

# 尚需现场验收

AC-03 的 staging 新版部署、已登录工作台订单显示及授权隔离由部署任务留证。本报告的 PASS 仅覆盖源码和既有官方只读契约，不代表现场发布完成。
