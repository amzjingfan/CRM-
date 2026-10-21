---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-VARIANT-001-20261021-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-VARIANT-001
tested_sha: 64aefa1206497c9bf2d003b9698a3e906e78e185
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-VARIANT-001-20261021-R01.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-VARIANT-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows local Next.js production build and merged-main staging containers; synthetic browser API interception
created_at: 2026-10-21T11:10:49Z
updated_at: 2026-10-21T11:13:57Z
---

# 复现与修复证据

- 修复前在已部署旧版 staging 上运行长规格浏览器回归，断言可见值不溢出，实际 `false !== true`，准确复现截图中的省略号；短规格原用例仍通过。
- 改为规格值换行后，本地定向长规格用例通过；无规格用例确认仅显示“—”且无规格复制按钮，不伪造值。
- 最终 subject `64aefa12` 上：`npm run build`、`npm run typecheck`、`npm test`（47/47）通过；`npm run lint` 为 0 error、4 条既有 warning。生产构建下 `UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui` 为 54/54。开发服务器下缓存专用用例曾失败，按该用例要求改用生产构建复核后通过；其他开发模式浏览器用例当时 51/51。

# staging 手动门禁与运行核对

- 源码 PR #498 合入 `main=5e11f7b6` 后，从干净 checkout 构建并推送同 SHA revision 的后端与前端不可变镜像；旧运行摘要先读出，无猜测。
- `CheckOnly`、六摘要预取、`ValidateOnly`、`Deploy` 均通过；迁移头 `025_workspace_actions`，11 个 CRM 容器正常运行，后端/前端/检索镜像摘要和健康状态匹配。四个公网入口 `/healthz`、`/v1/health`、`/v1/health/ready`、`/workspace` 均 HTTP 200。
- 已部署 staging 页面执行长规格与无规格合成浏览器回归 2/2；浏览器仅拦截 `/v1/`，不访问真实买家数据或发送消息。私有备份模式 `0600`，预取、validate、deploy 证据哈希及回滚摘要见[低敏证据](../../../release/evidence/staging/crm-staging-customer-sidebar-variant-20261021.json)。临时 GHCR 登录已注销。

# 现场核对边界

已请求用户刷新原始真实订单卡确认视觉效果。Codex 内置浏览器读取登录态标签再次超时，记录 `UI_UNAVAILABLE`；因此不声称直接观察了该真实订单。平台本身未返回 `sku_name` 的订单仍显示缺失标识，这是数据缺失而非本次截断缺陷。GitHub Actions 两个作业均在零步骤时失败，不计为 CI 通过；本次无后端业务改动，未重跑后端全量测试。无外发、退款、发券或 production 发布。

# 结论

本地与 staging 合成验证及部署门禁通过，AC-01～AC-03 为 `PASS`。真实登录态页面未由 Codex 直接读取；若用户刷新后仍见省略号，按该订单截图和返回的 `sku_name` 再作独立诊断。
