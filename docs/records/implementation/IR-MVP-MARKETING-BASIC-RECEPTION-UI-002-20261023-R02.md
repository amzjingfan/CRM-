---
record_id: IR-MVP-MARKETING-BASIC-RECEPTION-UI-002-20261023-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-MARKETING-BASIC-RECEPTION-UI-002
base_sha: 5adaf0be9371e2a866d1e7848858aa5a41bae686
final_sha: db16111df252c4d941cfd1b6c1223a83e2c58cac
requirement_ids: [MVP-MARKETING-BASIC-RECEPTION-UI-002]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-MARKETING-BASIC-RECEPTION-UI-002-20261023-R02.md
review_record: docs/reports/reviews/RR-MVP-MARKETING-BASIC-RECEPTION-UI-002-20261023-R02.md
created_at: 2026-10-23T12:21:06Z
updated_at: 2026-10-23T12:21:06Z
supersedes: docs/records/implementation/IR-MVP-MARKETING-BASIC-RECEPTION-UI-002-20261023-R01.md
---

# 合并主线及 staging 交付

智能营销侧栏默认收起且仅展开两项；基础接待三项改为页内导航。个人/团队话术选择、独立分组添加与管理及停用分组过滤保留。源码 PR #545、#547、#550 依次合入后，最终交付源码为 `db16111df252c4d941cfd1b6c1223a83e2c58cac`；本修订记录集成与部署事实，未新增产品代码。

手动构建并导入两项精确 OCI 摘要，保留检索、文档解析、单店人工发送和翻译模式。私有 PostgreSQL、MinIO 与公网 Nginx 配置备份后执行 staging ValidateOnly、部署与迁移 031；公网 Nginx 仅增加媒体上传路径限额和超时，保留现有 `/activate/`。完整低敏现场证据见 [release/evidence/staging/crm-staging-direct-reception-workspace-20261023.json](../../../release/evidence/staging/crm-staging-direct-reception-workspace-20261023.json)。

# 边界与回滚

自动回复、自动营销及高风险写入仍关闭。未发真实 TikTok 测试消息，production 未发布。回滚使用私有备份、原前后端不可变摘要及 Nginx 旧配置；策略迁移存在新有效期数据时不得盲目降级。
