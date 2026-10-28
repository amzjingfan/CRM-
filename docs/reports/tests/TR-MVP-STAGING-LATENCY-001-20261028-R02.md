---
record_id: TR-MVP-STAGING-LATENCY-001-20261028-R02
record_type: test
revision: R02
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: e64ef52c9702540a5c5eb3a151cd19afce97b0e0
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R02.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
environment: Windows local Python 3.11 and Node 20; staging rootless Docker, Nginx gateway, authenticated read-only browser
created_at: 2026-10-28T18:07:00+08:00
updated_at: 2026-10-28T18:07:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R01.md
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT=centralized`，测试源码位于 `src/tests/`。R01 覆盖已合入性能功能；本次针对无动态 Agent 的精确发布源码 `e64ef52` 本地复测并在 staging 实际部署、只读验收。

# 命令和逐项结果

- release checkout `uv run pytest -q`：2407 passed、43 skipped；Ruff check、format（386 文件）与 mypy（179 源文件）通过。
- 前端合同 `npm run test`：48/48；`npm run typecheck` 通过；`npm run lint`：0 错误、8 项既有警告；release Docker 构建通过。生产合成浏览器 117/117 在恢复 Agent 文件前的相同前端树上通过，故不冒充 release SHA 全树浏览器复测。
- 源码 bundle 8,013,164 字节，SHA-256 `6af70ad175150797a4b003d52810cba6efe47e57a4c08a6d89b609fbfab5de0e`；staging 干净 checkout HEAD 与 OCI revision 均为 release SHA。27 个 OCI blob 校验、六角色摘要导入复核通过。
- 私有环境、PostgreSQL、MinIO 与公网 vhost 备份及可读性通过；`Test-StagingProductionGates.ps1` 的 `ValidateOnly=validated`、`Deploy=passed`；数据库迁移为 `heads_applied`、固定出口与 12 容器、三个健康 HTTP 200 通过。`nginx -t` 与 reload 通过。
- 公网 `/settings/stores` HTTP 200 且 HTML `no-store`；指纹 JS 首次 `MISS` 耗时 1.728 秒、第二次 `HIT` 耗时 0.000 秒；API 不进入共享缓存。已登录工作台只读订单摘要先出现，详情、默认两条物流/展开入口、规格和已送达买家售后状态可见；未保存买家或订单字段。

# REQ/AC 或门禁与证据映射

精确摘要、备份哈希、门禁结果和测量见[低敏证据](../../../release/evidence/staging/crm-staging-latency-performance-only-20261028.json)。`/healthz` 部署前后每段各 20 次且均为 200：业务机 TTFB p50/p95 `0.000833/0.004535` → `0.0006585/0.001604` 秒；网关回环隧道 `0.905597/3.727746` → `1.241103/2.128384` 秒；公网 `1.782162/9.107670` → `2.471737/4.818602` 秒。公网连接建立后测 p50/p95 `0.1872205/1.200529` 秒。不同时间段的小样本不构成受控对照，不据此宣称公网延迟因本次发布而下降。

# 缺陷、未执行项与残余风险

部署后网关日志的小样本订单搜索 2 次 p50/p95 `4.174/4.749` 秒、详情 1 次 `4.269` 秒、物流 1 次 `2.130` 秒；隧道和公网仍是主要等待。未进行真实买家外发、退款、跨店真实订单访问或 production 部署；真实受限范围以原有安全开关为准。`Server-Timing` 应用字段已部署，尚需用网关日志与浏览器 Network 时间线进行更大样本同请求关联。未运行 GitHub Actions 作为部署方式。

# 结论和复测条件

部署与现场只读功能验收通过，性能任务整体 **PARTIAL**：AC-01 的线路修复和 AC-06 的受控冷/热、公网 p50/p95 验收仍未完成。下一步针对反向隧道重启/超时与公网 TCP 抖动定位并修复，按同一时段、同一请求分类、足量样本复测，再决定任务完成。
