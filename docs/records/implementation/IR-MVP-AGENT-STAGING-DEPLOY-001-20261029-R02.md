---
record_id: IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-AGENT-STAGING-DEPLOY-001
base_sha: f76262e48be8bd990f0d73f70b4f8b26fc46b429
final_sha: 00bc04a1ea8c6b23279ef95f8add8d9089a67a6c
requirement_ids: [MVP-AGENT-STAGING-DEPLOY-001]
acceptance_ids: [AC-01, AC-02]
test_record: docs/reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R02.md
review_record: docs/reports/reviews/RR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R02.md
created_at: 2026-10-29T09:36:00+08:00
updated_at: 2026-10-29T09:36:00+08:00
supersedes: docs/records/implementation/IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R01.md
---

# 组合源与执行边界

纳入已合并多店授权 PR #629 和仅状态收尾 PR #630；任务表冲突同时保留独立部署任务和主线多店授权 DONE。唯一迁移头为 `041_merge_agent_multishop_collab`。部署补齐仍只改变默认/调试覆盖层与已有门禁，不改变多店授权、Agent、前端或模型适配代码。

`00bc04a1` 的后端、前端、Docker、Compose、脚本和测试树与本次完整受影响回归的 `0330e9f4` 一致；两者之间仅合入 #630 状态文档。应用构建输入继续与多店授权完整受测源一致，测试复用边界见 TR。

# 已完成与待执行

组合源重新运行 180 项部署回归通过。现网环境、PostgreSQL 可读备份、MinIO 可读归档、原容器配置和镜像快照已经保存在私有恢复点；没有切换服务或迁移。现有 DeepSeek 配置的纯合成原生工具两轮协议预检通过，未传业务数据或发送平台消息。后续由本执行者从合并主线构建不可变镜像，核对备份、精确摘要、ValidateOnly、Deploy、041、健康和业务模式，再做现场验收；本记录不表示部署完成。
