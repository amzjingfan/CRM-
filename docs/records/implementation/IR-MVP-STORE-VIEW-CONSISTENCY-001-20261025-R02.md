---
record_id: IR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-STORE-VIEW-CONSISTENCY-001
base_sha: 5b619a754c3c7cdecb652b6872aeb3e3691d5a9c
final_sha: aadf5087969ceb8ccb2b533ce8a42c191c3f96d9
requirement_ids: [MVP-STORE-VIEW-CONSISTENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R02.md
review_record: docs/reports/reviews/RR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R02.md
created_at: 2026-10-25T03:49:00Z
updated_at: 2026-10-25T03:49:00Z
supersedes: docs/records/implementation/IR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R01.md
---

# 实施目标与范围

[源码 PR #553](https://github.com/CP11-gh/CRM/pull/553) 已 squash 合入 `main=aadf5087969ceb8ccb2b533ce8a42c191c3f96d9`。本修订仅记录合并主线与 staging 部署；功能实现、模型、权限及版本语义见 R01，未增加产品源码修改。

# 实际变更及原因

从干净、已合并主线构建并发布 linux/amd64 前后端不可变 OCI 镜像，revision 均为合并 SHA；候选源码与合并主线的后端、前端及对应 Dockerfile 构建输入相同。旧检索模型和 MinerU 解析镜像保持。私有 PostgreSQL、MinIO、运行模式及环境快照完成后，手动 `ValidateOnly` 和 `Deploy` 通过，迁移升级到 `032_knowledge_file_archive`，12 个 CRM 容器运行。精确摘要和哈希见[低敏现场证据](../../../release/evidence/staging/crm-staging-store-view-consistency-20261025.json)。

# 关键决定与偏差

PR 的 GitHub Actions 前后端作业均零步骤失败，不能计为 CI 通过。用户明确要求直接部署；本次仅对 PR #553 合并及 staging 使用 R01 的完整本地门禁和审查作为替代。production G8 仍未放行。现有 Webhook 读取、单店人工发送、工作台翻译和文档解析模式在部署中保持。

# 数据、配置、接口、迁移或 Prompt 影响

staging 新增可空 `knowledge_files.archived_at`，当前 11 个文件仍在且归档数为 0。接口和模型影响见 R01；本修订未修改 Prompt、检索服务或网关配置。

# 验证交接

合并源码与运行摘要、私有备份、门禁、迁移、健康、公网页面缓存及风险见 [TR R02](../../reports/tests/TR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R02.md) 与 [RR R02](../../reports/reviews/RR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R02.md)。

# 限制、风险与回滚

已登录 UI 工具超时，现场交互未直接复核；本地合成生产浏览器 108/108 不冒充真实店铺验收。网关 SSH 私钥临时受限副本操作被自动审批拒绝，未从网关主机复核 Nginx；本次未更改网关配置，公网路径另行通过。公司系统 Docker 中另一个 Redis 容器有持续自动重启，CRM 部署只使用 Rootless daemon，未操作该容器，不声称系统 Docker 状态完全不变。回滚先保护新业务增量，按私有快照切回原前后端摘要；已有归档后不得盲目降级 032 或覆盖数据库备份。