---
record_id: TR-MVP-STAGING-LATENCY-001-20261029-R10
record_type: test
revision: R10
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: c1fcc1c74dbb073b2d560c178499b2ac5ec99f2e
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R09.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
environment: staging authenticated in-app browser and business proxy safe access log
created_at: 2026-10-29T01:42:00+08:00
updated_at: 2026-10-29T01:42:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R09.md
---

# 已登录门店刷新补测

R09 记录的首次浏览器刷新读取超时保持原始事实。部署后再次使用已登录的 staging 门店列表，初始界面显示一条授权店铺。点击“刷新店铺”后，可访问性树无内容变化；随后只读检查确认表格仍有一行、刷新按钮可用。未改动店铺数据或触发任何外发。

同一时间窗口，业务机内层 Nginx 的低敏规范化路径日志里，`GET /v1/settings/store-authorizations` 最近三条成功请求的 `request_time` 分别为 22、18、16 毫秒，状态均为 200。最后一条与本次点击时间相近，但未取得端到端 Trace ID，不将其作为精确配对的用户可见耗时。浏览器控制工具绑定、页面状态读取各自花费数十秒，无法从这些工具壁钟时间分离页面网络与渲染耗时。

本次只确认已登录刷新后已有授权行未消失且按钮恢复。前端冷/热回显的精确时间、跨店、故障与限流现场验收仍未完成；公网绝对 p50/p95 在已证实入口/隧道网络波动期间仅作诊断。整体任务维持 `VERIFYING / PARTIAL`。低敏观测值见 [补测证据](../../../release/evidence/staging/crm-staging-store-refresh-readonly-20261029.json)，发布及本地回归依据 [TR R09](TR-MVP-STAGING-LATENCY-001-20261029-R09.md)。
