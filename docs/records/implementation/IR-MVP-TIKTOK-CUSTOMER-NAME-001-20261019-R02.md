---
record_id: IR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-TIKTOK-CUSTOMER-NAME-001
base_sha: 5e65ba37d1476d62ca444b9050e403e48e797720
final_sha: f48779af3779ef7804703feb1c6f1ff4755bbe36
requirement_ids: [MVP-TIKTOK-CUSTOMER-NAME-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R02.md
review_record: docs/reports/reviews/RR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R02.md
created_at: 2026-10-19T10:02:00+08:00
updated_at: 2026-10-19T10:02:00+08:00
supersedes: docs/records/implementation/IR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R01.md
---

# 实施结果

源码修复仍为 [PR #412](https://github.com/CP11-gh/CRM/pull/412)：TikTok 通知缺少昵称时，客户 upsert 保留已有名称；提供新昵称时正常更新。代码、接口、迁移和权限在本修订没有变化。

2026-10-19 使用 GitHub 凭据和已授权 SSH 路径，在当前 main `1476253` 的干净 staging checkout 上完成只读源码门禁及 Rootless 手动 `ValidateOnly`/`Deploy`。候选后端 OCI revision `6e1d24b` 是该 main 的祖先，`src/backend` 与 `src/docker/Dockerfile.backend` 构建输入完全相同；前端与检索镜像沿用原不可变摘要。部署门禁保持原单店人工发送、Webhook 读取及工作台翻译，自动回复、高风险写入、G5/LLM 均关闭。原后端摘要仍在 Rootless Docker 本地，可用于受审恢复；本次没有执行回滚。

低敏[现场清单](../../../release/evidence/staging/crm-staging-tiktok-customer-name-20261019.json)和 [R02 TR](../../reports/tests/TR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R02.md)记录运行摘要、健康、买家名称与未测范围。未发送 TikTok 消息，未运行 GitHub Actions，未发布 production。
