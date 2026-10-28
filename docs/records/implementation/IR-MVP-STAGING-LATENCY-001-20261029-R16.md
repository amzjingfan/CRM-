---
record_id: IR-MVP-STAGING-LATENCY-001-20261029-R16
record_type: implementation
revision: R16
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 010fa4c3ceb70655602b220e42942e263c7a4350
final_sha: 053ebc9f625042e6c38c3c3c10df6e4c9e0284ba
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R20.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261029-R16.md
created_at: 2026-10-29T07:30:00+08:00
updated_at: 2026-10-29T07:30:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R15.md
---

# 看板局部修复发布

主线 [PR #623](https://github.com/CP11-gh/CRM/pull/623) 已合入授权店铺先触发指标读取、店铺名称后补齐的修复，索引经 PR #624 对齐。以 staging 实际运行的 `82e9fd83` 为基线，单独摘取 `src/frontend/app/dashboard/page.tsx` 和合成浏览器用例到干净 release `3efa1f2e`；两个 blob 与合并主线一致。未部署最新 main 的动态 Agent v2。

按 `3efa1f2e` 构建的 linux/amd64 前端镜像通过 OCI revision 与不可变摘要核验。业务机 GHCR 直拉停滞时，以 SHA-256 校验的现有 SSH 通道传送同一镜像，远端加载后按精确摘要拉取成功。源码 Git bundle、私有环境/PostgreSQL/MinIO 备份和可读性已核对；相同配置先 `ValidateOnly`，再直接 `Deploy`，运行容器前端摘要一致，后端、检索及解析镜像不变。没有通过 GitHub Actions 部署。

原单店人工发送、Webhook 读取、翻译、现有 Agent 调试、文档导入及固定出口保持；自动回复、通用 LLM 与高风险写入关闭。没有真实买家外发、退款或 production 操作。回滚只恢复旧前端精确摘要 `sha256:7ff0098991f96845df0099ebaea931bebbe4edf658eaeb7a3a56626c4dc01a30`，保留业务数据增量。完整哈希与门禁见 [TR R20](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R20.md) 和[低敏证据](../../../release/evidence/staging/crm-staging-dashboard-authorized-20261029.json)。整体任务仍为 `VERIFYING`。
