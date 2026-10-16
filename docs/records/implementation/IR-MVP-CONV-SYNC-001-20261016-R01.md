---
record_id: IR-MVP-CONV-SYNC-001-20261016-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-CONV-SYNC-001
base_sha: 1950a0b26ddd28fda14679eaef82fd785ca20113
final_sha: 9c9e805f25fee45d51dbd0e96a60a07baab8b326
requirement_ids: [MVP-CONV-SYNC-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-CONV-SYNC-001-20261016-R01.md
review_record: docs/reports/reviews/RR-MVP-CONV-SYNC-001-20261016-R01.md
created_at: 2026-10-16T17:54:00+08:00
updated_at: 2026-10-16T17:54:00+08:00
supersedes: null
---

# 授权客服会话同步到工作台

用户要求让真实 TikTok Shop 会话及完整历史显示在 CRM。实现使用现有 TikTok 只读客户端和 PostgreSQL 会话、消息表：已授权且连接中的渠道逐页读取会话与消息，按平台 ID 幂等写入，并记录最新消息 ID 供下一轮跳过未变化会话。单店失败回滚当前事务，已提交页可在下一轮续跑；现有 Webhook Worker 用独立数据库会话调度同步，保留事件认领能力。

工作台继续使用已有店铺授权查询，初次打开取得最新消息页并可加载更早历史；买家、客服、机器人、系统显示不同身份。staging 只读叠加文件仅为 worker 开启同步，默认及 production Compose 固定关闭；真实普通消息发送、自动回复、高风险写入仍关闭。没有数据库迁移或公开新 API。

源码和测试候选为 `9c9e805f25fee45d51dbd0e96a60a07baab8b326`，PR #248。staging 镜像发布、回填、现场工作台和真实双向消息状态由后续现场记录补充；本记录不把本地集成测试当作现场验收。
