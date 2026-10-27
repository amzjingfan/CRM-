---
record_id: TR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-AGENT-DEBUG-ANSWER-001
tested_sha: a4e58e53005768ec78e4e73911904a364181a087
implementation_record: docs/records/implementation/IR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R01.md
requirement_ids: [MVP-AGENT-DEBUG-ANSWER-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows local, isolated PostgreSQL/pgvector; staging pending
created_at: 2026-10-27T09:24:14Z
updated_at: 2026-10-27T09:24:14Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

测试源码位于集中式 `src/tests/`。先为截图中的固定提示、知识草稿和单轮混合问题新增行为测试并观察红灯，随后实现修复并运行受影响测试与完整隔离数据库回归。未使用真实买家资料作为测试夹具。

# 命令和逐项结果

- `uv lock --check`：通过。
- `uv run --frozen ruff check . ../tests/backend ../tests/integration/postgres`：通过。
- `uv run --frozen ruff format --check . ../tests/backend ../tests/integration/postgres`：387 个文件格式通过。
- `uv run --frozen mypy app scripts`：212 个源码文件通过。
- Agent 工作流定向测试：112 passed。
- 后端全套本地测试：2409 passed、43 skipped、2 条依赖警告。该次执行早于最终 source SHA 的测试夹具调整，仅作为辅助证据。
- **最终 source SHA** `a4e58e53005768ec78e4e73911904a364181a087`：`./src/scripts/run-postgres-integration-tests.ps1` 使用隔离 PostgreSQL/pgvector、迁移头 `034_agent_debug_runs`，2449 passed、3 skipped、2 条依赖警告；耗时 225.74 秒。测试数据库容器已停止并移除。
- `git diff --check`：待证据提交前复核。

# AC 与证据映射

- AC-01：无可信轨迹但工具成功时，安全且独立复核通过的模型不确定性回答进入人工审核；固定提示仅留给不安全或拒绝的草稿。定向回归通过。
- AC-02：已绑定文件的安全模型回答即使 `needs_human=true` 仍可显示带引用草稿。定向回归通过。
- AC-03：混合问题在调试模式分别执行授权只读工具和绑定文件检索；两部分独立复核、无效知识引用不外露。定向回归通过。
- AC-04：完整后端与隔离数据库回归通过；正式路径、店铺隔离、DLP、RAG 总超时及零平台发送边界保留。
- AC-05：staging 已登录浏览器的真实 DeepSeek、绑定文件、只读工具和回答展示尚待执行。

# 缺陷、未执行项与结论

**PARTIAL**：本地行为与回归通过；源 PR 门禁、staging 手动部署和实际 Agent 调试未完成。此前截图 trace `ea3d6ae3-106c-484e-88b3-bee7d29b9f62` 的只读迹线显示 `query_logistics:succeeded`、无知识引用、工具草稿被固定文案覆盖，作为故障定位证据，不计修复验收。未发送 TikTok 消息，未发布 production。
