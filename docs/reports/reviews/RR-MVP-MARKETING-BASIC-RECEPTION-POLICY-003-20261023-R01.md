---
record_id: RR-MVP-MARKETING-BASIC-RECEPTION-POLICY-003-20261023-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-MARKETING-BASIC-RECEPTION-POLICY-003
reviewed_sha: 77c1086ca3059a2d4483eb49014fec59a298ebb5
implementation_record: docs/records/implementation/IR-MVP-MARKETING-BASIC-RECEPTION-POLICY-003-20261023-R01.md
test_record: docs/reports/tests/TR-MVP-MARKETING-BASIC-RECEPTION-POLICY-003-20261023-R01.md
review_focus: [authorization, store-isolation, csrf, idempotency, audit, migration, schedule-validation, no-auto-send]
created_at: 2026-10-23T08:41:10Z
updated_at: 2026-10-23T08:41:10Z
supersedes: null
---

# 审查范围、依据与重点风险

审查 031 迁移、策略查询及写入服务、请求/响应模型、前端状态及列表交互和本次回归。重点是保存后可见、跨店隔离、有效期歧义、旧记录兼容，以及页面开关不得绕过人工辅助边界。

# 发现、级别、位置和证据

未发现阻断项。服务端列表先求 `marketing.view` 允许店铺，再排除关联了任何无权店铺的策略；`DISTINCT` 使多店策略只占一条和一次计数。创建及更换适用店铺校验 `marketing.manage` 与 `marketing.view`，与列表可见性一致。写入仍走原有 idempotency、CSRF 和审计路径。新增有效期严格校验日期、每日时间和旧字段互斥，JSONB 降级在已有新数据时失败关闭。前端计算状态只读配置，不存在自动发送调度或平台写入。

主线合入文档摄取后，旧测试固定 030 为最终头的假设失效；本任务把 031 显式接到 030 并保留合流父节点断言。Windows Git 文件名解码修正为 UTF-8，没有改变产品运行行为。

# 已验证与未验证内容

最终候选在隔离 PostgreSQL 完成空库升级、031 降级和再升级；全量后端 2381 passed/3 skipped、前端合同 48/48、生产浏览器 93/93、全量 Ruff、Mypy、类型与构建通过。浏览器数据为合成数据，真实已登录 staging 策略列表、现场镜像摘要、运行模式与部署备份仍待核验。未执行真实买家外发或 production 发布。

# 结论和返修条件

`APPROVE` 源码进入 PR 和受控 staging 手动部署。若现场运行摘要、RAG Worker、权限、单店人工发送范围或迁移基线与审查前提不一致，停止部署并重新核对；不得为通过门禁关闭保护能力。
