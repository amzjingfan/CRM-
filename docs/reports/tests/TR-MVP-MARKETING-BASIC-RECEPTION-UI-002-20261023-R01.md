---
record_id: TR-MVP-MARKETING-BASIC-RECEPTION-UI-002-20261023-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-MARKETING-BASIC-RECEPTION-UI-002
tested_sha: c7843608be82af404b938634c2e08350ed37e14f
implementation_record: docs/records/implementation/IR-MVP-MARKETING-BASIC-RECEPTION-UI-002-20261023-R01.md
requirement_ids: [MVP-MARKETING-BASIC-RECEPTION-UI-002]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows isolated worktree; dedicated local PostgreSQL 16 on port 5434; Next.js production server on 127.0.0.1:3101
created_at: 2026-10-23T06:42:19Z
updated_at: 2026-10-23T06:42:19Z
supersedes: null
---

# 范围、环境与布局

`TEST_LAYOUT: centralized`。真实数据库测试仅连接本任务独立的临时 `pgvector/pgvector:pg16` 容器，不使用 staging 客户数据。生产浏览器测试拦截 `/v1/` 并注入合成账号、店铺与话术；本地截图仅保留在已忽略的 `src/tests/.artifacts/`。

# 命令与结果

| 检查 | 本次结果 |
|---|---|
| `alembic upgrade head`、`downgrade 028_basic_reception_config`、再 `upgrade 029_reception_group_enabled` | PASS，最终头为 029 |
| `uv run --frozen python -m pytest -q -rs`，隔离 `TEST_DATABASE_URL` | 2294 passed、3 skipped；跳过项仅本机缺 POSIX bash 的进程等待器 |
| `uv run --frozen ruff check app/reception`、`ruff format --check app/reception`、`mypy app/reception` | PASS |
| `npm run test` | 48/48 PASS |
| `npm run typecheck`、`npm run lint` | PASS；lint 0 error、5 条既有 warning |
| `npm run build` | PASS，三个基础接待页面包含在生产路由 |
| `UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui` | 83/83 PASS |
| `git diff --check` | PASS |

# 验收映射

- AC-01：浏览器检查初始收起、两层点击展开、三个页面链接及跨页面选择保持。
- AC-02：浏览器在个人列表中新增团队归属话术，验证写入范围及分组；源码中编辑归属选择器禁用且更新请求不包含归属。
- AC-03：浏览器检查独立添加分组、右侧管理抽屉、超过首个 API 页的分组、状态开关；截图核对布局。
- AC-04：隔离 PostgreSQL 验证停用后默认回复列表为 0，管理查询仍有 2 条，启用后恢复；浏览器验证停用状态仍可管理且不向消息接口写入。
- AC-05：本地迁移、权限、回归与构建已通过；合并后的直接 staging 部署和真实登录页面核对待执行。

# 限制与复测条件

当前为源码候选 `PARTIAL`，未部署 staging，未在真实登录态变更任何话术，未向 TikTok 买家发送消息。部署后需验证精确镜像摘要、迁移头、运行模式、健康与真实页面，再追加现场记录；production 仍为 No-Go。
