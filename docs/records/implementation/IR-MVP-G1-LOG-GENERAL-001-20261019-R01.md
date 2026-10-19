---
record_id: IR-MVP-G1-LOG-GENERAL-001-20261019-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-G1-LOG-GENERAL-001
base_sha: 7a8e78c0643989c6b5ced33ce0f6b260eb5fe6ab
final_sha: 91f1593d98db710da2febb29ff8686da3617accf
requirement_ids: [MVP-G1-LOG-GENERAL-001, G1-L]
acceptance_ids: [G1-L]
test_record: docs/reports/tests/TR-MVP-G1-LOG-GENERAL-001-20261019-R01.md
review_record: docs/reports/reviews/RR-MVP-G1-LOG-GENERAL-001-20261019-R01.md
created_at: 2026-10-19T16:34:54+08:00
updated_at: 2026-10-19T16:34:54+08:00
supersedes: null
---

# 实施目标与范围

按用户 2026-10-19 明确的新口径，以授权店铺真实订单的通用 `202309` 物流轨迹成功响应验收 v0.1 G1-L。CBT 首程增强 `202604` 保留为后续独立能力。

# 实际变更及原因

`TikTokReadClient` 新增只读 `get_standard_tracking`，固定官方 `GET /fulfillment/202309/orders/{order_id}/tracking`，复用现有渠道 Token、签名、`shop_cipher`、固定出口、错误映射和 `seller.logistics` 预检。新增独立响应模型校验通用轨迹的描述、毫秒时间和动作码，不用增强接口特有的单号或动作名称解释普通承运商轨迹。原 `get_tracking` 的 CBT `202604` 契约不变；无数据库迁移、公开路由或平台写入。

# 关键决定与偏差

用户选择以通用接口成功放行 G1-L。现场真实 FedEx 样本取得 11 条轨迹，但这是正式适配器引入之前的一次性同签名只读探针；本轮源码通过确定性契约与完整后端回归，尚未将新镜像部署到 staging。不能把普通物流轨迹说成 CBT 首程通过。

# 验证交接与限制

见 [R01 TR](../../reports/tests/TR-MVP-G1-LOG-GENERAL-001-20261019-R01.md)、[R01 RR](../../reports/reviews/RR-MVP-G1-LOG-GENERAL-001-20261019-R01.md)及[低敏现场证据](../../../release/evidence/staging/crm-staging-g1l-generic-fedex-20261019.json)。USPS、Seller Center 逐条比对和新客户端的 staging 镜像运行未验证；G2/G6/G8 和 production 仍各自受阻。
