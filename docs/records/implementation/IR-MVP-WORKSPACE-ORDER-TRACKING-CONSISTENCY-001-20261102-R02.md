---
record_id: IR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001
base_sha: e8016604ea10e36f63e16e737415f38461c1d4a6
final_sha: b98b955b962df638d9a899fc17c2396cbcb2ad54
requirement_ids: [MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001]
acceptance_ids: [AC-03, AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R03.md
review_record: null
created_at: 2026-11-02T18:28:37+08:00
updated_at: 2026-11-02T18:28:37+08:00
supersedes: docs/records/implementation/IR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R01.md
---

# 实施目标与范围

修复可见订单卡片在物流详情打开前缺少实际承运商的问题。所有后续绑定的 TikTok 店铺共用现有订单服务和展示规则，不按店铺名称分叉。只改变前端只读加载时机与视图同步；不改发送、退款、权限、数据库或官方 API 契约。

# 实际变更及原因

- 根因是卡片预取订单详情及通用物流后便停止；跨境订单的 `shipping_provider` 可能是平台揽收方式，通用轨迹没有实际承运商，增强多包裹接口原先只在打开弹窗后调用。
- 新增共享的 `shouldResolveEnhancedCarrier` 规则：仅对已进入物流阶段或有运单、实际承运商仍未知、且当前店铺有增强轨迹资格的订单，在卡片进入视口并取得通用轨迹后尝试增强读取。已有 USPS 等实际承运商的订单不增加自动调用；没有增强资格的店铺保持通用读取。
- 详情提前打开时复用相同判断；卡片、详情与弹窗通过前端单飞请求共用同一进行中的增强读取。弹窗接受预取结果并保留增强翻译来源，避免同步回卡片时重置为通用轨迹。平台八小时每单占位与缓存仍由原后端控制。
- 增强接口失败或未给承运商时保留未知值及通用轨迹；不把 `Collections by TikTok` 冒充真实物流商。商品、订单及轨迹仍按现有店铺与买家授权核验读取。

# 关键决定与偏差

预取限制在可见订单、承运商未知且有增强资格的情形，避免对所有历史订单或已有实际承运商的订单发出额外请求。按店铺 `seller_type` 判断增强资格是当前通用产品规则，不是针对 XBM 的特例。

# 数据、配置、接口、迁移或 Prompt 影响

无响应形状、配置、迁移或 Prompt 变化。只读增强接口被提前按需调用，真实调用次数可能增加；既有店铺隔离、平台冷却与失败关闭保持。

# 验证交接

subject `b98b955b962df638d9a899fc17c2396cbcb2ad54` 上生产构建、类型、lint、81 项契约与 68 项工作台生产模式浏览器测试通过，详见 TR R03。RR=N/A：前端只读加载时机，不修改权限、公共 API 或高风险写入。现场 staging 与内置浏览器验收继续记录在后续 TR。

# 限制、风险与回滚

官方未返回实际承运商或增强接口在八小时冷却中时仍显示 `—`；合成响应不代替全部真实店铺验收。回滚前端精确镜像可恢复原请求时机；无数据库回滚。
