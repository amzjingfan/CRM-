---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-ORDERS-001-20261021-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-ORDERS-001
base_sha: db916cfda6768040f105fc940685fbfc018c7fd4
final_sha: 6f8f6c05e8668e71d785e31e152d51b96d2bf6cf
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-ORDERS-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-ORDERS-001-20261021-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-ORDERS-001-20261021-R01.md
created_at: 2026-10-20T16:20:00Z
updated_at: 2026-10-20T16:20:00Z
supersedes: null
---

# 目标与原因

已合并侧栏在 staging 返回真实商品 27 件、优惠券 19 张，但本地订单投影 0 笔。官方只读单会话参与者身份与订单搜索现场核对表明，已知买家的 IM ID 与 CRM 一致，其订单域 `user_id` 可检索到 1 笔有商品、金额和物流字段的真实订单。原侧栏只查本地投影，因此显示为空。

# 变更

- TikTok 真实读取模式下，先按当前会话的授权店铺取得渠道，再读官方 202601 单会话，核对唯一买家 IM ID；使用该买家的订单域 `user_id` 调用官方 202309 订单搜索，逐条核对返回订单身份。其他模式保持原投影查询。
- 对订单状态和六种字段做全量已取页过滤，最多读取 20 页、2000 笔；身份、游标、重复订单、上限或金额结构异常均失败关闭。平台缺失的金额返回 `null`，界面显示横线，不补造 0。
- 无数据库迁移、新 Scope、真实写入、优惠券发放或退款。产品、接口和架构当前文档已同步。

# 回滚与限制

源码回滚到合并前版本可恢复原本地投影路径；staging 回滚必须保留发布后消息，不能直接用旧数据库备份覆盖。单买家超过 2000 笔订单时明确报错，后续可改为服务端游标设计。生产 G8 No-Go 不变。
