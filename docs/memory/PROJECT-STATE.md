# 项目状态与恢复入口

2026-10-30；治理档位 STANDARD；TikTok 人工辅助；CP11-gh/CRM；origin/main；当前证据分支 docs/department-staging-evidence-20261030，`CANDIDATE_SUBJECT_SHA=b21f59a76adce8775eb5f9d61993e3b42886d72a`，`EVIDENCE_HEAD_SHA=READ_AT_GATE`；任务状态以 [TASKS](../tasks/TASKS.md) 为准。staging 已从干净合并主线 `b21f59a76adce8775eb5f9d61993e3b42886d72a` 手动更新前后端；包含 PR #646 部门接待与派单和已合并的 Agent 回复交付，数据库迁移头 `044_reception_assignment`。精确镜像、私有备份、ValidateOnly/Deploy、12 个容器、固定出口、三健康与已登录部门页见 [部门发布证据](../../release/evidence/staging/crm-staging-department-assignment-20261030.json)及 [TR R02](../reports/tests/TR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R02.md)。三索引为 `CANDIDATE_VIEW`，证据合入权威主线后重建为 `CURRENT`。production 未发布。

随后主线 PR #652/#653 已合入 TikTok 店铺授权单入口源码与证据；该改动晚于本次 staging 发布源码，尚未部署。授权页旧卡片与全局入口已移除，异常店铺行内重新授权绑定自身 store_id；其范围及验证见 [授权 TR R01](../reports/tests/TR-MVP-TIKTOK-OAUTH-UX-001-20261030-R01.md)。模板与批量差异更新仅有 [设计提案](../superpowers/specs/2026-10-30-agent-templates-batch-design.md)，尚未实施。

用户指定的 staging 清理已完成：只保留一个系统管理员和「TikTok US 测试店铺」「测试店铺」「XBM」，删除 50 个合成账号及 2 家合成店铺；清理前私有数据库备份、审计、提交后对账及恢复限制见 [CLEANUP-20261030-001](../operations/cleanup/CLEANUP-20261030-001.md)。MinIO 对象未删，未做整库恢复演练。

当前逐店自动派单配置为 0，默认关闭；原单店人工真实发送 allowlist 未扩大。自动回复、自动营销、主动物流通知、高风险平台写入保持关闭；Agent 调试及正式人工建议维持，测试未向真实买家发送消息。真实入站自动派单及多坐席现场竞争未演练。用户新增的全店人工真实发送要求已单列 [MVP-TIKTOK-ALL-STORE-MANUAL-SEND-001](../tasks/TASKS.md) 为 READY，须逐店核验渠道与权限后另行部署。

此前 Agent 回复现场验收见 [TR R01](../reports/tests/TR-MVP-AGENT-REPLY-STAGING-001-20261030-R01.md)；模板与批量差异更新仅为 [设计提案](../superpowers/specs/2026-10-30-agent-templates-batch-design.md)，尚未实施。GitHub Actions 零步骤作业不计通过，按持续批准的本地替代门禁处理。G8 production 仍 No-Go。

Workspace hygiene: ATTENTION。主 checkout 的未知历史、活动 worktree 和未跟踪 `src/frontend/AGENTS.md` 保留；此前对此文件的移除操作被自动批准审查拒绝，本轮未重试。本次仅清理用户精确指定的 staging 账号与店铺，未清理本地未知文件。

下一动作：①按独立任务核验并实施全部已授权店铺的人工发送，保持自动发送关闭；②若用户要求查看单入口授权 UI，再单独发布其源码到 staging；③若准备启用自动派单，在合成或受控环境补测真实入站与多坐席竞争。
