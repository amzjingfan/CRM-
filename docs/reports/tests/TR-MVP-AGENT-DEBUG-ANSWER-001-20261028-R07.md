---
record_id: TR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R07
record_type: test
revision: R07
status: PARTIAL
task_id: MVP-AGENT-DEBUG-ANSWER-001
tested_sha: c63421fa4bf19b92c66aa57b8298b75dcc83a9a5
implementation_record: docs/records/implementation/IR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R06.md
requirement_ids: [MVP-AGENT-DEBUG-ANSWER-001]
acceptance_ids: [AC-02, AC-03, AC-04, AC-05]
environment: Windows local; isolated Docker PostgreSQL/pgvector; Python 3.11; staging follow-up pending
created_at: 2026-10-28T00:21:14Z
updated_at: 2026-10-28T00:21:14Z
supersedes: docs/reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R06.md
---

# Staging 复现

用户仅对 #572 批准本地验证替代 GitHub 零步骤 CI。合入 `main=30b29c96` 后，镜像 `sha256:b19441aa8085cb80aa33e03befe2b1fe465544187b00f7719fc83cd3139f70cb` 经私有备份、来源和摘要核对、`ValidateOnly`、`Deploy`、迁移头 `034_agent_debug_runs` 与公网健康检查通过；`production_release=false`。TikTok US 测试店铺原有文件 `agent-debug-redeploy-synthetic-policy-20261027.txt` v1 仍获批并绑定。

- 纯知识问题 trace `9fe39419-653f-4831-83cc-d09e875d4780`：页面显示模型生成的签收后七天回答，引用该文件，状态 `HUMAN_REVIEW`。
- 同轮物流加知识问题 trace `05cc80f4-c8c8-4a39-8bcf-a741457f4318`：页面显示 `LLM_OUTPUT_INVALID`；运行记录为 `failure_stage=faq_draft`、`output_schema_issues=answer:other`。未得到完整同轮回答，不能记为通过。

# 本次候选本地结果

- 行为测试先红：混合调试请求的知识草稿 `temperature=None`，未满足固定值断言；变更后 Agent 工作流和 Prompt 注册定向回归 **152 passed**，正式 FAQ 的温度仍为 `None`。
- `uv lock --check`、全后端 Ruff check/format、`mypy app scripts` 与 `git diff --check` 均通过。
- 隔离 PostgreSQL/pgvector 完整后端回归 **2460 passed、3 skipped、2 warnings**；三个跳过项需要 POSIX bash，测试容器测后移除。
- 版本化 Phase 4 确定性安全评测：237 样本，安全和原因码准确率均 1.0，unsafe escape 0。它不调用真实模型。
- 同一合成知识、检索分数 0.7432 的受控 DeepSeek 探针在固定 `temperature=0` 连续三次返回有效 Schema、包含七天事实且无位置风险；仅为模型格式诊断，不等于本 subject staging 全链路通过。

# 待完成

本 subject 尚未合并或部署 staging。需沿用保留的审批绑定文件验证纯知识引用、真实只读物流工具与知识同轮回答、零平台发送；成功前维持 `PARTIAL` 和任务 `VERIFYING`，production G8 No-Go。测试结束前不反复创建或删除知识文件。
