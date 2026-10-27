---
record_id: TR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R04
record_type: test
revision: R04
status: PARTIAL
task_id: MVP-AGENT-DEBUG-ANSWER-001
tested_sha: d0a2e6e4cd1ab62892d3b0d8e6f6a3dc021a07ff
implementation_record: docs/records/implementation/IR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R03.md
requirement_ids: [MVP-AGENT-DEBUG-ANSWER-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: authenticated staging browser; manually deployed main bc076c5bec48f2c173dc72c4fc4fa4f58b5d10b4
created_at: 2026-10-27T12:45:00Z
updated_at: 2026-10-27T12:45:00Z
supersedes: docs/reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R03.md
---

# 测试范围、环境与 TEST_LAYOUT

集中式测试源仍在 `src/tests/`。R03 在最终 subject 上的隔离数据库 2455 passed/3 skipped、Ruff、mypy、锁检查见 [R03](TR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R03.md)；本轮未重跑源码测试。用户仅对 [PR #569](https://github.com/CP11-gh/CRM/pull/569) 批准以该本地验证替代在零步骤失败的 GitHub CI。PR 已 squash 合入 main `bc076c5bec48f2c173dc72c4fc4fa4f58b5d10b4`，并按要求不用 Actions/CICD 手动部署 staging。后端 OCI 镜像 `sha256:f9e0a8f88232e01acaf3b136515892cec1ec603c9a918ae0fdfca9e53122797d`；前端、检索和解析镜像不变。部署前私有环境、PostgreSQL 和 MinIO 快照均已创建并验证可列出；`validate`、`deploy`、迁移头 034、12 容器和 `/healthz`、`/v1/health`、`/v1/health/ready` 三项 200 均通过。完整摘要见[低敏发布证据](../../../release/evidence/staging/crm-staging-agent-debug-live-tracking-20261027.json)。production 未发布。

# 已登录现场结果

- TikTok US 测试店铺的既有授权会话，只读提问“我的订单的物流现在到哪里了？”：trace `5de03cb4-6598-4e5e-bc82-a713db8b86fa`，`query_logistics` 成功，审计摘要 `tracking_status=delivered`、`has_tracking_event=true`；页面展示模型回答“物流状态显示订单已经送达。”，进入 `HUMAN_REVIEW`。该单问的官方轨迹读取与回答通过。
- 绑定并审批一份非真实承诺的合成文档后，同轮询问物流状态和合成退货窗口：trace `43ff2c8d-13fd-4898-9951-5a408b8a268d`，工具成功，知识候选命中、检索分数 0.7612，但知识复核被本地位置文本低置信度检查拒绝，`safety_reasons=MODEL_REFUSAL`，无引用；页面仅显示系统固定的物流提示。AC-02/03 的真实同轮回答 **未通过**，不能把工具成功和检索命中等同于完整回答。
- 测试后已撤销合成文档当前版审批、移除 Agent 绑定并保存配置；文件走产品软删除，数据库确认 `deleted_at` 非空，列表为 0。版本和审计记录保留。未向 TikTok 买家发送消息。

# AC 结论与复测条件

AC-01 和物流相关 AC-05 在本次现场通过；AC-02/03 的知识引用及工具加知识同轮答案未通过；AC-04 的只读、隔离、超时与零发送没有改变。总体 **PARTIAL**，任务维持 `VERIFYING`，production 仍为 No-Go。后续应针对知识复核安全边界建立确定性复现，修正后重新走独立 PR、验证、部署和已登录现场验收；不得放宽 DLP 或把固定提示称为模型原文。
