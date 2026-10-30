---
record_id: RR-MVP-DEPARTMENT-UNIFIED-DISPATCH-001-20261030-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-DEPARTMENT-UNIFIED-DISPATCH-001
reviewed_sha: f86458c35bf4a76c2d3dc8765d1186b41cf978e0
implementation_record: docs/records/implementation/IR-MVP-DEPARTMENT-UNIFIED-DISPATCH-001-20261030-R01.md
test_record: docs/reports/tests/TR-MVP-DEPARTMENT-UNIFIED-DISPATCH-001-20261030-R01.md
review_focus: [correctness, authorization, store_isolation, login_session, migration, no_external_send]
created_at: 2026-10-30T11:28:22Z
updated_at: 2026-10-30T11:28:22Z
supersedes: null
---

# 审查范围、依据与重点风险

审查 `fe5102c5..f86458c3` 的权限查询、会话在线依据、部门派单、账号目录、迁移、前端和行为测试；依据产品与 API 当前文档以及用户的连续浏览器标注。

# 发现、级别、位置和证据

- 已修复：主管范围的源店铺必须有效，避免停用或已删店铺的残留主管角色扩展到部门其他店铺；见 `auth/store_access.py` 与全量集成回归。
- 已修复：全账号目录中不可见的其他部门不能回显为“未分部门”；账号页标记“其他部门”，浏览器回归覆盖。
- 未发现阻断级别的跨店越权、非管理员写入、自动消息发送或迁移丢失。GET 全员可用但 POST/PATCH/DELETE 仍是系统管理员加 CSRF；非管理员的独立联系方式字段清空。部门派单按真实逐店回复权限过滤，系统管理员排除候选。

# 已验证与未验证内容

2730 项后端、166 项浏览器（165 常规加 1 单独生产缓存项）、55 项契约、静态检查、生产构建与带旧数据的 044→045 迁移通过。未验证 staging 真实入站、业务库迁移或生产运行开关；需按独立发布门禁处理。

# 结论和返修条件

源码审查 APPROVE；若合并前 subject 或主线冲突导致行为代码变化，须重新绑定 SHA 并重跑受影响测试。此审查不构成 staging 或 production 放行。
