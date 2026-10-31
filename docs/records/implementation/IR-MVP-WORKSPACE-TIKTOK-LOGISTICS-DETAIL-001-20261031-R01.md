---
record_id: IR-MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001-20261031-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001
base_sha: 8bf9873c4ebaa1eeda882acad24acfbb1ff7a0b8
final_sha: 8247cd5658b6c73824ebe3b85551b358fc485c18
requirement_ids: [MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-TIKTOK-LOGISTICS-DETAIL-001-20261031-R01.md
review_record: null
created_at: 2026-10-31T03:27:07Z
updated_at: 2026-10-31T03:27:07Z
supersedes: null
---

# 实施目标与范围

让已同步的 TikTok 原生物流卡片在聊天记录中提供与发送前物流草稿一致的“查看详情”入口。仅改变工作台只读交互，不改变消息发送或订单接口。

# 实际变更及原因

- `TikTokMessageCard` 在 `kind=logistics_card` 且有明确 `order_id` 时使用既有 `TrackingTimelinePopover`；按需调用当前会话订单详情，依据 `package_id` 选中对应包裹。
- `MessageBubble` 向卡片传递当前会话与翻译开关。缺订单号不显示详情入口，避免根据同一买家的其他订单猜测原消息身份。
- 在 `docs/architecture/API.md` 记录复用现有同店、同买家核验接口的边界。

# 关键决定与偏差

TikTok 返回 `OTHER` 的另一些 Seller Center 卡片与本次有订单 ID 的原生 `LOGISTICS_CARD` 不同。两处会话现场只读响应只有占位文案且 `data` 为空；无法建立原消息到订单的准确关联，单列 `MVP-WORKSPACE-TIKTOK-OTHER-CARD-001` 等待平台字段或官方接口，不在本实现中伪造卡片。

# 数据、配置、接口、迁移或 Prompt 影响

无数据库迁移、后端接口、配置、Prompt 或发送边界变化。详情入口只调用现有 `/workspace/sessions/{id}/sidebar/orders/detail`。

# 验证交接

见关联 TR。本地合成浏览器测试先在缺少入口时报错，再于实现后通过；完整工作台浏览器、前端契约、类型、lint 与生产构建通过。

# 限制、风险与回滚

真实 staging 页面尚待发布后核对。TikTok 缺订单 ID 的 `OTHER` 仍显示原占位文案；订单详情被平台限流时复用现有弹窗错误提示。回滚前端镜像或 revert 本源码提交即可恢复旧交互，不影响已存消息。
