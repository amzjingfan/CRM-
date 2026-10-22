---
record_id: IR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-SETTINGS-TEAM-ACCOUNTS-002
base_sha: 2a3bb5f91558fc4c709a9db1594cdcc6ef4e877c
final_sha: 257eafd3c0bcfe0c7ada3dae6433abaea9bc5482
requirement_ids: [MVP-SETTINGS-TEAM-ACCOUNTS-002]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R02.md
review_record: docs/reports/reviews/RR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R02.md
created_at: 2026-10-22T07:20:08Z
updated_at: 2026-10-22T07:20:08Z
supersedes: docs/records/implementation/IR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R01.md
---

# 实施目标与范围

R01 的账号和部门源码由 [PR #519](https://github.com/CP11-gh/CRM/pull/519) squash 合入 `main=e6322efd0deb51497e1b7b831d9417accad6a513`。本轮将该主线的前后端不可变镜像手动部署到 staging；production 未发布。

# 实际变更及原因

从干净主线工作树构建 `linux/amd64` 前后端镜像，逐一核对 OCI revision 为合并 SHA。源码 Git bundle 和镜像归档经本机与 staging 双端 SHA-256 核对；staging 的干净持久 checkout 精确匹配主线。借助既有私有 GHCR 凭据推送镜像，并按不可变摘要拉回核对。运行态原三摘要与单店人工发送、Webhook 读取、工作台翻译模式先只读保存；六角色预取、`ValidateOnly`、受限 PostgreSQL 备份后才执行 `Deploy`。

# 关键决定与偏差

GitHub Actions 在任何步骤前失败；按项目中用户已选择的手动本地门禁完成发布，不将该失败计作 CI 通过。部署没有创建真实员工账号、改变 TikTok 发送目标或外发消息。

# 数据、配置、接口与迁移影响

部署门禁将 staging 迁移从 `025_workspace_actions` 升至唯一 head `026_team_accounts_departments`。备份为 staging 私有 `0600` 文件，`pg_restore -l` 可读取；低敏哈希与运行摘要见[部署证据](../../../release/evidence/staging/crm-staging-team-accounts-departments-20261022.json)。新账号或部门写入后，迁移降级会失败关闭；恢复必须保存部署后新增消息和业务数据，不直接用旧备份覆盖。

# 验证交接

R01 的本地完整测试和安全复核继续有效；本次实际部署、迁移、服务、公网页面及部署页面合成浏览器结果见关联 R02 TR。已登录管理员的真实页面显示尚待用户核对。

# 限制、风险与回滚

旧后端、前端和检索摘要及私有备份保留在 staging 恢复点。旧应用与新 schema 的实际回滚未演练，不能将镜像保留或备份可读等同于无损回滚验证。并发限制、角色权限和咨询分配逻辑仍按用户决定暂不执行。
