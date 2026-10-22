---
record_id: TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R03
record_type: test
revision: R03
status: PARTIAL
task_id: MVP-SETTINGS-TEAM-ACCOUNTS-002
tested_sha: 6bf4177d4f3768eb4e238c4545e19a50691ef44b
implementation_record: docs/records/implementation/IR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R03.md
requirement_ids: [MVP-SETTINGS-TEAM-ACCOUNTS-002]
acceptance_ids: [AC-01, AC-03, AC-05]
environment: local Windows Python 3.11 and Node 20; staging Rootless Docker with existing test accounts
created_at: 2026-10-22T09:14:07Z
updated_at: 2026-10-22T09:14:07Z
supersedes: docs/reports/tests/TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R02.md
---

# 测试范围、环境与 TEST_LAYOUT

回归源码位于唯一测试根 `src/tests/backend/auth_security/`；临时打包与部署脚本位于已忽略的 `src/tests/.artifacts/`。正式部署摘要见[机器证据](../../../release/evidence/staging/crm-staging-team-list-legacy-role-fix-20261022.json)，备份与门禁完整 JSON 仅保留在 staging 私有目录。

# 命令和逐项结果

| 检查 | 本次结果 |
|---|---|
| 故障复现 | 旧 staging 服务层 `list_team` 以真实账号数据抛出 `ValidationError`，字段 `role` 为 `literal_error`；数据库聚合确认 50 个现有专用角色账号。新回归测试在改源码前同样失败。 |
| subject 提交后的 `uv run --frozen python -m pytest -q` | 2244 passed、30 skipped；跳过项含未启动隔离 PostgreSQL 的集成测试。 |
| Ruff check／format、`mypy app scripts` | 均通过，mypy 192 个源码文件无错误。 |
| 前端 `typecheck`、`npm run test`、`npm run build` | 通过；契约 47/47，生产构建包含账号与部门页。`npm run lint` 0 错误、5 条既有警告。 |
| 主线与镜像 | [PR #522](https://github.com/CP11-gh/CRM/pull/522) squash 合入 `main=c14847b1`；受审源码 bundle 与后端镜像传输双端哈希一致，后端 GHCR 摘要拉回验证。 |
| staging 私有备份与部署门禁 | `pg_dump -Fc`、`pg_restore -l`、模式 `0600`；六摘要预取、`ValidateOnly=validated`、`Deploy=passed`，前端／检索摘要未变。 |
| 部署后只读复测 | 同一 staging 服务层 `list_team` 返回 51 个账号（含 50 个专用角色），可全部序列化；`list_departments` 返回 0 个部门；部署后日志 `ValidationError` 计数 0。 |
| 运行和公网 | 数据库 `026_team_accounts_departments (head)`；11 个 CRM 容器运行，五个健康／页面入口均 HTTP 200；原人工发送目标仍为一个店铺。 |

GitHub Actions 本 PR 两作业再次在零步骤失败，未计作 CI 通过；沿用项目已采用的本地质量检查与 staging 手动门禁。部署页 HTTP 200 与服务层通过不能冒充已登录浏览器验收。

# REQ/AC 与证据映射

- AC-01、AC-03：员工列表对历史／测试角色不再整体失败；部门页共享员工请求也可完成。实际浏览器显示等待用户确认。
- AC-05：写入角色校验仍拒绝专用角色；源码静态检查、本地回归、备份与 staging 门禁如上。既有认证、CSRF、店铺隔离和审计未改动。

# 缺陷、未执行项与残余风险

本轮未启动隔离 PostgreSQL 完整集成入口；此处复测使用 staging 现有数据，只读且不创建账号。原任务的受控账号／邮箱登录、真实管理员两页界面确认尚待完成；旧镜像在新 schema 上的回滚仍未实演。未发送外部消息或发布 production。

# 结论和复测条件

导致两页 500 的真实数据读取路径已先红后绿，并在 staging 部署后重跑通过；登录态浏览器确认与原任务的登录验收未完成，整体保持 `PARTIAL`、任务保持 `VERIFYING`。
