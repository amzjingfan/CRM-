---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001-20261022-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001
tested_sha: f512fb8a8a52ed4139a5f94a431752b5f65715d0
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001-20261022-R01.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows local Next.js development reproduction and production build; synthetic Chrome API interception
created_at: 2026-10-22T04:48:20Z
updated_at: 2026-10-22T04:48:20Z
---

# 复现与本地验证

新增长卖家 SKU 浏览器用例后，在修复前运行定向测试，真实得到 `false !== true`：完整值在 DOM 中，但文字溢出可见区域。仅让卖家 SKU 行换行后，长货号、原有长商品规格、缺失规格三项定向测试 3/3 通过；复制回读等于完整合成货号。

从 subject `f512fb8a` 的变更执行：`npm run typecheck` 通过；`npm test` 47/47；`npm run lint` 0 error、5 条已知 warning；`npm run build` 通过。生产构建下 `UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui` 59/59，包括新增长货号用例。开发服务器上完整浏览器 57 passed/1 failed/1 skipped，唯一失败为 HTML `Cache-Control` 专用用例预期 `no-store`、开发响应为 `no-cache`；生产构建重跑该项及全套 59/59 通过。未重跑后端，因无后端变更。

# 待验收

源码尚未合入主线并部署 staging，原真实订单仍待刷新核对。没有向买家发送消息，production 不在本次范围，因此 R01 暂记 `PARTIAL`。
