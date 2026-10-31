---
record_id: IR-MVP-SUPERVISOR-STORE-AUTH-001-20261031-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-SUPERVISOR-STORE-AUTH-001
base_sha: 230923b110d66a9fefce7210be3e0454817dc517
final_sha: 2fe8276b87d4fb26e4093ab000ccc43491453f4f
requirement_ids: [MVP-SUPERVISOR-STORE-AUTH-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-SUPERVISOR-STORE-AUTH-001-20261031-R01.md
review_record: docs/reports/reviews/RR-MVP-SUPERVISOR-STORE-AUTH-001-20261031-R01.md
created_at: 2026-10-31T01:44:10Z
updated_at: 2026-10-31T01:44:10Z
supersedes: null
---

# 实施目标与范围

客服主管可查看所属部门店铺授权、对原店重新授权，并可首次添加及选择新 TikTok 店铺。普通客服及跨部门店铺仍无此权限。

# 实际变更及原因

原店铺授权列表由 `settings.channels` 拦截，主管无此权限；新店 OAuth 的开始、任务进度与多店确认只接受系统管理员，导致页面 403 与授权流程中断。迁移 `047_supervisor_store_auth` 为主管增加仅覆盖店铺授权的 `settings.store_authorize`，授权列表和渠道只读接口按该权限的店铺范围查询。OAuth 开始、回调、任务进度、单店完成及多店确认均复核主管是否属于唯一负责部门，新增店铺在同一事务归入该部门。复用现有店铺或卖家共享凭证前逐店核对管理权限。前端隐藏主管无权执行的别名修改、删除授权、断开渠道及 Mock 渠道写入入口。

# 关键决定与偏差

用户明确要求主管可首次添加并授权新店。新店默认归入主管的唯一负责部门；若账号同时符合多个负责部门则失败关闭，避免不确定归属。通用渠道写入、删除授权和店铺别名仍保持管理员权限。

# 数据、配置、接口、迁移或 Prompt 影响

增加一项权限及主管角色关联，可回退迁移；没有修改现有店铺、凭证、外部发送开关或自动派单。`GET /settings/store-authorizations`、`GET /settings/channels` 与 TikTok OAuth 接口采用新的授权权限，响应结构不变。产品与 API 当前文档已同步。

# 验证交接

最终代码提交为 `2fe8276b87d4fb26e4093ab000ccc43491453f4f`。相关权限、OAuth、前端契约及隔离 PostgreSQL 测试和代码审查结论见对应 TR/RR。

# 限制、风险与回滚

本地测试使用合成店铺和隔离数据库，未调用真实 TikTok 授权或发送买家消息。回滚需先恢复旧应用版本，再执行迁移 downgrade；不能直接改动真实店铺授权。生产发布仍需独立门禁。
