---
record_id: TR-MVP-STAGING-LATENCY-001-20261029-R20
record_type: test
revision: R20
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: 053ebc9f625042e6c38c3c3c10df6e4c9e0284ba
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R16.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
environment: isolated staging release 3efa1f2e3c7d75030401aee7a1c189a4b4f54b23, linux/amd64 frontend, local production browser and authenticated read-only staging browser
created_at: 2026-10-29T07:30:00+08:00
updated_at: 2026-10-29T07:30:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R19.md
---

# 看板局部发布验收

`TEST_LAYOUT=centralized`。隔离 release 相对实际运行 `82e9fd83` 只改看板页面及合成浏览器测试；两个 blob 与主线源候选相同。`npm test` 51/51，生产构建完整浏览器 129/129，`npm run typecheck`、`npm run build` 通过，`npm run lint` 0 error、8 个既有 warning。主线源候选的先红后绿和 133/133 生产浏览器见 [R19](TR-MVP-STAGING-LATENCY-001-20261029-R19.md)。合成用例证明店铺名称未返回时指标仍可先显示，不能代替真实页面计时。

镜像本机/业务机的精确摘要、linux/amd64 和 OCI revision 一致；私有备份三件可读、权限 `0700/0600`。`ValidateOnly=validated`、`Deploy=passed`，迁移头已应用、12 容器运行、固定出口与原单店人工发送及安全开关保持。公网三健康加看板、门店、工作台、快捷回复路由均为 HTTP 200，单次 TTFB 约 0.73–1.82 秒，只作诊断样本。已登录 in-app browser 只读状态显示看板已补齐授权店铺名称、核心指标及次要组件，未执行写入；浏览器工具墙钟不能当作页面加载耗时。

[PR #623](https://github.com/CP11-gh/CRM/pull/623) 最终 head `b70866c7` 的 run `40784270034`，后端 job `123153418018` 与前端 job `123153418362` 均 runner 空、0 steps，CI **未运行**，采用项目已批准本地替代门禁。未现场量测用户可见冷/热、真实跨店与并发 401、真实 TikTok 429/失败或全站配对对照。公网波动期 p50/p95 只作为诊断，不把单样本视为加速证据。局部发布通过，整体 `PARTIAL`、任务 `VERIFYING`。机器证据见[低敏记录](../../../release/evidence/staging/crm-staging-dashboard-authorized-20261029.json)。
