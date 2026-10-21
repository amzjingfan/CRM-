---
record_id: IR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R03
record_type: implementation
revision: R03
status: FINAL
task_id: MVP-WORKSPACE-BROWSER-COMMENTS-001
base_sha: 5d5f532ce323f694412740377e3e74e478ffe58e
final_sha: f951e294514bdfcd1eb79ab59228d9f953ba5d2b
requirement_ids: [MVP-WORKSPACE-BROWSER-COMMENTS-001]
acceptance_ids: [AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R03.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R03.md
created_at: 2026-10-21T09:27:22Z
updated_at: 2026-10-21T09:27:22Z
supersedes: docs/records/implementation/IR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R02.md
---

# 实施目标与范围

用户在已部署订单卡截图中发现“物流状态”显示英文 `Delivered`，随后要求物流状态统一为中文，并为最新物流描述提供小型按需翻译按钮。沿同一任务返修；不修改 TikTok 原始订单、物流描述或真实发送边界。

# 实际变更及原因

- 已知结构化物流阶段显示中文；缺少结构化状态时，仅将最新描述中明确的常见阶段归一化为中文，无法可靠识别时显示“状态待更新”。官方订单的 `COMPLETED` 不直接推断为“已送达”。
- 保留物流商原始描述；中文工作台且已启用翻译时显示小型“译成中文”按钮。点击后通过新只读接口按订单 ID 重新核对当前会话、店铺、买家和订单，再翻译最新描述；响应原文与当前卡片不一致时丢弃旧译文。失败时原文保留并可重试。
- 翻译沿用现有 DeepSeek 翻译节点、CSRF、`workspace.view`、速率限制和低敏审计；含需脱敏内容的描述在模型调用前拒绝。没有新增模型或配置开关。

# 数据、配置、接口、迁移或 Prompt 影响

新增 `POST /workspace/sessions/{session_id}/sidebar/orders/tracking-translation`，请求体仅含数字订单 ID，响应含原文和中文译文；已同步 `docs/architecture/API.md` 与 `docs/product/PRODUCT.md`。无数据库迁移、配置、Prompt、自动发送或高风险写入变化。

# 验证交接、风险与回滚

最终源码 SHA 的本地证据见 TR R03；按权限和失败关闭审查见 RR R03。当前 staging 仍运行旧镜像；合入主线后需使用不可变前后端摘要、保留运行中镜像和私有备份，按既有 staging 门禁发布并复核。真实 DeepSeek 调用及用户登录态按钮尚未现场执行。
