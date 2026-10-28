---
record_id: TR-MVP-STAGING-LATENCY-001-20261029-R13
record_type: test
revision: R13
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: eab7e2c207308fde34be1ca50f25d32be1670cfa
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R11.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
environment: staging authenticated in-app browser and public gateway safe JSON access log
created_at: 2026-10-29T03:24:00+08:00
updated_at: 2026-10-29T03:24:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R12.md
---

# 只读观察与分段结果

性能专用 release `4edddffb` 运行期间，在已登录浏览器中只读查看门店、看板、工作台、知识库及 Agent 管理。门店页显示一条授权；看板从“测试店铺”切换到“TikTok US 测试店铺”后，币种和咨询分类随所选店铺变化；工作台会话列表、消息与客户侧栏回显；知识库当前店铺、分类及空列表状态和 Agent 当前店铺、零 Agent 状态均回显。未向买家发送消息、退款或执行写入。

入口机从活动 staging 安全 JSON 日志只读聚合 2026-10-28 18:50–19:18:45 UTC 的 134 条请求，134 条均 2xx；仅输出规范化路由族和分位数，没有导出原始日志、IP 或查询参数。[低敏聚合证据](../../../release/evidence/staging/crm-staging-latency-readonly-pages-20261029.json)保留各组样本量。工作台会话列表 18 条入口 `request_time` p50/p95 为 754/2363 ms、应用 `Server-Timing` 为 16/124 ms；消息 17 条为 500/1781 ms、应用 19/116 ms。门店 API 4 条入口 167/506 ms、应用 14/16 ms；知识文件 3 条入口 538/656 ms、应用 31/31 ms；看板指标 2 条入口 174/538 ms、应用 25/47 ms。上述 API 的 TikTok 分段均为 0，显示该窗口的等待主要发生在应用处理之外；入口总耗时包含响应传输，不能用分位数相减直接得出单请求 WAN 时间。

# 未完成与判定

这组数据是生产式共享网络上的小样本、非配对观察；浏览器控制工具每次导航的壁钟时间包含工具等待，不能当成用户可见页面耗时。切换看板店铺仅核对可见币种/咨询摘要，未完成所有页面跨店和买家身份的精确数据隔离验收。真实过期会话并发 401、匹配的冷/热回显、失败及 429 限流现场路径仍未验证；本次也未触发这些请求。WAN 异常期间公网 p50/p95 仍只作诊断，整体加速尚不能宣称，任务保持 `PARTIAL / VERIFYING`。

入口只读访问使用本机临时密钥副本，原密钥未改动。该副本已限制为当前 Windows 账号可读；自动审批拒绝删除它，需人工清理。此事项不改变 staging 运行配置。
