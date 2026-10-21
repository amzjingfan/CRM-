---
record_id: RR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001-20261021-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001
reviewed_sha: 736c214ed457332ac9316301ea7a6b8976433fe3
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001-20261021-R01.md
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001-20261021-R01.md
review_focus: [correctness, buyer_identity, store_isolation, platform_read_only, data_integrity]
created_at: 2026-10-21T02:07:22Z
updated_at: 2026-10-21T02:07:22Z
supersedes: null
---

# 审查范围、依据与重点风险

审查订单支付时间、优惠金额投影及客服界面状态映射。风险是把订单状态误当支付或物流事实、把平台 Python 对象文本显示给客服，或为截图一致性打开退款/外发操作。

# 发现、级别、位置和证据

源码仍从已核对买家身份的订单读取；本次没有改变会话/店铺授权、详情跨买家 404、平台 Scope 或消息发送。`paid_at` 直接取官方/本地值，缺失为 `null`。优惠金额对象解析失败为 `null`，前端只映射已知枚举。审查中发现物流状态不应从订单 `DELIVERED` 等状态推断，已在 subject SHA 中改为仅使用真实 `tracking_status`，否则显示空值。退款按钮保持禁用，商品/优惠券只填人工草稿。

# 已验证与未验证内容

后端 2220 passed/3 skipped、前端 47/47、受影响浏览器及最终生产构建通过；新版本 staging 真实页面尚未验收，交给部署任务。未对官方未返回的付款截止、发货截止、取消原因及退款金额作推断。

# 结论和返修条件

批准源码合入。若真实响应出现新的金额结构或状态枚举，只读确认契约后再添加映射；若 staging 页面仍出现原始对象或跨店数据，停止部署验收并返修。
