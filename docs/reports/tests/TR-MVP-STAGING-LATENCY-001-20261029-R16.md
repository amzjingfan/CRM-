---
record_id: TR-MVP-STAGING-LATENCY-001-20261029-R16
record_type: test
revision: R16
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: 86e5c4e48862da445932ad50529c3a85bd3801f5
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R13.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
environment: local frontend dev and production build, synthetic read-only browser fixture; staging network read-only probes
created_at: 2026-10-29T06:05:00+08:00
updated_at: 2026-10-29T06:05:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R15.md
---

# 测试范围与结果

`TEST_LAYOUT=centralized`。新增浏览器用例拦住 `/v1/settings/stores`，让 `/v1/auth/me` 与配置读取正常返回；旧实现约 3.5 秒因配置行未出现而失败，修复后约 1.6 秒通过。用例不调用写入接口。最终源码的基础接待浏览器 21/21；开发浏览器 131 passed、1 production-only skip；生产构建浏览器 132/132；前端契约 `npm run test` 51/51；typecheck、build 通过；lint 为 0 error、8 个既有 warning；`git diff --check` 通过。生产浏览器由本地 `next start` 提供页面，standalone 提示不影响本次 200 和用例结果。

# 分段诊断与限制

同轮只读 30 次 `/healthz`：业务机回环（正确 Host 头）30/30 HTTP 200，TTFB p50/p95 0.000609/0.001068 秒；入口经隧道 30/30 200，0.446484/1.169609 秒；入口本地 HTTPS 30/30 200，0.284850/1.003837 秒；公网 30/30 200，0.786616/1.760033 秒。它们是各自独立请求，不可直接相减为单次请求耗时。入口近 10 分钟健康请求日志 62/62 200，Nginx `request_time` 和上游耗时 p50/p95 均为 159/636 毫秒。业务机活动 SSH 隧道 RTT 约 147.7 毫秒，累计重传字节约为发送字节的 6.35%；这是网络抖动线索，不能单凭累计值断定本次具体请求原因。健康路由没有 `Server-Timing` 应用分段。没有保存原始日志、IP、查询或买家信息。

本次尚未发布此新增 UI 修复，未完成已登录 staging 的真实冷热对照、跨店、401、429 及用户可见回显计时。公网 p50/p95 在当前 WAN 波动下仅作诊断，不作应用修复绝对阈值。故整体任务结论维持 `PARTIAL`，待精确前端镜像发布和只读现场复核后补充下一版记录。
