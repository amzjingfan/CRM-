---
record_id: TR-MVP-SUPERVISOR-STORE-AUTH-001-20261031-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-SUPERVISOR-STORE-AUTH-001
tested_sha: 2fe8276b87d4fb26e4093ab000ccc43491453f4f
implementation_record: docs/records/implementation/IR-MVP-SUPERVISOR-STORE-AUTH-001-20261031-R01.md
requirement_ids: [MVP-SUPERVISOR-STORE-AUTH-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows PowerShell; uv frozen backend; Node 22 frontend; isolated pgvector PostgreSQL 16 at 127.0.0.1:5433
created_at: 2026-10-31T01:54:21Z
updated_at: 2026-10-31T01:54:21Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。对 subject SHA `2fe8276b87d4fb26e4093ab000ccc43491453f4f` 验证主管授权入口、部门归属、跨店拒绝、共享凭证影响范围、权限迁移、前端构建与回归。PostgreSQL 用 Compose 独立项目和 tmpfs，完成后删除；不访问 staging 或 TikTok。

# 命令和逐项结果

- `uv run --frozen ruff check . ../tests/backend ../tests/integration/postgres`：通过。
- `uv run --frozen ruff format --check . ../tests/backend ../tests/integration/postgres`：570 文件已格式化。
- `uv run --frozen mypy app scripts`：303 个源文件无问题。
- `uv run --frozen python -m pytest -q ../tests/backend/auth_security/test_store_authorizations.py ../tests/backend/auth_security/test_supervisor_store_oauth_routes.py ../tests/backend/platform/test_tiktok_oauth.py ../tests/backend/knowledge_base/test_document_schema.py`：70 通过。
- 独立 Compose PostgreSQL 16 执行 `uv run --frozen alembic upgrade head` 到 `047_supervisor_store_auth`；随后 `uv run --frozen python -m pytest -q -rs --ignore=../tests/integration/postgres/test_agent_template_runtime_postgres.py`：**2984 通过、5 跳过、0 失败**，耗时 283.81 秒。完整本地低敏日志位于忽略目录 `src/tests/.artifacts/supervisor-store-auth-20261031/backend-suite-accepted-url.log`；测试容器已删除。
- 前端 `npm ci`、`npm run lint`、`npm run typecheck`、`npm run test`、`npm run build`：均退出 0；契约 77 通过。Lint 有 11 条既有非阻断警告，改动页面没有新增警告。
- `git diff --check`：通过；变更文件清单与权限边界已人工复核。

# REQ/AC 与证据映射

AC-01：授权及渠道列表主管 200、普通客服 403，且服务层按 `settings.store_authorize` 缩小店铺范围。AC-02：单店及多店授权测试核对新店部门关联，真实 PostgreSQL 集成验证主管新增店铺对其可见。AC-03：无负责部门、多负责部门、跨店复用拒绝。AC-04：共享卖家凭证的其他已连接店铺越权时拒绝，先校验后轮换。AC-05：迁移及全量适用回归通过。

# 缺陷、未执行项与残余风险

第一次全量回归在独立 5436 端口执行，仓库中多项历史 Agent 模板测试硬编码只接受 5433 或其专用数据库 URL，导致 190 个 setup 错误；该次结果为 2794 通过、5 跳过、190 错误，**不作为通过证据**。待 5433 空闲后，在新的独立 Compose 数据库按其白名单 URL 重跑，获得上述通过结果。专用 `test_agent_template_runtime_postgres.py` 固定要求另一个独立数据库名和 56874 端口，此轮未运行；其范围为 Agent 模板运行，不覆盖本次授权代码。5 项跳过包括 Windows 缺 POSIX bash 3 项与模板专用迁移条件 2 项。真实 TikTok OAuth、已登录 staging 主管界面、外部消息和 production 未执行。

# 结论和复测条件

当前源码的授权范围、迁移和本地 UI 构建符合 AC-01 至 AC-05。合并后若部署 staging，须另行完成私有备份、精确镜像、迁移预检和已登录主管只读回显；本 TR 不宣称现场已修复。
