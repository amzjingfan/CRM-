# 项目状态与恢复入口

2026-10-30；STANDARD；TikTok 人工辅助；CP11-gh/CRM；目标主线 `origin/main=d6f8974624f64b8bec30d47f33b4a79b3f42d21d`，当前分支 `feature/department-assignment-20261029`。本任务 CANDIDATE_SUBJECT_SHA=`dcc2ada1eb3290c64857b4b5e5e0328402f4281d`，EVIDENCE_HEAD_SHA=READ_AT_GATE；主线为候选祖先。

当前活动任务 `MVP-DEPARTMENT-AUTO-ASSIGN-001` 状态见 TASKS：单客服部固定角色和逐店接待资格，普通客服可转交本人同店会话，逐店派单默认关闭；合格在线坐席按近期人工服务和容量负载派单，失败留在待分配队列，零自动外发。AC-01～04 本地通过，AC-05 的 staging 部署需用户单独批准；production 未发布。产品、架构和发布边界见 `docs/product/PRODUCT.md`、`docs/architecture/SYSTEM.md`、`docs/operations/DEPLOYMENT.md`。

最新证据：[IR](../records/implementation/IR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R01.md)、[TR](../reports/tests/TR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R01.md)、[RR](../reports/reviews/RR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R01.md)。隔离 PostgreSQL 迁移往返通过；后端 2730 passed/3 skipped，前端 55/55，浏览器 161 passed/1 skipped；Ruff、格式、mypy、typecheck、lint 0 error/8 既有 warning、构建通过。三索引为 CANDIDATE_VIEW；PR CI 待创建后核验。

既有 staging 仍保持此前已验收 Agent 版本及安全开关，本次接待功能尚未部署。没有真实买家发送、退款或生产数据操作。Workspace hygiene: ATTENTION；主 checkout 的未知文件和活动 worktree 受保护，无本轮清理批次或永久删除。

下一动作：①创建并核验本任务唯一 PR，按适用门禁合并；②准备 staging 迁移、备份、预检的可审阅结果；③取得用户单独部署批准后再发布和现场验收。
