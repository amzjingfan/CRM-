---
record_id: IR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R06
record_type: implementation
revision: R06
status: FINAL
task_id: MVP-AGENT-DEBUG-ANSWER-001
base_sha: 30b29c968a657f6e10a57a20f726548d13339643
final_sha: c63421fa4bf19b92c66aa57b8298b75dcc83a9a5
requirement_ids: [MVP-AGENT-DEBUG-ANSWER-001]
acceptance_ids: [AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R07.md
review_record: docs/reports/reviews/RR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R06.md
created_at: 2026-10-28T00:21:14Z
updated_at: 2026-10-28T00:21:14Z
supersedes: docs/records/implementation/IR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R05.md
---

# 目标与现场根因

主线 `30b29c96` 经手动门禁部署 staging 后，同一审批绑定文件的纯知识问题已显示带引用的七天回答（trace `9fe39419-653f-4831-83cc-d09e875d4780`）。混合问题 trace `05cc80f4-c8c8-4a39-8bcf-a741457f4318` 在文件知识草稿处两次触发 `LLM_OUTPUT_INVALID`，安全 Schema 问题码为 `answer:other`；页面未显示同轮建议。原请求未指定温度，同一输入的模型格式存在随机偏差。

# 实际变更

- 仅已绑定文件的 Agent 调试知识草稿调用固定 `temperature=0.0`，仍使用 `ConciseFaqAnswerModelOutput` 严格 Schema 与注册 Prompt `faq-answer-debug-file-v1.1.0`。正式 FAQ 与工具模型请求的温度保持原值。
- 工作流版本升至 `faq-agent-workflow-v1.8.8`，同步 AI 当前文档和 Agent Prompt 版本清单。没有改模型提供商、DLP、声明、引用、复核、店铺隔离、数据库、接口或平台发送边界。

# 验证、回滚和限制

受控 DeepSeek 探针使用同一合成知识和混合问题的检索分数 0.7432，在 `temperature=0.0` 连续三次返回有效简答、包含七天事实且位置风险为无；这不是完整 Agent 页面验收。最终 subject 的隔离 PostgreSQL/pgvector 全套、静态检查及 237 样本确定性安全评测见 R07 TR。回滚点为已部署主线 `30b29c96` 的后端摘要 `sha256:b19441aa8085cb80aa33e03befe2b1fe465544187b00f7719fc83cd3139f70cb`，新版本仍须 staging 同轮测试。测试文件按用户要求保留至成功后统一清理；production 不发布。
