---
record_id: TR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-MARKETING-BASIC-RECEPTION-001
tested_sha: 439c50c926240e34e85d543629dab9cd03bdaea4
implementation_record: docs/records/implementation/IR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R01.md
requirement_ids: [MVP-MARKETING-BASIC-RECEPTION-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows PowerShell; isolated PostgreSQL/pgvector test Compose service; Python 3.11 via uv; Next.js 16 production build and local Chrome; centralized test layout
created_at: 2026-10-23T02:47:35Z
updated_at: 2026-10-23T03:18:16Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。后端源码验证从 `src/backend/` 执行，前端从 `src/frontend/` 执行；测试源码位于 `src/tests/backend/` 与 `src/tests/frontend/`。浏览器使用本机 Next 生产构建、Chrome 和拦截 `/v1/` 的合成数据；不连接真实 TikTok、买家或 staging。PostgreSQL 使用隔离 Compose `test` 服务，迁移到头后运行完整 pytest。

# 命令和逐项结果

| 范围 | 实际命令或入口 | 结果 |
|---|---|---|
| 后端静态检查 | `uv run ruff check . ../tests/backend ../tests/integration/postgres`; `uv run ruff format --check . ../tests/backend ../tests/integration/postgres`; `uv run mypy app scripts` | 最终候选 SHA `439c50c` 上通过；format 344 个文件已格式化，mypy 198 个源文件无错误。 |
| 前端静态、契约和构建 | `npm run lint`; `npm run typecheck`; `npm run test`; `npm run build` | 最终候选 SHA 上通过；lint 0 错误、5 条既有警告；契约 48/48；生产构建通过。 |
| 浏览器 | 本机生产构建启动后以 `UI_CACHE_EXPECT_PRODUCTION=1` 执行 `npm run test:ui` | 最终候选 SHA 上 81/81 通过，含个人优先、团队其次的快捷键选用；先前 SHA `490790e` 的 79/79 仅为开发过程结果。 |
| 后端全量与迁移 | `src/scripts/run-postgres-integration-tests.ps1` | 最终 SHA 隔离 PostgreSQL 完整脚本退出 0：2294 passed、3 skipped（仅 POSIX bash 进程等待器用例）、2 条既有依赖弃用警告，耗时 233.00 秒。重复快捷键编辑专测 7/7 通过；迁移 028 upgrade → downgrade 027 → upgrade 028 通过。先前 SHA `490790e` 的 3 条 OAuth 夹具失败和 SHA `082b6b6` 的 2294/3 绿灯均只记为开发过程。 |
| 早期后端回归 | `uv run pytest`（隔离数据库测试之前、rebase 之前） | 2266 passed、31 skipped、2 条既有警告；仅作为开发过程记录，不作为最终 SHA 门禁。 |

# REQ/AC 与证据映射

- AC-01：智能营销侧边栏三个入口、个人/团队、分组、快捷键、标签、站点、文本消息段及预览由前端浏览器测试和契约测试覆盖。
- AC-02：工作台快捷回复弹层、筛选、草稿预填、人工审阅及媒体不可用状态由浏览器测试覆盖；没有向真实平台发消息。
- AC-03：超时/欢迎策略列表、配置写入、筛选、复制、排序和开关由浏览器与后端测试覆盖；配置启用不会创建营销事件，`delivery_enabled=false`。
- AC-04：后端测试覆盖个人与团队权限、跨店铺 404、多店策略可见性、CSRF、幂等、低敏审计，以及迁移升降级；最终 PostgreSQL 全量已通过。
- AC-05：前端门禁已在本机生产构建验证。直接 staging 部署、真实登录态页面和迁移/健康冒烟尚无本次证据，不计作通过。

# 缺陷、未执行项与残余风险

隔离 PostgreSQL 全量首次报告 3 条失败；旧 OAuth 测试夹具加入真实目标店铺角色后，最终 SHA 的完整套件已绿灯。独立代码审查指出两项 P2：编辑快捷回复撞名返回 500，以及 `/快捷键` 漏查团队范围；均已修正并复测。未执行真实外部消息、图片/视频发送、自动回复、真实店铺 UI 验收和 production 发布；这些均不属于本次本地测试结果。五条 lint 警告为既有警告，无 lint 错误。

# 结论和复测条件

本地源码验证通过，但 AC-05 的合并后 staging 直接手动门禁、真实登录态与健康/迁移现场结果尚无本次证据，因此本 TR 为 `PARTIAL`。合并后的现场发布与只读页面验收需另记 R02 或独立部署证据，不得以本机合成数据代替。
