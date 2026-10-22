---
record_id: IR-MVP-SETTINGS-TIKTOK-STORES-001-20261022-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-SETTINGS-TIKTOK-STORES-001
base_sha: 83e8c605acdf7567017ca6b4ebac882188712b13
final_sha: 76767ed78682614e78ef66fedcd1284a43f2256f
requirement_ids: [MVP-SETTINGS-TIKTOK-STORES-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-SETTINGS-TIKTOK-STORES-001-20261022-R01.md
review_record: docs/reports/reviews/RR-MVP-SETTINGS-TIKTOK-STORES-001-20261022-R01.md
created_at: 2026-10-22T10:20:07Z
updated_at: 2026-10-22T10:20:07Z
supersedes: null
---

# 实施目标与范围

按用户原型将系统设置的店铺列表改为 TikTok 授权列表，展示名称、别名、平台与系统 ID、站点、状态及授权时间。Custom 应用的“添加店铺”直接跳转卖家授权；“重新添加”保留原平台店铺身份校验。用户确认“删除”保留内部店铺和历史数据。

# 实际变更及原因

新增仅系统管理员可发起的新店 OAuth 入口。授权成功且平台唯一店铺、Scope、Token 校验通过后，worker 在同一事务创建内部 Store 与 TikTok ChannelAccount；取消、失败及重复已连接店铺不建空店。手动删除仅销毁本地 Token 可用性、隐藏列表行并保留绑定，未来同一平台店铺复用系统 ID；平台侧解除授权仍在异常列表显示。列表支持状态筛选、名称/别名搜索、别名编辑、复制系统 ID 和删除二次确认。

独立安全审查指出授权时间可能早于 Refresh Token 到期、非 TikTok 内部店铺混入列表、手动删除后的晚到 Webhook、跨店铺角色借权四类风险；本提交分别修正时间投影与列表过滤、Webhook 入站及队列处理、目标店铺权限校验，并增加对应回归。

# 数据、接口、配置和迁移影响

迁移 `027_tiktok_direct_store_oauth` 将短期 OAuth job 的 `store_id` 改为可空并新增固定回跳页；存在未绑定店铺 job 时降级失败关闭。新增 POST 店铺 OAuth 与 PATCH 别名接口；渠道只读响应增加站点、授权期限、低敏状态及最近授权时间。平台授权期限与 Refresh Token 期限取更早者。未添加新密钥或扩大自动发送；真正撤销 TikTok 平台侧应用授权仍需卖家在平台操作，UI 明示此区别。

# 验证交接与限制

本地测试和审查见所链 TR/RR。staging 尚未部署或验证，任务保持 `VERIFYING`；发布只能使用合并后的受审主线，先核对不可变镜像、当前运行模式与私有备份，部署后核对迁移头 `027`。未发起真实卖家授权、未删除真实店铺、未向买家发送消息、未发布 production。旧版回退前须处理无店铺 OAuth job 并保护部署后的业务增量。
