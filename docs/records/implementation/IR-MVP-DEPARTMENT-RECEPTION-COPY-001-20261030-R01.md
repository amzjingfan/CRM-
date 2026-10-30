---
record_id: IR-MVP-DEPARTMENT-RECEPTION-COPY-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-DEPARTMENT-RECEPTION-COPY-001
base_sha: 4bcc638f13587c54e374c705c9b9c5bc947c038e
final_sha: af29152e19ad252a5bb6f25c0b33b84a42cf511a
requirement_ids: [MVP-DEPARTMENT-RECEPTION-COPY-001]
acceptance_ids: [AC-01, AC-02]
test_record: docs/reports/tests/TR-MVP-DEPARTMENT-RECEPTION-COPY-001-20261030-R01.md
review_record: null
created_at: 2026-10-30T12:15:35Z
updated_at: 2026-10-30T12:15:35Z
supersedes: null
---

# 目标与变更

根据用户对 staging 部门派单页的反馈，移除重复解释主管、客服和在线规则的长段落。部门标题已有负责店铺，派单开关、待领取原因、客服资格表继续呈现操作所需状态。只改前端组件和对应合成浏览器用例；不改变派单 API、权限、在线判断或发送开关。

# 验证与恢复

行为测试先因冗余段落存在而失败，移除后通过；详情见 [TR](../../reports/tests/TR-MVP-DEPARTMENT-RECEPTION-COPY-001-20261030-R01.md)。恢复可回退该前端提交，不涉及迁移或数据。
