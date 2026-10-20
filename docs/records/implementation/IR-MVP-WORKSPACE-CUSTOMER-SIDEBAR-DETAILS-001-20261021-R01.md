---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001
base_sha: e4e4622c9cb396dab005f4da8e906186094909eb
final_sha: 26faf36d0570c4ce90f5875ce26618adb112558d
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R01.md
created_at: 2026-10-20T18:26:43Z
updated_at: 2026-10-20T18:26:43Z
supersedes: null
---

# 实施目标与范围

在已确认的原型 A 客户侧栏中补足真实订单卡片的付款方式、承运商和最新物流，保持 TikTok 人工辅助、只读和单店边界。

# 实际变更及原因

- TikTok 订单边界模型接收官方订单详情中已有的 `payment_method_name`、`shipping_provider`。
- 新增按会话与数字订单 ID 读取详情的内部接口；先核对坐席授权店铺及官方会话买家 IM ID，再用当前授权渠道读取订单详情，核对订单域买家 ID 后读取通用物流轨迹。以平台毫秒时间选最新节点并转成 UTC；缺项返回 `null`。
- 订单列表标示是否可读取真实详情。卡片“详情/刷新详情”仅在真实订单出现，成功后展示实际返回字段，失败展示错误与重试；不会自动发消息。
- 同步产品与 API 当前事实文档，测试覆盖身份不符、跨买家、禁用真实读取、非 ASCII 订单号、缺物流授权和合成浏览器交互。

# 关键决定与偏差

详情在坐席明确点击时读取，避免订单列表每页最多 20 个条目触发额外平台查询。订单号只进入 POST 请求体，不进入工作台 URL。平台只读详情调用若返回其他买家订单，服务端拒绝响应且不再查询轨迹；上游轨迹失败时整次详情失败，不把部分字段标成完整详情。

# 数据、配置、接口、迁移或 Prompt 影响

新增 `POST /v1/workspace/sessions/{session_id}/sidebar/orders/detail`，要求登录、`workspace.view`、CSRF 和会话店铺授权；没有迁移、配置、Prompt 或平台写接口变更。

# 验证交接

源码提交为 `26faf36d0570c4ce90f5875ce26618adb112558d`。本地验证与 staging 现场状态见关联 TR；代码风险审查见 RR。

# 限制、风险与回滚

本地合成浏览器不能代替已登录真实店铺界面验收。若新接口在 staging 无法读取轨迹，应保留原镜像摘要并按手动部署文档回滚服务镜像；不使用旧数据库备份覆盖部署后新增消息。
