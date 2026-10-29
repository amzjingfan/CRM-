# 项目状态与恢复入口

2026-10-29；STANDARD；TikTok 人工辅助 v0.1；仓库 CP11-gh/CRM，目标 origin/main。

MVP-AGENT-STAGING-DEPLOY-001 为 VERIFYING，分支 fix/agent-detailed-tools-20261029；BASE_SHA=9b22a7ba059a548c690bea367fd76b82ea9836ea，CANDIDATE_SUBJECT_SHA=39d09e1ace21493c847930ee79a76cd979042335，EVIDENCE_HEAD_SHA=READ_AT_GATE。计划 docs/superpowers/plans/2026-10-29-agent-detailed-tools.md。用户要求配置并验收三项真实只读工具的详细回答，集中修复/发布后启用工作台人工 AI 建议，禁止平台发送。

staging 仍运行 45d872c060f9b632de340318f32bf9de2904efb5，041 合流 head、12 容器；仅调试开启，正式建议/LLM/自动回复/营销/高危关闭，原单店人工发送和翻译范围保持。最新已定稿 IR/TR/RR 为 20261029-R03，TR PARTIAL；清单 release/evidence/staging/crm-staging-agent-multishop-20261029.json。本轮尚未部署。

当前测试店铺 Agent 已通过 Codex 浏览器发布 v3：项目 DeepSeek、七段提示词和买家订单查询/订单详情/完整物流三工具。用户已明确采用模型语义识别隐私并原位脱敏，取消动态回答中的旧业务/地址词法否决；权限、店铺、工具、输入投影、证据与人工发送门禁保持。

本轮候选在隔离进程使用真实授权上下文：三类问题均 review_ready，回答 1047/1112/970 字符；完整物流一包裹八轨迹；正式建议 1309 字符且三工具成功、outbound_delta=0。此结果不是公网运行服务已更新。实际 Agent v3 和当前模型参与；模型安全合成评测 10/10。前端 lint/typecheck/52 契约/build 通过。先前完整 PostgreSQL 2426/3 是审查修复前结果，最终候选必须复跑。

独立最终审查发现汇总异常、外层超时、已知失败轮用量三个 Important，已在同批修复并完成 RED→GREEN 的 38 项回归；不保留晚到正文/事实，取消继续向上传播。待完整最终验证与受审单次发布。

真实测试会话无买家入站；按授权插入一条明确标记、本地专用合成触发，不向 TikTok 写入。恢复所需私有 manifest 位于忽略的 src/tests/.artifacts/agent-detailed-tools-20261029；最终成功后清理本条及仅由其派生的记忆，保留真实消息、运行和审计。其他八份 RAG 文件均 draft，未以其充当已审批文件现场证据。

三索引先前 CURRENT=296/321/279；本轮最终源记录尚未产生。production G8 No-Go。041 后新增业务、配置、运行和记忆须保留，不盲目还原旧库。

Workspace hygiene: ATTENTION。根 checkout 未共享历史、未知私有文件、其他活动 worktree 及未跟踪 src/frontend/AGENTS.md 保留；临时输出仅 src/tests/.artifacts，无文件清理批次。

下一动作：①最终候选完整验证并形成单一 PR；②协调唯一执行者、备份、受审手动部署人工建议模式；③Codex 浏览器三工具/工作台草稿无发送验收、合成触发清理、证据和任务闭环。

最终 subject 完整验证：2438 passed/3 Windows skips，427格式文件、mypy252、前端52/build、动态16、共享237通过；IR/TR/RR R04定稿，本地门禁通过、总体TR PARTIAL，等待统一实际发布。三索引CANDIDATE_VIEW=297/322/280；CI情况尚待PR现场核对。
