---
record_id: RR-MVP-MARKETING-BASIC-RECEPTION-UI-002-20261023-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-MARKETING-BASIC-RECEPTION-UI-002
reviewed_sha: c7843608be82af404b938634c2e08350ed37e14f
implementation_record: docs/records/implementation/IR-MVP-MARKETING-BASIC-RECEPTION-UI-002-20261023-R01.md
test_record: docs/reports/tests/TR-MVP-MARKETING-BASIC-RECEPTION-UI-002-20261023-R01.md
review_focus: [authorization, store-isolation, csrf, idempotency, migration, disabled-replies, no-auto-send]
created_at: 2026-10-23T06:42:19Z
updated_at: 2026-10-23T06:42:19Z
supersedes: null
---

# 范围、依据与重点风险

审查候选源码的分组启停、回复列表 API、导航、管理/工作台页面、迁移与测试。重点核对停用语义、权限与店铺隔离、幂等/CSRF/审计沿用原写入路径，以及新 UI 不触发自动发送。

# 发现、证据与处理

未发现阻断项。停用状态经服务端默认查询过滤，管理页明确传 `include_disabled=true`，工作台选择器另过滤分组；仅在前端隐藏不足以满足该语义，故两个层次均实现。回复计数按已授权列表返回的分组 ID 聚合，未通过计数查询扩展店铺范围。团队新增选项仅对现有 `marketing.manage` 权限开放，编辑时归属不可变。迁移给旧数据启用默认值并在隔离库完成升降级。

# 已验证与未验证

后端全量 2294 passed/3 skipped、前端契约 48/48、生产浏览器 83/83、静态检查、构建及迁移实测通过。浏览器用例以合成 API 数据验证点击与响应，不代表真实店铺登录态；staging 运行摘要、迁移与界面仍需手动部署后确认。未进行真实策略写入、买家发送或 production 发布。

# 结论

`APPROVE` 源码进入 PR 与受控 staging 手动部署。若 staging 现有运行模式、源 SHA、备份或迁移门禁与本记录不符，停止部署并重新评审。
