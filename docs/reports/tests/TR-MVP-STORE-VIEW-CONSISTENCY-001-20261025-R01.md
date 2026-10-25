---
record_id: TR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-STORE-VIEW-CONSISTENCY-001
tested_sha: 35c3929e1d2c88ba965d4ac2f39391a826412fb0
implementation_record: docs/records/implementation/IR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R01.md
requirement_ids: [MVP-STORE-VIEW-CONSISTENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows local worktree; isolated pgvector/pgvector:pg16 PostgreSQL at 127.0.0.1:15439; Next.js 16.4.2 production build at 127.0.0.1:3101; synthetic browser fixtures
created_at: 2026-10-25T03:19:00Z
updated_at: 2026-10-25T03:19:00Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`，测试源码均在 `src/tests/`。使用本任务独立临时 PostgreSQL 容器和合成数据，不读取或写入 staging/production 店铺。源码候选为 `35c3929e1d2c88ba965d4ac2f39391a826412fb0`；除本记录、IR/RR、任务和索引证据外，工作树无后续交付源码修改。

# 命令和逐项结果

- `DATABASE_URL=... TEST_DATABASE_URL=... PYTHONPATH=src/backend PYTHONUTF8=1 uv run --frozen python -m pytest -q`：精确候选上 **2398 passed、3 skipped、2 warnings**，耗时 202.96 秒。两条警告来自 Starlette/httpx 和 passlib/argon2 的弃用提示；无测试失败。
- 文件生命周期、OpenAPI 和迁移定向测试在候选前最终格式化后 **15 passed、1 warning**。隔离数据库实际验证跨店分类 404、同店分类修改、归档、恢复、软删除、重复幂等请求、版本和审计留存。
- `uv run ruff check app ...`、`uv run ruff format --check app ...` 通过；184 个检查范围文件符合格式。 `uv run mypy app`：176 个源文件无错误。
- `npm run test`：前端契约 **48/48**。`npm run build`：Next.js 16.4.2 生产构建和 TypeScript 检查通过，16 条动态路由生成。`npm run lint`：0 error、7 条既有 warning。
- 从生产构建在 127.0.0.1:3101 运行 `UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui`：**108/108**。覆盖知识 FAQ/文件详情等宽、切店清除旧详情、文件调整分类/归档/删除、1 FAQ + 21 文件可到第二页、看板旧响应、营销旧编辑器、工作台旧菜单及迟到会话详情；浏览器 API 全部拦截为合成数据。
- 独立 PostgreSQL 执行 `uv run alembic current`、`uv run alembic downgrade -1`、`uv run alembic upgrade head`，实测迁移头依次为 `032_knowledge_file_archive → 031_reception_policy_schedule → 032_knowledge_file_archive`。此验证在无归档数据的隔离库进行，含归档数据时的有意拒绝降级由迁移代码和审查覆盖。
- `git diff --cached --check` 及候选提交后的 `git status` 核对无交付源码未提交差异；未跟踪的 Next 自动生成 `src/frontend/AGENTS.md` 按项目未知文件规则保留且未纳入提交。

# REQ/AC 或门禁与证据映射

- AC-01：浏览器测试确认知识详情切店立即关闭，旧数据不重现；迟到工作台详情、看板指标和营销编辑状态均不能跨店铺展示。
- AC-02：文件详情与 FAQ 外框等宽；新文件操作及同名显式替换经浏览器和后端 API 测试，版本保持不可变，归档/删除保留历史和审计。原有复核、下载、FAQ 审批及导入测试仍在完整回归中通过。
- AC-03：服务端分类总数继续在数据库筛选后计算；浏览器覆盖 1 条 FAQ + 21 个文件的第二页到达。类型和状态筛选的页内范围已在页面及产品文档明示。
- AC-04：看板、营销、工作台的确认竞态有回归；Agent 页无店铺切换入口，未改动。文件列表批量查询测试确认查询数不随文件数逐行增加。
- AC-05：完整本地后端、前端契约、生产浏览器、格式、lint、类型、构建、迁移及审查均完成。

# 缺陷、未执行项与残余风险

真实 staging 页面未部署或点击验收，不能把合成浏览器用例表述为真实店铺现场通过。GitHub Actions/PR 合并检查不属于本地 PASS 结论，须读取 PR 实际状态。三个 skipped 和两条依赖弃用 warning 如实保留。类型与状态的全库筛选尚无统一服务端接口；当前页内筛选不改变分类总数口径。含归档数据的迁移降级会拒绝无损回退。

# 结论和复测条件

对候选提交的本地既定验收为 **PASS**。若合并后源码树变化、API 或迁移调整，应重跑受影响门禁。staging 和 production 均需要独立部署与现场证据；production G8 No-Go 不因本记录改变。
