---
record_id: IR-MVP-AGENT-LIVE-DEBUG-001-20261026-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-AGENT-LIVE-DEBUG-001
base_sha: cef8646ad599856b4b19b7207ef38cc8daa4c1da
final_sha: 9302bb6d4d16b67d942f23251e58d7356e116ac5
requirement_ids: [MVP-AGENT-LIVE-DEBUG-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-AGENT-LIVE-DEBUG-001-20261026-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-LIVE-DEBUG-001-20261026-R01.md
created_at: 2026-10-26T06:10:01Z
updated_at: 2026-10-26T06:10:01Z
supersedes: null
---

# 实施目标与范围

把 Agent 管理页“预览与调试”的固定文案改为已保存服务类 Agent 的真实模型调试，使用其绑定文件和授权会话可用的只读工具；仅部署 staging，不发送 TikTok 消息。

# 实际变更及原因

- 新增真实调试 API、响应中的内容/引用/工具/追踪字段以及页面展示；停用 Agent 也可调试已保存配置。
- 调试显式传入绑定文件范围。空绑定代表零文件，不再回退到整店 FAQ；正常客服运行的既有 FAQ 行为继续使用原范围语义。
- 无授权会话时不给工具上下文；有会话时按当前店铺、读取权限、已启用工具和安全只读工具集合求交。审计接受事件和 Agent 运行记录分别留痕。
- 独立 `AGENT_DEBUG_ENABLED` 与总超时控制调试；staging 覆盖层保持通用 `LLM_ENABLED=false`。本地和 staging 均验证没有平台发送。

# 关键决定与偏差

真实买家会话可能把订单与买家信息发送给第三方模型，本次 TikTok US 现场验收只用不带会话的合成问题。该店铺当前零文件、零订单，真实绑定文件命中及成功工具读取未在该店铺完成；不把无上下文保守转人工当成两项通过。

# 数据、配置、接口、迁移或 Prompt 影响

新增 `POST /agents/{id}/debug`，要求 CSRF、`agent.manage`、限流与当前店铺隔离。迁移 `034_agent_debug_runs` 允许无客户会话的调试运行；调试会话外键为空。staging 手动发布后启用独立开关，原通用模型、自动回复和自动营销边界不变。生产 Prompt 内容与模型配置未改。

# 验证交接

完整命令、现场 trace 与未测项见 [TR](../../reports/tests/TR-MVP-AGENT-LIVE-DEBUG-001-20261026-R01.md)、[RR](../../reports/reviews/RR-MVP-AGENT-LIVE-DEBUG-001-20261026-R01.md) 和[低敏部署证据](../../../release/evidence/staging/crm-staging-agent-live-debug-20261026.json)。源码 subject SHA 与部署镜像 OCI revision 均为 `9302bb6d4d16b67d942f23251e58d7356e116ac5`。

# 限制、风险与回滚

TikTok US 店铺缺少可测试的绑定文档和订单，真实 RAG 命中/工具成功路径待受控样本复测。回滚先关独立调试开关或切回备份记录的旧后端/前端摘要并保留新增运行记录；有无会话调试记录时不可盲目降级迁移 034。production 仍为 No-Go。
