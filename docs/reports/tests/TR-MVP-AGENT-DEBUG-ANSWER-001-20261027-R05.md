---
record_id: TR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R05
record_type: test
revision: R05
status: PARTIAL
task_id: MVP-AGENT-DEBUG-ANSWER-001
tested_sha: b55847f8d697c8dc12f87860a773c93e6368445c
implementation_record: docs/records/implementation/IR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R04.md
requirement_ids: [MVP-AGENT-DEBUG-ANSWER-001]
acceptance_ids: [AC-02, AC-03, AC-04, AC-05]
environment: Windows local; isolated Docker PostgreSQL/pgvector test profile; Python 3.11; staging live follow-up pending
created_at: 2026-10-27T15:08:03Z
updated_at: 2026-10-27T15:08:03Z
supersedes: docs/reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R04.md
---

# 范围与本地结果

`TEST_LAYOUT: centralized`；新增回归位于 `src/tests/backend/agent/`。在最终 subject SHA 上运行：

- `uv lock --check`、`uv run --offline ruff check . ../tests/backend ../tests/integration/postgres`、`uv run --offline ruff format --check . ../tests/backend ../tests/integration/postgres`、`uv run --offline mypy app scripts`：全部通过。
- 设置 `PYTHONPATH` 为工作树的 `src/backend` 和 `src/tests/backend` 后，从仓库根运行 `src/scripts/run-postgres-integration-tests.ps1`：迁移到 head，**2459 passed、3 skipped、2 warnings**；三个跳过项需要 POSIX bash，隔离 `postgres-test` 测后已停止并移除。
- 混合路径测试断言检索查询与知识生成/复核仅包含退货问句，工具状态与引用仍合并展示；注册 Prompt 的 SHA、Schema 及明确地址失败关闭由相关测试覆盖。

# Staging 现场与待验收

主线 `c2448dbd` 已手动重新部署，后端 OCI 摘要 `sha256:81ca5d23e0a31cef1092259a5355a3da9fbf8aa68511e1b2e466e61b2c6302f7`，迁移头 `034_agent_debug_runs`、12 容器及三个公网健康接口通过。TikTok US 测试店铺授权会话的只读物流单问显示“物流状态显示订单已经送达。”，`query_logistics` 成功且审计摘要有 `tracking_status=delivered`。随后同一合成文件获批并绑定 Agent；混合问句 trace `7c8e2d62-10a7-4176-891b-1beefbe17e9a` 在 FAQ 草稿 Schema 失败；另一次 trace `d3c054f1-529e-4503-bece-34c479efe9b6` 工具成功、文件候选命中但复核前被 Prompt DLP 低置信位置文本拒绝，引用为空；知识单问 trace `a7f12519-5668-4a7c-98ed-7078120110c8` 同样命中但无可展示答案。这些是旧运行镜像的失败证据，不能算本 subject 的现场通过。

用户要求同一测试文档持续保留至全链路成功后再统一清理；当前文件 `agent-debug-redeploy-synthetic-policy-20261027.txt` 的 v1 审批、Agent 绑定和索引保留。未创建真实买家，未发送 TikTok 消息。尚需将此 subject 经 PR 门禁合入目标主线、手动部署，再以同一文件验证页面同时显示工具回答、七天规则和知识引用；未通过前任务维持 `VERIFYING`，production No-Go。
