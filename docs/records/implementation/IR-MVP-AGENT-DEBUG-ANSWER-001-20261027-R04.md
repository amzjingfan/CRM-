---
record_id: IR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R04
record_type: implementation
revision: R04
status: FINAL
task_id: MVP-AGENT-DEBUG-ANSWER-001
base_sha: c2448dbd40c168d2f7de459273a98c1d9d689ec3
final_sha: b55847f8d697c8dc12f87860a773c93e6368445c
requirement_ids: [MVP-AGENT-DEBUG-ANSWER-001]
acceptance_ids: [AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R05.md
review_record: docs/reports/reviews/RR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R04.md
created_at: 2026-10-27T15:08:03Z
updated_at: 2026-10-27T15:08:03Z
supersedes: docs/records/implementation/IR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R03.md
---

# 目标和根因

重新部署主线后，已授权物流工具单问在 staging 显示模型答案；同轮工具加绑定文件的知识部分无引用。独立知识提问也命中一个片段（检索分数 0.8067），但模型候选进入复核前，本地 Prompt DLP 对位置文本给出低置信度判定，按失败关闭规则拒绝外发。混合提问还把完整的物流加知识问题传给文件草稿节点，曾出现无对象 ID 的物流业务声明 Schema 错误。

# 实际变更

- 仅在 Agent 调试的混合路径，按独立问句分离已由只读工具处理的部分。文件检索、草稿和独立复核只收到剩余知识问句；无法独立拆出的知识问题不猜测，保留通过安全复核的工具建议。
- 已绑定文件的调试回答使用单独登记的 `faq-answer-debug-file-v1.0.0` Prompt，要求简洁表达并完整保留条件、引用和业务声明。该 Prompt 仍使用原严格 Schema、Provider 白名单、地址/联系方式/标识 DLP 与独立模型复核。
- 工作流版本升级至 `faq-agent-workflow-v1.8.7`。正式 FAQ 与工具回答 Prompt、模型配置、HTTP 接口、数据库和前端无变更。

# 验证、限制与回滚

先以本地模拟验证普通两逗号政策句会使复核输入进入 `BUSINESS_PROMPT_LOCATION_TEXT_LOW_CONFIDENCE`，精简单句可通过该输入检查；再以工作流测试锁定混合问句的检索文本、草稿及复核 Prompt 范围。最终 subject 的隔离 PostgreSQL/pgvector 全套、Ruff、mypy 和锁文件检查见 R05 TR。真实模型能否稳定按简答 Prompt 生成安全草稿仍需 staging 验证；不降低 DLP 阈值，也不把无引用的工具回答算作全链路成功。部署前保留上一版镜像与私有快照作为回滚点；production 不发布。
