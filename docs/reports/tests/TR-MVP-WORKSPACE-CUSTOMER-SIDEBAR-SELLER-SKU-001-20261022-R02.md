---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001-20261022-R02
record_type: test
revision: R02
status: PARTIAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001
tested_sha: f512fb8a8a52ed4139a5f94a431752b5f65715d0
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001-20261022-R02.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: merged-main Linux amd64 staging Rootless Docker; synthetic Chrome intercepts all workspace API calls
created_at: 2026-10-22T05:00:56Z
updated_at: 2026-10-22T05:00:56Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001-20261022-R01.md
---

# 验证结果

R01 在 subject `f512fb8a` 的定向先红后绿、本地前端 typecheck/build、契约 47/47 和生产浏览器 59/59 保留；本次没有重跑全套本地检查。PR #512 的两个 GitHub Actions 作业均在第零步骤失败，不计为 CI 通过。

从 `main=ce70bbba` 的干净源码构建前端，源码 bundle 和镜像归档传输 SHA-256 一致，镜像 ID 与 OCI revision 匹配。发布前读出原三摘要和单店人工发送范围；六角色预取 `passed`、配置验证 `validated`、私有 PostgreSQL 备份 `0600` 且 `pg_restore -l` 可读、部署 `passed`。运行前端摘要匹配候选，后端和检索摘要未变；迁移头、固定出口、11 个容器和 `/healthz`、`/v1/health`、`/v1/health/ready`、`/workspace` 公网 HTTP 200 均通过。一次 `/v1/health` 客户端请求出现短暂 EOF，独立重试为 HTTP 200；其他检查和门禁结果未受影响。摘要及私有门禁哈希见[部署证据](../../../release/evidence/staging/crm-staging-customer-sidebar-seller-sku-20261022.json)。

已部署页面运行长 SKU 货号、长商品规格和缺失规格三项合成浏览器回归：3/3。请求全部拦截 `/v1/` 并使用合成会话；长货号完整换行，复制回读完整值，未触及真实买家数据或发送。

# 待验收与范围

用户已被请求刷新原真实订单卡确认货号显示及复制，结果尚待返回，故本报告暂记 `PARTIAL`。Codex 未直接读取该登录态页面；无买家外发、退款、发券或 production 发布。
