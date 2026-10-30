---
record_id: IR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-DEPARTMENT-AUTO-ASSIGN-001
base_sha: d6f8974624f64b8bec30d47f33b4a79b3f42d21d
final_sha: b21f59a76adce8775eb5f9d61993e3b42886d72a
requirement_ids: [REQ-01, REQ-02, REQ-03, REQ-04]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R02.md
review_record: docs/reports/reviews/RR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R02.md
created_at: 2026-10-30T03:29:33+00:00
updated_at: 2026-10-30T03:29:33+00:00
supersedes: docs/records/implementation/IR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R01.md
---

# 实施目标与范围

R01 的单客服部固定角色、逐店资格、默认关闭自动派单和人工归属保护源码已由 PR #646 合入主线。本修订记录用户批准后的 staging 数据清理与发布，且不扩大真实消息发送范围。

# 实际变更及原因

- 依用户精确要求清除 staging 50 个合成账号和 2 家合成店铺，保留指定管理员与 3 家店铺；清理审计、私有备份和恢复限制见 [CLEANUP-20261030-001](../../operations/cleanup/CLEANUP-20261030-001.md)。
- 从干净合并主线 `b21f59a7` 构建前后端 `linux/amd64` 私有镜像，按远端不可变摘要和 OCI revision 核对后，使用现有 Rootless staging 门禁手动发布。该主线同时包含此前已在 staging 运行的 Agent 回复修复；产品目录相对旧运行源码仅包含部门分配增量。
- 迁移从 `043_logistics_updates` 升级至 `044_reception_assignment`。三个现存店铺没有被自动开启派单，现有单店人工发送、Webhook/翻译、Agent 调试及正式人工建议模式原样保留。

# 关键决定与偏差

用户另要求“所有店铺人工真实发送、自动发送关闭”，已另立 `MVP-TIKTOK-ALL-STORE-MANUAL-SEND-001`；本次部署没有执行该扩大范围。未使用 GitHub Actions 部署，也未向真实买家发送测试消息。

# 数据、配置、接口、迁移或 Prompt 影响

运行中的后端与前端切至本次不可变摘要，数据库头为 `044_reception_assignment`；检索及解析镜像不变。私有环境文件未改，`AUTO_REPLY_ENABLED=false`、自动营销和高风险写入关闭。恢复须保留 044 后业务增量，不以旧备份覆盖当前库。

# 验证交接

本次 `ValidateOnly`/`Deploy`、备份、迁移、运行摘要、三健康、固定出口、保留数据及已登录 UI 复核见 [TR R02](../../reports/tests/TR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R02.md) 和[低敏机器证据](../../../release/evidence/staging/crm-staging-department-assignment-20261030.json)；风险复核见关联 RR。

# 限制、风险与回滚

真实 TikTok 入站触发自动派单未在 staging 演练；当前逐店派单默认关闭。若需回退应用，先核对并保留当前业务增量，再使用记录中的旧镜像和相同安全开关受控切换；不盲目降级 044 或整库恢复。production 仍未发布。
