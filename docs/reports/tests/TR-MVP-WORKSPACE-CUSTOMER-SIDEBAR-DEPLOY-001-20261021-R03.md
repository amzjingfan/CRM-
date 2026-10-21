---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R03
record_type: test
revision: R03
status: PASS
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001
tested_sha: 15ceabf8eac90f2fe8c7843e24af26381c3e0499
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R02.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: staging Rootless Docker; authenticated user screenshots; manual deployment evidence
created_at: 2026-10-21T03:58:00Z
updated_at: 2026-10-21T03:58:00Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R02.md
---

# 验证范围与事实来源

R02 已记录合并源码的手动镜像部署、私有备份、六摘要预取、validate/deploy、固定出口、数据库头、11 个服务和三项公网健康 200。本次 R03 只补齐发布后已登录 TikTok 工作台的真实订单、商品 SKU 和优惠券卡片视觉验收。截图含订单与商品标识，仅保留于用户对话；仓库只存[低敏核对结果](../../../release/evidence/staging/crm-staging-customer-sidebar-ui-20261021.json)。浏览器自动化读取超时，记 `UI_UNAVAILABLE`，不冒充自动化截图。

# 逐项结果

- 订单：用户截图中的真实订单卡显示买家实付金额、付款时间、支付方式、物流状态、物流单号、承运商及最新物流描述与时间；详情任务 [R03](TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R03.md) 已独立记录同单官方只读与跨买家 404。物流卡片 [R02](TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001-20261021-R02.md) 记录前端 `4f32c04e` 的手动更新及健康。
- 商品：用户在同一 staging 工作台截图展开商品 SKU，卡片显示商品价格、商品状态“上架中”，SKU 表显示 SKU、卖家 SKU 与库存状态“有货”。截图同时有“正在加载 SKU 详情…”字样；单帧无法确认其是否持续，当前只验收已呈现的字段。
- 优惠券：用户截图显示优惠券状态“已过期”、可读优惠金额“立减 $10.00”、展示渠道“常规展示”、领取截止时间和填入回复草稿入口；未出现之前的原始金额对象。
- R02 官方只读与授权边界证据沿用：同店买家订单、店铺商品、优惠券加载；本次未触发买家外发、退款或发券。生产发布仍未授权。

# AC 映射与限制

- AC-01、AC-02、AC-04：R02 手动发布与恢复证据；后续前端物流卡片部署证据补充当前运行版本。
- AC-03：本次三个已登录真实页面截图，加上 R02 的同店官方只读与跨买家 404。截图证明示例订单、商品 SKU、优惠券可见；它不能证明每一种物流状态或所有商品/优惠券均已现场抽样。
- 用户截图只显示静态时点，不证明 SKU 加载提示持续存在或消失；若持续存在，另行复现并修复。

# 结论

客户侧栏 staging 手动部署与三类真实只读卡片的本次验收为 `PASS`。未使用 GitHub Actions 作为门禁，没有新增外发或高风险写入；production G8 No-Go。
