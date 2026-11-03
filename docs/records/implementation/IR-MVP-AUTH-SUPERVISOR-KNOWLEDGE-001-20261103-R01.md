---
record_id: IR-MVP-AUTH-SUPERVISOR-KNOWLEDGE-001-20261103-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-AUTH-SUPERVISOR-KNOWLEDGE-001
base_sha: 7fe0788ff9c97ec0e5ed6ffc80f2946c4f89cfed
final_sha: b558a4a8c9c137e56777a64006e51b7bec4ef196
requirement_ids: [SUPERVISOR_KNOWLEDGE_MANAGE]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-AUTH-SUPERVISOR-KNOWLEDGE-001-20261103-R01.md
review_record: docs/reports/reviews/RR-MVP-AUTH-SUPERVISOR-KNOWLEDGE-001-20261103-R01.md
created_at: 2026-11-03T04:05:41Z
updated_at: 2026-11-03T06:15:03Z
supersedes: null
---

# 实施目标与范围

用户批准客服主管管理所属客服部负责的全部有效店铺的知识库。范围仅为知识管理和对应读取；不扩展普通客服、Agent 配置或消息发送权限。

# 实际变更及原因

- 迁移 `051` 给主管角色增加既有的 `knowledge.manage` 权限，逆迁移移除该角色与权限的关联。
- 知识权限的店铺集合同时要求主管角色与部门成员关系；部门店铺范围由现有共享查询产生。管理员既有全部有效店铺权限保持。
- FAQ 分类、条目、导入及通用文件的读取使用 `knowledge.view`，写入、审核与重试使用 `knowledge.manage` 核对目标资源店铺。跨店资源返回 404。
- 同步产品与 API 文档，并新增权限隔离测试、迁移链测试及隔离 PostgreSQL 实库测试。

# 关键决定与偏差

主管角色若仅残留某店的角色绑定，但已不属于该店负责部门，知识权限不再借该角色访问；其他非主管角色的店铺权限仍按自身角色绑定核对。

# 数据、配置、接口、迁移或 Prompt 影响

仅新增角色权限关联迁移，无表结构或 HTTP 形状变化。既有 CSRF、幂等、审批及审计保持；无 Prompt、外部平台或发送配置变化。

# 验证交接

见同任务 TR/RR。未部署 staging 或 production。

# 限制、风险与回滚

隔离数据库的迁移和集成回归已通过；回滚代码及迁移可撤销主管知识管理授权。不得将本地验证当作 staging 生效证据。
