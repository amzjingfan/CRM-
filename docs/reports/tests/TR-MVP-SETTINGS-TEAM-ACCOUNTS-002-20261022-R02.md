---
record_id: TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R02
record_type: test
revision: R02
status: PARTIAL
task_id: MVP-SETTINGS-TEAM-ACCOUNTS-002
tested_sha: 257eafd3c0bcfe0c7ada3dae6433abaea9bc5482
implementation_record: docs/records/implementation/IR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R02.md
requirement_ids: [MVP-SETTINGS-TEAM-ACCOUNTS-002]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: staging Rootless Docker; manual immutable-image deployment from merged main; synthetic API browser probe; no real employee creation
created_at: 2026-10-22T07:20:08Z
updated_at: 2026-10-22T07:20:08Z
supersedes: docs/reports/tests/TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R01.md
---

# 测试范围、环境与 TEST_LAYOUT

R01 的隔离 PostgreSQL 2267 passed/3 skipped、迁移升降级、后端静态检查、前端构建／47 契约／60 生产浏览器均是源码验证。本次新增 staging 镜像、备份、迁移、运行健康和已部署页面合成浏览器验证。临时发布脚本、镜像归档与合成浏览器副本位于已忽略的 `src/tests/.artifacts/`；正式低敏结果在[机器证据](../../../release/evidence/staging/crm-staging-team-accounts-departments-20261022.json)，原始备份和门禁 JSON 仅在 staging 私有目录。

# 命令和逐项结果

| 检查 | 本次结果 |
|---|---|
| PR #519 合并源与主线 | `main=e6322efd0deb51497e1b7b831d9417accad6a513`；前后端镜像 `linux/amd64` 标签均为该 SHA |
| Git bundle／镜像传输 | 双端 SHA-256 一致；staging 干净 checkout 为该主线 SHA；新镜像按 RepoDigest 拉回成功 |
| `Prepare-StagingRollbackImages.ps1` 与 `Test-StagingProductionGates.ps1 -ValidateOnly` | 六角色预取与配置验证通过，原单店人工发送、Webhook 读取及工作台翻译模式记录且未改变 |
| `pg_dump -Fc`、`pg_restore -l` | 私有备份 382815 字节、模式 `0600`、可列目录；SHA-256 `d919381d25131f4d574b822fc1ed9fe01249332e1b2bc440547db474cf6083a2` |
| `Test-StagingProductionGates.ps1 -Deploy` | `passed`；运行前后端摘要精确匹配候选，检索摘要不变；11 个 CRM 容器运行 |
| `alembic current --check-heads` | `026_team_accounts_departments (head)` |
| 公网 GET | `/healthz`、`/v1/health`、`/v1/health/ready`、`/settings/team`、`/settings/team/departments` 均 200；设置页 `Cache-Control` 为 `no-store` |
| 已部署页面合成浏览器 | 账号新建无店铺管理员路径、部门成员移除且权限入口禁用：2 passed、0 failed；所有 `/v1/` 请求被 Playwright 拦截，没有写入真实数据 |

GitHub Actions 两个 PR 作业各在零步骤失败，未作为 CI 通过证据。镜像构建和前述手动门禁以项目既有用户决定为替代路径。

# REQ/AC 与证据映射

- AC-01～AC-04 的源码行为和权限、CSRF、审计、迁移兼容由 R01 覆盖；本次合成页面探针确认已部署页面载入账号与部门入口及成员按钮状态。
- AC-05 的 staging 备份、迁移头、精确运行摘要与公网页面均通过。真实管理员页面的视觉核对和真实账号登录尚未执行；未创建真实员工或改变成员关系。

# 缺陷、未执行项与残余风险

新 schema 上的旧镜像回滚未实演；一旦新增账号或部门产生数据，迁移降级失败关闭，旧备份不能直接覆盖部署后的新消息。合成 API 探针不证明真实管理员的权限与页面视觉。应用内浏览器可列出 staging 标签，但新开的员工管理标签读取超时，记 `UI_UNAVAILABLE`；真实登录态检查等待用户确认。并发限制和角色权限是明确延后范围。没有 TikTok 外发或 production 发布。

# 结论和复测条件

staging 部署及合成验收通过，真实管理员页面与账号／邮箱实际登录未现场验证，因此总体保持 `PARTIAL`，任务保持 `VERIFYING`。用户确认页面后可补真实视觉验收；真实登录要在受控账号和不影响现有人员的条件下独立验证。
