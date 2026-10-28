---
record_id: IR-MVP-STAGING-LATENCY-001-20261029-R09
record_type: implementation
revision: R09
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 7b83dfcaf83df82b6b2a708666b8c86ac7fc32f4
final_sha: c1fcc1c74dbb073b2d560c178499b2ac5ec99f2e
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R09.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261029-R09.md
created_at: 2026-10-29T01:25:00+08:00
updated_at: 2026-10-29T01:25:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R08.md
---

# 目标与实际发布

R08 的门店授权聚合和刷新回显代码已由 [PR #599](https://github.com/CP11-gh/CRM/pull/599) 合入主线 `0eda0319`，文档索引由 [PR #600](https://github.com/CP11-gh/CRM/pull/600) 对账。用户要求只部署性能修复，因此从运行中的性能专用 release `f9bfc109` 摘取同一变更形成干净源码 `18cea7f2`；后端相对当前运行的 `e64ef52c` 仅多本次 stores 三文件，未纳入主线动态 Agent 新代码。首次将临时登录与清理写在同一命令被自动策略拒绝；拆成受限目录中的登录、发布和独立注销后，GHCR 发布成功。

从该源码本机构建并发布 linux/amd64 前后端镜像，业务机按不可变摘要拉取并核对 OCI revision、RepoDigest。使用已存在的干净 `f9bfc109` 远端 clone 加精确 Git bundle，生成独立干净 `18cea7f2` checkout。备份环境、PostgreSQL 自定义 dump 与 MinIO tar 到仓库外私有目录，校验目录/文件权限、目录可读性与 SHA。原单店人工发送、Webhook 读取、工作台翻译、Agent 调试、文档解析范围在切换前核对；`ValidateOnly` 和 `Deploy` 通过，数据库仍为 `034_agent_debug_runs`，12 容器健康。新后端与前端摘要及三个公网健康 200 已复核，临时远端和本地 GHCR 登录均注销。

# 限制与恢复

已登录门店页显示一条授权行；刷新后的浏览器读取在 60 秒内未返回，故不把现场刷新时延算通过。公网 HTML 五条样本 1.212–1.927 秒，与部署前样本不构成同条件加速证明。无消息外发、退款或 production 操作。回滚时仅使用本次证据中的旧前后端摘要，并保留现有数据库/MinIO 增量和全部安全开关；不得恢复备份覆盖业务增量。精确摘要、备份、门禁及局限见 [TR R09](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R09.md) 与 [低敏发布证据](../../../release/evidence/staging/crm-staging-stores-progressive-20261029.json)。
