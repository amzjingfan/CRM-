---
record_id: RR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-001-20261020-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-001
reviewed_sha: 9cd859d637c9852d7780e929c0e8818d781bfa59
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-001-20261020-R01.md
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-001-20261020-R01.md
review_focus: [correctness, authorization, store_isolation, platform_read_only, data_integrity, user_interface]
created_at: 2026-10-20T14:53:40Z
updated_at: 2026-10-20T14:53:40Z
supersedes: null
---

# 审查范围、依据与重点风险

复核 subject SHA 的后端适配、会话与店铺授权、订单投影、前端侧栏、测试及文档；依据产品 v0.1 边界、TikTok 官方只读路径和本次完整本地验证。重点关注跨店读取、错误平台数据、未经确认外发及错误地把部分目录搜索宣称为全量结果。

# 发现、级别、位置和证据

- 无阻断发现。`search_sidebar_orders` 先按授权会话绑定店铺、平台、买家；目录客户端从该店已连接 TikTok 渠道取得 Scope 与签名，缺权限先于平台 HTTP 拒绝。
- 已修正测试夹具：新增侧栏只读 POST 需要正确空分页响应，原宽泛 POST 计数不能代表消息发送。修正后生产模式浏览器 42/42 通过。
- 订单历史字段缺失、目录标题/券编码逐页过滤和优惠券买家资格不确定均在 UI/文档明示；退款禁用，券和商品仅进入草稿。

# 已验证与未验证内容

已验证本地合成路径、隔离数据库权限和现有 staging 渠道 Scope 布尔值。未验证新代码在 staging 的真实 TikTok 商品/券返回、实际部署和恢复；这些是独立部署任务的门禁。此审查由当前实施任务进行，不冒称独立人工审阅。

# 结论和返修条件

批准源码候选进入 PR 合并与后续 staging 手动发布。若现场目录 API 结构、Scope 或店铺隔离与契约不符，停止部署验收并在同一任务链中修复、重跑相关验证；production 保持 No-Go。
