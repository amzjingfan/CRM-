---
record_id: TR-MVP-STAGING-LATENCY-001-20261028-R04
record_type: test
revision: R04
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: 9415044da2848877a722a4b790c2e6734a0ecec4
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R04.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-05, AC-06]
environment: staging public Nginx, authenticated settings and workspace, public HTTPS
created_at: 2026-10-28T19:38:00+08:00
updated_at: 2026-10-28T19:38:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R03.md
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT=centralized`。本次只有 Nginx 日志格式，无新增测试源码。通过隔离 `nginx -t`、私有备份、活动哈希、只读 HTTPS 探针和低敏日志聚合验证；未发送消息、退款或部署 production。

# 命令和逐项结果

- 候选与备份 SHA-256 分别为 `b32a1da759acb0f0c218ae3082acbc3ca3d37f359c3765a84b11f22baa794fd7`、`5e733a1dcd8b7a09323093b5a26634fe53f91c3b44349f55ee1a796d401229d2`；差异仅新增 `server_timing`。私有目录 `0700`，备份与候选 `0600`；独立主配置 `nginx -t` 通过。
- 首次活动重载后即时日志检查见旧 worker，自动回滚且复核原哈希与语法。第二次活动重载第 2 次探测记录 `app;dur=<整数>, tiktok;dur=<整数>`；活动哈希等于候选，`nginx -t` 与本机 HTTPS `/v1/health` 200。
- 公网健康路径 30/30 为 200，TTFB p50/p95 1.750/5.189 秒；入口对应窗口 30 条总耗时 p50/p95 171/1175 毫秒，应用报告 1/2 毫秒，TikTok 0。入口总耗时含响应传输，不能把分位数直接相减为单请求网络耗时。
- 已登录页面日志：工作台列表 23 条入口 p50/p95 885/2167 毫秒、应用 20/25 毫秒；消息 22 条入口 366/1239 毫秒、应用 16/23 毫秒；店铺列表 2 条入口 188/905 毫秒、应用 12/15 毫秒；授权 1 条入口 781 毫秒、应用 17 毫秒。上述 TikTok 耗时均 0。样本量不足以宣称全站验收。
- 后端与前端容器仍健康且摘要分别为 `sha256:a1f05c91…428c36`、`sha256:eeb53b2d…10b63`；未用 GitHub Actions 部署。

# REQ/AC 或门禁与证据映射

[低敏现场证据](../../../release/evidence/staging/crm-staging-server-timing-20261028.json)保存精确哈希、样本量、分位数和回滚事实。源代码中的工作台后台刷新每 5 秒先请求会话列表再请求选中会话消息；这两次请求串行叠加公网等待，是下一处可修复的回显慢点。

# 缺陷、未执行项与残余风险

公网广域网重传与抖动仍在。尚未取得数据库、TikTok 实际读接口、全站主要页面、跨店和错误/限流各 30 次受控冷/热样本；本轮只有健康、工作台和少量设置页的诊断样本。入口新字段仅在应用返回数值头时可解析，其他请求为空。

# 结论和复测条件

入口日志分段可用，`AC-05` 前进但未完成。需处理工作台串行刷新、线路与剩余页面后再做受控公网 p50/p95 和隔离验收；整体任务仍 **PARTIAL / VERIFYING**。
