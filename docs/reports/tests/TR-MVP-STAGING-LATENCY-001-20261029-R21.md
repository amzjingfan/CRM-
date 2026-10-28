---
record_id: TR-MVP-STAGING-LATENCY-001-20261029-R21
record_type: test
revision: R21
status: PASS
task_id: MVP-STAGING-LATENCY-001
tested_sha: 053ebc9f625042e6c38c3c3c10df6e4c9e0284ba
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R17.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
environment: deployed performance-only staging release 3efa1f2e; exact-release local backend cache test; read-only authenticated browser; prior exact-source and release gates
created_at: 2026-10-29T07:52:00+08:00
updated_at: 2026-10-29T07:52:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R20.md
---

# 修订验收结论

`TEST_LAYOUT=centralized`。本轮在当前线上隔离 release `3efa1f2e` 的后端源码执行 `uv run pytest -c pyproject.toml ../tests/backend/domain/test_workspace_sidebar_live_orders.py -q`，19/19 通过；首次未显式指定配置的局部命令因 `app` 导入路径未设置在收集阶段失败，改为显式 `-c` 后通过，未将首次错误计作产品缺陷。缓存用例直接覆盖冷请求与 20 秒内热命中、过期、跨店、授权凭证轮换、手动刷新、429 失败不缓存和大结果不驻留。线上前端隔离 release 的 51/51 契约、129/129 生产浏览器、类型/构建、精确镜像与发布门禁沿用 [R20](TR-MVP-STAGING-LATENCY-001-20261029-R20.md)。

已登录 staging 数据看板只读切换两家授权测试店铺：切换后币种从 USD 变 CNY，咨询摘要与数据更新时间更新；恢复原店铺后 USD 回显。没有提交配置、向买家发消息或操作退款。其他已登录工作台、订单、门店、基础接待、知识库和 Agent 页面回显及合成故障回归分别见 [R13](TR-MVP-STAGING-LATENCY-001-20261029-R13.md)、[R15](TR-MVP-STAGING-LATENCY-001-20261029-R15.md)、[R17](TR-MVP-STAGING-LATENCY-001-20261029-R17.md)、[R19](TR-MVP-STAGING-LATENCY-001-20261029-R19.md)、[R20](TR-MVP-STAGING-LATENCY-001-20261029-R20.md)。本轮临时试验过更易被浏览器工具读取的慢 API 日志文本；该未发布试验已撤回，不算线上功能或验收结果。

| 验收 | 对应证据与结论 |
|---|---|
| AC-01 网络定位 | [R03](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R03.md)、[R04](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R04.md)：入口回环与公网各 30 次前后对照，业务应用段远小于入口/隧道等待；WAN 重传与偶发 504 留为外部线路风险。 |
| AC-02 TikTok 连接 | [R02](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R02.md)：只读连接复用、逐请求签名、店铺凭证隔离和固定出口发布门禁通过。 |
| AC-03 侧栏渐进 | [R14](TR-MVP-STAGING-LATENCY-001-20261029-R14.md) 与 R20 的生产浏览器回归：摘要在详情前显示，物流不阻塞订单字段，自动详情最多并发两项，429 可手动重试。 |
| AC-04 私有缓存 | 本轮精确 release 19/19 后端测试及 R20 浏览器刷新用例：20 秒缓存按店铺、买家及授权隔离，过期/刷新可见，429 不缓存；HTML/API 不进入公共缓存，仅指纹静态资源可共享。 |
| AC-05 分段观测 | [R04](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R04.md) 与 [R13](TR-MVP-STAGING-LATENCY-001-20261029-R13.md)：入口 request/upstream、后端 app/TikTok `Server-Timing`、前端按页面族聚合的慢 API 耗时与 Trace ID；已观察工作台、设置和看板等主要页面。 |
| AC-06 应用侧回显 | R13/R15/R17/R19/R20 与本轮看板跨店：本地冷/热、迟到响应、跨店、401、503、429 合成行为和已登录只读页面回显符合预期；原单店人工发送和全部安全开关保持。公网 p50/p95 按用户修订只作网络异常期诊断。 |

结论 `PASS` 限于上述修订后的 staging 应用侧验收。没有人为触发真实 TikTok 429 或真实过期会话并发 401；这些失败路径以隔离合成用例验证，不把它们说成线上真实故障。公网单次 TTFB、工具调用墙钟以及非配对样本都不能证明全站稳定提速；WAN 线路仍可造成秒级等待，production 维持 G8 No-Go。不能把本任务结论推广到生产或所有未来店铺流量。
