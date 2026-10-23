---
record_id: IR-MVP-MARKETING-BASIC-RECEPTION-UI-002-20261023-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-MARKETING-BASIC-RECEPTION-UI-002
base_sha: 5adaf0be9371e2a866d1e7848858aa5a41bae686
final_sha: c7843608be82af404b938634c2e08350ed37e14f
requirement_ids: [MVP-MARKETING-BASIC-RECEPTION-UI-002]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-MARKETING-BASIC-RECEPTION-UI-002-20261023-R01.md
review_record: docs/reports/reviews/RR-MVP-MARKETING-BASIC-RECEPTION-UI-002-20261023-R01.md
created_at: 2026-10-23T06:42:19Z
updated_at: 2026-10-23T06:42:19Z
supersedes: null
---

# 实施目标与范围

按用户四条页面批注及两张参考图修复基础接待导航、快捷回复归属选择、分组管理和列表布局。用户确认停用分组后，工作台不可选该组话术，管理页继续保留编辑及重新启用能力。

# 实际变更及原因

- 智能营销默认收起，点击后只出现“营销流程”和“基础接待”；后者点击后再展开三个基础接待页面。将三个页面原有顶部重复页签移除。展开状态在当前浏览器会话内保存，以便页面跳转后保持用户选择。
- 快捷回复列表分为个人/团队与可见分组筛选，独立提供“管理分组”“添加分组”“新增快捷回复”，按参考表格展示话术。分组管理改为右侧抽屉，展示回复数量、启停状态、重命名和删除；添加分组使用单独对话框。
- 新增话术时按现有权限允许选择个人或团队归属，并加载对应分组；编辑时归属固定，避免将已有话术隐式移动到另一权限范围。
- 分组新增 `enabled` 字段与迁移 029，默认启用。分组列表返回回复数量；回复列表默认排除停用分组话术，管理页通过 `include_disabled=true` 保留查看与编辑，工作台分组入口亦隐藏停用分组。

# 关键决定与偏差

停用属于话术可选性控制，不删除分组或回复。工作台选择回复仍仅填草稿或进入既有人工审阅；没有新增自动发送路径。个人和团队仍使用原有 `workspace.reply`、`workspace.view`、`marketing.manage` 与店铺范围校验。

# 数据、接口、迁移影响

迁移 029 给 `reception_groups.enabled` 添加非空布尔列，旧分组以 `true` 回填。`GET /v1/marketing/reception/groups` 新增 `enabled`、`reply_count`；`PATCH /groups/{id}` 接受 `enabled`；`GET /replies` 增加默认 `false` 的 `include_disabled`。未新增密钥、服务、平台写入或角色权限。

# 验证交接与风险

本地隔离 PostgreSQL 升级/降级/再升级、后端全量、前端契约、类型、lint、构建和生产浏览器结果见 TR；源码审查见 RR。当前只证明候选源码，待合并后从干净主线直接手动部署 staging 并补现场记录。若回滚迁移 029，先核对新分组状态的业务影响，不能盲目降级；production 不在本次范围。
