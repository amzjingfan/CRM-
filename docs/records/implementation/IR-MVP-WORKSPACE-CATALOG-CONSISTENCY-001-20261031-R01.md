---
record_id: IR-MVP-WORKSPACE-CATALOG-CONSISTENCY-001-20261031-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-CATALOG-CONSISTENCY-001
base_sha: d5fe2735eeb7b5d6d48939a0b32b10b1803930e8
final_sha: a1be18c4c266293b8fdc6c6f88514f990cfd1d19
requirement_ids: [MVP-WORKSPACE-CATALOG-CONSISTENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CATALOG-CONSISTENCY-001-20261031-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-CATALOG-CONSISTENCY-001-20261031-R01.md
created_at: 2026-10-31T07:50:35Z
updated_at: 2026-10-31T07:50:35Z
supersedes: null
---

# 实施目标与范围

统一全站侧栏；让人工工作台与 Agent 店铺工具只获得明确上架且有库存的商品、当前可领取的优惠券；统一不同店铺与订单状态的基础字段，并让订单摘要以可见卡片预览进入人工回复草稿。本次不部署 staging/production，不发送买家消息。

# 实际变更及原因

- `AppShell` 移除知识库与 Agent 的原型专用侧栏分支及覆盖样式，两页直接复用其他页面的导航和账号区。
- 共用店铺查询服务按平台商品状态 `ACTIVATE` 和 SKU 正库存筛选列表、按 ID 搜索及详情；详情二次校验可避免搜索后下架/售罄仍被推荐。Agent 的商品工具调用相同服务。
- 共用优惠券查询服务按 `ONGOING` 和平台返回的领取起止秒级时间筛选。Agent 优惠券工具调用相同服务；不把买家领取资格当作已验证。
- 工作台侧栏也作保守展示筛选，保留平台分页游标；空白页可继续加载。订单卡片在九种状态显示相同基础字段，平台未提供的值用 `—`，退款/取消特殊字段保持按需展示。
- 订单“填入回复草稿”展示视觉摘要，实际发送内容仍是人工可编辑的文本，并保留既有审阅流程和发送开关。

# 关键决定与偏差

用户补充要求 Agent 工具与工作台采用同一商品及优惠券筛选，因此筛选落在现有共用服务层。平台分页总量仍表示未过滤的平台总数，不能误称可用数量。订单摘要只是工作台预览，不伪称 TikTok 原生订单卡片。

# 数据、配置、接口、迁移或 Prompt 影响

目录 API 的响应形状不变，但商品/优惠券列表语义收紧；商品详情对不可推荐商品返回 404。无迁移、配置、Prompt 或真实发送能力变更。已同步 `docs/product/PRODUCT.md`、`docs/architecture/API.md`、`docs/architecture/AI.md`。

# 验证交接

见关联 TR：重放到 2026-10-31 最新主线后的最终 subject `a1be18c4` 上，相关后端 1795 通过/1 条件跳过，受影响生产构建浏览器 138/138，前端契约 78/78，类型、lint、Ruff、mypy 与构建通过。

# 限制、风险与回滚

未做真实 TikTok 账号下各店商品/优惠券实例验收，也未发布 staging。若平台不提供库存或领取时间，采用保守筛选；买家独享资格仍需人工核实。回滚本 subject 或其部署镜像可恢复旧展示，未改动数据库。
