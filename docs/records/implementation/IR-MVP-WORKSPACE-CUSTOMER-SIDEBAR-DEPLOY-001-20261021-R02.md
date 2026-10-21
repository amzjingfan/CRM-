---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001
base_sha: 15ceabf8eac90f2fe8c7843e24af26381c3e0499
final_sha: 15ceabf8eac90f2fe8c7843e24af26381c3e0499
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R02.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R02.md
created_at: 2026-10-21T02:42:00Z
updated_at: 2026-10-21T02:42:00Z
supersedes: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R01.md
---

# 目标与已执行范围

将用户三张真实 staging 截图指出的订单、商品及优惠券字段修复，从已合并 `main=15ceabf8eac90f2fe8c7843e24af26381c3e0499` 手动发布到 staging。未使用 GitHub Actions 作为发布门禁，未触及 production。

# 变更和恢复点

在干净持久 Git checkout 上通过 GitHub 当前 main 与 Rootless `CheckOnly` 核对；从该 SHA 构建后端与前端镜像并以不可变摘要预取到 staging。切换前保留原三个摘要、原单店发送模式和 `0600` PostgreSQL 私有备份。六角色预取、`ValidateOnly` 与 `Deploy` 均通过；当前运行摘要、迁移头、固定出口、三项公网健康及 11 服务状态见[低敏现场证据](../../../release/evidence/staging/crm-staging-customer-sidebar-real-fields-deploy-20261021.json)。

# 边界和偏差

原单店人工发送、Webhook 读取与工作台翻译保持开启；自动回复、通用 LLM 与高风险写入保持关闭。本次未发送买家消息、退款或发券。Codex 应用内浏览器读取连续超时，已登录页面的发布后视觉验收仍待用户刷新截图，不能用健康或合成浏览器结果替代。

# 回滚

旧摘要与私有备份留在 staging；恢复前应先保护切换后新增数据，再以原单店范围和旧不可变摘要走现有手动 validate/deploy。不能直接用旧数据库备份覆盖新增消息。Production G8 仍 No-Go。
