---
record_id: IR-MVP-STAGING-LATENCY-001-20261028-R07
record_type: implementation
revision: R07
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 3a3aafd00badd7e79eb4b3e1e1965b025cf524c0
final_sha: fe627e4f3d7246e57cc4e7e0dd9c766c8e47d862
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R07.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261028-R07.md
created_at: 2026-10-28T23:35:00+08:00
updated_at: 2026-10-28T23:35:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R06.md
---

# 目标和变更

数据看板原先等待指标、趋势、渠道、预警与热门咨询五个接口全部完成后才回显；一个慢接口或失败会阻塞整页。`fe627e4f` 将核心指标独立加载，四个次要组件各自呈现加载、错误或数据状态。店铺与周期切换继续使用请求代号丢弃旧响应；组件失败不把预警伪装为零。原本显示“最近 0 个自然日”的加载期副标题改为加载提示。新增慢组件和次要组件失败的生产浏览器行为回归，旧代码在慢组件用例中先失败，修复后通过。

# 范围和发布

主线候选只改变看板页面与集中式浏览器测试，无 API、缓存、迁移、凭证或发送行为变化。用户要求只部署性能修复，因此从已运行的性能专用 release `97ac71ef` 摘取两文件相同 blob，形成独立 release `f9bfc109`；相对该基线只改变这两文件。后端、动态 Agent 和人工发送范围未随当前主线更新。

发布前从干净源码构建 linux/amd64 单清单前端镜像 `sha256:ea586aa4f2531c489a32077951eb750a00951715b8db9b3d68b76fd8cd9ac292`。源码 bundle 与 OCI 归档两端哈希核对，远端 Rootless Docker 保留精确 RepoDigest。独立私有环境、PostgreSQL、MinIO 备份及可读性、`ValidateOnly`、`Deploy` 通过，12 个 CRM 容器运行，后端摘要不变，一次性 GHCR 凭据已注销。公网健康和 `/dashboard` 为 200；已登录默认授权店铺的看板显示五块数据。见 [TR R07](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R07.md) 和 [低敏发布证据](../../../release/evidence/staging/crm-staging-dashboard-progressive-20261028.json)。

# 限制与恢复

本次证明次要组件的慢请求或失败不阻塞核心指标；公网 `/dashboard` 单次 TTFB 仍为 6.48 秒，WAN/隧道抖动未解决。已登录跨店切换因浏览器工具超时未获得现场回显证据，全站冷/热及失败限流实测继续待办，任务保持 `VERIFYING`。如需恢复，仅将前端切回已记录的 `sha256:7bfce9ae5bd2ccc9b83b4c43beccad76bbf39b3fd3b16bf2b527c35ce22ba74c`，保护业务数据和安全开关。
