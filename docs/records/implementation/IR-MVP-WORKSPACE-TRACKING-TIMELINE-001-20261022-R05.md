---
record_id: IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R05
record_type: implementation
revision: R05
status: FINAL
task_id: MVP-WORKSPACE-TRACKING-TIMELINE-001
base_sha: 326b1d358a5b3d7cc4e3053e4b447a9c8dea1a1b
final_sha: 97c5d6bb6f7734e27eaafcf779df8f8a0ff74541
requirement_ids: [MVP-WORKSPACE-TRACKING-TIMELINE-001]
acceptance_ids: [AC-05]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R05.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R05.md
created_at: 2026-10-22T04:24:00Z
updated_at: 2026-10-22T04:24:00Z
supersedes: docs/records/implementation/IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R04.md
---

# staging 发布范围

源码 [PR #509](https://github.com/CP11-gh/CRM/pull/509) 已 squash 合入 `main=326b1d35`，其后端、前端和对应 Dockerfile 的 Git 树与 R04 subject 相同。从干净的精确 main SHA 分离工作树构建 `linux/amd64` 前后端镜像，OCI revision 标签均为该合并 SHA；经完整 Git bundle、镜像归档传输到 staging，双方 SHA-256 一致。在 staging Rootless Docker 发布至现有 GHCR 仓库并按不可变摘要引用，不重建检索镜像。

手动门禁先核对原三摘要、当前单店人工发送/Webhook/翻译开关，随后完成六角色预取、`ValidateOnly`、私有 PostgreSQL 备份及 `pg_restore -l`、Deploy 和运行摘要复核。候选前后端摘要、回滚三摘要、私有门禁文件的 SHA-256 与低敏运行结果见 [部署证据](../../../release/evidence/staging/crm-staging-workspace-native-card-20261022.json)。未修改生产环境、店铺数据或外部消息；真实发送权限范围沿用部署前配置。

# 恢复与限制

门禁保留上一版三镜像摘要及仅 staging 私有的备份、模式快照，失败时按现有 staging 回滚门禁恢复并复核健康。GitHub Actions 两作业在零步骤失败，本次以 R04 本地完整验证和 staging 手动门禁为依据，不记作 CI 通过。实际 TikTok 买家原生卡片投递没有测试；production G8 仍为 No-Go。
