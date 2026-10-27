---
record_id: IR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-AGENT-DEBUG-ANSWER-001
base_sha: dea7707d7862c0910337c82a9289c1d27dd4607b
final_sha: a4e58e53005768ec78e4e73911904a364181a087
requirement_ids: [MVP-AGENT-DEBUG-ANSWER-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R01.md
created_at: 2026-10-27T09:24:14Z
updated_at: 2026-10-27T09:24:14Z
supersedes: null
---

# 实施目标与范围

修复 Agent 预览与调试在只读工具成功后仍隐藏安全模型草稿、显示固定提示的问题；支持同一轮混合问题在授权只读工具后检索当前 Agent 绑定的已审批文件，并展示经分别复核的回答与引用。

# 实际变更及原因

- 将调试模式下 `needs_human` 视为交付坐席复核的信号，不再直接判为模型草稿不安全。确定性 DLP、事实依据、引用、独立模型复核仍须通过，自动发送资格仍为 false。
- 对明确混合问题在工具安全检查后进入已有知识检索节点，只使用当前店铺已绑定文件；工具与知识草稿独立复核，安全部分才可组合展示。无有效引用时只展示已经通过复核的工具部分。
- 调试输出先确定人工审核动作再组装结果，避免安全模型草稿被仅供自动发送的固定模板遮蔽。无可信物流轨迹时模型须说明无法核验现状，不得编造位置。
- 增加工具无轨迹、需人工审核的知识草稿、单轮混合回答与不可信知识引用的行为测试；同步 AI 架构和 Agent 模块说明。工作流版本递增至 `faq-agent-workflow-v1.8.5`，Prompt 正文未改。

# 数据、配置、接口、迁移或 Prompt 影响

没有数据库迁移、配置开关或公共 API 结构变化。仅改变 Agent 调试输出的工作流路径和内容；正式对客路径继续使用既有安全与发送门禁。模型供应商、凭证和外部 TikTok 写接口均未改。

# 验证交接、限制与回滚

本地后端全套、隔离 PostgreSQL/pgvector 全套、Ruff、mypy 与锁文件检查见关联 TR。staging 真实模型、绑定文件和授权买家只读工具的现场验收尚未执行；不能把本地通过视为现场完成。回滚使用部署前后端不可变镜像摘要，不降级数据库或覆盖业务增量。
