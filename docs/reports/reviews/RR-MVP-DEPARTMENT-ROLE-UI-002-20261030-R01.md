---
record_id: RR-MVP-DEPARTMENT-ROLE-UI-002-20261030-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-DEPARTMENT-ROLE-UI-002
reviewed_sha: 0fb8202f5b39b77e085228b3dd6acc64ecf88c35
implementation_record: docs/records/implementation/IR-MVP-DEPARTMENT-ROLE-UI-002-20261030-R01.md
test_record: docs/reports/tests/TR-MVP-DEPARTMENT-ROLE-UI-002-20261030-R01.md
review_focus: [correctness, store_isolation, authorization, no_external_send, test_cleanup]
created_at: 2026-10-30T14:09:20+08:00
updated_at: 2026-10-30T14:09:20+08:00
supersedes: null
---

# 审查范围、依据与重点风险

自审 `98972c26752a897bf7dda1d924af5d8e1da70b00..0fb8202f5b39b77e085228b3dd6acc64ecf88c35`，对照任务 AC、`docs/engineering/DEVELOPMENT.md` 和现有角色/店铺授权接口。重点为 UI 摘要不可授予权限、店铺隔离、菜单不遮挡、合成测试不外发。

# 发现、级别、位置和证据

未发现阻断项。角色与派单表仅读取现有授权 API；保存角色仍走原有逐店接口。菜单定位为客户端视口坐标，浏览器断言覆盖可见边界及底部操作命中。staging 合成事件在事务内回滚，无买家外发与残留。

# 已验证与未验证内容

已验证本地生产构建、56 项相关浏览器回归、7 项可复现的部门与派单后端测试、此前 14 项定向后端测试，以及 staging 连接测试店的受控入站逻辑。未验证真实 TikTok webhook、生产发布或 staging 新版前端页面。

# 结论和返修条件

同意合并本次 UI 修复与测试证据。若后续发现服务端角色语义或外部入站行为与现有契约不符，应单独返修并复测。
