---
record_id: TR-MVP-SETTINGS-TIKTOK-STORES-001-20261022-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-SETTINGS-TIKTOK-STORES-001
tested_sha: 76767ed78682614e78ef66fedcd1284a43f2256f
implementation_record: docs/records/implementation/IR-MVP-SETTINGS-TIKTOK-STORES-001-20261022-R01.md
requirement_ids: [MVP-SETTINGS-TIKTOK-STORES-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows PowerShell; Python 3.11 via uv; Next.js 16.3.8 production build and local Chrome browser; isolated worktree
created_at: 2026-10-22T10:20:07Z
updated_at: 2026-10-22T10:20:07Z
supersedes: null
---

# 测试范围与环境

源码提交 `76767ed78682614e78ef66fedcd1284a43f2256f`。测试布局 `centralized`；后端从 `src/backend/` 运行，前端从 `src/frontend/` 运行。生产浏览器只连接本机生产构建，不触发真实 TikTok 授权或店铺删除。

# 命令与结果

- `uv run --frozen pytest -q`：2260 passed、30 skipped；跳过项为依赖受控环境的集成测试。两条第三方依赖弃用警告未改变结果。
- `uv run --frozen ruff check app ../tests/backend/platform/test_tiktok_oauth.py ../tests/backend/platform/test_tiktok_oauth_redirect.py migrations/versions/027_tiktok_direct_store_oauth.py` 与对应 `ruff format --check`：通过。
- `uv run --frozen mypy app scripts`：192 个源文件通过；`uv run --frozen alembic heads`：唯一头 `027_tiktok_direct_store_oauth`。
- `npm run typecheck`、`npm run lint`、`npm run build`：通过；lint 为 0 错误、5 条既有警告。
- `npm run test`：48 passed；生产构建本机服务上 `UI_CACHE_EXPECT_PRODUCTION=1` 的 `npm run test:ui`：62 passed，含直接授权、字段、状态/搜索、平台撤销、别名、重新添加、删除二次确认与响应式表格。
- `git diff --check` 与提交前低敏凭证模式扫描：通过。初次全量测试命令错误未加载项目 pytest 配置，改用 `uv run pytest` 后完成；初次浏览器用例因确认文案调整失败，修正断言后全量 62/62 通过。

# 验收映射与限制

AC-01/02/03 的 UI、契约及服务层行为已由本地测试覆盖；AC-04 的角色范围、OAuth 一次性 state、凭证清除、Webhook 排队边界及迁移头由后端测试和静态检查覆盖。AC-05 的 staging 镜像发布、真实登录态列表及真实卖家授权尚未执行，故本 TR 为 `PARTIAL`。无真实 TikTok 写入、无买家外发、无 production 放行；staging 部署后须另记机器证据与真实页面结果。
