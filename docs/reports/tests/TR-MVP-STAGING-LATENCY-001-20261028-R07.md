---
record_id: TR-MVP-STAGING-LATENCY-001-20261028-R07
record_type: test
revision: R07
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: fe627e4f3d7246e57cc4e7e0dd9c766c8e47d862
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R07.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-05, AC-06]
environment: local production Next.js with intercepted synthetic API and isolated staging release, staging business host and authenticated public browser
created_at: 2026-10-28T23:35:00+08:00
updated_at: 2026-10-28T23:35:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R06.md
---

# 范围与结果

`TEST_LAYOUT=centralized`。主线候选 `fe627e4f` 的 `npm run typecheck`、`npm run build` 通过，`npm run lint` 为 0 error/8 个既有 warning，`npm test` 48/48，`UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui` 125/125。慢组件阻塞用例在旧实现先因等不到指标失败，修复后通过；次要组件 503 用例确认核心指标保留、预警区显示错误而非零。该用例第一次运行因测试定位器匹配 Next.js 自带路由播报器失败，修正定位器后通过；属测试定位问题。专用 release `f9bfc109` 的类型、构建、lint、48/48 契约和 121/121 生产浏览器通过；两候选的看板页面及测试 blob 完全一致，浏览器总数差来自主线其他产品测试。

# 发布与现场

候选仅有两文件差异。OCI 压缩层 64,408,970 字节，归档本地与远端 SHA 相等，运行镜像 revision、linux/amd64 和 RepoDigest 匹配。私有备份目录 `0700`，环境、自定义 pg_dump、MinIO tar 均 `0600` 且可读取；`ValidateOnly=validated`、`Deploy=passed`。12 个 CRM 容器运行，前端为新摘要，后端仍为 `sha256:a1f05c91…428c36`，单店人工发送和安全开关保持。一次性 GHCR 凭据已注销。

公网 `/healthz`、`/v1/health`、`/v1/health/ready`、`/dashboard` 均 200。已登录浏览器的默认授权店铺显示核心指标、趋势、渠道、预警和热门咨询空态；切换另一个店铺的浏览器调用超时，**未得到现场跨店回显证据**，合成旧响应隔离回归仍通过。未点击保存、发送或退款；无 Actions 部署或 production 操作。精确摘要、备份和门禁 SHA 见 [低敏证据](../../../release/evidence/staging/crm-staging-dashboard-progressive-20261028.json)。

# 未完成项

部署后 `/dashboard` 一次公网 TTFB 为 6.476 秒，不能把局部并行回显推断为公网整体提速；既有分段证据显示入口/隧道显著抖动，用户允许公网 p50/p95 在网络异常期间作为诊断对比。真实用户同条件前后回显、全站冷/热、跨店、故障和限流现场验收仍缺，整体 `PARTIAL / VERIFYING`。
