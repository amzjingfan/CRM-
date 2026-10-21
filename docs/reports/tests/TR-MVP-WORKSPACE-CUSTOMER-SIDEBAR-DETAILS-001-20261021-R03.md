---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R03
record_type: test
revision: R03
status: PASS
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001
tested_sha: 3e01d7fc752e46c3105946ca3f3165b44c5c8aba
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R02.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: staging Rootless Docker; official TikTok read-only API; authenticated user screenshot on later deployed frontend
created_at: 2026-10-21T03:50:41Z
updated_at: 2026-10-21T03:50:41Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R02.md
---

# 测试范围、环境与 TEST_LAYOUT

R01 覆盖集中式后端/前端测试，R02 覆盖合并主线的手动 staging 发布、官方订单只读及跨买家 404。R03 补齐登录态真实订单卡视觉证据；截图含订单及物流标识，仅留在用户对话中。

# 命令和逐项结果

- R02 官方只读探针返回付款方式、承运商、最新物流描述与时间，跨买家读取同单为 404；已部署页面合成浏览器 3/3，通过且无发送。
- 此后字段修复合并主线并更新后端至 revision `15ceabf8eac90f2fe8c7843e24af26381c3e0499`，仅增加付款时间和优惠金额投影，订单授权分支未变；最新前端 revision `4f32c04e2cc2f92170f30c91b8a2ca4d1bf75266` 已运行 healthy，公网 ready 为 200。关联物流卡片 R02 已记录完整手动发布门禁。
- 用户刷新已登录 TikTok 订单会话并提供截图，卡片实际显示买家实付金额、付款时间、ApplePay、已送达、物流单号、USPS、最新物流描述与时间；订单详情按钮为“刷新详情”。
- Codex 浏览器读取既有及新标签超时，仍标记 `UI_UNAVAILABLE`；用户截图是可见页面证据。未向买家发送消息、退款或发券。

# REQ/AC 或门禁与证据映射

- AC-01：R01 授权和失败关闭回归、R02 官方跨买家 404；之后后端投影增量不改授权路径。
- AC-02：R02 真实详情数据存在，R03 登录态卡片显示来源字段与轨迹时间，缺失状态行为由源码测试覆盖。
- AC-03：R02 手动发布及 3/3 合成页面交互，R03 用户在更新后的 staging 实际页面截图确认。

# 缺陷、未执行项与残余风险

未逐一制造其他订单物流状态的真实买家订单；独立物流状态缺失时只能按明确订单运输阶段或空值显示，不能推断“待派送”。商品/优惠券完整页面验收归独立侧栏部署任务。production G8 No-Go。

# 结论和复测条件

订单详情任务 AC-01～03 的本地、官方只读、手动 staging 和已登录视觉证据齐备，R03 为 `PASS`。如后续发现字段与 TikTok 后台不一致，先比对同单官方只读数据，不根据轨迹描述猜测状态。
