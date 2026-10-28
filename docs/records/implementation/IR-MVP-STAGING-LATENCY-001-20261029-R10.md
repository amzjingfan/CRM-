---
record_id: IR-MVP-STAGING-LATENCY-001-20261029-R10
record_type: implementation
revision: R10
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: ad3add077999eb2f883e35fa338409d788fb6fe9
final_sha: eab7e2c207308fde34be1ca50f25d32be1670cfa
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R11.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261029-R10.md
created_at: 2026-10-29T02:18:00+08:00
updated_at: 2026-10-29T02:18:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R09.md
---

# 目标与变更

全站并发请求的过期浏览器会话曾各自刷新 Cookie，在抖动公网链路上增加往返。前端认证客户端现在对同页并发 401 共用一次刷新；较晚返回的只读请求复用已刷新的会话并最多重试一次。只读范围为 GET/HEAD，以及确认无写入的会话搜索、侧栏搜索、订单详情、通用和增强物流 POST。其他写请求维持原刷新路径，同一次请求的幂等键在重试中不变。失败刷新保持未认证结果；CSRF Cookie、店铺权限和服务端授权逻辑均未改变。

# 范围与限制

本次仅改变浏览器认证客户端、前端回归测试和 API 契约说明；无迁移、新配置、后端、Agent、平台 API 或外部消息发送。此修复消除已定位的重复认证往返，不构成全站冷/热回显改善证明。staging 仍须从当前运行的专用性能 release 精确摘取该前端改动，不能直接部署含动态 Agent 改写的最新 main。回滚只需切回前端旧镜像摘要，保留数据库和业务增量。

# 验证交接

本地契约与生产浏览器回归见 [TR R11](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R11.md)；认证、安全、规格审查见 [RR R10](../../reports/reviews/RR-MVP-STAGING-LATENCY-001-20261029-R10.md)。整体任务继续 VERIFYING。
