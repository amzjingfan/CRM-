---
record_id: TR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R05
record_type: test
revision: R05
status: PASS
task_id: MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001
tested_sha: b98b955b962df638d9a899fc17c2396cbcb2ad54
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R02.md
requirement_ids: [MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001]
acceptance_ids: [AC-01, AC-03, AC-05, AC-06]
environment: staging logged-in Codex in-app browser, 2026-11-02
created_at: 2026-11-02T23:01:14+08:00
updated_at: 2026-11-02T23:01:14+08:00
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R04.md
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。重新打开 Codex 内置浏览器标签，在已登录 staging 工作台只读核对 TikTok US 测试店铺和 XBM 的各一笔已有订单。先点击“客户信息”使侧栏真正打开，再检查订单卡，之后才分别查看订单详情和物流弹层。未创建测试数据、发送买家消息、退款或操作 production。

# 现场步骤和逐项结果

| 店铺 | 订单卡（打开详情前） | 订单详情和物流弹层 | 结果 |
|---|---|---|---|
| TikTok US 测试店铺 | 订单“已完成”，支付“已付款”，物流“已送达”；物流商 USPS；最新轨迹 `Delivered, Individual Picked Up at Postal Facility`，时间 2026/10/8 08:11:00 | 详情页物流商 USPS；物流弹层 USPS、同一最新轨迹，8 条节点；未出现错误提示 | PASS |
| XBM | 订单“运送中”，支付“已付款”，物流“运送中”；物流商 SwiftX；最新轨迹 `Out for delivery.`，时间 2026/11/2 21:09:59 | 详情页物流商 SwiftX；物流弹层 SwiftX、同一最新轨迹，16 条节点；未出现错误提示 | PASS |

首次查看可访问性树时，关闭的 `customer-panel` 仍保留旧的 `物流商 —` 节点；其样式将侧栏平移到视口外。该节点不是用户可见订单卡，不能据此判定回显失败。打开侧栏后，两店卡片在打开详情和弹层前已自动回显实际物流商及最新轨迹。

# REQ/AC 与证据映射

AC-01 的已完成订单标签及物流阶段分离由 TikTok US 现场样本确认；AC-03、AC-06 的实际承运商自动回显及卡片/详情/弹层一致由两店现场样本确认；AC-05 的已登录 staging 只读验收本次通过。R03 保留同 subject 的 81/81 契约、68/68 合成浏览器、lint/typecheck/build 等源码验证记录；R04 保留运行镜像包含 PR #717、容器及健康路径的先前证据，本次未重新检查镜像摘要或重跑这些命令，不把历史结果冒充本次执行。

# 残余风险与结论

本次现场抽样为每店一笔已有订单，未覆盖无承运商、多包裹、平台限流/失败、所有未来接入店铺的真实订单。未来店铺共用同一源码路径的结论来自实现和契约，不等于逐店现场验收。当前两店的目标回显场景 `PASS`；没有发现需要本轮修复的可见缺陷。production 仍为 No-Go。
