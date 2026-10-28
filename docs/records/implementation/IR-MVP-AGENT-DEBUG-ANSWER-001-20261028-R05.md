---
record_id: IR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R05
record_type: implementation
revision: R05
status: FINAL
task_id: MVP-AGENT-DEBUG-ANSWER-001
base_sha: 8096728f6a194358e52dbb0c31db7354e821cb2d
final_sha: d368b529ae23c61bccab51eebe5a53326a87a213
requirement_ids: [MVP-AGENT-DEBUG-ANSWER-001]
acceptance_ids: [AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R06.md
review_record: docs/reports/reviews/RR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R05.md
created_at: 2026-10-27T16:04:45Z
updated_at: 2026-10-27T16:04:45Z
supersedes: docs/records/implementation/IR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R04.md
---

# 目标与现场根因

合并主线 `8096728f` 经手动门禁部署 staging 后，保留的已审批绑定文件仍有检索命中（score 0.8067），真实模型草稿也已生成，但独立复核前被 Prompt DLP 以 `BUSINESS_PROMPT_LOCATION_TEXT_LOW_CONFIDENCE` 拒绝；页面只显示保守转人工文本。对同一合成输入的受控模型诊断确认草稿答案包含两个普通逗号，触发位置形态规则，与文件内容或工具权限无关。仅加强提示词仍生成两逗号答案，故不能只靠自然语言指令修复。

# 实际变更

- 仅 Agent 调试绑定文件草稿使用 `ConciseFaqAnswerModelOutput` 严格 JSON Schema，在模型输出边界限制 `answer` 不含逗号、顿号、分号和换行；模型仍需返回原 FAQ 的引用、语言、置信度和完整业务声明。
- 注册的调试 Prompt 升至 `faq-answer-debug-file-v1.1.0`，正文 SHA-256 为 `a2ba4a59789810deec88d4cf396e057fef27e79cd8d93aab2bb1e3ad3ef9534d`，Schema 名称也纳入原 Provider 白名单校验。正式 FAQ 与工具回答不使用新 Schema。
- 不改 DLP、检索、店铺隔离、独立复核、超时、人工确认发送或平台发送开关；不增加新服务、接口或迁移。

# 回滚与限制

回滚到已合入主线 `8096728f` 的后端摘要 `sha256:7ac4ef205921485e05482265cedd3161b92bdc4e0c5501f61c819722935e1d5f`。本次修复保留原失败关闭：复杂文档中模型若无法满足严格 Schema 或其他字段仍触发 DLP，调试回答继续转人工。已绑定的合成文件按用户要求留至全链路成功后统一清理；production 不发布。
