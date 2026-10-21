---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001-20261021-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001
base_sha: 3e01d7fc752e46c3105946ca3f3165b44c5c8aba
final_sha: 7cd8e43e27544036027f2b2d8be2a5fc411d97ca
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001-20261021-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001-20261021-R01.md
created_at: 2026-10-21T01:05:00Z
updated_at: 2026-10-21T01:05:00Z
supersedes: null
---

# 实施目标与范围

修复真实 TikTok 零订单买家在客户侧栏打开“订单”时误显示“返回数据结构异常”。仅调整订单只读适配器，不修改外发、退款、优惠券或生产配置。

# 实际变更及原因

在 staging 已授权会话中只读复现：官方 `POST /order/202309/orders/search` 返回成功，`data` 仅含 `total_count=0` 与空 `next_page_token`，省略 `orders`；旧 `_validated_list` 把字段缺失一律映射为 502。新逻辑仅在三个条件同时满足时将省略列表视为空页，其他响应保持严格校验。添加五个正反回归样例，并同步 API 契约说明。

# 关键决定与偏差

官方文档展示非空订单响应中的 `orders`；零订单省略行为依据本次 staging 真实只读返回。为保持失败关闭，不把所有缺失列表通用化，也不修改其他 TikTok 列表接口。

# 数据、配置、接口、迁移或 Prompt 影响

工作台侧栏公开响应结构不变；无数据库迁移、配置、Prompt 或权限变化。

# 验证交接

源码候选测试与风险审查见关联 TR/RR。staging 发布与同一会话复测另留运行证据；production 保持 No-Go。

# 限制、风险与回滚

若未来 TikTok 零订单格式再次变化，本适配器仍可能失败关闭。回滚到 `base_sha` 对应 backend 镜像即可恢复旧行为，但会重新出现本缺陷。
