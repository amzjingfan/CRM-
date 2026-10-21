---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001-20261021-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001
base_sha: d27b133e719dd115ad8ec5386c943b1c83ee2ed5
final_sha: 736c214ed457332ac9316301ea7a6b8976433fe3
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001-20261021-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001-20261021-R01.md
created_at: 2026-10-21T02:07:22Z
updated_at: 2026-10-21T02:07:22Z
supersedes: null
---

# 实施目标与范围

根据用户提供的三张已登录 staging 截图修正客户侧栏：订单按状态展示适用字段，商品与优惠券不直接暴露平台状态码及优惠金额对象。此记录只覆盖源码；合入主线后的手动 staging 发布归现有 `MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001`。

# 实际变更及原因

- 订单只读投影增加可空 `paid_at`，直接来自官方 `paid_time` 或现有本地订单 `paid_at`。未付款、待出货、物流中/已完成、已取消卡片分别显示适用的支付、出货、物流、取消行；平台未返回的截止、退款和取消事实显示空值。订单金额统一标为订单总额，不把订单状态推断为支付金额或物流轨迹。
- 商品上架状态与 SKU 的真实库存数量各自显示；TikTok `ACTIVATE` 等状态映射成中文/英文标签。
- 优惠券金额对象只在包含真实 `amount` 和 `currency` 且数值有效时转换为币种与数值；无法识别时返回空值。前端映射 `EXPIRED`、`REGULAR`、`PROMO_CODE` 等平台枚举，保留原有只能填入人工草稿的边界。

# 关键决定与偏差

原型的付款截止、最晚发货、取消原因、退款状态和所有金额拆分并未由现有官方只读模型稳定提供，不能复制原型示例值。详情仍按原有授权和买家校验规则按需加载付款方式、承运商及最新物流，不对每张卡自动增加平台调用。

# 数据、配置、接口、迁移或 Prompt 影响

订单侧栏响应增加可空 `paid_at`，优惠券 `discount_value` 由结构化金额安全转换为可读字符串或 `null`。无数据库迁移、配置、Scope、外发、退款、发券和模型变更。

# 验证交接

源码与测试见本任务 TR；staging 必须从本源码合入后的精确 `main` 构建镜像，另留低敏部署和真实侧栏证据。production G8 No-Go。

# 限制、风险与回滚

未知优惠券金额结构会显示空值；未知订单/商品/优惠券状态使用“暂无”而非猜测。若部署后出现回归，按 staging 现有手动门禁恢复旧不可变摘要；恢复数据库备份前须保护部署后新增会话消息。
