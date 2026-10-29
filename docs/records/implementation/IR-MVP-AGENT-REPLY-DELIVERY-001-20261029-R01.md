---
record_id: IR-MVP-AGENT-REPLY-DELIVERY-001-20261029-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-AGENT-REPLY-DELIVERY-001
final_sha: b3ce00a35bda8a1504f7f56cb4d910bc0fa0b865
created_at: '2026-10-29T15:47:50+00:00'
updated_at: '2026-10-29T15:47:50+00:00'
supersedes: null
base_sha: c7ba0f4c2ce725b9e7672ce24db73f60b235f4af
test_record: docs/reports/tests/TR-MVP-AGENT-REPLY-DELIVERY-001-20261029-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-REPLY-DELIVERY-001-20261029-R01.md
requirement_ids:
- MVP-AGENT-REPLY-DELIVERY-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
- AC-04
- AC-05
---

# 范围与实际结果

实现原生SDK草稿流、原问题绑定的模型分段审阅、最新物流正文及文字后原生卡片、有序持久交付和新节点物流通知。没有部署、真实消息发送或开启通用自动回复。买家流式当前落为完整复核消息分段交付的审阅栏预演，不宣称TikTok原生同气泡Token追加。

# 关键决定

Provider保留原complete并新增complete_streaming，严格选取submit_reply_parts.texts；生成中草稿只供授权坐席看，取消/空结果/跨会话清理。每段独立依据及隐私复核，语言遵循原问题。物流默认latest，history仅内部核查，完整卡片只读核验后显示。审阅计划先文字后卡片；相同key冻结准确正文，各段写前unknown、完成attempt CAS，已成功文字不重发，可信零写入失败可重试，unknown只对账。

通知工具使用独立持久事件与授权，不伪造human_confirmed；双全局开关与店铺策略默认关闭/preview。首次基线、旧/重复/乱序跳过，每单至少八小时外部轮询并退避；pending本地恢复，reviewing十分钟租约/owner CAS，unknown仅对账。复用既有jobs/工具/适配器，不增服务。

# 接口、迁移与配置

Chat新增review_plan与draft/result附加字段；workspace新增物流卡片预览和reply-batches；agents新增通知策略/台账/手工预演。042/043共五新表，含复核lease字段；配置示例和PRODUCT/API/AI/SYSTEM/DEPLOYMENT同步。原人工文本、翻译、媒体、卡片及绑定文件RAG仍回归通过，未删除其他模块数据。

# 验证及恢复

最终候选完整验证、失败修复和既有数据库差异见TR；独立并发/授权审查见RR。回滚先关闭新增入口及通知策略并恢复受审镜像，不在有业务增量的环境盲目降库。043/042降级会删除新台账，只在明确批准且已有备份时执行。本轮往返仅隔离合成库。

