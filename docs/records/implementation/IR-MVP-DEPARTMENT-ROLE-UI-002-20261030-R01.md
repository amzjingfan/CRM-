---
record_id: IR-MVP-DEPARTMENT-ROLE-UI-002-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-DEPARTMENT-ROLE-UI-002
base_sha: 98972c26752a897bf7dda1d924af5d8e1da70b00
final_sha: 0fb8202f5b39b77e085228b3dd6acc64ecf88c35
requirement_ids: [MVP-DEPARTMENT-ROLE-UI-002]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-DEPARTMENT-ROLE-UI-002-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-DEPARTMENT-ROLE-UI-002-20261030-R01.md
created_at: 2026-10-30T14:09:20+08:00
updated_at: 2026-10-30T14:09:20+08:00
supersedes: null
---

# 实施目标与范围

按参考图展示单客服部的固定角色与逐店咨询分配摘要，修复新账号部门选项和账号“更多”菜单被表格裁切的问题。

# 实际变更及原因

- 部门角色页显示管理员、主管、普通客服的按店账号数、职责与权限；沿用现有逐店角色调整，不引入自定义角色。
- 咨询分配页按店显示派单开关、参与客服、主管及待领取数；可搜索并查看现有逐店设置。
- 新建客服账号默认选择已有部门负责的店铺；所选店铺无部门时明确提示。
- 账号“更多”菜单按视口空间定位，允许向上展开；滚动、缩放、点击外部及 Escape 会关闭菜单。

# 关键决定与偏差

参考图中的自定义角色未引入。本期产品基线为单客服部及三种固定角色。菜单只调整展示和交互，未修改账号编辑或后端权限逻辑。

# 数据、配置、接口、迁移或 Prompt 影响

无数据库迁移、公共接口或开关变更；自动派单保持默认关闭，外部自动发送范围不变。

# 验证交接

见关联 TR。最终源码及测试提交为 `0fb8202f5b39b77e085228b3dd6acc64ecf88c35`。

# 限制、风险与回滚

连接店铺测试走现有标准化入站服务的合成事件，并非真实 TikTok webhook。回滚可通过撤销本提交恢复原 UI；未改动 staging 数据。
