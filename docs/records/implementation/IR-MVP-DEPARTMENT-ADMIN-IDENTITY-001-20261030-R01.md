---
record_id: IR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-DEPARTMENT-ADMIN-IDENTITY-001
base_sha: 57c9e7dd514b982678973b7cf7abdb95b36bed1e
final_sha: ae94787896fb53a01a7780045253ae86763eb235
requirement_ids: [MVP-DEPARTMENT-ADMIN-IDENTITY-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R01.md
created_at: 2026-10-30T13:54:48Z
updated_at: 2026-10-30T13:54:48Z
supersedes: null
---

# 目标与实现

主管只读账号目录把旧邮箱登录账号的独立邮箱字段隐藏后，登录账号栏也变为“—”。`list_team` 在非管理员响应中先以邮箱补齐缺失的登录标识，再继续清空邮箱、手机与上次登录字段；账号写入和权限不变。

系统管理员原已通过全局角色拥有全部有效店铺 `workspace.reply`，部门接待展示与真实派单查询却各自硬性排除管理员。移除这两处特例，继续要求管理员属于该部门、显式勾选参与、账号启用且登录会话有效。派单只改变 CRM 会话归属，不发送平台消息。账号编辑提示同步说明管理员可选择参与，默认不参与。

# 恢复与限制

无迁移或配置变更；可回退到发布前精确镜像。旧邮箱登录标识对所有已认证员工可见，这是本次用户要求的账号目录行为，独立联系方式仍隐藏。真实入站派单与真实买家消息不在本次本地测试范围，staging 发布另留现场证据。
