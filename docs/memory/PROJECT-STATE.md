# 项目状态与恢复入口

2026-10-30；治理档位 STANDARD；TikTok 人工辅助；CP11-gh/CRM；origin/main；证据分支 feature/all-store-manual-send-20261030，`CANDIDATE_SUBJECT_SHA=18a0d7bb0b0ca6b2bb601de32af7128d1a41a9ec`，`EVIDENCE_HEAD_SHA=READ_AT_GATE`；任务状态以 [TASKS](../tasks/TASKS.md) 为准。staging 从干净合并主线 `18a0d7bb` 的同版不可变镜像手动扩展人工发送至两家已授权 TikTok 店铺，迁移头 `044_reception_assignment`。精确镜像、私有备份、ValidateOnly/Deploy、12 容器、固定出口、三健康及只读发送模式见 [全店人工发送证据](../../release/evidence/staging/crm-staging-all-store-manual-send-20261030.json)和 [TR R01](../reports/tests/TR-MVP-TIKTOK-ALL-STORE-MANUAL-SEND-001-20261030-R01.md)。任务待证据合并收尾，production 未发布。

此前部门接待与派单从干净主线 `b21f59a76adce8775eb5f9d61993e3b42886d72a` 发布，部门现场与清理事实见[部门发布证据](../../release/evidence/staging/crm-staging-department-assignment-20261030.json)和[TR R02](../reports/tests/TR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R02.md)。PR #654/#655 已合入主线；全店人工发送由后续独立发布扩展。

本轮发布记录 PR #656 已合入主线 `3a97bf4371ec58ba088005a1dd673f1b7a17f0a8`；IR/TR/RR 三项源记录从合并主线复核并更新索引为 `CURRENT`。PR 的两项 CI 在零步骤时失败，按持续批准的本地替代门禁处理，不记为 CI 通过。

主线 PR #652/#653 的授权单入口源码现已包含于当前 staging 镜像：授权页旧卡片与全局入口移除，异常店铺行内重新授权绑定自身 store_id；功能测试见[授权 TR R01](../reports/tests/TR-MVP-TIKTOK-OAUTH-UX-001-20261030-R01.md)，独立发布核对见[OAuth 现场证据](../../release/evidence/staging/crm-staging-oauth-single-entry-20261030.json)。模板与批量差异更新仅有[设计提案](../superpowers/specs/2026-10-30-agent-templates-batch-design.md)，尚未实施。

用户指定的 staging 清理已完成：只保留一个系统管理员和「TikTok US 测试店铺」「测试店铺」「XBM」，删除 50 个合成账号及 2 家合成店铺；清理前私有数据库备份、审计、提交后对账及恢复限制见 [CLEANUP-20261030-001](../operations/cleanup/CLEANUP-20261030-001.md)。MinIO 对象未删，未做整库恢复演练。

当前逐店自动派单配置为 0，默认关闭；人工真实发送 allowlist 为「TikTok US 测试店铺」与「XBM」，未接入 TikTok 的「测试店铺」失败关闭。自动回复、自动营销、主动物流通知、高风险平台写入保持关闭；Agent 调试及正式人工建议维持，测试未向真实买家发送消息。在「测试店铺」短暂建立合成两坐席的并发派单与幂等验证已通过，测试账号、配置、咨询及审计清理为 0；真实 TikTok 入站仍未演练。

此前 Agent 回复现场验收见 [TR R01](../reports/tests/TR-MVP-AGENT-REPLY-STAGING-001-20261030-R01.md)；模板与批量差异更新仅为 [设计提案](../superpowers/specs/2026-10-30-agent-templates-batch-design.md)，尚未实施。GitHub Actions 零步骤作业不计通过，按持续批准的本地替代门禁处理。G8 production 仍 No-Go。

Workspace hygiene: ATTENTION。主 checkout 的未知历史、活动 worktree 和未跟踪 `src/frontend/AGENTS.md` 保留；此前对此文件的移除操作被自动批准审查拒绝，本轮未重试。本次仅清理用户精确指定的 staging 账号与店铺，未清理本地未知文件。

下一动作：①合并全店人工发送证据并将任务标记 DONE；②如需证明真实授权体验，在已登录测试店铺执行 OAuth 回跳与多店选择；③若准备常态启用自动派单，在受控平台会话补测真实入站。
