# 项目状态与恢复入口

2026-10-29；STANDARD；TikTok人工辅助v0.1；CP11-gh/CRM；目标origin/main。

MVP-AGENT-STAGING-DEPLOY-001为VERIFYING。用户已批准单点手动部署、真实只读买家上下文、必要字段给DeepSeek及合成样本，最新追加中英文都测；不发送平台消息。#636/639已合入，staging当前0fb0f96b，041、12容器/三公网健康及原人工模式通过。自动回复、营销、高风险与后台自动LLM仍关闭；production G8 No-Go。另一协调会话确认无待纳入资产且不并行切换。

公开英文调试四工具（订单列表/详情/物流/RAG）成功19.899秒，1包裹8轨迹、3个文件v1引用及唯一文档名称；纯RAG早前公开15.824秒成功。中文两次四工具成功却在最终SDK请求APITimeoutError：通用15秒先于总45秒。工作台英文问题曾得到中文草稿，不能当双语验收完成。正常页面现发布v6语言要求，文件仍绑定。

当前分支fix/agent-model-deadline-20261029，BASE_SHA=0fb0f96bdd86298a0b684e0247684f854a94414d。原生Provider可选绝对deadline，动态执行传入同一deadline，SDK用剩余预算且过期零创建；其他调用默认超时不变，零重试。SDK timeout转LLM_TIMEOUT，保留已完成工具和已知用量。RED24/GREEN27、焦点86、完整隔离PG2561通过/3Windows条件跳过、独立审查无阻断；Ruff414/mypy255/锁通过；真实候选中英调试和中英正式建议四类均通过（22.664/18.794/24.897/35.926秒），正确语言/知识唯一事实/四工具，仍尚未部署本补修。前端树相对0fb未变；最新生产浏览器142、契约52见R07，不伪称本次新跑。

最新正式记录R07和release/evidence/staging/crm-agent-routed-question-local-20261029.json；当前还需R08及最终现场记录。失败、诊断辅助脚本错误和未完成用量均按真实情况保留。已核实业务号可显示，私密内容由模型过滤/重组/独立复核；本轮未新增地址或语言正则。

合成文档、同一合成入站及仅由其派生的会话记忆保留到最终中英文现场成功后统一清理。消息已在精确manifest/标记核对后按中英验收改为中文revision3，不修改真实消息或会话摘要；不要重建买家或提前删除。私有和临时材料在src/tests/.artifacts/agent-rag-staging-20261029；原消息manifest见先前验收artifact。

MVP-RECEPTION-TEAM-FEEDBACK-001源码已随0fb前端部署；其本地验证见对应记录，本任务未额外人工验收那些页面。

三索引CANDIDATE_VIEW=301/326/284，源记录为事实。Workspace hygiene: ATTENTION。未知主checkout历史、活动worktree、未跟踪src/frontend/AGENTS.md和旧worktree未知diff保留。CLEANUP-20261029-001仅可恢复隔离本次10个误置缓存、hash一致，无永久删除。

下一动作：①冻结最终门禁与集成；②精确镜像/新备份/手动门禁统一更新；③公开中英文调试/工作台和负例验收，最终清理合成夹具、记录证据后完成任务。
