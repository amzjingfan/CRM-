---
record_id: TR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-TIKTOK-MULTISHOP-AUTH-001
tested_sha: bfb470e5e76d1ddc52facee21708ffead73c16d3
implementation_record: docs/records/implementation/IR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01.md
requirement_ids: [MVP-TIKTOK-MULTISHOP-AUTH-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows 11; Python via uv; Node via npm; isolated PostgreSQL/pgvector Docker service on local port 55434; synthetic TikTok client and browser fixtures
created_at: 2026-10-28T09:09:46Z
updated_at: 2026-10-28T09:09:46Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

在最终 subject `bfb470e5e76d1ddc52facee21708ffead73c16d3` 的隔离 worktree 运行，布局为 `centralized`。PostgreSQL 使用专属 `crm-multishop-test` Compose 项目和本机 55434 端口，不接入 staging/production；TikTok 客户端、浏览器 API 均为合成数据。

# 命令和逐项结果

- `uv run alembic current; uv run alembic downgrade -1; uv run alembic upgrade head; uv run alembic current`：头版本最终为 `035_tiktok_seller_multishop`；降级和重升级通过。
- `uv run python -m pytest -q -rs`，`DATABASE_URL` 与 `TEST_DATABASE_URL` 均指向上述隔离库：**2459 passed、3 skipped、2 warnings**，244.24 秒。三项跳过均是 Windows 上需要 POSIX bash 的既有 process waiter 用例；两条警告来自 Starlette/httpx 与 passlib/argon2 依赖。低敏本机日志：`src/tests/.artifacts/tiktok-multishop-full-backend-final.log`，不提交。
- `uv run ruff check . ../tests/backend ../tests/integration/postgres`：通过。
- `uv run ruff format --check . ../tests/backend ../tests/integration/postgres`：388 files already formatted。
- `uv run mypy app scripts`：212 source files 无问题；`uv lock --check`：通过。
- `npm run typecheck`、`npm test`、`npm run build`：通过；前端契约 **49/49**。
- `npm run lint`：0 errors，8 条现有未改文件警告。
- 在本地生产构建服务运行 `UI_CACHE_EXPECT_PRODUCTION=1; npm run test:ui`：浏览器交互 **114/114**，0 skipped，包括多店勾选、暂存后继续、原有店铺操作与其他页面回归。
- `git diff --cached --check`：提交前通过。

# AC 与证据映射

- AC-01：OAuth 0/1/N 店铺、权限、候选选择、冲突、过期和重放测试；多店选择只发送勾选 ID。
- AC-02：共享卖家凭证逐店读取、行锁认领、一次刷新、单店撤销及无权跨店重授权拒绝测试。
- AC-03：旧单店凭证读取与刷新、平台新增第二店时继续连接、重新授权保留 CRM 店铺 ID 和历史绑定测试。
- AC-04：真实 PostgreSQL 两店共享授权及并发认领测试、迁移升降升、完整后端与前端回归、独立审查。

# 未执行项与残余风险

没有真实 TikTok 多店 OAuth、Webhook、人工发送或 staging/production 部署；本地合成测试不作为真实平台验收。未执行真实双会话撤销与选择交错场景，代码已用选中渠道行锁串行化。Windows 上 3 项 POSIX bash 用例按既有条件跳过；前端 lint 8 条现有警告不在本任务修改范围。

# 结论和复测条件

本次本地实现的适用门禁通过。部署前另行按目标环境验证迁移备份、真实多店授权、逐店凭证与 Webhook，以及已有单店人工辅助业务；生产仍由 G8 独立决定。
