---
record_id: TR-MVP-STAGING-LATENCY-001-20261028-R05
record_type: test
revision: R05
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: 921e3c051a0bf54d942531947faff9f98c04009c
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R05.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
environment: local production Next.js, staging business host, public HTTPS and ingress read-only logs
created_at: 2026-10-28T21:15:00+08:00
updated_at: 2026-10-28T21:15:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R04.md
---

# 范围与结果

`TEST_LAYOUT=centralized`。主线候选 `921e3c05` 在干净独立工作树验证：TypeScript typecheck 通过；ESLint 0 error、8 个既有 warning；前端合同 48/48；生产构建通过；以本地生产 Next 服务执行浏览器 122/122。新用例在列表响应被阻塞时验证消息独立请求和渲染。最初没有启动本地服务的一次浏览器运行因连接拒绝失败，启动生产服务后 122/122 通过，不计作产品回归失败。

staging 专用 release `9d6ccc20` 从既有已部署性能分支产生，差异只含前端实现和该测试；干净构建工作树的生产构建、浏览器 118/118、合同 48/48 通过。最终主线候选包含后合入的 Agent 页面测试，因此浏览器数量增加，未将 Agent 产品代码带入 staging。

# 发布门禁与现场

前端镜像本机从精确 release 源码构建，验证 OCI 修订标签与单一摘要；因业务机从 GHCR 预取新层过慢，经校验 SHA-256 的 OCI 归档从受控本机传入业务机并导入同一摘要。部署前的环境、PostgreSQL 自定义转储、MinIO 归档置于私有 `0700/0600` 路径，目录清单可读性检查通过。仓库门禁 ValidateOnly=`validated`、Deploy=`passed`；12 个 CRM 容器健康，后端镜像未变，单店人工发送范围及 Agent 调试、文档开关保持。公网三个健康端点、工作台与店铺设置页面为 200；已登录工作台只读显示会话和消息，未触发真实发送。具体摘要见[低敏证据](../../../release/evidence/staging/crm-staging-workspace-refresh-20261028.json)。

# 性能与未完成项

发布后 30 次顺序公网 `/healthz` 均 200，TTFB p50/p95 2.678/5.601 秒，TCP connect 0.184/2.213 秒。入口最近 90 条同路由为 89 次 200、1 次 504，请求耗时 p50/p95 0.191/1.720 秒；两个窗口并非同一请求逐条配对，不能直接相减。另一次 30 次公网探测为 29 次 200、1 次非 200，未记录该状态；入口 5000 条近窗还显示会话列表 2060/2068 次 200、消息 2027/2030 次 200，包含历史窗口与未登录请求。公网链路和偶发入口错误仍需调查。

工作台并行请求减少慢列表阻塞消息的等待，但未获得真实用户同条件前后 30 次回显对照。尚未完成全站主要页面、TikTok 读接口、数据库、跨店、冷/热、失败/限流受控样本；`MVP-STAGING-LATENCY-001` 仍 **PARTIAL / VERIFYING**。未用 Actions 部署，未发消息、退款或发布 production。
