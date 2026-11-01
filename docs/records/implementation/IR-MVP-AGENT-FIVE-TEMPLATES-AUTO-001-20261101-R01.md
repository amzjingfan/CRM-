---
record_id: IR-MVP-AGENT-FIVE-TEMPLATES-AUTO-001-20261101-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-AGENT-FIVE-TEMPLATES-AUTO-001
base_sha: 59233e0f880cab1750b9f8868e655dfb1fd466f5
final_sha: ad9a9c9c1ea76970835fd255f768c30ebf5ba7c8
requirement_ids: [MVP-AGENT-FIVE-TEMPLATES-AUTO-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-AGENT-FIVE-TEMPLATES-AUTO-001-20261101-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-FIVE-TEMPLATES-AUTO-001-20261101-R01.md
created_at: 2026-11-01T14:07:14Z
updated_at: 2026-11-01T14:07:14Z
supersedes: null
---

# 实施目标与范围

保留订单物流模板，新增售前商品、售后商品、物流状态更新和回复兜底四个共享模板；店铺分别应用并绑定本店知识。实现店铺级多 Agent 自动回复**待审阅预演**、有货商品筛选与按买家语言的固定第三轮兜底。真实自动发送继续关闭。

# 实际变更及原因

- 四个新模板以七段式提示词、原生 function call 工具白名单和知识槽位发布为 v1；原订单物流模板没有重建或覆盖。
- 商品搜索、详情与工作台目录统一只展示上架且有正库存 SKU；缺库存不判断为有货。
- 常规咨询先由模型路由至业务 Agent；物流更新只接收已核实新节点事件；连续两轮无业务答案后第三轮采用买家语言的固定礼貌话术。业务问题成功后计数清零。
- 店铺预演开关采用权限、CSRF、乐观锁、审计及幂等入队，持久化待审阅建议；预演不经过平台外发路径。新增 049 迁移与 staging 作业配置。
- 前端提供模板说明、预演开关及工作台审阅状态；接口、AI、架构、产品、部署和测试文档随源码同步。

# 关键决定与偏差

物流事件和兜底 Agent 有专用触发条件，不因普通问题强制参与。现场测试店无本地订单和可核实新物流节点；以隔离 PostgreSQL 事件/预演/零外发测试补充。三条真实入站均得到业务答案，因此没有人为制造第三轮无解；中英固定话术由隔离行为测试验证。

# 数据、配置、接口、迁移或 Prompt 影响

新增 `049_agent_auto_reply_preview`，`/v1/agents/auto-reply-preview` 与只读预演流程。自动回复全局真实发送门禁仍关闭，人工发送原授权范围不变。模板不存店铺知识文件或买家信息；测试文件仅在授权店铺独立导入、审批、绑定，验收后软删除。

# 验证交接

本地全量、独立数据库、前端构建与生产浏览器、staging 手动部署和已授权真实只读建议见 TR 及[低敏机器证据](../../../release/evidence/staging/crm-staging-five-agents-20261031.json)。产品 PR #704 已合并；本文件只记录已合并 subject 的验收事实。

# 限制、风险与回滚

staging 浏览器控制持续超时，已登录 UI 视觉核对标记 `UI_UNAVAILABLE`；正式认证 API 与本地生产浏览器测试不能冒称现场 UI 验收。真实物流事件、第三轮无解和 TikTok 买家端自动发送均未现场触发。回滚使用发布前私有备份及精确镜像，049 迁移保留；不回滚测试期间的真实业务增量。production 继续 No-Go。
