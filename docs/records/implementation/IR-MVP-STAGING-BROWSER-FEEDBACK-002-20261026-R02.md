---
record_id: IR-MVP-STAGING-BROWSER-FEEDBACK-002-20261026-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-STAGING-BROWSER-FEEDBACK-002
base_sha: cef8646ad599856b4b19b7207ef38cc8daa4c1da
final_sha: 9f3e8ee4fc0c4c71aeaf03512a59bba3f1bf42b9
requirement_ids: [MVP-STAGING-BROWSER-FEEDBACK-002]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-STAGING-BROWSER-FEEDBACK-002-20261026-R02.md
review_record: null
created_at: 2026-10-26T05:00:00Z
updated_at: 2026-10-26T05:00:00Z
supersedes: docs/records/implementation/IR-MVP-STAGING-BROWSER-FEEDBACK-002-20261026-R01.md
---

# 实施目标与范围

R01 的前端行为修复经 [PR #558](https://github.com/CP11-gh/CRM/pull/558) squash 合入 `main=4c8d2365e64e3a0d90df45107200bb8c72b32c81`，并从该干净主线直接部署 staging。本修订补记合并及现场部署事实；产品实现、接口、数据结构与权限无新增变更。

# 实际变更及原因

- 三个基础接待页面统一面包屑、标题、页内标签和卡片外框；营销浮层默认收起，展开后可由点击外部收起。
- 买家阶段改用客户侧栏同一授权会话的未筛选平台订单，已送达订单自动显示售后，人工覆盖可恢复自动；阶段颜色区分。
- 订单卡详情和收据为只读内部预览；原退款按钮没有退款执行能力，现明示暂未开放。
- staging 仅替换前端不可变镜像 `ghcr.io/cp11-gh/crm-frontend@sha256:0e46a68be38f0cc6e7a4871fb741db5e0d117db04246bdd163aed2138a49f316`。后端、检索与文档解析镜像保持原摘要，原单店人工发送及文档摄取服务保持运行。

# 关键决定与偏差

按用户明确要求手动直接部署 staging，不使用 GitHub Actions 作本次门禁。PR 检查在零步骤失败，不计作 CI 通过；采用本地生产构建、浏览器和契约测试以及现场 `ValidateOnly`、`Deploy` 门禁。部署前创建私有 PostgreSQL、MinIO 与环境快照。没有向真实买家发送消息、执行退款或发布 production。

# 数据、配置、接口、迁移或 Prompt 影响

本次无新迁移、公共 API、配置开关或 Prompt 变更。现场既有 Alembic `033_file_version_approval` 为 head，部署门禁返回 `heads_applied`；未降级或重写文档摄取数据。

# 验证交接

本地和现场逐项结果见 [TR R02](../../reports/tests/TR-MVP-STAGING-BROWSER-FEEDBACK-002-20261026-R02.md)。不可变镜像、私有备份哈希、门禁摘要及公网检查见[低敏部署证据](../../../release/evidence/staging/crm-staging-browser-feedback-20261026.json)。

# 限制、风险与回滚

真实浏览器只读核对了一个有已送达订单的会话及营销菜单；未新建/修改真实策略，也未验证真实退款或平台发票。若前端需回滚，仅恢复前端旧摘要 `sha256:0b2173969cf11fc8c92a2ab1751ec18bba89384c8c785ea1cbdd80b83c975c98` 并重新检查运行模式和公网健康；不得用旧数据库备份覆盖部署后增量。production 仍受 G8 No-Go 约束。
