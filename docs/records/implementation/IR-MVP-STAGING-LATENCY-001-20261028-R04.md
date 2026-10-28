---
record_id: IR-MVP-STAGING-LATENCY-001-20261028-R04
record_type: implementation
revision: R04
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 23eb8f961c663a2067e22b40e450243066d36e5c
final_sha: 9415044da2848877a722a4b790c2e6734a0ecec4
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R04.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261028-R04.md
created_at: 2026-10-28T19:38:00+08:00
updated_at: 2026-10-28T19:38:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R03.md
---

# 实施目标与范围

为 staging 全站慢请求提供入口、应用及 TikTok 调用分段证据。只在公网 Nginx 的安全 JSON 访问日志中增加应用已有的 `Server-Timing` 响应头；不切换应用镜像或扩大日志中的请求内容。

# 实际变更及原因

源配置只增加 `server_timing` 字段，入口继续只记录 `$uri`，不记录查询参数、请求体、买家内容或凭证。后端已有 `app;dur=<整数>, tiktok;dur=<整数>`，公网 `/v1/health` 已验证该头存在。此前容器结构化日志只保留事件名，无法从日志汇总耗时；入口新增字段支持按固定路由类别聚合。

# 关键决定与偏差

首次重载后即时检查读到旧 worker 格式，自动恢复了原配置；再次重载后第 2 次探测记录到数值字段。两个过程均保留私有原配置并复核 `nginx -t`。无新服务、共享缓存或生产变更。

# 数据、配置、接口、迁移或 Prompt 影响

仅 staging Nginx 访问日志格式变更；现有 API 响应头不变。无迁移、数据库写入或 TikTok 平台调用新增。

# 验证交接

[TR R04](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R04.md)与[低敏现场证据](../../../release/evidence/staging/crm-staging-server-timing-20261028.json)记录源码与活动配置哈希、私有备份、恢复、样本及范围限制。

# 限制、风险与回滚

工作台和设置页已能区分后端耗时与入口总耗时，但设置页样本少，未覆盖冷热、跨店和故障场景。出现日志异常或入口回归时，用私有 `before.conf` 恢复原 vhost，`nginx -t` 后重载；不触碰容器和业务数据。
