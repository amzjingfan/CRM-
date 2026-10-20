---
record_id: TR-MVP-WORKSPACE-SEARCH-TRANSLATION-001-20261020-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-SEARCH-TRANSLATION-001
tested_sha: d40e904346d3b378ecabe228f9e4de6fabc813c8
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-SEARCH-TRANSLATION-001-20261020-R01.md
requirement_ids: [MVP-WORKSPACE-SEARCH-TRANSLATION-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows 11, Python 3.11.15, Node 24.19.0, isolated PostgreSQL Compose profile, local production Next.js and headless Chrome with synthetic APIs
created_at: 2026-10-20T08:19:25Z
updated_at: 2026-10-20T08:19:25Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

集中式测试位于 `src/tests/backend/`、`src/tests/integration/postgres/` 和 `src/tests/frontend/`。PostgreSQL 使用 Compose 隔离测试库并在结束后清理；浏览器测试拦截 `/v1/`，使用合成会话、订单和翻译。没有真实 TikTok 外发，也没有真实 DeepSeek 请求。

# 命令和逐项结果

- 精确 subject `d40e904346d3b378ecabe228f9e4de6fabc813c8` 上，`src/scripts/run-postgres-integration-tests.ps1`：2223 passed、3 skipped、2 warnings，退出码 0，隔离 PostgreSQL 容器已移除。
- `uv lock --check`、`ruff check app ../tests/backend ../tests/integration/postgres`、`ruff format --check app ../tests/backend ../tests/integration/postgres`、`mypy app scripts` 通过；`git diff --cached --check` 通过。
- 前端 `npm test`：47/47；`npm run typecheck` 与生产 `npm run build` 通过；`npm run lint`：0 错误、2 条既有内部跳转警告。用生产 Next.js 执行 `UI_CACHE_EXPECT_PRODUCTION=1; npm run test:ui`：38/38，通过。
- 首轮完整 PostgreSQL 回归曾因新搜索预览条件的 SQLAlchemy 自动关联失败 1 项；显式关联 `Conversation` 后复测通过。新增浏览器重试用例首轮因定位器同时匹配两处标题、第二轮因页面切换时清理失败草稿而失败；分别修正定位器和保留原会话失败草稿后，最终完整浏览器回归 38/38 通过。开发服务器上的缓存测试与生产缓存条件不符；最终使用生产构建验证。

# REQ/AC 或门禁与证据映射

AC-01：隔离 PostgreSQL 验证买家、订单、物流、商品、批量 OR、分页总数、跨店订单负向和字面 `%`；合成浏览器验证单项/批量界面。AC-02：浏览器请求体断言及 API 实现检查。AC-03：浏览器验证译文预览不发送、编辑或迟到响应使预览失效、准确文字审阅后人工确认，失败重试只在原会话显示。AC-04：后端行为测试覆盖授权、发送模式、低敏检查、审计和 Prompt 注册；路由使用现有权限、CSRF 与限流依赖。AC-05：上述全量回归、构建与静态检查。

# 缺陷、未执行项与残余风险

Windows 缺少 POSIX bash，3 项既有进程等待器用例按规则跳过；现有 Starlette/httpx 与 argon2 各 1 条弃用警告。没有对真实授权店铺执行搜索现场核对、实际 DeepSeek 翻译质量或外发消息。GitHub Actions 未用于构建/部署，也不计为本次验证证据。译文可能不准确，人工审阅是发送前的必要步骤。

# 结论和复测条件

`PASS`：AC-01～AC-05 的本地实现验收通过。部署前须另按 staging 门禁核对不可变镜像、配置、健康和只读页面；本 TR 不构成 production 放行。
