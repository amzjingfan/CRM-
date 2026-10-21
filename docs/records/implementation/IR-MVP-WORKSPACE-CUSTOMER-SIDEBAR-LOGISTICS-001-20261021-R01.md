---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001-20261021-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001
base_sha: 15ceabf8eac90f2fe8c7843e24af26381c3e0499
final_sha: 6e1f2489007b085b5a02d0aff2df6f4d2f86c44e
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001-20261021-R01.md
review_record: null
created_at: 2026-10-21T03:09:31Z
updated_at: 2026-10-21T03:09:31Z
supersedes: null
---

# 实施目标与范围

修复真实订单卡片需手动点“详情”才出现物流字段的问题，使参考图中的可取得字段直接显示在可见卡片上。本记录只涵盖前端源码；staging 发布与现场验收另行留证。

# 实际变更及原因

- 通过 `IntersectionObserver` 仅对进入可见区域的真实订单卡片读取一次既有受权订单详情；屏外订单不同时请求。原“详情”按钮保留为失败重试或主动刷新入口，正在请求时去重。
- 真实已付款订单的官方 `payment.total_amount` 标为“买家实付金额”；未付款与本地同步订单保持各自金额标签。物流阶段优先使用已有独立状态；不存在时仅从 `IN_TRANSIT`、`SHIPPED`、`DELIVERED` 映射，不将 `COMPLETED` 推断为已送达。
- 运送中及已送达卡片固定展示物流状态、单号、承运商、最新物流描述和时间六项所需行；第三方没有返回的值显示空占位，不造“待派送”或其他轨迹节点。

# 关键决定与偏差

参考图中的“待派送”不是当前通用轨迹响应的稳定独立状态，故仅展示平台明确提供的粗粒度物流阶段与原始轨迹描述。自动读取沿用原服务端的会话、店铺、官方买家 ID 核对和 CSRF 边界；没有增设公开接口。

# 数据、配置、接口、迁移或 Prompt 影响

没有数据库、API 结构、配置、Scope、模型或平台写入变化。前端对可见真实订单增加一次现有只读详情请求，需关注平台限流与权限错误；失败可见并可手动重试。

# 验证交接

本地红绿浏览器复现、静态检查、契约及生产构建见对应 TR。从合入 `main` 的精确源码手动构建并发布 staging 后，需在已授权会话只读核对至少一张有物流轨迹的订单卡，不触发退款、发券或买家消息。

# 限制、风险与回滚

详细“待派送”若没有官方结构化状态仍不会显示；完整订单状态与真实轨迹可能不同。staging 出现回归时按部署前快照恢复前端旧不可变摘要，保留部署后业务数据，不用旧数据库备份覆盖消息。
