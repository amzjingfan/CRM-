---
record_id: RR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001
reviewed_sha: 26faf36d0570c4ce90f5875ce26618adb112558d
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R01.md
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R01.md
review_focus: [correctness, authorization, store_isolation, buyer_identity, platform_read_only, data_integrity]
created_at: 2026-10-20T18:26:43Z
updated_at: 2026-10-20T18:26:43Z
supersedes: null
---

# 审查范围、依据与重点风险

审查源码提交 `26faf36d0570c4ce90f5875ce26618adb112558d` 相对 `e4e4622c9cb396dab005f4da8e906186094909eb` 的订单模型、侧栏服务、路由、前端与测试。依据是已确认原型 A、任务 AC、`docs/engineering/DEVELOPMENT.md` 和当前 API/产品边界。

# 发现、级别、位置和证据

- 重大/重要未关闭发现：0。
- `sidebar_order_detail` 路由保留 `workspace.view` 和 CSRF；服务先调用 `_conversation` 限定坐席店铺，官方参与者与 CRM IM ID 必须相同，订单详情的 ID 与订单域买家 ID 必须相同。单元测试分别覆盖买家不符与跨买家，失败前不查轨迹。
- 订单 ID 在请求体中按 ASCII 数字限制；真实读取未开启时不创建 TikTok 客户端。TikTok 适配器原有 `seller.order.info` 与 `seller.logistics` Scope 约束和签名读接口未被改动。
- 最新轨迹按平台毫秒时间取最大值，时间异常返回 502；无节点或无字段不会造值。前端仅“填入回复草稿”，退款仍禁用，本次无自动外发。

# 已验证与未验证内容

本地全量及受影响验证见 TR。真实 staging 页面与该版本后台接口的联合核对尚未完成，不能将代码审查结论视为现场验收或 production 放行。

# 结论和返修条件

对源码安全与正确性给出 `APPROVE`。若 staging 返回身份不匹配、缺物流授权或 UI 未展示真实字段，应在同任务下修复并形成新候选 SHA、复测和新的 RR 修订，不放行生产。
