---
record_id: RR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-SETTINGS-TEAM-ACCOUNTS-002
reviewed_sha: 257eafd3c0bcfe0c7ada3dae6433abaea9bc5482
implementation_record: docs/records/implementation/IR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R01.md
test_record: docs/reports/tests/TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R01.md
review_focus: [authentication, authorization, store-isolation, csrf, audit, migration, compatibility, rollback]
created_at: 2026-10-22T06:55:51Z
updated_at: 2026-10-22T06:55:51Z
supersedes: null
---

# 审查范围、依据与重点风险

审查身份查找、令牌版本、账号写入、部门组织表、管理员与店铺授权、CSRF、审计、迁移升降级及旧邮箱兼容。对照用户确认的角色权限与并发延后范围。

# 发现、级别、位置和证据

首次迁移存在双 head，已接到 `025_workspace_actions` 并通过完整升级及独立往返测试。旧邮箱创建 API 可能因新增登录名字段中断，已保留邮箱单独创建兼容并加测试。部门移出只删除 `department_members`，隔离数据库测试确认 `user_roles` 保留。密码重置提升 `auth_version`，两类旧令牌被拒绝，审计仅记录变更事实。

# 已验证与未验证内容

新部门写入依赖系统级 `admin` 与 CSRF；读取与店铺范围交集绑定，不可见部门返回 404。登录沿原 IP 限流与密码校验。新字段无凭证或客户数据入仓，真实密码不入审计。迁移对现有账号赋默认时区及并发数；含新数据时降级失败关闭。未执行 staging 数据迁移、真实账号登录或生产部署。

# 结论和返修条件

本地候选源码可进入 PR 与 staging 发布前门禁；此批准不代表 staging 或生产放行。若 staging 备份／迁移头／运行摘要不匹配，停止部署并按私有恢复快照处理；若后续定义角色或咨询分配规则，应另立需求，不在本任务中隐式扩大权限。
