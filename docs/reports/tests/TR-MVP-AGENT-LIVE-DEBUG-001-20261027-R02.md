---
record_id: TR-MVP-AGENT-LIVE-DEBUG-001-20261027-R02
record_type: test
revision: R02
status: PARTIAL
task_id: MVP-AGENT-LIVE-DEBUG-001
tested_sha: b1053d4027266df3d334f67db3bae8aa5724e96e
implementation_record: docs/records/implementation/IR-MVP-AGENT-LIVE-DEBUG-001-20261027-R02.md
requirement_ids: [MVP-AGENT-LIVE-DEBUG-001]
acceptance_ids: [AC-02, AC-04]
environment: Windows local backend; TikTok US staging browser and low-sensitivity backend logs
created_at: 2026-10-27T07:01:49Z
updated_at: 2026-10-27T07:18:30Z
supersedes: docs/reports/tests/TR-MVP-AGENT-LIVE-DEBUG-001-20261026-R01.md
---

# 现场诊断

- 授权会话的只读 `query_logistics` 工具真实调用成功，trace `c7b66b45-4f51-4c4f-ac57-e2fd89875d35`；无可靠追踪单号时保守转人工，零平台发送。
- 合成知识文件 v2 审批并绑定后，trace `046d22ca-f419-4a90-8204-29ca46e9ebfa` 检索分数 0.7723、候选 1；trace `1a7e1edd-03c1-47d1-8118-ad182f9821d2` 分数 0.6318、候选 1。后端两次都记录 `llm_input_blocked`、`BUSINESS_PROMPT_ADDRESS_CONTEXT_AMBIGUOUS`，知识回答请求未到模型。
- 本地复现为业务词“编号”中的“号”与数字 7、商品/人工复核误组合成地址风险。测试数据清理后页面显示该店 0 份知识、无测试分类；Agent 恢复启用且无测试绑定。

# 最终候选本地验证

- `src/backend` 运行 `.venv/Scripts/python.exe -m pytest -q`：2404 passed、43 skipped、2 个依赖弃用警告，193.62 秒。
- 同目录运行 Ruff check、Ruff format check：通过，255 个文件格式正确；mypy `app`：179 个源码文件无问题。
- 新增回归用例检查普通业务编号允许，真实完整地址和“门牌编号：7”继续拦截。全量测试在合并后的 `b1053d4027266df3d334f67db3bae8aa5724e96e` 运行。
- `src/scripts/run-postgres-integration-tests.ps1`：迁移及完整隔离 PostgreSQL/pgvector 回归 2444 passed、3 skipped（POSIX Bash 专用），207.61 秒；测试容器已停止并移除。
- `src/frontend`：`npm run lint` 为 0 error、8 条既有 warning；`npm run typecheck`、`npm test` 48/48、`npm run build` 通过；生产构建下 `UI_CACHE_EXPECT_PRODUCTION=1` 的 `npm run test:ui` 为 113/113。

# 结论与剩余验证

本地修复和回归 **PASS**；修复后的 staging 尚未部署，真实模型能否从绑定知识生成带引用回答仍 **未验证**，综合状态 **PARTIAL**。现有图路由对同时包含工具问题和知识问题的单轮输入优先走工具，未证明同轮工具加 RAG 回答。PR #564 的前后端 GitHub CI 两项均在零步骤处失败，未执行测试。用户明确批准仅本 PR 用上述本地验证替代 CI 合并门禁；CI 本身不计通过。production 未放行。
