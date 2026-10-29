---
record_id: IR-MVP-RECEPTION-TEAM-FEEDBACK-001-20261029-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-RECEPTION-TEAM-FEEDBACK-001
base_sha: 47bec42bac3293225d098bf745994f6e32cc81ef
final_sha: a156d8dc8330a3f9d7a8ae56e6d8932a71d4b481
requirement_ids: [REQ-01, REQ-02, REQ-03, REQ-04]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-RECEPTION-TEAM-FEEDBACK-001-20261029-R01.md
review_record: docs/reports/reviews/RR-MVP-RECEPTION-TEAM-FEEDBACK-001-20261029-R01.md
created_at: 2026-10-29T18:19:44+08:00
updated_at: 2026-10-29T18:19:44+08:00
supersedes: null
---

# 实施目标与范围

修复用户在 staging 标注的欢迎语编辑、适用店铺悬停名单、欢迎语与超时回复操作列、员工账号删除入口。部门角色与店铺咨询分配仅形成建议，不改变运行权限和派单规则。

# 实际变更及原因

- 更新策略仅提交 `PolicyUpdate` 接受的字段；新建继续提交 `kind`。原编辑请求多带 `kind`，与后端 `extra=forbid` 冲突而返回 422。
- 策略列表在适用店铺计数悬停或键盘聚焦时展示全部名称；浮层位于表格滚动容器外，避免被裁切。共享操作列扩大并保持按钮同一行。
- 员工账号的“更多”添加删除入口。仅已停用账号可点，二次确认后调用现有永久删除接口；服务端仍执行管理员、CSRF、自删、状态和受保护引用校验。
- 同步当前产品和接口文档，添加合成浏览器行为回归。

# 关键决定与偏差

用户提供的两份角色/咨询分配文档仅作为后续方案资料。当前改动不复制其外部产品接口和权限目录；不执行真实账号删除、不自动发送或更改 staging/production。

# 数据、配置、接口、迁移或 Prompt 影响

无新 API、迁移或配置。复用已存在的 `DELETE /settings/team/{user_id}/permanent`；前端只开放其有条件入口。策略更新请求体减少一个不被接受的字段。

# 验证交接

见关联 TR。部署前需从受审源码构建并按 staging 发布门禁单独验证；本记录只证明本地候选。

# 限制、风险与回滚

真实 staging 登录态尚未复测，页面现网未因本提交改变。回滚前端提交可恢复旧 UI，不涉及数据库变更。永久删除无法恢复，运行时继续依赖服务端保护和人工确认。
