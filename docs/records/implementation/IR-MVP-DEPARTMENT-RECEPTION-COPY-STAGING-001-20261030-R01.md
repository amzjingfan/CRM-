---
record_id: IR-MVP-DEPARTMENT-RECEPTION-COPY-STAGING-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-DEPARTMENT-RECEPTION-COPY-STAGING-001
base_sha: b5d4985b42fc2daac677a16805bfa18126b6439e
final_sha: b5d4985b42fc2daac677a16805bfa18126b6439e
requirement_ids: [MVP-DEPARTMENT-RECEPTION-COPY-STAGING-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-DEPARTMENT-RECEPTION-COPY-STAGING-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-DEPARTMENT-RECEPTION-COPY-STAGING-001-20261030-R01.md
created_at: 2026-10-30T12:34:25Z
updated_at: 2026-10-30T12:34:25Z
supersedes: null
---

# 目标与实施

从 PR #670 已合并主线 `b5d4985b` 直接构建并部署 staging 前端，移除部门派单页的冗余说明段落。后端和其他服务镜像保持当前摘要，运行配置不变。干净主线 Git bundle 经 SHA-256 核对传至业务机，远端干净 checkout 的 HEAD 与合并提交相同；前端 linux/amd64 OCI revision、RepoDigest 和传输哈希一致。

部署前在 crmdeploy 私有目录备份环境、PostgreSQL 和 MinIO，并检查可读性和权限。当前/候选 ValidateOnly、Deploy、045、12 服务与健康验证通过。精确证据见[低敏 JSON](../../../release/evidence/staging/crm-staging-department-reception-copy-20261030.json)。

# 边界与恢复

人工发送只保留既有两家授权店铺，Agent 调试/建议保持，自动回复、营销、高风险写入关闭；未向真实买家测试外发，未操作退款或 production。恢复可切回上一前端镜像，保留数据库 045 和发布后业务增量，不直接覆盖整库。
