---
record_id: IR-MVP-WORKSPACE-TRANSLATION-RESTORE-001-20261031-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-TRANSLATION-RESTORE-001
base_sha: 8ea30f55edec14b864d656d40e569cba37190ac8
final_sha: 1e7e15fba356877876e71f7d70cafcd1235d571e
requirement_ids: [MVP-WORKSPACE-TRANSLATION-RESTORE-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-TRANSLATION-RESTORE-001-20261031-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-TRANSLATION-RESTORE-001-20261031-R01.md
created_at: 2026-10-31T00:07:06Z
updated_at: 2026-10-31T00:07:06Z
supersedes: null
---

# 实施目标与范围

恢复 staging 工作台已有的单条英文消息翻译入口，并保持现有镜像、两店人工发送及全部安全开关。

# 实际变更及原因

后端运行态 WORKSPACE_MESSAGE_TRANSLATION_ENABLED=false 使会话详情返回 translation_enabled=false，前端因此隐藏文字消息翻译按钮。消息翻译代码和接口仍在。用现有受审源码与不可变镜像运行手动 staging 门禁，显式增加 -EnableWorkspaceTranslation，让固定翻译 overlay 将后端开关恢复为 true。仓库交付说明补充切换前后核对要求；文档 subject 为 1e7e15fb，运行镜像 revision 见发布证据。

# 关键决定与偏差

本次是运行配置恢复，没有重建或变更产品镜像。首次正式部署未到切换阶段：远端 PowerShell 确认参数传递失败；修正后 GHCR 私有镜像拉取拒绝。临时使用已登录账号的包读取权限拉取同一精确摘要，门禁成功后立即退出服务器 GHCR 登录。先前失败尝试不计为通过。

# 数据、配置、接口、迁移或 Prompt 影响

只在 staging 后端启用工作台翻译；数据库迁移仍为 046_merge_templates_dispatch，接口形状、数据、Prompt 与模型均未改。Webhook 读取、两店人工真实发送、Agent 调试和正式建议维持；自动回复、营销、高风险 TikTok 写入及 G5 SSE 关闭。

# 验证交接

私有环境、PostgreSQL custom dump 和 MinIO 归档完成并验证可读；当前/候选双 ValidateOnly、Deploy、镜像摘要、运行开关、迁移和三公网健康均通过。已登录工作台 AX 树中买家与客服的英文文字消息重新出现“译成中文”。精确摘要及门禁原件 SHA 见 TR 和 release/evidence/staging/crm-staging-workspace-translation-restore-20261031.json。

# 限制、风险与回滚

没有触发真实 DeepSeek 翻译调用，因此验证的是入口回显和配置门禁，不宣称当次供应商译文成功。若需停止翻译，按受审门禁去掉该 overlay 并双预检；回滚不得覆盖部署后的业务数据增量。production 不变。
