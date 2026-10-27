---
record_id: IR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-AGENT-DEBUG-ANSWER-001
base_sha: 417c6762b1a90f74ee7cab845f86508b5ed230b2
final_sha: dc9116eef74d0f197a9fccf397076fdd49ad2248
requirement_ids: [MVP-AGENT-DEBUG-ANSWER-001]
acceptance_ids: [AC-01, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R02.md
review_record: docs/reports/reviews/RR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R02.md
created_at: 2026-10-27T10:09:10Z
updated_at: 2026-10-27T10:09:10Z
supersedes: docs/records/implementation/IR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R01.md
---

# 实施目标与范围

R01 已由 [PR #567](https://github.com/CP11-gh/CRM/pull/567) 合入主线并手动部署 staging。真实买家只读物流调试显示“没有可安全展示的建议”，未达到 AC-01。此修订在原范围内修正低置信度工具草稿的调试分流。

# 实际变更及原因

现场 trace `af8b34a3-b90a-4ab1-858c-ea72c9124bc0` 证明 `query_logistics:succeeded`，安全拒绝原因 `none`，但最终置信度 0.5000 先进入转人工节点；结果在动作降为 `HUMAN_REVIEW` 前组装，丢掉了已经安全复核的模型草稿。现在仅当调试模式、要求的工具全为白名单只读工具、执行成功且工具草稿通过确定性及独立模型复核时，将低置信度转为“展示草稿并人工审核”。后续知识拒答不能遮蔽安全工具解释。原始置信度和分类保持不变，不增加自动发送资格。

将既有无轨迹行为测试改为模型置信度 0.50，先复现 `draft_reply=None`，修复后通过；混合问题知识模型拒答的原有回归也再次通过。工作流版本递增至 `faq-agent-workflow-v1.8.6`，Prompt 正文和 Schema 未改。

# 数据、配置、接口、迁移或 Prompt 影响

没有迁移、公共 API 结构、配置或前端修改。正式对客工作流、租户隔离、DLP、12 秒检索与 45 秒调试超时、零平台发送不变。

# 验证交接、限制与回滚

最终 source SHA 的隔离数据库全套和静态检查见 R02 TR。新版本尚未部署 staging；须按旧后端摘要 `sha256:05196a52eb505697fd442ebe1aa8a04671e3a8f4fb663874b188efd3315ceec8` 留回滚，再验已授权买家只读工具和绑定知识的同轮回答。production 仍 No-Go。
