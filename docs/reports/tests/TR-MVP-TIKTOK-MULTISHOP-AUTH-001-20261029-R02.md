---
record_id: TR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261029-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-TIKTOK-MULTISHOP-AUTH-001
tested_sha: c289a9a07e9a71b244b6a07b93a56f9f57e3f699
implementation_record: docs/records/implementation/IR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261029-R02.md
requirement_ids: [MVP-TIKTOK-MULTISHOP-AUTH-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows 11; uv Python 3.11; Node/npm and local Chrome; dedicated pgvector/pg16 tmpfs container at 127.0.0.1:5434; synthetic TikTok client and browser fixtures
created_at: 2026-10-29T01:23:33Z
updated_at: 2026-10-29T01:23:33Z
supersedes: docs/reports/tests/TR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01.md
---

# 测试范围、环境与 TEST_LAYOUT

在隔离 worktree 的最终功能树上执行，测试布局为 `centralized`。专属临时 PostgreSQL/pgvector 容器只绑定本机 5434，已在测试结束后停止并自动移除；既有 5433 测试服务未触碰。未读取真实 TikTok 或 staging 数据。

# 命令和逐项结果

- `uv run python -m pytest -q`，`DATABASE_URL` / `TEST_DATABASE_URL` 指向专属隔离库：**2394 passed、3 skipped、2 warnings**。3 项为 Windows 上要求 POSIX 的既有用例；警告来自 Starlette/httpx 和 passlib/argon2。
- 同命令不提供测试数据库时：**2340 passed、57 skipped**；另在隔离库定向执行 TikTok 多店、OAuth 任务、旧 OAuth 与 Agent 协作集成测试：**8 passed**。TikTok/OAuth 及迁移文档定向后端：**125 passed**。
- `uv run alembic heads` / `current`：唯一头 `041_merge_agent_multishop_collab`。隔离库从 base 升到 `041`；明确降至 `034_agent_debug_runs` 后重升 `041` 通过。合流图上相对 `downgrade -1` 返回 `Ambiguous walk`，改用明确版本目标后通过。
- `uv run ruff check app ../tests/backend ../tests/integration/postgres`：通过；`ruff format --check`：390 文件通过；`uv run mypy app scripts`：252 源文件通过；`uv lock --check`：通过。
- `npm run test`：**52/52**；`npm run typecheck`、`npm run build`：通过；`npm run lint`：0 error，8 条既有未改文件 warning。
- 本地 Next 生产构建服务及 `UI_CACHE_EXPECT_PRODUCTION=1; npm run test:ui`：**134/134**，含多店勾选和主线店铺刷新、Agent/知识库交互；无浏览器跳过。
- `git diff --cached --check` 与冲突标记搜索：通过。功能 subject 提交后只编写 IR/TR/RR、派生索引、任务及恢复状态，不改变受测产品树。

# AC 与证据映射

- AC-01：定向 OAuth 正常/空/多店、过期、重放、冲突与生产浏览器选择测试。
- AC-02：隔离数据库共享授权、行锁认领、逐店凭证及跨店权限测试。
- AC-03：既有单店授权与刷新回归，完整后端及前端兼容回归。
- AC-04：唯一迁移头、`034→041→034→041` 路径、完整隔离库后端、前端生产构建与审查。

# 缺陷、未执行项与残余风险

首次直接调用 `uv run pytest` 在本机脚本入口未设置项目 import path，收集失败；使用仓库配置可工作的 `uv run python -m pytest` 重跑并通过完整套件。未运行真实多店卖家 OAuth、真实 Webhook、真实平台读取/发送、staging 或 production；这些不包含在本地 PASS 内。8 条前端 lint warning 来自本任务未改文件。

# 结论和复测条件

功能集成的本地适用门禁通过。若 PR 最终源码树变化，必须重跑受影响验证；staging 发布须单独核对备份、迁移、镜像摘要、原单店人工辅助和真实多店只读链路。
