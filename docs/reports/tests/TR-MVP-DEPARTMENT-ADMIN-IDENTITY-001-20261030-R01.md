---
record_id: TR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-DEPARTMENT-ADMIN-IDENTITY-001
tested_sha: ae94787896fb53a01a7780045253ae86763eb235
implementation_record: docs/records/implementation/IR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R01.md
requirement_ids: [MVP-DEPARTMENT-ADMIN-IDENTITY-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows, isolated PostgreSQL localhost:5433, Node 20, Next production build on 127.0.0.1:3104, synthetic browser routes
created_at: 2026-10-30T13:54:48Z
updated_at: 2026-10-30T13:54:48Z
supersedes: null
---

# 验证结果

TEST_LAYOUT: centralized。新增数据库集成断言先在旧代码失败：主管查询旧管理员账号 `login_name=None`，预期为实际邮箱登录标识。修复后该断言和管理员部门回复资格、显式参与、在线派单断言通过。只使用随机合成用户、店铺和会话；测试事务回滚，没有平台外发。

- `uv run --frozen pytest -c pyproject.toml -q`：2730 passed、3 skipped；隔离 PostgreSQL 迁移头已应用。针对 `test_reception_assignment_postgres.py` 与 `test_reception_dispatch_postgres.py`：2 passed。
- `uv lock --check`、`ruff check`、`ruff format --check`、`mypy app scripts`：全部通过。
- `npm run lint`：0 errors、8 条既有 warning；`npm run typecheck`、`npm run build`：通过；`npm run test`：55 passed。
- 生产构建 `npm run test:ui`：166 passed，其中管理员派单参与浏览器用例通过；`git diff --check` 通过。

浏览器全量第一次以未复制静态资源的 standalone 服务启动，指纹 CSS 返回 404，页面用例失败；该环境结果未计入候选。改用 `next start` 后静态 CSS 为 200，完整 166 项重跑通过。未做真实 TikTok 入站、真实买家发送或 production 验收；staging 另行验证。
