---
record_id: IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R03
record_type: implementation
revision: R03
status: FINAL
task_id: MVP-AGENT-STAGING-DEPLOY-001
base_sha: 45d872c060f9b632de340318f32bf9de2904efb5
final_sha: 45d872c060f9b632de340318f32bf9de2904efb5
requirement_ids: [MVP-AGENT-STAGING-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R03.md
review_record: docs/reports/reviews/RR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R03.md
created_at: 2026-10-29T10:35:46+08:00
updated_at: 2026-10-29T10:35:46+08:00
supersedes: docs/records/implementation/IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R02.md
---

# 实际部署

用户批准 staging 与跨会话协调后，本执行者独占发布，另一授权会话只负责多店功能集成和现场只读复核。PR #629/#630 与部署补齐 #631 合并后冻结 `45d872c0`；从跟踪源码导出干净 Git bundle，镜像在本机构建、推送并通过内网哈希传输导入，未使用 Actions 部署。

前后端分别部署 `sha256:5e2721fe…3b2eeb`、`sha256:69f5aa00…d14618`，均为 linux/amd64 且 OCI revision 等于源 SHA；检索和解析镜像保持。私有环境、PostgreSQL、MinIO、原容器和镜像先备份，再补做切换前最新可读备份。按原店铺发送白名单、读取/Webhook、翻译和文档模式执行 ValidateOnly/Deploy，共享锁内迁移到 `041_merge_agent_multishop_collab`。12 容器、健康、固定出口、不可变摘要及运行态开关核验通过，临时 GHCR 凭据已注销。

仅 backend 开启 v2 预览调试，正式入口及通用 LLM 保持关闭。主模型上下文设为已核实容量内的保守 32768；模型、Key、原业务白名单与其他配置语义不变。未新授权店铺、未创建合成业务数据、未保存 Agent 配置、未发送平台消息或操作 production。调试正常生成内部运行记录及派生会话记忆。

# 功能验收仍未完成

六分类/十六能力目录、旧 v1 配置和两工具绑定，以及原店铺/渠道/工作台已登录只读回归通过。但指定买家上下文的两次真实模型请求均未交付可接受业务回答：首次 `no_verified_evidence`，第二次子 Agent `sensitive_agent_output`、父运行 `specialist_incomplete`。未绑定文件，工具加 RAG 联合链路没有验收，任务保持 VERIFYING。

只读源码诊断发现，worker 的敏感输出早返回会省略已取得的工具事件；因此页面显示的零调用不能独立证明平台查询从未发生。本次没有修改这一业务路径或放宽安全规则。部署事实和功能未通过分别记录在[低敏证据](../../../release/evidence/staging/crm-staging-agent-multishop-20261029.json)。

# 恢复边界

私有备份与旧前后端摘要保留。若需关闭新能力，使用受审 staging 门禁去掉调试模式并保留原人工工作台模式；不能以旧数据库覆盖新增业务、版本、运行、记忆或协作记录，也不能盲目降级 041。现场没有执行恢复演练，备份可读性不等于恢复成功。production G8 No-Go。
