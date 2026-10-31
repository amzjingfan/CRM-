---
record_id: IR-MVP-WORKSPACE-LIVE-FEEDBACK-001-20261031-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-LIVE-FEEDBACK-001
base_sha: 6938204a95b7879a96a1cb6a1f2b55604363f0e6
final_sha: 550316f4e8f6784c9ef6d05a4a9e5837dc8e86e6
requirement_ids: [MVP-WORKSPACE-LIVE-FEEDBACK-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-LIVE-FEEDBACK-001-20261031-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-LIVE-FEEDBACK-001-20261031-R01.md
created_at: 2026-10-31T11:13:26Z
updated_at: 2026-10-31T11:13:26Z
supersedes: null
---

# 实施目标与范围

修复工作台订单付款状态的无依据空白，并把此前仅作视觉预览、实际发送摘要文本的订单操作改为 TikTok 原生订单卡片。只修本批工作台反馈；不改变退款、自动发送和真实消息授权范围。

# 实际变更及原因

- 订单支付标签先采用平台明确的支付状态；未给状态而有付款时间时显示曾付款。取消订单的退款结果保持待核实，不从取消状态推断已退款。
- 订单卡片草稿与正文输入分离，审阅后调用新的订单卡片接口；不再把订单摘要填入文本发送链路。原生卡片内容只包含服务端重新核验的订单号，消息历史持久化卡片展示快照。
- 服务端沿用会话权限、店铺及买家核验、人工二次确认、CSRF、幂等、同店未结清消息熔断、审计和结果未知人工对账。TikTok 写客户端只发一次 `ORDER_CARD`，不在失败后自动重试。
- 旧物流卡片错误码和包裹字段语义保持；订单卡片不带包裹号。同步产品及 API 当前文档。

# 关键决定与偏差

官方 Send Message 支持 `ORDER_CARD` 与序列化 `{"order_id":"…"}`。本地预览是已核验订单快照，买家最终收到的版式由 TikTok 生成。此前 CBT 已取消订单无物流不推造；TK app 会话的只读测试确认另一笔已送达 CBT 订单可经通用 202309 接口返回 14 条轨迹。增强 202604 接口仍未证明对该订单可用。

# 数据、配置、接口、迁移或 Prompt 影响

新增 `POST /workspace/sessions/{session_id}/messages/order-card` 和内部消息类型 `order_card`；不增加迁移、环境开关、Prompt 或自动发送能力。已同步 `docs/architecture/API.md`、`docs/product/PRODUCT.md`。

# 验证交接

本地最终 subject 的后端、平台请求契约、前端契约、工作台合成浏览器、静态与构建验证见关联 TR。真实买家零试发；staging 部署和登录态验收须另记后续 TR。

# 限制、风险与回滚

真实 TikTok 买家卡片外观未通过测试发送验证，不能把本地预览当成平台实际渲染。若卡片接口被平台拒绝，保留失败或未知记录并由人工对账。回滚需切回此前精确前后端镜像；无迁移，保留部署后的业务数据增量。
