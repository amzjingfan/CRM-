---
record_id: IR-MVP-TEAM-MULTISTORE-RECEPTION-UI-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-TEAM-MULTISTORE-RECEPTION-UI-001
base_sha: 25980fd1b74cf4bed3bccf8bb3e6530090c70c14
final_sha: 0d8b66e067bad3b96e9e78db3f98cef0acc93c9e
requirement_ids: [MVP-TEAM-MULTISTORE-RECEPTION-UI-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-TEAM-MULTISTORE-RECEPTION-UI-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-TEAM-MULTISTORE-RECEPTION-UI-001-20261030-R01.md
created_at: 2026-10-30T16:17:31+08:00
updated_at: 2026-10-30T16:17:31+08:00
supersedes: null
---

# 实施目标与范围

修复 staging 标注的账号角色名称不一致、多店授权与角色编辑不可用，以及派单开关、资格和在线状态的误导性展示。不变更服务端权限和派单规则，不发送买家消息。

# 实际变更及原因

- 账号和部门页统一显示“系统管理员／客服主管／普通客服”，账号列表标出全店或授权店铺数量。
- 新建和编辑账号支持多选负责店铺、逐店选择现有角色；权限修改仍走 `PATCH /settings/team/{id}` 的 `assignments`。编辑基本资料时不提交角色，避免无意覆盖。非标准或重复角色账号只允许编辑基本资料。
- 派单页区分“开关已开启”与“当前有人可接待”；展示缺少普通客服本店授权、管理员不参与派单、账号停用等资格原因，并解释 60 秒工作台心跳。

# 关键决定与偏差

截图中的开关保存成功，无法派单由没有本店合格客服造成。保留“开关可开启、无人合格时入待领取队列”的现有产品契约。部门归属继续在部门管理页调整，账号编辑只处理逐店角色与授权。

# 数据、配置、接口、迁移或 Prompt 影响

无新接口、迁移和配置。复用现有服务器端逐店权限校验、CSRF 和审计；自动发送开关及人工发送店铺范围不变。

# 验证交接

见同任务 TR/RR。本记录只证明源码实现；staging 发布需另行按发布门禁记录。

# 限制、风险与回滚

账号角色权限由现有后端拒绝非法修改，最后一个系统管理员仍受保护。未对真实账号执行角色修改，未测试真实入站派单。回滚可恢复上一受审前端镜像，保留业务数据增量。
