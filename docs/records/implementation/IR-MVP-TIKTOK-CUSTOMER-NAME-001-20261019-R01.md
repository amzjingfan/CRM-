---
record_id: IR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-TIKTOK-CUSTOMER-NAME-001
base_sha: 5e65ba37d1476d62ca444b9050e403e48e797720
final_sha: f48779af3779ef7804703feb1c6f1ff4755bbe36
requirement_ids: [MVP-TIKTOK-CUSTOMER-NAME-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R01.md
review_record: docs/reports/reviews/RR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R01.md
created_at: 2026-10-19T09:35:00+08:00
updated_at: 2026-10-19T09:35:00+08:00
supersedes: null
---

# 实施目标与原因

用户发现原已显示昵称的真实 TikTok 会话短暂变成“匿名客户”。已登录 staging 工作台随后恢复原昵称。只读数据库核对显示该会话成功处理的 3 条新消息 Webhook 均缺少 `sender.nickname`；Webhook 客户 upsert 原先无条件把 `None` 写入 `customers.name`，定时会话同步随后重新写入昵称。

# 实际变更

[PR #412](https://github.com/CP11-gh/CRM/pull/412) 已 squash 合入 `main=f48779af3779ef7804703feb1c6f1ff4755bbe36`。仅在标准化通知实际提供名称时更新现有客户名称；缺失名称保留店铺内已有值。补充缺失昵称与新昵称两条行为回归，并在 `docs/architecture/SYSTEM.md` 记录此同步契约。

# 边界与交接

没有修改 API、迁移、权限、消息正文、人工发送、自动回复或生产配置，也没有外发消息。当前 staging 仍运行原后端镜像，该源码修复尚未部署；G5 正使用共享 staging 执行独立手动窗口，先待其恢复并复核最终镜像，再决定本任务的手动部署。回滚代码使用受审 `git revert`，运行镜像恢复已核对的旧摘要。验证和残余风险见 TR/RR。
