---
record_id: TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R10
record_type: test
revision: R10
status: PASS
task_id: MVP-AGENT-STAGING-DEPLOY-001
tested_sha: 7fce34ef954d398af29de8ef36c62978fa58f8c2
created_at: '2026-10-29T21:43:38+08:00'
updated_at: '2026-10-29T21:43:38+08:00'
supersedes: docs\reports\tests\TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R09.md
implementation_record: docs\records\implementation\IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R10.md
requirement_ids:
- MVP-AGENT-STAGING-DEPLOY-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
- AC-04
---

# 最终本地与现场结论

本地最终subject2571passed/3Windows POSIX条件skip/2依赖warning，Ruff/format/mypy255/lock、动态16、安全237与独立焦点46通过；精确来源见R09，未重复运行同树前端52/142。CI run40877496658、两个jobs123459975760/123459976167均runner0/steps0/failure，没有执行测试，按持续授权使用本地替代，不记CI通过。

| 入口 | 耗时秒 | 结果 |
|---|---:|---|
| 英文debug v6 |31.733|四工具、3引用、英文正文、平台上限内|
| 中文debug v6 |18.096|四工具、1引用、中文正文、平台上限内|
| 英文正式v7 |30.132|英文1668字、3引用、四工具成功；物流首次失败后成功|
| 中文正式v7 |30.297|中文834字、2引用、四工具成功；物流首次失败后成功|
| 英文缺政策依据 |7.152|英文澄清、no_hits、零引用、人工复核|
| 中文缺政策依据 |8.550|中文澄清、两次no_hits、零引用、人工复核|

每个工具记录mocked=false，查询命中、无命中和失败分别保留语义状态。四正例都显示绑定文档唯一名称Indigo Lighthouse及所问三证据项，不把测试资料当真实政策。正式引用数来自对应子Agent最终引用计数；公开DTO不含版本，不能声称DTO返回v1。验收期间唯一审批绑定文件有效v1，调试UI核对文件名；此前chunk数据库join见R08。

# 失败与恢复

v6英文正式首次34.833秒answer_too_long没有展示；正常发布v7的可编辑精简表达后得到1668字。v7中文首次32.334秒evidence_review_invalid没有展示，手动重试得到834字。真实物流服务存在瞬时失败，模型在相同总deadline内再次查询成功；失败事件不删除。不把这些首次请求算通过，也不宣称100%稳定。该限制需要持续观测；本次已验收中英可见完整答案和失败不输出未核验结果。

# 清理与未触达

统一清理文件软删除、绑定、合成消息1和专属记忆1，真实数据0变更/平台发送0，完整编辑834字逐字一致。保留私有恢复副本和全部运行审计。自动回复/营销/高风险/后台自动LLM关闭，生产未触达。当前只完成既定双语/RAG/精简验收；用户后续提出的逐条分批与主动物流通知不是本轮已验收能力。
