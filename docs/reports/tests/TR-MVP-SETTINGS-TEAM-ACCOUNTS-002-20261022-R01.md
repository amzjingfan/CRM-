---
record_id: TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-SETTINGS-TEAM-ACCOUNTS-002
tested_sha: 257eafd3c0bcfe0c7ada3dae6433abaea9bc5482
implementation_record: docs/records/implementation/IR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R01.md
requirement_ids: [MVP-SETTINGS-TEAM-ACCOUNTS-002]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows local worktree; Python 3.11 uv; isolated Docker postgres-test; Next.js production build and local Chrome; no real customer data
created_at: 2026-10-22T06:55:51Z
updated_at: 2026-10-22T06:55:51Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

测试源码仅位于 `src/tests/backend/`、`src/tests/integration/postgres/` 与 `src/tests/frontend/`。隔离 PostgreSQL 使用 Compose `test` profile 的临时库，迁移到 `026_team_accounts_departments` 后测试；前端使用本机生产构建与合成 API 拦截，不接入真实店铺。

# 命令和逐项结果

| 命令／检查 | 本次结果 |
|---|---|
| `uv run ruff check . ../tests/backend ../tests/integration/postgres`、`ruff format --check` | 通过；333 文件格式通过 |
| `uv run mypy app scripts` | 通过；192 源文件 |
| `./src/scripts/run-postgres-integration-tests.ps1` | 迁移到唯一 head 后，2267 passed、3 skipped；跳过项依赖 POSIX bash |
| 隔离库 `alembic upgrade head → downgrade 025_workspace_actions → upgrade head → current --check-heads` | 通过；唯一 head `026_team_accounts_departments` |
| 新账号无邮箱创建、账号／邮箱认证、密码令牌版本、跨店部门拒绝、部门移除保留 RBAC 的定向测试 | 最后兼容性调整后 10 passed；新数据库路径另 1 passed |
| `npm run typecheck`、`npm test`、`npm run build` | 通过；契约 47/47，部门页进入生产构建 |
| `npm run lint` | 0 error、5 warning；均为已有导航与图片规则 |
| `UI_CACHE_EXPECT_PRODUCTION=1; npm run test:ui` | 生产模式 60/60，通过账号创建、部门成员移出、待定义权限入口及其余回归 |

初次迁移测试发现新增 revision 错接到旧版本，形成双 head；已改接 `025_workspace_actions` 后完整迁移与往返检查通过。开发模式缓存用例预期与 Next 开发服务器不同，改在生产模式复测全部通过；未修改缓存断言。

# REQ/AC 与证据映射

- AC-01：账号列表、搜索、抽屉、创建与停用由生产模式浏览器回归及构建覆盖；密码修改由后端测试覆盖。
- AC-02：用户名／邮箱、旧 `email` 字段与旧邮箱创建兼容、密码重置令牌失效由认证单元与隔离数据库测试覆盖。
- AC-03：部门路由、店铺隔离、成员移出仅删除组织关系由单元、浏览器与隔离 PostgreSQL 测试覆盖。
- AC-04：时区／并发数字段经 schema、数据库与页面回显；权限按钮禁用由浏览器测试覆盖。
- AC-05：本地静态、迁移、完整回归通过。staging 精确镜像、备份、发布及真实登录态页面尚未执行。

# 缺陷、未执行项与残余风险

本记录不声称 staging 已部署、真实员工账号登录或生产放行。GitHub Actions 的历史零步骤失败不能计作本次 CI 通过。3 个后端跳过项属于 Windows 缺少 POSIX bash；不涉及新账号／部门路径。并发限制、角色权限与咨询分配规则按用户决定暂不实施。

# 结论和复测条件

本地源码与隔离数据验证通过；因 staging 发布和真实页面验收未完成，任务总体为 `PARTIAL`。部署后需核对迁移头、运行摘要、健康、账号及部门页面，再补现场结论。
