---
record_id: RR-MVP-SUPERVISOR-STORE-AUTH-001-20261031-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-SUPERVISOR-STORE-AUTH-001
reviewed_sha: 2fe8276b87d4fb26e4093ab000ccc43491453f4f
implementation_record: docs/records/implementation/IR-MVP-SUPERVISOR-STORE-AUTH-001-20261031-R01.md
test_record: docs/reports/tests/TR-MVP-SUPERVISOR-STORE-AUTH-001-20261031-R01.md
review_focus: [authorization, tenant_isolation, oauth_lifecycle, shared_credentials, migration, csrf]
created_at: 2026-10-31T01:54:21Z
updated_at: 2026-10-31T01:54:21Z
supersedes: null
---

# 审查范围、依据与重点风险

复核 `2fe8276b` 的迁移、接口与服务授权链、新店关联、跨店共享凭证、前端可见操作及测试。依据用户明确批准主管首次添加并授权新店，保持普通客服、其他部门和管理员专属写操作的边界。

# 发现、级别、位置和证据

- 原因：授权列表使用主管不具备的 `settings.channels`，新店 OAuth 中途又使用系统管理员校验，造成 403。新权限仅赋予主管并由后端逐店复核，不放开通用渠道写入。
- 高风险点：多店授权可能轮换已有卖家的共享 Token。`oauth_service.py` 在任何 Token 更新前检查现有已连接店铺的访问与管理权；单店共享凭证路径保持相同检查。跨范围拒绝测试通过。
- 高风险点：主管新增店铺没有既有逐店角色。服务端在新店创建事务内写入所属部门关联，且只有唯一负责部门的主管可发起；集成测试验证新店进入授权可见范围。
- 授权回调不依赖浏览器 Cookie，但一次性 state 绑定原发起用户；任务进度和确认仍核对原发起人、权限与 CSRF。普通客服路由负例通过。
- 店铺别名、授权删除和 Mock 渠道写入仍受原管理员校验，主管界面不展示这些入口；前端隐藏只改善体验，后端仍是权威边界。

# 已验证与未验证内容

静态、类型、70 项定向、2984 项适用后端、77 项前端契约和生产构建通过；独立数据库迁移到 047。未进行真实 TikTok 回调、staging 登录态交互或 production 发布。历史专用 Agent 模板运行模块未在此次复用的数据库上运行，其范围独立，见 TR。

# 结论和返修条件

同意合并当前权限修复。若 staging 迁移/回显或实际 OAuth 失败，应按受审发布门禁停止并回到同任务修复；不可通过关闭 CSRF、店铺隔离或共享凭证校验绕过。
