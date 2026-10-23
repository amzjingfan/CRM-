---
record_id: TR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-MARKETING-BASIC-RECEPTION-001
tested_sha: 439c50c926240e34e85d543629dab9cd03bdaea4
implementation_record: docs/records/implementation/IR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R02.md
requirement_ids: [MVP-MARKETING-BASIC-RECEPTION-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: local isolated PostgreSQL and production browser; direct manual staging deploy and authenticated browser UI
created_at: 2026-10-23T03:29:56Z
updated_at: 2026-10-23T03:46:54Z
supersedes: docs/reports/tests/TR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R01.md
---

# 范围与环境

`TEST_LAYOUT: centralized`。源码 [PR #539](https://github.com/CP11-gh/CRM/pull/539) 已合入 `main=d19f683558c1d186478fb4f4a0682d8af95f5a15`，从干净合并源直接手动部署 staging。源码本地 2294 passed/3 skipped、前端契约 48/48、生产浏览器 81/81 等真实结果见 [R01](TR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R01.md)，不在此冒充现场复测。

# 现场门禁与页面结果

| 现场检查 | 结果 |
|---|---|
| 干净主线源码、OCI amd64/revision、后端/前端不可变摘要 | PASS；摘要见 [低敏证据](../../../release/evidence/staging/crm-staging-basic-reception-20261023.json) |
| 六角色预取、部署前私有备份 389366 字节/0600/`pg_restore -l`/哈希一致、`ValidateOnly` | PASS；完整备份哈希保留在私有证据中 |
| 精确摘要 `Deploy`、迁移头 028、运行容器与模式 | PASS；部署后端/前端摘要精确匹配，检索不变；迁移头 `028_basic_reception_config`，CRM 11 容器；固定出口与既有单店人工发送、TikTok 读取/Webhook、翻译范围保持，自动回复/高风险写入/AI 营销/LLM/SSE 关闭，查询上限 10 |
| 公网 `/healthz`、`/v1/health`、`/v1/health/ready` 与基础接待三页面 | PASS；六路径均 HTTP 200 |
| 已登录 staging 浏览器：侧栏三入口与页面呈现 | PASS；“基础接待”及快捷回复、超时自动回复、进店欢迎语均可见且可进入；快捷回复有个人/团队、分组/搜索和空态；两策略页提示自动发送关闭 |
| 真实配置写入与买家发送 | NOT RUN；本次只读核对，未创建/修改配置，未向买家发送消息 |

# 验收映射与证据边界

AC-01～04 的本地源码证据沿用同一 subject 的 R01。AC-05 的直接手动门禁、现场迁移与已登录页面只读检查已通过；低敏原件见 [`crm-staging-basic-reception-20261023.json`](../../../release/evidence/staging/crm-staging-basic-reception-20261023.json)。本次真实登录态核对了导航和页面，未验证真实策略创建或实际买家发送。不得保存店铺 ID、账号、Token、客户内容或私有备份路径。

# 结论与限制

本记录对 AC-01～05 的已批准人工辅助与配置界面范围为限定 `PASS`。策略实际触发和买家发送不在本次边界；真实配置写入未执行，不能由页面可见性推断其现场结果。证据分支尚未合入，任务维持 `VERIFYING`；production 仍为 No-Go。
