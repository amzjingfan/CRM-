---
record_id: TR-MVP-AGENT-PROTOTYPE-RAG-001-20261026-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-AGENT-PROTOTYPE-RAG-001
tested_sha: 09455b510f1e8f2281d1ad4f0fb8911fc8ae6ae0
implementation_record: docs/records/implementation/IR-MVP-AGENT-PROTOTYPE-RAG-001-20261026-R01.md
requirement_ids: [MVP-AGENT-PROTOTYPE-RAG-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
environment: Windows local worktree; isolated Docker PostgreSQL with pgvector; local Next.js production build and Playwright synthetic browser
created_at: 2026-10-26T02:34:46Z
updated_at: 2026-10-26T02:34:46Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。测试源码在 `src/tests/`。隔离 PostgreSQL 容器只承载自动化合成数据，测试结束已停止移除；前端浏览器拦截 `/v1/`，未连接真实店铺、模型、TikTok 或 staging。

# 命令和逐项结果

- `src/scripts/run-postgres-integration-tests.ps1`：迁移 033 与完整后端，`2413 passed, 3 skipped`，两个现有库告警；3 个跳过均需 POSIX bash。本次新增真实 SQL 文件检索验证审批后命中、撤销后不命中。
- 同一隔离 PostgreSQL 上执行 `alembic upgrade head`、`downgrade -1`、再 `upgrade head`，最终 `alembic current` 为 `033_file_version_approval (head)`。
- 追加绑定权限后定向 `pytest`：25 passed；Ruff 检查全通过、383 个文件格式通过、mypy 177 个源文件通过。
- `npm run test`：48 passed；`npm run lint`：0 error、7 个既有规则警告；`npm run typecheck` 和 `npm run build` 通过。
- 生产构建服务 `127.0.0.1:3101` 上设置 `UI_CACHE_EXPECT_PRODUCTION=1` 运行 `npm run test:ui`：110 passed、0 skipped，包括 Agent 店铺隔离、绑定与审批、建 Agent、弹窗、五页签、预览无模型/平台调用。
- 一次 `test:ui` 在未启动本地服务时全为 `ERR_CONNECTION_REFUSED`；按测试文档启动生产构建服务后完整重跑并通过，不计代码缺陷或通过证据。

# REQ/AC 或门禁与证据映射

AC-01/02/04 由浏览器与 Agent 配置行为测试覆盖；AC-03 由文件审批、绑定门禁、SQL 条件及真实 PostgreSQL 检索测试覆盖；AC-05 由 Embedding、SQL、Rerank 定向超时测试和工作流失败终态测试覆盖；AC-06 由全量后端、前端契约/浏览器、静态检查、构建及迁移升降级覆盖。

# 缺陷、未执行项与残余风险

未进行真实 Provider 调用、staging 已登录交互或生产负载下索引构建计时。自动化无法代替人工审查文件内容与客户事实。GitHub Actions 门禁待 PR 创建后核对，不能从本地结果推断 CI 已通过。

# 结论和复测条件

当前候选本地行为与迁移验证为 **PASS**。源码合并须另外满足 PR 的适用 CI、审查和安全门禁；若索引耗时或实际店铺数据量超预期，部署前增加迁移窗口验证。
