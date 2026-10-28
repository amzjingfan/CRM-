---
record_id: TR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R06
record_type: test
revision: R06
status: PARTIAL
task_id: MVP-AGENT-DEBUG-ANSWER-001
tested_sha: d368b529ae23c61bccab51eebe5a53326a87a213
implementation_record: docs/records/implementation/IR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R05.md
requirement_ids: [MVP-AGENT-DEBUG-ANSWER-001]
acceptance_ids: [AC-02, AC-03, AC-04, AC-05]
environment: Windows local; isolated Docker PostgreSQL/pgvector; Python 3.11; staging live follow-up pending
created_at: 2026-10-27T16:04:45Z
updated_at: 2026-10-27T16:04:45Z
supersedes: docs/reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R05.md
---

# 本次复现与本地验收

staging 主线 `8096728f` 后端镜像 `sha256:7ac4ef205921485e05482265cedd3161b92bdc4e0c5501f61c819722935e1d5f` 已通过手动部署门禁、迁移头 `034_agent_debug_runs` 与健康检查。相同合成文件仍在 TikTok US 测试店铺获批并绑定 Agent；知识单问 trace `4bb7170b-3297-4370-a60e-b2a069433c8b` 候选数 1、分数 0.8067，草稿模型成功，独立复核输入却以 `BUSINESS_PROMPT_LOCATION_TEXT_LOW_CONFIDENCE` 被拒绝，页面无引用。此为本修复前现场失败，不算本 subject 通过。

- 受控合成模型诊断：原 Schema 草稿包含两个普通逗号且命中低置信位置规则；加强纯文字提示仍如此。改用新严格 Schema 的受控调用返回有效结构、包含七天事实，候选整体位置风险为无。该单次诊断只证明供应商接受新 Schema，不等于 Agent 页面全链路通过。
- `uv lock --check`、全后端 Ruff check/format、`mypy app scripts`、`git diff --check`：通过。
- Agent/Provider 定向回归：240 passed。隔离 PostgreSQL/pgvector 完整后端回归：**2460 passed、3 skipped、2 warnings**，迁移到 head 后测后移除测试容器；三个跳过项需要 POSIX bash。
- 版本化 Phase 4 确定性安全评测：237 样本，安全准确率与原因码准确率均 1.0，unsafe escape 为 0。它不调用真实模型。
- Schema 回归锁定多逗号草稿在模型输出边界被拒绝、无逗号简答可解析；现有真实地址失败关闭、调试混合问题和正式路径回归仍通过。

# 待完成

本 subject 尚未合入主线或部署 staging。必须用保留的同一份已审批合成文件验证知识单问出现模型七天回答和引用、混合问句同时出现真实只读物流工具结果及文件引用、零平台发送；通过前本 TR 为 `PARTIAL`，任务 `VERIFYING`，production G8 No-Go。用户要求测试完成前不反复新建或清理知识文件。
