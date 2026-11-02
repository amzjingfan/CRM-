---
record_id: IR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001
base_sha: 85a6892929e9f28fdcfc103e85a20364633cabd1
final_sha: 248fc487a07388ac7392339bfc262459e4ac7596
requirement_ids: [MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R01.md
review_record: null
created_at: 2026-11-02T12:07:15+08:00
updated_at: 2026-11-02T12:07:15+08:00
supersedes: null
---

# 实施目标与范围

统一全部店铺工作台的订单完成标签、物流阶段、实际承运商及通用轨迹的错误提示。只改前端只读展示，不改官方 API、权限、数据库、买家发送或退款。

# 实际变更及原因

- 新增 `src/frontend/lib/order-display.ts`，集中映射订单状态、独立物流阶段、轨迹描述与实际承运商。订单 `DELIVERED`/`COMPLETED` 在卡片、详情关联摘要和原生订单草稿统一显示“已完成”；包裹 `DELIVERED` 仍显示“已送达”。明确物流状态优先于订单物流阶段，完成订单本身不推断包裹已送达。
- `Collections by TikTok` 属于平台揽收方式，不能冒充实际承运商。订单实际承运商按匹配包裹 ID/运单号取值；多个相关包裹承运商不同显示“多家物流商”，无法确认时显示 `—`。
- 增强轨迹成功后将包裹承运商及不旧于通用轨迹的最新节点映射回当前订单卡和详情，并保持该节点可翻译。通用轨迹已有节点时增强读取失败不显示整笔物流失败；通用与增强均无节点时保留错误。
- 订单草稿预览与侧栏共用订单状态映射；补充确定性契约及合成浏览器回归。同步产品与架构当前事实。

# 关键决定与偏差

本次不从 `COMPLETED` 单独推断物流已送达；只有独立物流状态、明确的 `DELIVERED` 订单物流阶段或可识别的官方物流描述可得出包裹送达。增强结果保留在当前订单卡视图，不持久化，也不重新触发增强读取。

# 数据、配置、接口、迁移或 Prompt 影响

无数据结构、接口形状、配置、迁移、Prompt 与发送能力变化。订单 UI 和只读物流弹层的展示语义改变。

# 验证交接

最终 subject `248fc487a07388ac7392339bfc262459e4ac7596` 上契约 80/80、工作台合成浏览器 65/65、typecheck、lint 0 错误和生产构建通过，详见 TR。RR=N/A：仅前端只读展示，未触及权限、敏感数据或公共 API。

# 限制、风险与回滚

合成浏览器响应不代表每家真实店铺的官方字段都已现场证实。平台未返回可确认的实际承运商时明确留空。回滚此 subject 或其前端精确镜像可恢复旧展示；无数据库回滚动作。
