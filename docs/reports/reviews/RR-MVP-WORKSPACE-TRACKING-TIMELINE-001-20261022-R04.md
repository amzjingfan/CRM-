---
record_id: RR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R04
record_type: review
revision: R04
status: APPROVE
task_id: MVP-WORKSPACE-TRACKING-TIMELINE-001
reviewed_sha: 97c5d6bb6f7734e27eaafcf779df8f8a0ff74541
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R04.md
test_record: docs/reports/tests/TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R04.md
review_focus: [buyer-isolation, package-membership, human-confirmation, idempotency, unknown-reconciliation, platform-write]
created_at: 2026-10-22T04:08:00Z
updated_at: 2026-10-22T04:08:00Z
supersedes: docs/reports/reviews/RR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R03.md
---

# 审查依据与发现

核对 `218befe0..97c5d6bb` 的新写入路径：路由要求 `workspace.reply`、CSRF 和幂等键；`confirmed` 必须为布尔真；服务端从已授权会话重新取得唯一官方买家和其订单，不接受客户端提供卡片正文或商品图片。指定的包裹 ID 必须来自订单行或当前订单的官方增强轨迹；已知多包裹而未指定时拒绝。商品预览和发送后快照只在能够映射到所选包裹时填充，避免展示其他包裹商品。

新类型通过原 `send_platform_message` 工具与 TikTok 写适配器，同店 `processing/unknown` 熔断、真实发送白名单、单次请求、审计和人工对账仍适用；旧文本哈希保持不变。传输结果未知不自动重试；未知消息对账保留物流卡片快照。前端弹窗按钮仅建草稿，审阅确认才发送；“查看详情”走原店铺授权的只读接口，不能依赖客户端草稿作为权威轨迹。

未发现阻止源码合并的问题。剩余平台风险为 TikTok 对当前店铺/订单的原生卡片类型尚无真实发送回执，部署后只可核对草稿和受控 API 合成路径，不为测试向买家发消息。生产发布独立门禁未满足。
