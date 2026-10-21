---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-VARIANT-001-20261021-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-VARIANT-001
base_sha: 8830d6c88ef18eea36985bc81e7816ff702005ad
final_sha: 64aefa1206497c9bf2d003b9698a3e906e78e185
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-VARIANT-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-VARIANT-001-20261021-R01.md
review_record: N/A
created_at: 2026-10-21T11:10:49Z
updated_at: 2026-10-21T11:10:49Z
---

# 实施目标与原因

用户在 staging 订单卡截图中看到“商品规格：…”且部分订单正常显示。订单投影已把 TikTok `sku_name` 传到前端；卡片的商品字段与复制值同时使用 `white-space: nowrap`、`overflow: hidden` 和省略号，右侧固定宽度价格挤压长规格，所以数据存在但文字被截断。

# 实际变更

- 仅让订单卡的商品规格行在窄侧栏内换行，并保留小型复制按钮；商品名称及其他字段原有布局不变。
- 平台未返回规格时仍显示“—”，不把 SKU ID 或卖家 SKU 当成商品规格。
- 新增合成浏览器长规格溢出回归与无规格回归；更新当前产品范围说明。源码 subject `64aefa12` 经 [PR #498](https://github.com/CP11-gh/CRM/pull/498) squash 合入 `main=5e11f7b6eb3381b57869db5daf6abcbdfbe193a9`，受影响源码树比较无差异。

# 数据、安全与发布边界

无接口、权限、数据结构、迁移、配置、Prompt 或 TikTok 写入变化。后端镜像仅以同一合入 SHA 重建，后端业务内容未变化。staging 从干净主线源码手动部署；旧镜像和私有 `0600` 数据库备份保留可回滚。未发送买家消息、退款或发布 production。

# 验证与恢复

复现、最终源码检查、staging 门禁及运行摘要见对应 TR 和[低敏部署证据](../../../release/evidence/staging/crm-staging-customer-sidebar-variant-20261021.json)。恢复需使用该证据中的旧三摘要及 staging 私有备份，并重新运行受审恢复门禁。Production G8 保持 No-Go。
