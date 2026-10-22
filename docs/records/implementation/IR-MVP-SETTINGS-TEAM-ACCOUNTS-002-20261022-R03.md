---
record_id: IR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R03
record_type: implementation
revision: R03
status: FINAL
task_id: MVP-SETTINGS-TEAM-ACCOUNTS-002
base_sha: 7d0772fe2c4583547f75a9b0e34852058db268bc
final_sha: 6bf4177d4f3768eb4e238c4545e19a50691ef44b
requirement_ids: [MVP-SETTINGS-TEAM-ACCOUNTS-002]
acceptance_ids: [AC-01, AC-03, AC-05]
test_record: docs/reports/tests/TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R03.md
review_record: docs/reports/reviews/RR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R03.md
created_at: 2026-10-22T09:14:07Z
updated_at: 2026-10-22T09:14:07Z
supersedes: docs/records/implementation/IR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R02.md
---

# 实施目标与范围

修复 staging 员工账号和部门页同时显示“系统内部错误”。账号列表是两页共享的加载请求；staging 现有 50 个容量测试账号使用专用角色，旧读取路径将数据库角色套入只接受三种可分配角色的写入模型，抛出 `ValidationError`。

# 实际变更及原因

新增只读角色响应模型，保留数据库已有角色编码；新建和修改账号的写入模型仍只允许 `admin`、`supervisor`、`agent`。前端读取类型对应改为字符串角色，写入类型不变；增加先红后绿的回归测试，并更新 API 契约。源码 [PR #522](https://github.com/CP11-gh/CRM/pull/522) 从 subject `6bf4177d` 合入主线 `c14847b1`。

# 数据、配置、接口与部署影响

无迁移、数据库写入或权限扩大。只读 `assignments[].role` 可返回已有内部角色编码；可分配角色范围不变。前端仅有编译后擦除的类型变化，staging 保留原前端和检索镜像，仅按新主线源码构建、推送、部署后端不可变镜像。保留原单店人工发送、Webhook 读取和工作台翻译运行设置。

# 验证交接

复现、提交后本地测试、备份、手动 staging 门禁、真实数据服务层只读复测及公网健康见 [TR R03](../../reports/tests/TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R03.md) 和[低敏机器证据](../../../release/evidence/staging/crm-staging-team-list-legacy-role-fix-20261022.json)。已登录管理员两页的实际浏览器确认仍在等待用户回复。

# 限制、风险与回滚

未创建真实员工、发送买家消息或发布 production。staging 私有备份可读取、旧镜像摘要保留，但不把它们当作已演练的无损回滚；恢复前应核对部署后的业务增量。原任务的受控账号／邮箱实际登录验收仍待完成。
