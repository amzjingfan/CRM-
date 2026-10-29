---
record_id: IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R08
record_type: implementation
revision: R08
status: FINAL
task_id: MVP-AGENT-STAGING-DEPLOY-001
final_sha: daf879b8bbf7ce293ea773690f8ef1ebc27bcc44
created_at: '2026-10-29T20:01:34+08:00'
updated_at: '2026-10-29T20:01:34+08:00'
supersedes: docs/records/implementation/IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R07.md
base_sha: 0fb0f96bdd86298a0b684e0247684f854a94414d
test_record: docs/reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R08.md
review_record: docs/reports/reviews/RR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R08.md
requirement_ids:
- MVP-AGENT-STAGING-DEPLOY-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
- AC-04
---

# 实施目标和实际变更

用户追加中英文都测。已部署0fb的英文公开四工具+RAG通过；中文长回答两次在四工具成功后遭SDK APITimeoutError，单次通用15秒先于Agent总45秒耗尽。原生Provider现在接收可选绝对deadline，动态执行两个上下文传同一deadline，三SDK使用创建时的剩余预算；过期零SDK创建。原有外层绝对截止和取消不变。未传deadline的配置发布等调用继续原通用超时和零重试。DeepSeek/OpenAI SDK超时映射LLM_TIMEOUT，保留已完成工具和已知用量，不伪造未知失败用量。

# 决定、配置和范围

无全局env超时变更、新依赖、迁移、公共API或权限扩大。工作台英文问题曾输出中文，作为失败保留；正常页面保存/发布v6七段配置，明确英文问题用英文、中文用中文，坐席/历史/文档/子任务语言不覆盖原文；属于可编辑运营要求，不增加语言正则。合成消息仅按精确scope/标记/hash从英文revision2改为中文revision3以预检正式中文入口，真实消息与会话摘要不改。

# 验证交接

本地2561/3、RED24/GREEN27、焦点86、静态255与独立审查通过。独立候选进程对中英debug/formal四类均完成四工具、RAG唯一文档事实、正确语言、真实业务号和无Markdown，引用按真实chunk核对预期文件v1。该进程只载入候选模块，不修改运行服务或设置；公开最终验收仍待源码部署后执行。

# 限制与恢复

总45秒仍生效，不保证所有复杂问题或上游异常都能完成。中文formal一次物流THIRD_PARTY_ERROR由模型再次调用成功，保留原失败事件。历史15秒超时、路由误拦、辅助脚本错误和语言偏离不能消失。保留0fb精确镜像和新备份，回退不盲目覆盖DB。合成资料保留至最终公开中英验收后统一清理；production继续No-Go。
