---
record_id: TR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R08
record_type: test
revision: R08
status: PASS
task_id: MVP-AGENT-DEBUG-ANSWER-001
tested_sha: c63421fa4bf19b92c66aa57b8298b75dcc83a9a5
implementation_record: docs/records/implementation/IR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R07.md
requirement_ids: [MVP-AGENT-DEBUG-ANSWER-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows local isolated PostgreSQL/pgvector; authenticated staging browser; TikTok US authorized read-only session
created_at: 2026-10-28T01:00:00Z
updated_at: 2026-10-28T01:00:00Z
supersedes: docs/reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R07.md
---

# 范围与本地验证

`TEST_LAYOUT=centralized`。R07 已记录本 subject 的先红后绿行为测试、Agent/Prompt 定向 **152 passed**、隔离 PostgreSQL/pgvector 全套 **2460 passed、3 skipped、2 warnings**、Ruff、mypy、`uv lock --check` 与 237 样本安全评测；三个跳过项需要 POSIX bash。GitHub 前后端 CI 在零步骤失败，不能算通过；用户批准仅本次 [PR #573](https://github.com/CP11-gh/CRM/pull/573) 用本地验证替代。PR 已合入 `main=5f0feb7ffeec4290a5cabcb8df0550df696c7aca`，后端树核对相同。

# staging 实际结果

手动部署门禁 PASS：main/OCI revision、镜像摘要、私有备份、`ValidateOnly`、`Deploy`、迁移头 `034_agent_debug_runs` 和三个公网健康接口 200；production 未发布。沿用同一份此前保留的审批绑定合成文件，在 Codex 浏览器中以 TikTok US 测试店铺的授权会话现场运行：

| 用例 | Trace | 页面和后端结果 |
|---|---|---|
| 纯知识：合成退货窗口 | `ae1d5d67-a54f-4563-8955-f3a6eb31e169` | 模型显示签收后七天内、需人工核对；引用合成文件；`succeeded / human_review`，分数 0.8067、2895 ms，未调用工具。 |
| 物流加知识同轮 | `35c0f2fd-2091-43c8-ae50-05870097a2f1` | 模型显示真实物流“已送达”并回答合成七天规则；`query_logistics:succeeded`，同一文件引用；`succeeded / human_review`，分数 0.8067、5246 ms。 |

两条 trace 的审计动作均仅为 `agent.debug.run:accepted`；调试路径不创建客户消息，运行决策为 `human_review`，未触发平台消息发送。相关低敏字段和清理结果见[机器证据](../../../release/evidence/staging/crm-staging-agent-debug-grounded-answer-20261028.json)。测试后 Agent 保存绑定数为 0，合成文件 `deleted_at` 非空，当前店铺知识列表 0；原文件版本和审计留存。没有重复导入或重建测试文件。

# 验收与残余风险

AC-01 的安全物流单问见 R04 现场记录；AC-02、AC-03、AC-05 的带引用模型回答与真实只读工具同轮现场通过；AC-04 的店铺隔离、12/45 秒超时、DLP 和零发送边界未放宽，本地回归及现场行为吻合。**本任务 PASS**，但不能推出任意知识文件或问题都保证输出，模型仍可能因格式或安全复核失败而关闭。知识库页面现有“文档检索本期未接入”说明与 Agent 调试现状不一致，属于独立文案缺陷；不影响本次真实链路判定，后续修正。production G8 维持 No-Go。
