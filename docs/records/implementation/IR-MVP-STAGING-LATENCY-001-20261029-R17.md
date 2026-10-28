---
record_id: IR-MVP-STAGING-LATENCY-001-20261029-R17
record_type: implementation
revision: R17
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: e5186e9b675c2d863f0bc1051e252f06306d45ea
final_sha: 053ebc9f625042e6c38c3c3c10df6e4c9e0284ba
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R21.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261029-R17.md
created_at: 2026-10-29T07:52:00+08:00
updated_at: 2026-10-29T07:52:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R16.md
---

# 性能任务应用侧收口

本记录汇总已合入并从性能专用 release 分批直部署 staging 的修复，不产生新的产品代码或部署：TikTok 只读 HTTP 连接安全复用；订单摘要先回显、详情和物流独立读取且自动详情最多并发两项；20 秒按店铺、买家、授权凭证隔离的订单私有缓存和手动刷新；工作台、门店、基础接待、看板及认证请求的并行、渐进回显；入口上游连接复用与仅指纹静态资源共享缓存；入口、后端和前端 API 的低敏分段耗时。每个源码和发布步骤仍以先前 IR/TR/RR、主线 PR 与低敏 release 证据为准，最终运行前端为 `3efa1f2e` 的精确摘要，后端保持原摘要。

用户明确放宽网络异常时的公网绝对耗时门槛。业务机处理与入口/隧道及公网的差距、重传和偶发 504 已定位并有前后样本；无备用线路，WAN 故障仍是外部依赖。本任务按已修订的 AC-06 验收应用侧行为、隔离与失败恢复，公网 p50/p95 仅保留诊断记录，不宣称全站用户可见耗时已稳定达到某个阈值。没有扩大发送范围、开启自动回复、部署动态 Agent v2、触发真实买家消息或退款，也没有操作 production。完整映射见 [TR R21](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R21.md) 与 [RR R17](../../reports/reviews/RR-MVP-STAGING-LATENCY-001-20261029-R17.md)。
