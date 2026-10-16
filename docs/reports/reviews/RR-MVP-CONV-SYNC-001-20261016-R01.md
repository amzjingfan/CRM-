---
record_id: RR-MVP-CONV-SYNC-001-20261016-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-CONV-SYNC-001
reviewed_sha: 9c9e805f25fee45d51dbd0e96a60a07baab8b326
implementation_record: docs/records/implementation/IR-MVP-CONV-SYNC-001-20261016-R01.md
test_record: docs/reports/tests/TR-MVP-CONV-SYNC-001-20261016-R01.md
review_focus: [tenant-isolation, idempotency, read-only-api, sensitive-logging, deployment-switches, recovery]
created_at: 2026-10-16T17:54:00+08:00
updated_at: 2026-10-16T17:54:00+08:00
supersedes: null
---

# 代码与部署边界复核

同步仅选择 connected TikTok 渠道和客服 Scope；客户/会话按内部店铺映射，消息平台 ID 冲突时拒绝跨店铺或跨会话归属。平台游标重复、身份缺失和未知角色失败关闭；消息正文不进入同步日志或命令输出。逐页提交支持中断重跑，渠道之间使用独立回滚后的 ORM 加载。历史读取使用 GET，不调用标记已读或发送端点。

默认与 production Compose 固定关闭同步，staging 仅 worker 显式启用；现有真实写入、自动回复和高风险能力仍关闭。门禁测试检查四个应用进程与回滚契约。Webhook 与后台同步可能在同一买家首次入站时竞争创建记录；现有会话/消息唯一约束会使一方回滚并按原重试机制恢复，现场需观察错误计数。该残余风险不扩大店铺权限或平台写入。

审查结论：批准此 staging 只读候选进入 CI 和现场验收；不等于批准向买家发消息、生产发布或关闭 G2/G3 门禁。
