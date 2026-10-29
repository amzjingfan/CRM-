# 项目状态与恢复入口

2026-10-29；STANDARD；TikTok人工辅助v0.1；仓库CP11-gh/CRM，目标origin/main。

MVP-AGENT-STAGING-DEPLOY-001为VERIFYING，第二批本地验收完成，部署等待用户另行明确批准。工作分支fix/agent-http-output-final-20261029，BASE_SHA=e3fcbd1a7df18ab5d5df7b64e45b65e02c93773e，CANDIDATE_SUBJECT_SHA=ff4d5e262bed31f07d9ec04a7c021c1a2b7fa9ba，EVIDENCE_HEAD_SHA=READ_AT_GATE。集成结果从目标分支现场核对，不把合并等同发布。

本地：最终应用树与fa180完全相同，完整后端2514通过/3Windows条件跳过，新评测统计8项通过；Ruff437、mypy255、锁文件、前端lint/typecheck/52契约/105浏览器及前后端本地镜像构建通过。实际候选隔离进程的三工具五类问题5/5、英文/业务号/无Markdown，正式草稿1745字符；无平台外发。输出v2.3合成语义初轮14完成+1超时，统计缺陷已修并对原行补测1次完成；不声称一次15/15。配置语义16项按相同源码SHA复用。详情见IR/TR/RR 20261029-R05及release/evidence/staging/crm-agent-output-ui-local-20261029.json。

最终Agent输出和配置发布由模型语义判断，不引入新地址正则/词数规则。先过滤、重组、独立复核；仅明确unsupported可证据重生成；无效协议立即停止；已复核正文共享去重，原时限及取消/数值进度保留。语言偏离由模型标记后用安全正文改写。工作台完整草稿编辑/译文预览、超2000先精简后送审发送均已覆盖。

运行服务保持第一批#634的e3fc，041、原人工模式/范围及后台自动关闭保持；没有本批部署/registry推送，Agent发布版本仍v3，v4仅草稿和隔离投影。必须在用户批准后重建精确集成源发布镜像、单点协调、重新备份并正常发布v4，再做Codex浏览器现场验收。production G8继续No-Go。

同一合成入站与仅由其派生的记忆保留至最终现场验收后统一清理；manifest在忽略的src/tests/.artifacts/agent-detailed-tools-20261029。不得动真实消息、运行和审计，不重建买家，不发送平台消息。其他RAG文件draft，本次不声称现场RAG检索通过。原超时调用用量未知，未当作完整账单。

三索引CANDIDATE_VIEW=298/323/281；正式源记录为事实。Workspace hygiene: ATTENTION。根checkout未知历史/文件、活动worktree、未跟踪src/frontend/AGENTS.md和上个worktree未知逆向diff均保留。临时测试输出仅src/tests/.artifacts，本轮没有文件清理批次。

下一动作：①复核本地证据与目标分支集成；②等待用户明确批准部署；③批准后单点发布、公开UI复测与合成触发最终清理。
