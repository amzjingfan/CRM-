---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-001-20261020-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-001
base_sha: 6846108b023e67050028d5f8d0d7fa8216b9f603
final_sha: 9cd859d637c9852d7780e929c0e8818d781bfa59
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-001-20261020-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-001-20261020-R01.md
created_at: 2026-10-20T14:53:40Z
updated_at: 2026-10-20T14:53:40Z
supersedes: null
---

# 实施目标与范围

将已确认的客户侧栏原型 A 接入真实 TikTok 只读数据：所选会话买家的订单、该会话店铺的商品/SKU 与优惠券。源码任务在本地完成验证；从合并主线手动部署及真实页面只读验收由 `MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001` 承担。

# 实际变更及原因

- 订单侧栏按会话授权、店铺、平台和买家查询已同步订单，支持六类字段、状态及分页。后续订单同步保留实际返回的商品 ID、SKU ID、SKU 名称、图片及金额拆分；历史缺项明确留空。
- 商品与优惠券走当前店铺渠道的 TikTok 官方只读分页接口。商品按 Product Basic Scope 检查，优惠券按现有客服或促销 Scope 检查；商品名、券编码在当前平台页过滤并提示继续加载。商品展开时另取完整详情以显示 SKU、库存和图片。
- 工作台侧栏替换原快捷操作为订单、商品、优惠券三页。商品和优惠券按钮只将文字填入可编辑草稿；退款禁用，不调用发券、退款或消息发送。
- 同步 API、架构和产品文档，补跨店隔离、官方签名路径、前端交互及旧测试拦截器的行为验证。

# 关键决定与偏差

官方商品搜索不提供全目录标题查询，优惠券编码也需逐页过滤，因此界面明确提示可能有后续结果。平台未返回的销售量、价格拆分和买家优惠资格不作推断。staging 现有唯一 TikTok 渠道只读核对结果为已连接、Product Basic 与优惠券读取 Scope 均具备；未申请或扩大授权。

# 数据、配置、接口、迁移或 Prompt 影响

新增工作台侧栏搜索 POST 与商品详情 GET；POST 要求 `workspace.view`、CSRF 和会话店铺权限。订单只在现有 `Order.raw_payload` 与 `OrderItem.raw_payload` 保存平台字段，无迁移、无新配置或 Prompt。商品与优惠券不持久化，也不修改 TikTok 平台状态。

# 验证交接

本地格式、类型、完整隔离数据库回归、前端契约、生产构建和生产模式浏览器回归均通过；精确命令、结果、跳过项和范围见关联 TR。真实平台结果及 staging 发布须由后续部署任务单独留证，不能以本地 Mock 宣称现场完成。

# 限制、风险与回滚

订单旧数据缺少新字段时不自动回填。商品名、优惠券编码跨平台页搜索依赖人工继续加载；平台权限或上游响应异常时失败关闭。回滚源码可恢复原侧栏，但部署回滚须保留新增会话消息并依现有 staging 门禁执行。Production G8 No-Go 不变。
