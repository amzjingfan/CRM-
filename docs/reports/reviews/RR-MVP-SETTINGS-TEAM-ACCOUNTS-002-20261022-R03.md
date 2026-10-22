---
record_id: RR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R03
record_type: review
revision: R03
status: APPROVE
task_id: MVP-SETTINGS-TEAM-ACCOUNTS-002
reviewed_sha: 6bf4177d4f3768eb4e238c4545e19a50691ef44b
implementation_record: docs/records/implementation/IR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R03.md
test_record: docs/reports/tests/TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R03.md
review_focus: [read-contract, role-assignment, store-scope, staging-boundary, rollback]
created_at: 2026-10-22T09:14:07Z
updated_at: 2026-10-22T09:14:07Z
supersedes: docs/reports/reviews/RR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R02.md
---

# 审查范围、依据与重点风险

检查账号列表对已有内部角色的读取修复及其对创建／编辑权限边界的影响，核对真实 staging 复现、部署门禁、原运行模式和恢复材料。

# 发现、级别、位置和证据

根因在 `app/users/service.py` 的只读 `_assignment_rows` 重用了 `TeamRoleAssignment` 写入模型。新 `TeamRoleView` 只用于服务输出和 `TeamMemberView`；`TeamMemberCreate`、`TeamMemberUpdate`、`_validate_assignments` 仍限制可分配角色和范围。前端仅放宽读取类型，UI 对未知角色显示原编码，不据此授予权限。回归测试同时证明已有角色可序列化、新写入仍被拒绝。

staging 与本地复测证据见 TR R03；部署未改数据库模型、认证、CSRF、店铺隔离或现有人工发送目标。前端和检索镜像未替换。GitHub Actions 零步骤失败未冒充 CI 通过。

# 已验证与未验证内容

审查了实际源码差异、提交后本地门禁、受审主线与不可变后端摘要、私有备份、运行摘要及同一 staging 数据的读路径。未创建账号、测试真实登录、向买家发消息或演练旧镜像回滚；登录态页面需用户确认。

# 结论和返修条件

批准这次只读兼容修复和受限 staging 部署；原任务继续 `VERIFYING`。若用户刷新后仍见错误，以新 trace 和当前镜像摘要重新定位，不能用旧备份覆盖后续业务数据。
