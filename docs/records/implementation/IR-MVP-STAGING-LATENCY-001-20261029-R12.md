---
record_id: IR-MVP-STAGING-LATENCY-001-20261029-R12
record_type: implementation
revision: R12
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 14528b7b1f80c56194af4c137a767a5288d77d07
final_sha: 40f39665b03a67712384dec13fec06c0c25ba2bf
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-03, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R14.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261029-R12.md
created_at: 2026-10-29T05:20:00+08:00
updated_at: 2026-10-29T05:20:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R11.md
---

# 目标与实际变更

订单卡片原有详情重试，完整详情视图却在只读详情查询失败或 429 后只显示错误。源码提交 `56c8c86d` 为详情视图加入手动“重试详情”：重试时清除旧错误并显示加载状态，保留已同步的订单摘要，仍使用当前会话和订单的原只读接口；物流原有重试行为由新合成浏览器测试覆盖。产品文档随后补齐这一行为，PR #612 最终 head `40f39665`、合并提交 `7c61f78b`。无后端、接口、迁移、授权、退款或发送边界变化。

按用户“仅部署当前修复”的约束，从原性能 release `4edddffb` 摘取源码形成干净 release `eb0eedc7`。测试夹具与隔离 release 的旧入口发生一处 cherry-pick 冲突，保留旧夹具并加入对象参数适配；前端组件 Git blob 与合并主线完全一致。release 对原运行版本只改组件与对应浏览器测试，不含主线动态 Agent 改写。镜像 linux/amd64 的本机、GHCR 与业务机 RepoDigest 一致，OCI revision 为 `eb0eedc7`。

# 部署与安全边界

业务机从原干净持久源码和校验通过的 Git bundle 建立新干净部署目录；私有环境、PostgreSQL 自定义 dump 和 MinIO tar 已按 `0700/0600` 备份，并核对目录可读。相同摘要与原运行模式的 `ValidateOnly`、`Deploy` 通过，迁移头已应用，12 个容器运行，前端切换为精确摘要 `sha256:73304958…fdff9`。后端、检索、解析、原单店人工发送范围、Webhook、翻译、现有 Agent 调试与文档导入保持；动态 Agent v2 未启用，自动回复和通用 LLM 关闭。未使用 Actions 部署，未发送真实消息、退款或操作 production。

# 限制与回滚

四个公网只读入口返回 200；已登录工作台 UI 自动化 `getTab` 超时，现场订单画面记 `UI_UNAVAILABLE`。真实 TikTok 429、用户可见冷热回显及 WAN 性能仍未验收；整体任务保持 `VERIFYING`。回滚仅切回发布前前端摘要 `sha256:f2294806…5a83d`，保留部署后的业务增量，不用旧数据库/MinIO 备份覆盖。精确哈希与结果见 [TR R14](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R14.md) 和 [低敏发布证据](../../../release/evidence/staging/crm-staging-order-detail-retry-20261029.json)。
