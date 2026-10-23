---
record_id: TR-MVP-MARKETING-BASIC-RECEPTION-POLICY-003-20261023-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-MARKETING-BASIC-RECEPTION-POLICY-003
tested_sha: 77c1086ca3059a2d4483eb49014fec59a298ebb5
implementation_record: docs/records/implementation/IR-MVP-MARKETING-BASIC-RECEPTION-POLICY-003-20261023-R01.md
requirement_ids: [MVP-MARKETING-BASIC-RECEPTION-POLICY-003]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows isolated worktree; uv frozen backend dependencies; dedicated PostgreSQL 16 on 127.0.0.1:5434; Next.js production build on 127.0.0.1:3102
created_at: 2026-10-23T08:41:10Z
updated_at: 2026-10-23T08:41:10Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。浏览器用例拦截 `/v1/` 并使用合成账号、店铺与策略；PostgreSQL 使用本机独立 `pgvector/pgvector:pg16` 容器中的 `crm_policy3`，不触碰 staging 数据。所有临时日志及截图在已忽略的 `src/tests/.artifacts/`。最终候选为 `77c1086ca3059a2d4483eb49014fec59a298ebb5`，包含文档摄取已合入的主线和 031 接待策略迁移。

# 命令和逐项结果

| 检查 | 本次结果 |
|---|---|
| 从空隔离库 `alembic upgrade head`，`alembic downgrade -1`，再 `upgrade head` 与 `current` | PASS，单一头 `031_reception_policy_schedule`，030 合流两条 029；降级在无新有效期数据时可逆 |
| `uv sync --frozen --all-groups` | PASS，锁文件依赖安装 |
| `uv run --frozen pytest -q -rs`，设置隔离 `TEST_DATABASE_URL` | 2381 passed、3 skipped；跳过项仅需 POSIX bash 的进程等待器；2 条已知依赖弃用 warning |
| `uv run --frozen ruff check . ../tests/backend ../tests/integration/postgres` | PASS |
| `uv run --frozen ruff format --check . ../tests/backend ../tests/integration/postgres` | PASS，373 文件格式一致 |
| `uv run --frozen mypy app scripts` | PASS，208 源文件 |
| `npm ci`、`npm run typecheck`、`npm run lint` | PASS；lint 0 error、5 条既有 warning |
| `npm run test` | 48/48 PASS |
| `npm run build` | PASS，三个基础接待路由在生产构建中 |
| `UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui`，生产 Next 服务 | 93/93 PASS |
| `git diff --check` | PASS；未知的未跟踪前端指令文件保留，未纳入提交 |

# REQ/AC 与证据映射

- AC-01：先用两家授权合成店铺复现“第二家策略 POST 成功但列表 0 条”的红测试；修复后超时和欢迎各自保存、列表重载、再次打开均可见。真实 PostgreSQL 覆盖跨店无权策略不返回、列表去重与计数。
- AC-02：生产浏览器用例覆盖多店下拉、三种有效期以及保存再编辑。Schema 负例覆盖日期缺失、反序、带时区每日时间与旧新有效期混用；迁移完成 031 升降级。按店铺时区计算的状态仅在 UI 显示。
- AC-03：浏览器用例覆盖全部/有效/失效、店铺筛选、启停、编辑、复制、排序、删除、批量关联、分页和窄视口“更多”菜单。
- AC-04：全量后端及前端回归、静态检查与生产构建已通过；自动发送开关保持关闭，浏览器测试没有真实买家外发。
- AC-05：合并后直接 staging 部署与真实已登录页面核对尚未完成，因此本记录为 `PARTIAL`。

# 缺陷、未执行项与残余风险

合并文档摄取主线后的第一次全量后端运行有两项失败：旧测试把 030 写死为迁移头；Windows 默认 GBK 解码 `git ls-files -z` 时失败。两项均已修正，并在最终候选重跑得到上述 2381/3 结果。旧前端构建运行新文档摄取浏览器用例曾失败；依赖更新与重新构建后，最终生产构建上 93/93 通过。上述失败不作为最终通过结果。

本次未在真实店铺写入策略、触发自动发送或发布 production。staging 部署仍需读取现场摘要、保留现有文档解析与人工发送模式、备份、ValidateOnly、精确部署、健康与页面核对。

# 结论和复测条件

源码候选的本地验证通过，等待合并后的直接 staging 验证；若交付源码或迁移发生变化，重跑受影响检查。真实现场结果以独立发布证据和后续 TR 修订为准。
