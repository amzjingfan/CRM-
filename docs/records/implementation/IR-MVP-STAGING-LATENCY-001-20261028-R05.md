---
record_id: IR-MVP-STAGING-LATENCY-001-20261028-R05
record_type: implementation
revision: R05
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 971959b969900151b8d530b6c42bb115c4b2bcfe
final_sha: 921e3c051a0bf54d942531947faff9f98c04009c
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R05.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261028-R05.md
created_at: 2026-10-28T21:15:00+08:00
updated_at: 2026-10-28T21:15:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R04.md
---

# 实施目标与范围

工作台每 5 秒的后台刷新原先串行等待会话列表后才读取当前消息。入口日志表明列表与消息各自会经历显著网络等待，串行导致消息回显受慢列表阻塞。本轮仅让这两个只读请求同时开始，并各自独立更新界面。

# 实际变更及原因

同一轮刷新启动列表与已选会话消息请求，用 `Promise.allSettled` 等待两者结束后释放刷新锁；保留原有请求序号、激活状态、所选会话、已读和滚动位置防护。增加行为回归：阻塞列表响应时，消息请求仍发起并显示新消息。该回归在旧串行实现先失败，在修复后通过。

# 源码与部署边界

主线候选 `921e3c05` 从 `origin/main=971959b9` 仅新增上述前端实现与测试。用户要求只部署当前性能修复，因此 staging 从既有性能发布 `e64ef52c` 单独摘取同一实现形成 release `9d6ccc20`，与主线候选的前端实现 blob 完全相同。发布差异仅这两个文件；后端、部署配置、Agent 工具/动态重写与安全开关保持现状。staging 前端 OCI 单一摘要为 `sha256:ba138da355d1e51b33e15c389004f16c238ca55787201466778c70b7c472f98c`。

# 验证交接

[TR R05](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R05.md)和[低敏发布证据](../../../release/evidence/staging/crm-staging-workspace-refresh-20261028.json)记录本地生产构建、浏览器回归、私有备份、ValidateOnly/Deploy、容器与公网健康。发布不使用 GitHub Actions。

# 限制、风险与恢复

并行刷新消除一个人为串行等待，不保证公网整体速度。公网 p50/p95 与入口 p50/p95 仍相差显著，且入口出现 504；TikTok 详情、全部页面、跨店及故障/限流的足量验收尚未完成。回滚仅切回上一个已核验前端镜像摘要，保留部署后业务数据、现有后端与安全开关；私有备份仅用于确证恢复条件，不直接覆盖新增数据。
