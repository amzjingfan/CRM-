---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001
tested_sha: 26faf36d0570c4ce90f5875ce26618adb112558d
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R01.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows worktree; Python 3.11.15; uv 0.12.3; Next.js 16.3.8; Chrome synthetic browser; staging read-only aggregate probe
created_at: 2026-10-20T18:29:26Z
updated_at: 2026-10-20T18:29:26Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

候选源码提交 `26faf36d0570c4ce90f5875ce26618adb112558d`。源码测试位于集中式 `src/tests/backend/` 与 `src/tests/frontend/browser/`，普通临时探针在已忽略的 `src/tests/.artifacts/`，无真实数据提交。浏览器 `/v1/` 全部由合成数据拦截；真实店铺仅执行低敏只读聚合探针。

# 命令和逐项结果

| 检查 | 本次结果 |
|---|---|
| `PYTHONPATH=src/backend uv run pytest -q`，在 `src/backend` 执行 | 2212 passed，29 skipped，2 个依赖弃用警告，0 failed；在最终源码提交后运行 |
| `uv run ruff check . ../tests/backend ../tests/integration/postgres` | 通过；并发写 Ruff 缓存曾有访问警告，不影响规则结果 |
| `uv run ruff format --check . ../tests/backend ../tests/integration/postgres` | 323 files already formatted |
| `uv run mypy app scripts` | 188 个源码文件无问题 |
| `npm run lint` / `npm run typecheck` / `npm run test` / `npm run build`，在 `src/frontend` 执行 | 0 lint errors、4 个既有警告；typecheck 通过；47/47 契约测试通过；生产构建通过 |
| `UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui`，对本地 Next 生产构建 | 44/44 合成浏览器测试通过；含订单详情、搜索、金额、商品和优惠券交互，消息发送计数为 0 |
| staging 容器内运行已忽略的 `src/tests/.artifacts/probe-sidebar-order-detail.py`，只读聚合输出 | 会话存在、同店客户存在、官方 IM 身份匹配、订单存在、官方订单域买家匹配，通用物流节点 8；仅输出布尔值和数量 |

# REQ/AC 或门禁与证据映射

- AC-01：`test_workspace_sidebar_live_orders.py` 覆盖官方 IM 身份不符、跨买家订单、真实读取关闭、非 ASCII ID 与物流 Scope 缺失；平台适配器现有 Scope、签名和只读路径测试在全量后端回归中通过。
- AC-02：浏览器测试核对详情字段在点击后显示，且未调用发送；无真实详情的投影不会显示详情按钮。官方 staging 只读探针验证所选订单买家关系与轨迹存在。
- AC-03：本地类型、构建、全量及生产构建浏览器测试完成；新版接口与登录 UI 的 staging 联合验收尚未完成。

# 缺陷、未执行项与残余风险

本次未对真实买家发送消息、退款或发券；未发布 production。只读探针运行于上一版 staging 后端，证明平台身份和数据可用，不证明新增接口已部署或用户浏览器可见。已登录页面工具仍无法稳定连接，真实订单卡片的最终截图和点击结果待 staging 新版部署后核对；因此不能标记 `PASS`。

# 结论和复测条件

`PARTIAL`。源码验收通过；从合并后的受审主线手动发布 staging，确认新接口对当前会话返回真实字段、其他会话/买家失败关闭，并在已登录工作台核对卡片展示后修订 TR。
