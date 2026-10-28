---
record_id: TR-MVP-STAGING-LATENCY-001-20261029-R15
record_type: test
revision: R15
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: 40f39665b03a67712384dec13fec06c0c25ba2bf
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R12.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-03, AC-06]
environment: authenticated staging in-app browser, read-only customer workspace, performance-only release eb0eedc722a552b05eb685fcc15dd84ab7f0af59
created_at: 2026-10-29T05:34:00+08:00
updated_at: 2026-10-29T05:34:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R14.md
---

# 测试范围与结果

`TEST_LAYOUT=centralized`。在已登录的 staging in-app browser 中，只读绑定两个已有工作台会话，不发送消息、不操作退款或配置。此前 R14 的订单画面 `UI_UNAVAILABLE` 在本次得到有限现场补测：一个已有已送达订单的会话显示“售后买家”，客户侧栏已打开的详情同时回显订单、物流、商品和付款分区；物流分区先显示两条事件及“展开更多”，商品显示规格，敏感电话和地址以掩码呈现。另一个已有会话显示“售前买家”，客户侧栏回显“当前搜索或状态下暂无订单”。两个会话均能看到图片和视频入口，当前输入为空、发送按钮禁用。没有在页面上触发 TikTok API 写入。

本次浏览器绑定分别约 53 秒和 43 秒，截图请求 30 秒超时；这些是工具调用墙钟时间，不能当成页面加载、TikTok API 或用户可见回显耗时。未保存含买家数据的截图或完整页面文本。R14 的 50/50 生产浏览器、51/51 契约、本地合成 429 恢复、部署门禁及公网四路 200 结果仍可由 [R14](TR-MVP-STAGING-LATENCY-001-20261029-R14.md) 和[低敏发布证据](../../../release/evidence/staging/crm-staging-order-detail-retry-20261029.json)追溯；本次未重跑源码测试，也未更换镜像。

# 未完成与复测条件

本次两个会话属于同一测试店铺，且第一个详情在绑定前已打开，故不证明跨店隔离、点击后首次回显速度或冷/热对照。未现场触发真实 401 并发、TikTok 429/失败、手动重试，也没有配对的用户可见耗时。WAN 抖动期间公网 p50/p95 只作诊断；整体加载加速仍无可归因的现场结论。结论维持 `PARTIAL`，任务维持 `VERIFYING`。
