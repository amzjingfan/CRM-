---
record_id: TR-MVP-STAGING-LATENCY-001-20261029-R08
record_type: test
revision: R08
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: c1fcc1c74dbb073b2d560c178499b2ac5ec99f2e
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R08.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-05, AC-06]
environment: local production Next.js with intercepted synthetic APIs; isolated performance-only release; staging read-only network and runtime probes
created_at: 2026-10-29T00:48:00+08:00
updated_at: 2026-10-29T00:48:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R07.md
---

# 测试范围与结果

`TEST_LAYOUT=centralized`。旧页面在门店授权单请求用例中因等待被拦截的旧双接口超时；修复后通过。刷新保留行、503 错误提示、403 清空、成功删除即时移除等用例均在旧实现先失败，修复后通过。主线源码 `c1fcc1c7` 的 TypeScript、生产构建、前端 48/48 契约、生产模式浏览器 128/128、后端授权安全 17/17、目标 Ruff/格式/mypy 均通过；lint 为 0 error、8 个既有 warning。专用 release `18cea7f2` 的对应项目为 48/48、124/124、17/17，TypeScript、构建与目标静态检查通过；浏览器数量差来自主线其他产品用例。

# 网络与发布边界

2026-10-29 只读测 `/settings/stores` HTML：带正确 Host 头的业务机回环 30/30 HTTP 200，TTFB p50/p95 为 0.005/0.013 秒；入口经隧道 29/30 HTTP 200，p50/p95 为 1.694/7.341 秒，另 1 条 20 秒超时；公网 4/5 HTTP 200，成功样本 2.059–8.968 秒，另 1 条 15 秒超时。这是未认证页面 HTML 量测，不能代表已登录 API 回显。现网后端/前端镜像 revision 分别为 `e64ef52c`/`f9bfc109`，原 Agent 调试开关仍开启。两份本地 release 镜像构建成功；临时 GHCR 登录命令被自动审批策略拒绝，现有 Docker 凭据的前端推送返回 `unauthorized`。未产生 RepoDigest、私有备份、ValidateOnly、Deploy 或已登录现场新版本验收；staging 未切换。

# 结论与复测条件

本地用例证明慢旧接口不再阻塞页面，以及刷新、权限失败和成功写入后的即时回显。新聚合接口实际数据库耗时、已登录公网冷/热回显、跨店与故障/限流现场验收尚缺；WAN/隧道抖动仍显著。按用户决定，网络异常期间公网 p50/p95 仅作诊断对比。恢复可发布的私有镜像凭据或受审替代路径后，必须重新核对精确摘要、备份、ValidateOnly/Deploy 和安全开关；整体任务继续 `VERIFYING`。
