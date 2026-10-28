---
record_id: TR-MVP-STAGING-LATENCY-001-20261028-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: 2c77b8d9a729e467d702c116ad7403e94660f979
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R01.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
environment: Windows local Python 3.11, Node 20, Chrome synthetic browser; staging split ingress read-only
created_at: 2026-10-28T16:35:00+08:00
updated_at: 2026-10-28T16:35:00+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT=centralized`，测试源码在 `src/tests/`。基于 `origin/main=ac7216d4` 的重放提交 `c31b23f1`；不接触真实买家发送、退款或 production。

# 命令和逐项结果

- `uv run pytest -q`（`src/backend`，`PYTHONPATH=.;../tests;../tests/backend`）：2289 passed、54 skipped、2 warnings，286.85 秒。数据库隔离集成项因本机无 PostgreSQL 跳过，不能代替 staging 验收。
- 定向 TikTok 只读、侧栏、健康和 Nginx 资产测试：116 passed、3 skipped。
- `uv run ruff check . ../tests/backend ../tests/integration/postgres`、`uv run ruff format --check . ../tests/backend ../tests/integration/postgres`：通过，453 文件格式通过。`uv run mypy app`：211 源文件通过。
- `npm run test`：48/48 通过；`npm run typecheck` 通过；`npm run lint`：0 错误、8 项既有警告。
- 与源码相同的隔离目录（相同 `package-lock.json` SHA-256）执行 `npm run build`：生产构建通过，17 个动态页面路由生成；`UI_BASE_URL=http://127.0.0.1:3103`、`UI_CACHE_EXPECT_PRODUCTION=1` 执行 `npm run test:ui`：118/118 通过，含订单渐进加载、并发上限、详情/物流分离、缓存刷新和生产静态缓存契约。所有浏览器接口均为合成拦截，无真实平台请求。

# REQ/AC 或门禁与证据映射

只读 `/healthz` 每段 20 次，全部 HTTP 200：业务机回环 TTFB p50/p95 `0.000833/0.004535` 秒；入口机回环隧道 `0.905597/3.727746` 秒；公网 `1.782162/9.107670` 秒，公网 TCP connect `0.166276/7.199228` 秒。另一次 30 样本基线为业务机 `0.000865/0.001536`、隧道 `1.046814/2.387109`、公网 `3.455652/9.985869` 秒。隧道服务 active，累计重启 969 次；当天日志多次 `Timeout, server ... not responding`。

入口最近 10000 条成功请求的只读聚合：订单侧栏 API 66 条 p50/p95 `6.148/16.020` 秒；指纹静态资源 95 条 `1.909/8.135` 秒；店铺设置页 403 条 `1.124/3.152` 秒。该聚合不控制缓存冷热、用户与并发，不作为改进后对照实验。

# 缺陷、未执行项与残余风险

公网与隧道高抖动仍在。Docker Hub IPv6 授权端点连接超时，本次容器构建未完成；本机原构建目录发生 Windows `EBUSY`，已改在隔离目录成功验证相同前端源码的生产构建。主线新增动态 Agent 版本的部署须单独授权，因此未部署此候选，未取得候选的 staging 冷热、跨店、限流和 p50/p95 对比。`Server-Timing` 在 staging 尚不可用。

# 结论和复测条件

本地源码与只读链路定位通过；整体 AC-01/05/06 尚待网络修复和 staging 部署后复测，故 PARTIAL。部署时先复核独立的动态 Agent 授权边界，再以合并源码/镜像摘要完成门禁，至少各 30 次冷热请求及真实已登录订单只读核对。
