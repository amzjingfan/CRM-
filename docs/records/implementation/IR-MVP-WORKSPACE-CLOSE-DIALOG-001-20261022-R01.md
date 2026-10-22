---
record_id: IR-MVP-WORKSPACE-CLOSE-DIALOG-001-20261022-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-CLOSE-DIALOG-001
base_sha: 819e89cc795ae72d5cd92d930ed545f6a8f74b37
final_sha: 3afb15f8f5465a3e8c25fb7cfe801e147bd0b2e9
requirement_ids: [MVP-WORKSPACE-CLOSE-DIALOG-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CLOSE-DIALOG-001-20261022-R01.md
review_record: null
created_at: 2026-10-22T01:23:04Z
updated_at: 2026-10-22T01:23:04Z
supersedes: null
---

# 实施目标与原因

工作台右上角“关闭会话”直接调用 `window.confirm`，因此用户看到浏览器原生提示框，与工作台样式及已有站内弹窗不一致。

# 实际变更

- 用现有动作弹窗样式的站内 `<dialog>` 显示当前客户、关闭影响、取消和确认；打开后焦点留在弹窗内。
- 取消、Escape 和切换会话均清除待确认目标，不调用关闭接口。确认只提交打开弹窗时的会话 ID；提交期间禁用重复操作；请求失败时保持弹窗并显示可重试错误。原有重新打开入口保留。
- 增加合成浏览器行为回归和前端契约断言。源码 [PR #503](https://github.com/CP11-gh/CRM/pull/503) squash 合入 `main=56ea8d4e5d95951c9052220b26b3b54d051992b4`，受影响源码树与 subject 相同。

# 边界与恢复

未修改后端接口、授权、数据结构、迁移或真实 TikTok 发送范围。仅 staging 前端镜像切换；部署前后端和检索摘要相同，旧前端摘要与私有 `0600` 数据库备份保留。回滚须使用部署证据中的旧摘要、原运行模式及受审门禁；不可把数据库备份直接覆盖部署后新增数据。未向真实买家发送消息或关闭真实会话，production G8 仍为 No-Go。验证见对应 TR 与[低敏证据](../../../release/evidence/staging/crm-staging-workspace-close-dialog-20261022.json)。
