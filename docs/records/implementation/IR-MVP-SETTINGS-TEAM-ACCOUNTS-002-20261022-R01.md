---
record_id: IR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-SETTINGS-TEAM-ACCOUNTS-002
base_sha: 2a3bb5f91558fc4c709a9db1594cdcc6ef4e877c
final_sha: 257eafd3c0bcfe0c7ada3dae6433abaea9bc5482
requirement_ids: [MVP-SETTINGS-TEAM-ACCOUNTS-002]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R01.md
review_record: docs/reports/reviews/RR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R01.md
created_at: 2026-10-22T06:55:51Z
updated_at: 2026-10-22T06:55:51Z
supersedes: null
---

# 实施目标与范围

按用户提供的五张账号和部门原型更新系统设置。支持登录账号或邮箱、账号新建／编辑／改密码／停用及部门成员管理。用户确认账号并发数仅保存展示，部门切换角色／修改权限暂不执行。

# 实际变更及原因

- 登录请求接受 `identifier`，兼容旧 `email` 字段；账号名规范化为小写。新界面要求 6–16 位不可变登录账号，旧邮箱账号及旧邮箱创建 API 继续可用。
- 员工表展示指定字段和账号搜索；新建／编辑使用右侧抽屉，更多菜单提供改密码和停用。密码重置增加认证版本并立即使旧 Access/Refresh Token 失效，审计不包含密码。
- 新增部门、部门店铺和部门成员表及独立 API。读取按当前店铺权限过滤，写入需系统管理员、CSRF 与审计；移出部门只删除组织关系，不改变 `user_roles`。
- 账号并发数和时区可编辑、保存、回显，但不限制会话数。部门角色与店铺咨询分配页签、成员切换角色及修改权限控件标明待定，未增加写入逻辑。

# 关键决定与偏差

项目密码策略为至少 12 位，高于原型截图的 8 位提示；保留较强策略。手机号接受常见纯数字和带区号形式。账号昵称可空，界面创建时以登录账号作为默认昵称。部门店铺咨询分配的真实规则尚无确认依据，只呈现待定义入口。

# 数据、配置、接口与迁移影响

迁移 `026_team_accounts_departments` 接在现有 `025_workspace_actions` 后；旧用户邮箱保留，新列带默认值。只有新账号与部门均未使用时才允许降级；存在新数据时失败关闭，不能靠降级丢弃数据。接口与产品事实已同步到 `docs/architecture/`、`docs/product/` 和部署说明。无新服务、密钥、外部消息或生产操作。

# 验证交接

本地检查、隔离数据库迁移与完整后端套件、前端生产构建与合成浏览器证据见关联 TR。源码与安全边界复核见 RR。staging 部署及真实页面验收仍需独立发布门禁与后续记录。

# 限制、风险与回滚

并发数、角色权限和咨询分配逻辑尚未实施。staging 未因源码提交自动更新。部署前应对数据库建立受限备份；一旦产生新账号或部门，回退应用版本需维持兼容 schema 或制定经验证的前向恢复，不能直接使用迁移 downgrade。
