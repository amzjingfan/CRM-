---
record_id: TR-MVP-STAGING-LATENCY-001-20261029-R17
record_type: test
revision: R17
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: 86e5c4e48862da445932ad50529c3a85bd3801f5
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R14.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
environment: isolated staging release 82e9fd8365d09b0a2bd2cc8a44f82ed89c40d2fc, linux/amd64 frontend, local production browser and authenticated read-only staging browser
created_at: 2026-10-29T06:30:00+08:00
updated_at: 2026-10-29T06:30:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R16.md
---

# 范围与结果

`TEST_LAYOUT=centralized`。隔离 release 相对已运行 `eb0eedc7` 只有两个前端组件和一个浏览器测试改变。`npm run lint` 0 error/8 既有 warning，`npm run typecheck`、`npm run build` 通过，`npm run test` 51/51；本地生产构建以 `UI_CACHE_EXPECT_PRODUCTION=1` 跑完整浏览器 128/128，包括店铺名称延迟时配置先回显，未触发平台写入。主线源码的先红后绿、132/132 生产浏览器及只读网络分段见 [R16](TR-MVP-STAGING-LATENCY-001-20261029-R16.md)。

镜像本机/业务机摘要、架构和 revision 一致；私有备份三件可读且权限为 `0700/0600`；`ValidateOnly=validated`、`Deploy=passed`，迁移头已应用，12 容器运行，固定出口匹配，原单店人工发送范围和各安全开关保持。公网健康三路与基础接待三路共六路径 HTTP 200，单次 TTFB 约 1.0–1.9 秒，只作诊断。已登录 in-app browser 的快捷回复页显示授权店铺选择与空态，超时页显示一条既有策略及“仅配置状态，不自动发送”；均未写入。欢迎语页面的浏览器导航工具 60 秒超时，记 `UI_UNAVAILABLE`；公网该路由为 200。浏览器工具墙钟不能当成页面加载耗时。

# 未执行与结论

GitHub PR #617 的最终 head `256545fc` 对应 run `40777570858`，backend job `123130703875` 和 frontend job `123130703256` 均 runner 空、0 steps 失败；CI **未运行**，采用此前获批的本地替代门禁。未现场量测真实用户可见冷热回显，也未完成跨店、并发 401、真实 TikTok 429/失败和全站性能对照。WAN 波动期公网 p50/p95 只作诊断。局部发布通过，整体结论 `PARTIAL`，任务继续 `VERIFYING`。机器证据见[低敏记录](../../../release/evidence/staging/crm-staging-reception-progressive-20261029.json)。
