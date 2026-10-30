---
record_id: IR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-DEPARTMENT-ADMIN-IDENTITY-001
base_sha: 57c9e7dd514b982678973b7cf7abdb95b36bed1e
final_sha: 476cc8d5cf95e6304f53eec27a41d6bdaa01b056
requirement_ids: [MVP-DEPARTMENT-ADMIN-IDENTITY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R02.md
review_record: docs/reports/reviews/RR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R02.md
created_at: 2026-10-30T14:27:29Z
updated_at: 2026-10-30T14:27:29Z
supersedes: IR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R01
---

# 合并与发布

实现见 R01，代码 subject 为 `ae94787896fb53a01a7780045253ae86763eb235`。PR #673 squash 合入 main `476cc8d5cf95e6304f53eec27a41d6bdaa01b056`。从该干净合并源码构建前后端 linux/amd64 精确摘要，经私有备份、旧版/候选 ValidateOnly 和 Deploy 发布 staging。部署无新迁移，数据库仍为 `045_dept_dispatch_login`。

发布没有调整真实买家消息范围：原两家店铺人工发送、Webhook 只读和 Agent 调试/建议保持；自动回复、营销、高风险写入关闭。旧前后端摘要和私有备份为恢复点，不能用整库备份覆盖部署后的业务增量。发布原始摘要见[低敏证据](../../../release/evidence/staging/crm-staging-department-admin-identity-20261030.json)。
