---
record_id: IR-MVP-WORKSPACE-BROWSER-FEEDBACK-001-20261023-R03
record_type: implementation
revision: R03
status: FINAL
task_id: MVP-WORKSPACE-BROWSER-FEEDBACK-001
base_sha: 323bbf73054c6a5719d7a20e87211a51206cb8bb
final_sha: db16111df252c4d941cfd1b6c1223a83e2c58cac
requirement_ids: [MVP-WORKSPACE-BROWSER-FEEDBACK-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-BROWSER-FEEDBACK-001-20261023-R03.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-BROWSER-FEEDBACK-001-20261023-R03.md
created_at: 2026-10-23T12:21:06Z
updated_at: 2026-10-23T12:21:06Z
supersedes: docs/records/implementation/IR-MVP-WORKSPACE-BROWSER-FEEDBACK-001-20261023-R02.md
---

# 合并主线及 staging 交付

工作台快捷回复管理入口、表情关闭、复制反馈、买卖双方头像、会话右键与订单驱动的买家阶段已合入；允许人工覆盖并恢复自动判断。源码 PR #545、#547、#550 依次合入后，最终交付源码为 `db16111df252c4d941cfd1b6c1223a83e2c58cac`；本修订记录集成与部署事实，未新增产品代码。

手动构建并导入两项精确 OCI 摘要，保留检索、文档解析、单店人工发送和翻译模式。私有 PostgreSQL、MinIO 与公网 Nginx 配置备份后执行 staging ValidateOnly、部署与迁移 031；公网 Nginx 仅增加媒体上传路径限额和超时，保留现有 `/activate/`。完整低敏现场证据见 [release/evidence/staging/crm-staging-direct-reception-workspace-20261023.json](../../../release/evidence/staging/crm-staging-direct-reception-workspace-20261023.json)。

# 边界与回滚

自动回复、自动营销及高风险写入仍关闭。未发真实 TikTok 测试消息，production 未发布。回滚使用私有备份、原前后端不可变摘要及 Nginx 旧配置；策略迁移存在新有效期数据时不得盲目降级。
