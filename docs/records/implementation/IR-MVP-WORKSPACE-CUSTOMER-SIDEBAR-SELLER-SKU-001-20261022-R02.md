---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001-20261022-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001
base_sha: ce70bbbaa735157c8cfa1417f3e21bc27f67c52e
final_sha: f512fb8a8a52ed4139a5f94a431752b5f65715d0
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001-20261022-R02.md
review_record: N/A
created_at: 2026-10-22T05:00:56Z
updated_at: 2026-10-22T05:00:56Z
supersedes: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001-20261022-R01.md
---

# 合并与 staging 发布

R01 的前端修复与测试通过 [PR #512](https://github.com/CP11-gh/CRM/pull/512) squash 合入 `main=ce70bbba`；干净构建目录的前端和 Dockerfile Git 树与 subject `f512fb8a` 一致。由该精确主线构建 `linux/amd64` 前端镜像，OCI revision 为合并 SHA。源码 bundle 和镜像归档传至 staging 并核对双端 SHA-256，Rootless Docker 导入镜像后 ID 与 revision 匹配，再发布到现有 GHCR 仓库并以不可变摘要部署。后端与检索仍引用部署前摘要。

手动门禁先只读核对旧三摘要与单店人工发送范围，再完成六角色预取、`ValidateOnly`、私有 PostgreSQL 备份及 `pg_restore -l`、`Deploy`、运行摘要、11 个容器与四公网健康入口复核。完整摘要和低敏状态见[部署证据](../../../release/evidence/staging/crm-staging-customer-sidebar-seller-sku-20261022.json)；门禁原件及备份仅留在 staging 私有目录。

# 边界与恢复

仅更新 staging 前端；不改数据库、权限或外部发送行为，未向买家发送消息。原前端摘要、后端/检索摘要和私有备份保留供现有回滚门禁使用。GitHub Actions 两作业在执行步骤前失败，没有 CI 测试日志，本次以 R01 本地验证与 staging 手动门禁为依据；production G8 仍未放行。
