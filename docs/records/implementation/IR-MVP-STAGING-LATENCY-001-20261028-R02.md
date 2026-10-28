---
record_id: IR-MVP-STAGING-LATENCY-001-20261028-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 0b14b1d1be1a68e607d0665807048c81ca7fb01c
final_sha: e64ef52c9702540a5c5eb3a151cd19afce97b0e0
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R02.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261028-R02.md
created_at: 2026-10-28T18:07:00+08:00
updated_at: 2026-10-28T18:07:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R01.md
---

# 实施目标与范围

按用户最终指令，仅把性能修复直接部署 staging，不附带主线动态 Agent 重写。性能源码已通过 PR #584 合入 `main`；现场使用独立、已推送且干净的 `hotfix/staging-performance-only-20261028` 源码提交 `e64ef52c9702540a5c5eb3a151cd19afce97b0e0`，其中 Agent 八个文件恢复到现场既有版本。未部署 production。

# 实际变更及原因

性能功能仍为 R01 描述的 TikTok 只读连接复用、订单摘要渐进回显及详情/物流分离、店铺隔离 20 秒私有摘要缓存、浏览器与应用分段耗时。后端和前端从同一 release SHA 构建为不可变 linux/amd64 摘要。公网 Nginx 仅对 `/_next/static/` 使用既有 `cache_one`，新增上游耗时记录，保留原 `/activate/` 禁用规则。

# 关键决定与偏差

用户撤回“部署最新 main”的早先选择，因此未使用含动态 Agent 的最新主线作为 staging 构建输入。业务机直接 GHCR 拉取遇 TLS 超时，改用已逐层校验的 OCI 包经内网导入，六角色精确摘要复核后才切换服务。未使用 GitHub Actions 部署。

# 数据、配置、接口、迁移或 Prompt 影响

新增只读订单详情参数、独立标准物流请求及 `Server-Timing`；无新增迁移，现有迁移头保持。无新 Prompt。保持单店人工发送、固定出口、调试、翻译和全部安全开关；新 Agent v2 开关未设置。

# 验证交接

[TR R02](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R02.md)和[低敏部署证据](../../../release/evidence/staging/crm-staging-latency-performance-only-20261028.json)记录本次备份、预检、部署和现场测量。原始门禁报告、备份与 OCI 恢复包留在受限服务器，不含于仓库。

# 限制、风险与回滚

公网及反向隧道仍有秒级高抖动，整体任务保持 `VERIFYING`。若应用回归，使用部署前受审前后端摘要与 Nginx 私有备份恢复，保留部署后业务增量，不以旧 PostgreSQL/MinIO 快照直接覆盖实时数据。
