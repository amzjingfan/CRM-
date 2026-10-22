---
record_id: TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R04
record_type: test
revision: R04
status: PARTIAL
task_id: MVP-SETTINGS-TEAM-ACCOUNTS-002
tested_sha: 6bf4177d4f3768eb4e238c4545e19a50691ef44b
implementation_record: docs/records/implementation/IR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R03.md
requirement_ids: [MVP-SETTINGS-TEAM-ACCOUNTS-002]
acceptance_ids: [AC-01, AC-03, AC-05]
environment: authenticated staging browser; prior local and staging checks in R03
created_at: 2026-10-22T09:21:18Z
updated_at: 2026-10-22T09:21:18Z
supersedes: docs/reports/tests/TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R03.md
---

# 本次现场验收

用户刷新 staging 的“员工 → 账号”和“员工 → 部门”后回复“两页都正常”。此前两页显示“系统内部错误”的故障已在真实登录态页面消失。低敏现场记录见[浏览器确认](../../../release/evidence/staging/crm-staging-team-list-browser-confirmation-20261022.json)。

# 继承的验证与边界

[R03](TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R03.md)记录同一 subject `6bf4177d` 的红绿回归、后端 2244 passed/30 skipped、前端 47/47、静态检查、staging 手动门禁、真实 51 账号读取及部署健康。本次仅增加用户现场确认，未重新运行这些检查；GitHub Actions 零步骤失败不计作通过。

账号或邮箱实际登录、真实账号创建／改密／停用及部门写操作未在本次现场确认。原任务继续 `VERIFYING`，本 TR 保持 `PARTIAL`；未向买家发送消息，也未放行 production。
