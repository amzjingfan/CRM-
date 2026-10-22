---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001-20261022-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001
base_sha: b0870fb0ab33a8fea5b7b8d91b8b0dc39bce4814
final_sha: f512fb8a8a52ed4139a5f94a431752b5f65715d0
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001-20261022-R01.md
review_record: N/A
created_at: 2026-10-22T04:48:20Z
updated_at: 2026-10-22T04:48:20Z
---

# 现象和原因

用户在 staging 订单卡看到“SKU 货号：…”；合成订单返回完整卖家 SKU，浏览器 DOM 也有完整值，但可见文本的 `scrollWidth` 大于 `clientWidth`。订单商品行的通用 `small` 与复制值均使用单行省略样式，右侧固定价格进一步压缩可用宽度。此前仅商品规格行有换行例外，卖家 SKU 行仍被截断。

# 变更与边界

- 订单卡的卖家 SKU 行沿用商品规格行的窄侧栏换行和小型复制控件布局，名称、SPU、SKU ID 及价格保留原排版。
- 平台未返回卖家 SKU 时仍不显示该行，不用其他标识伪造货号。
- 合成浏览器用长货号先复现截断，再核对完整显示、复制的原始值与按钮在行内；产品说明同步。

仅前端样式和对应组件标记变化，无接口、权限、迁移、配置、模型或外部写入变化。staging 与 production 发布状态以正式 TR 和发布证据为准。
