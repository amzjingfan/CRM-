---
record_id: RR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261030-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001
reviewed_sha: 60265d6566fca45ef1196ac777ea281be0662016
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261030-R01.md
test_record: docs/reports/tests/TR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261030-R01.md
review_focus: [correctness, public_contract, tenant_isolation, privacy, external_media, backfill]
created_at: 2026-10-30T15:58:12Z
updated_at: 2026-10-30T15:58:12Z
supersedes: null
---

# 审查范围、依据与重点风险

复核 subject 相对 `5564a491` 的 TikTok Webhook、只读同步、工作台响应及渲染。重点是跨店错配、未读/派单副作用、第三方 URL、完整载荷保存、视频链接与历史回填重放。

# 发现、级别、位置和证据

- 原因链已闭合：旧适配器丢失非文本内容；只读模型没有 data/plaintext；Webhook 写入强制 text；工作台只有本地发出的物流卡片视图。
- 修复保持原会话与店铺校验，按外部消息 ID 幂等更新；旧消息仅修复展示，既有未读和派单条件不因更新触发。
- 解析器只提取白名单字段和 HTTPS 链接；React 文本转义，不记录原始第三方 JSON。视频不伪造 URL，加载失败保留封面。
- 最新 main 有独立 Agent 模板批次和 046 合流迁移，现 staging 在 045。直接以最新 main 建镜像会带入未批准部署能力；发布阶段必须保留此阻断边界。

# 已验证与未验证内容

后端全量、隔离 DB、前端静态/合同/构建、工作台富消息与开发全套浏览器通过；生产构建全套有 Agent 模板搜索单项失败，已在 TR 明列，不能声称全套通过。真实 TikTok 只读样本的字段形状和旧占位聚合已核对；未向买家发送消息。尚未核对 staging 上新媒体渲染、历史回填总量和签名 URL 的长期可用性。

# 结论和返修条件

批准代码进入主线；staging 发布须另按精确镜像与保留 045 的受审候选验证，不用本 RR 冒充发布审查。若回填发现跨店/会话不一致、平台字段形状变化或候选带入 Agent 迁移，则停止发布并修订本记录。
