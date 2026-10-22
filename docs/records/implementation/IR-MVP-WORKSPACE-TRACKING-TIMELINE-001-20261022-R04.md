---
record_id: IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R04
record_type: implementation
revision: R04
status: FINAL
task_id: MVP-WORKSPACE-TRACKING-TIMELINE-001
base_sha: 218befe0113291d14fd3bde98a4f95a1e9ac8718
final_sha: 97c5d6bb6f7734e27eaafcf779df8f8a0ff74541
requirement_ids: [MVP-WORKSPACE-TRACKING-TIMELINE-001]
acceptance_ids: [AC-05]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R04.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R04.md
created_at: 2026-10-22T04:08:00Z
updated_at: 2026-10-22T04:08:00Z
supersedes: docs/records/implementation/IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R03.md
---

# 实施目标与范围

用户指出 R03 的“发送物流卡片”只是长文本，要求如参考图所示在发送栏显示卡片，消息发送后也呈现卡片，点击“查看详情”打开与订单卡物流状态旁相同的完整轨迹。保持先预填、人工审阅、二次确认再发送；本次不向真实买家发送测试消息，不发布 production。

# 变更与原因

- TikTok 202606 写适配器支持官方 `LOGISTICS_CARD`，内容为序列化的订单 ID 与可选包裹 ID。普通 `TEXT` 原路径及其幂等哈希保持不变。新工作台 POST 要求 `workspace.reply`、CSRF、幂等键及显式 `confirmed=true`；服务端重新核对会话店铺、买家订单、包裹归属，并复用人工发送的白名单、同店熔断、审计和结果未知对账。
- 弹窗只创建结构化本地卡片草稿。发送栏显示商品、规格、金额、物流商、单号与最新节点；多包裹商品只按平台包裹 ID 或单号唯一映射，无法确定时不补造。点击现有发送控件先进入审阅弹窗，确认后才调用卡片 POST。会话中的卡片及其“查看详情”复用既有完整轨迹弹窗，含包裹切换、复制、截图与翻译。卡片消息保留已核对展示快照，详情仍按需读取官方轨迹。
- 同步产品、API、架构和 AI 当前文档；无迁移、配置或新依赖。R03 记录的是此前已部署文本草稿的真实事实，本轮修正 AC-05 的最终形态。

# 验证交接与限制

源码 subject 为 `97c5d6bb6f7734e27eaafcf779df8f8a0ff74541`，本地结果见 R04 TR，风险审查见 R04 RR。官方原生卡片请求体由合成 HTTP 测试验证，尚未真实向买家发送，也未证明 TikTok 对该具体店铺与订单接受此类型。staging 合入后部署和登录态核对另记后续报告；production 仍为 No-Go。
