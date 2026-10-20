---
record_id: IR-MVP-WORKSPACE-EXPERIENCE-001-20261020-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-EXPERIENCE-001
base_sha: d0ba04575407abdeddb66525467aaf9bf6f14621
final_sha: 1aff6dfd4302c64c9e1c7394f1ebd9898b3652c4
requirement_ids: [MVP-WORKSPACE-EXPERIENCE-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-EXPERIENCE-001-20261020-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-EXPERIENCE-001-20261020-R01.md
created_at: 2026-10-20T04:44:37Z
updated_at: 2026-10-20T05:10:04Z
supersedes: null
---

# 实施目标与范围

仅实现用户确认的工作台第 1、2 阶段：会话阅读、AI 草稿及 CRM 内部星标、指定坐席转交、关闭和重开。不扩大 TikTok 真实发送范围，不发布 staging 或 production。

# 实际变更及原因

- 列表展示逐会话未读数及星标，增加“星标”和“已关闭”筛选；相反的状态参数不能使已关闭筛选返回活跃会话。打开会话定位最新消息；阅读历史时保留视口，新消息不抢滚动，一键回到最新并标记已读。
- AI 安全建议填入空的会话专属可编辑草稿；已有人工草稿保留。建议不会自动发送，真实消息仍按人工确认和原有发送边界处理。
- 后端新增本地星标、关闭和重开操作及同店在职回复坐席列表。指定转交目标在工具调用前校验同店和回复权限，转交时重新锁定会话；关闭前检查未结清出站消息。
- Webhook 和只读同步仅在真实买家消息晚于关闭时间时恢复本地会话；只读同步补入上次成功同步后的买家新消息会增加未读，首次历史回填不制造旧消息未读。已关闭会话在工作台、服务和工具层均不能发送。

# 关键决定与偏差

星标表示 CRM 内部差评风险；关闭只改变 CRM 会话状态，不调用 TikTok Seller Center 关闭接口。未要求新买家测试、外部消息或自动回复。验收以合成浏览器数据和隔离 PostgreSQL 为准，不宣称 staging 已上线。

# 数据、配置、接口、迁移或 Prompt 影响

可回滚迁移 `025_workspace_actions` 为 `conversations` 增加 `is_starred` 和 UTC `closed_at`。`/workspace/sessions` 增加 `starred`、`closed` 过滤和响应字段；新增 `/star`、`/closed`、`/assignees`。无新运行配置、模型或 Prompt 变化。公共契约已同步 `docs/architecture/API.md` 与 `docs/architecture/SYSTEM.md`。

# 验证交接

完整命令、结果、跳过项及证据范围见关联 TR；权限、租户、并发和迁移风险见关联 RR。源码 PR #463 squash 合入后的功能 subject 为上述精确提交；合并前候选 `eaef1e59b437ed2bfbc62ac8da2d072d2ee45165` 与合并 SHA 的文件树 diff 为空。后续仅写证据和状态记录。

# 限制、风险与回滚

本次未部署，真实 TikTok 端到端交互和 staging 迁移仍未现场验收。回滚代码可恢复旧界面/API；迁移的 downgrade 会删除星标及关闭时间数据，实际部署后回退前须先备份并按发布门禁审查，不自动执行。
