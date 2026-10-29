# 项目状态与恢复入口

2026-10-29；STANDARD；TikTok人工辅助v0.1；仓库CP11-gh/CRM，目标origin/main。

MVP-AGENT-STAGING-DEPLOY-001为VERIFYING。用户已批准统一部署并追加知识文件检索全链路；RAG审计与引用补修 #636 已合入 `main=8393602f`，8393602f已手动部署，12容器/三健康和人工模式通过；Agent v4已发布。纯RAG浏览器通过。综合问题暴露路由改写DLP误拦，已补修并做独立候选四工具+文档引用预检，正跑最终回归。实际新基线e71ce680，分支fix/agent-routed-question-fallback-20261029。部署仍由本任务单点协调，不把候选预检等同公开服务复测。

MVP-RECEPTION-TEAM-FEEDBACK-001 的前四条页面修复已由 PR #637 合入 `main=ed791b75`，本地验证见关联 IR/TR/RR；staging 尚未部署本次前端，部门角色与店铺咨询分配只形成方案、不改变运行规则。

本地：最终应用树与fa180完全相同，完整后端2514通过/3Windows条件跳过，新评测统计8项通过；Ruff437、mypy255、锁文件、前端lint/typecheck/52契约/105浏览器及前后端本地镜像构建通过。实际候选隔离进程的三工具五类问题5/5、英文/业务号/无Markdown，正式草稿1745字符；无平台外发。输出v2.3合成语义初轮14完成+1超时，统计缺陷已修并对原行补测1次完成；不声称一次15/15。配置语义16项按相同源码SHA复用。详情见IR/TR/RR 20261029-R05及release/evidence/staging/crm-agent-output-ui-local-20261029.json。

最终Agent输出和配置发布由模型语义判断，不引入新地址正则/词数规则。先过滤、重组、独立复核；仅明确unsupported可证据重生成；无效协议立即停止；已复核正文共享去重，原时限及取消/数值进度保留。语言偏离由模型标记后用安全正文改写。工作台完整草稿编辑/译文预览、超2000先精简后送审发送均已覆盖。

运行服务当前8393602f，041、原人工模式/范围及后台自动关闭保持；Agent v4包含三业务工具和获批合成验收文件。GHCR本机上传两次超时后，经逐层校验的OCI传输到服务器再发布精确linux/amd64摘要并通过手动门禁。新发现的路由补修尚未部署。production G8继续No-Go。

同一合成入站与仅由其派生的记忆保留至最终现场验收后统一清理；manifest在忽略的src/tests/.artifacts/agent-detailed-tools-20261029。不得动真实消息、运行和审计，不重建买家，不发送平台消息。其他RAG文件draft，本次不声称现场RAG检索通过。原超时调用用量未知，未当作完整账单。

三索引CANDIDATE_VIEW=300/325/283；正式源记录为事实。Workspace hygiene: ATTENTION。根checkout未知历史/文件、活动worktree、未跟踪src/frontend/AGENTS.md和上个worktree未知逆向diff均保留。临时测试输出仅src/tests/.artifacts，本轮已登记可恢复缓存隔离批次 MAINT-CLEANUP-20261029-001，无永久删除。

下一动作：①完成路由补修的最终本地验证与集成；②精确镜像/备份/手动门禁补充统一部署；③Codex浏览器联合与工作台验收，全部成功后统一清理已知合成夹具。
