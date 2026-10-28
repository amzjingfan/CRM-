---
record_id: IR-MVP-STAGING-LATENCY-001-20261028-R03
record_type: implementation
revision: R03
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 5a4143062d37cdb811f33f9e2959d04df79f1415
final_sha: 81c851bf53b7216ef6f5bf4ee8d125aefacb0eaa
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R03.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261028-R03.md
created_at: 2026-10-28T18:52:00+08:00
updated_at: 2026-10-28T18:52:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R02.md
---

# 实施目标与范围

降低 staging 公网入口通过反向 SSH 隧道访问业务机时，每次重建上游连接造成的等待。只改公网 Nginx vhost，不切换前后端镜像、SSH 隧道服务、固定出口或应用安全开关。

# 实际变更及原因

`upstream crm_staging_tunnel` 继续指向 `127.0.0.1:18080`，每 worker 最多保留 8 条 HTTP/1.1 空闲连接，10 秒超时；8 个代理位置设置 `Connection ""` 允许复用。原有 `/activate/` 拒绝规则同步回仓库源配置，SSE 不缓冲、媒体上传限额、静态资源缓存与 HTML/API 不缓存边界保留。隔离回环测试支持连接复用降低入口等待。

# 关键决定与偏差

用户只允许部署当前性能修复，因此这次仅安装 Nginx 配置，不使用最新主线重建应用，也不启用动态 Agent。公网两机之间仍有重传和抖动；连接复用只是减少每次新增 SSH 转发通道的成本，不替代线路修复。

# 数据、配置、接口、迁移或 Prompt 影响

Nginx 配置变化如上；无数据、API、迁移或 Prompt 变化。没有扩大共享缓存范围或平台写入权限。

# 验证交接

[TR R03](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R03.md)与[低敏现场证据](../../../release/evidence/staging/crm-staging-nginx-keepalive-20261028.json)记录配置哈希、私有备份、语法检查、重载、功能回归和前后耗时。

# 限制、风险与回滚

公网 p50/p95 在此次 30 样本中没有改善，任务保持 `VERIFYING`。若出现 SSE、Webhook、媒体或 HTTP 异常，按私有 `before.conf` 恢复原 vhost，`nginx -t` 后重载；不改数据库或容器。
