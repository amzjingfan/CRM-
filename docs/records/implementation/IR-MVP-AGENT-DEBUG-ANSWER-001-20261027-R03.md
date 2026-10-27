---
record_id: IR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R03
record_type: implementation
revision: R03
status: FINAL
task_id: MVP-AGENT-DEBUG-ANSWER-001
base_sha: c130326d00314f9cde9ae466534aa1421465bbb8
final_sha: d0a2e6e4cd1ab62892d3b0d8e6f6a3dc021a07ff
requirement_ids: [MVP-AGENT-DEBUG-ANSWER-001]
acceptance_ids: [AC-01, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R03.md
review_record: docs/reports/reviews/RR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R03.md
created_at: 2026-10-27T11:11:00Z
updated_at: 2026-10-27T11:11:00Z
supersedes: docs/records/implementation/IR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R02.md
---

# 目标与现场根因

R02 合入 main 并手动部署 staging 后，已登录浏览器的 TikTok US 测试店铺使用授权会话调试物流问题。trace `c1c5aba9-adb2-4b3e-af32-d6a49cf1a204` 的 `query_logistics` 成功，但工具摘要 `tracking_status=null`，页面仍显示系统固定提示。工作台同一买家的订单卡通过 TikTok 详情及通用轨迹已显示“已送达”和最新轨迹。Agent 调试先前仅取已核验买家的订单列表投影，未读取独立物流轨迹。

# 实际变更

- TikTok 会话的订单/物流调试优先使用当次已核验的平台订单，即使本地存在旧订单也不以旧快照覆盖平台事实。
- 物流问题在同一 45 秒调试截止时间内调用既有工作台订单详情路径，复用店铺权限、会话买家和订单买家双重核验，以及官方 `202309` 通用轨迹读取。
- 只把最新轨迹描述、时间及明确可识别阶段投影给 `query_logistics`。订单状态不冒充物流状态，平台无轨迹或描述不能识别时阶段仍为空。收件地址不进入工具结果；原始轨迹和物流号不写工具审计摘要。
- 扩展内部只读工具结果的可选轨迹字段；不改 HTTP 请求/响应、迁移、配置或前端。Agent 仍只显示坐席复核建议，零平台消息。

# 验证、限制与回滚

红灯测试先证明旧实现不调用详情且没有轨迹字段；绿灯测试涵盖有无本地订单、已核验轨迹阶段、未知阶段及摘要脱敏。最终源码的隔离数据库全套、静态检查见 R03 TR。真实 TikTok 和 DeepSeek 功能仍须在 staging 复测；若失败，保留 R02 后端镜像摘要 `sha256:e9327aeb4d9526e69cd46a37c154f395fb1235e1d0a95273b0d3f0c2f500e0b0` 作为回滚点。production 不发布。
