---
record_id: RR-MVP-TIKTOK-STORE-SEND-001-20261018-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-TIKTOK-STORE-SEND-001
reviewed_sha: 6394282897abdb89349dee7399bb05629220ca2e
implementation_record: docs/records/implementation/IR-MVP-TIKTOK-STORE-SEND-001-20261018-R01.md
test_record: docs/reports/tests/TR-MVP-TIKTOK-STORE-SEND-001-20261018-R01.md
review_focus: [store_isolation, authorization, human_confirmation, idempotency, unknown_reconciliation, staging_gate, g5_restore]
created_at: 2026-10-18T12:14:00+08:00
updated_at: 2026-10-18T12:14:00+08:00
supersedes: null
---

# 审查范围、依据与重点风险

审查 PR #348/#350 与 `MVP-TIKTOK-STORE-SEND-001` AC-01～AC-04，依据 `docs/engineering/DEVELOPMENT.md`、`docs/architecture/API.md`、当前代码及 337 项定向测试。真实写入扩大到已审核店铺，重点检查默认拒绝、跨店隔离、重复发送和 G5 恢复配置。

# 发现、级别、位置和证据

未发现阻断 staging 单店人工发送的 P0/P1 问题。配置层强制单会话目标与店铺列表互斥且非空，并校验规范 UUID；工作台要求活动店铺及有效客服渠道；工具层按当前用户上下文和店铺锁拒绝未确认、跨店或未结清发送；TikTok 写客户端在 HTTP 前再次核对范围，并对不确定结果返回 `unknown` 而不重试。staging 门禁比对 Compose/运行态目标，G5 快照兼容旧单会话并恢复店铺目标。相关定向测试与现场汇总见 TR。

# 已验证与未验证内容

已验证确定性跨店拒绝、目标范围失败关闭、两个真实会话的 UI 发送模式以及一个已审核店铺 180 会话的只读汇总。没有向第二位真实买家外发；TikTok 对旧会话的实际可达性由平台按每次请求判定，`real` 模式不能替代平台回执。未审查 production 放行或自动回复。

# 结论和返修条件

批准当前 staging 单店、人工确认的普通文本范围收尾；production 继续 No-Go。若出现跨店可见/可发、无人工确认仍写入、`unknown` 后自动重试或恢复后范围扩大，立即停止该范围并按受审门禁回退、修复与重验。
