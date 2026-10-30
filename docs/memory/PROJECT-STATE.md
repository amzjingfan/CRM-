# 项目状态与恢复入口

2026-10-30；STANDARD；TikTok人工辅助；CP11-gh/CRM；origin/main。当前短期分支fix/tiktok-oauth-single-entry-20261030；CANDIDATE_SUBJECT_SHA=be936358bdce4f633a51fe599a5e5a7bbc1e074b，EVIDENCE_HEAD_SHA=READ_AT_GATE。任务唯一状态源为TASKS，主线现含Agent模板批量设计提案；本轮未部署。

新增设计提案（2026-10-30）：MVP-AGENT-TEMPLATE-BATCH-DESIGN-001已交付，见[Agent模板与批量差异更新设计](../superpowers/specs/2026-10-30-agent-templates-batch-design.md)，文档subject96da11d8，PR649已合并8a39e45b。用户已选模板＋批量应用及查看差异后选择店铺更新；完整设计仍待用户确认，未实施、未迁移、未改运行配置、未部署。独立builder检查无重要缺口，文档链接/任务唯一性/隐私/diff通过；未运行无关产品测试，也未生成虚构IR/TR/RR。此前已验收的staging与其他任务状态保持。

MVP-TIKTOK-OAUTH-UX-001 正在 VERIFYING：用户批准店铺页单入口并要求删除授权页旧 OAuth 卡片。候选已移除授权页全局按钮和卡片，异常店铺行内恢复绑定自身 store_id；旧回跳导向店铺页。授权进度新增低敏失败码和店铺 ID，列表显示店铺与渠道均连接后才报成功。最终候选本地前端契约55、相关浏览器9、后端OAuth53、类型/格式/lint/构建通过；全量浏览器首次尝试因独立端口3124未启动和并行构建超时退出1，不当作通过。IR/TR/RR R01 与三项索引 CANDIDATE_VIEW 已建立，待PR合并；staging/production未部署。

MVP-AGENT-REPLY-STAGING-001已验收：staging手动部署冻结release d111d164（基线d6f89746加本任务），前后端精确摘要见机器证据；043_logistics_updates、12服务和三个公网健康200。最终中英文真实工具＋绑定文件RAG回答、坐席原生草稿流、最新物流正文后卡片、正式确认框仅查看后取消通过。临时预演交付按钮、通知预演区域与假的Agent自动发送开关移除，真实调试保留。自动回复、主动物流通知双开关、营销与高风险仍关闭，production未放行。

发布源码本地2712/3平台skip、前端55/158；保留主线PR646的集成源码2731/3、前端55/161，Ruff450/mypy284/类型/构建/锁、动态16/安全237通过。既有20ms调度测试改为仅loop模块逻辑时钟，生产期限未改。保留现场路由/复核协议失败和重试，不声称一次成功率100%。CI源码及最终证据头均runner0/steps0未执行，按持续授权本地替代。

16条精确合成入站消息及专属测试记忆统一清理，原26条消息哈希不变、外发计数26不变；同一测试知识文件解绑软删，Agent正常发布v13，模型/工具及其余六段提示词保留，当前买家语言/简洁最新物流输出要求保留。分类保留，私有恢复备份和只读性验证通过，无整库恢复演练；临时registry凭据注销并移除，仅本任务本地测试服务已停止。

证据：IR/TR/RR-MVP-AGENT-REPLY-STAGING-001-20261030-R01，release/evidence/staging/crm-agent-reply-delivery-20261030.json；三索引从已合并主线源记录核对重建，CURRENT=307/332/290。旧R10双语工具/RAG通过事实保留。

并行任务MVP-DEPARTMENT-AUTO-ASSIGN-001仍VERIFYING：PR646已合入1da8d152，044迁移/接待权限/派单代码在主线保留，但需其单独部署批准，本次staging没有包含该增量。其IR/TR/RR及任务授权边界保持，后续发布应以包含本轮修复的主线统一构建，避免覆盖本次变更。

Workspace hygiene: ATTENTION。未知主checkout历史与活动worktree保护不动；本分支 `next dev` 生成的未跟踪 `src/frontend/AGENTS.md` 未纳入提交，自动批准审查拒绝了移除操作，保持原状。本轮无永久文件清理批次。原G4/G5/G8未满足事项不因本轮功能验收视为生产放行。

下一动作：①完成本轮 OAuth UI 源码与证据 PR 合并并复核任务状态；②用户确认模板批量设计后再编写实施计划；③接待/派单任务的独立 staging 部署仍待其授权。
