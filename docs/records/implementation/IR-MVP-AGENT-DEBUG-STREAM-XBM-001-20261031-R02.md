---
record_id: IR-MVP-AGENT-DEBUG-STREAM-XBM-001-20261031-R02
revision: R02
record_type: implementation
status: FINAL
base_sha: 8bf9873c4ebaa1eeda882acad24acfbb1ff7a0b8
final_sha: ecc94a7b2e7293553c307fa3f6393755962196e8
test_record: docs/reports/tests/TR-MVP-AGENT-DEBUG-STREAM-XBM-001-20261031-R02.md
review_record: docs/reports/reviews/RR-MVP-AGENT-DEBUG-STREAM-XBM-001-20261031-R02.md
requirement_ids: [MVP-AGENT-DEBUG-STREAM-XBM-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07]
task_id: MVP-AGENT-DEBUG-STREAM-XBM-001
created_at: 2026-10-31T03:36:15.944047+00:00
updated_at: 2026-10-31T03:36:15.944047+00:00
supersedes: docs/records/implementation/IR-MVP-AGENT-DEBUG-STREAM-XBM-001-20261031-R01.md
---

本轮交付说明及证据 subject 为 `ecc94a7b2e7293553c307fa3f6393755962196e8`；实际运行/测试镜像 revision 为 `8bf9873c4ebaa1eeda882acad24acfbb1ff7a0b8`，本任务后端、Agent页面/API及部署协议源码一致。后续主线的工作台物流卡片改动未在本轮镜像中部署，本TR不把其记为现场验收。文档检查针对前者，现场调用针对后者，不声称重新部署文档提交。

# 实际交付

代码实现及根因见R01；PR #688统一合入8bf9873c。合并版本与最终本地验证63b69216的src构建输入完全一致，未再逐缺陷PR/切换。真实草稿SSE、即时清空、取消审计、模型语种贯穿及语义检索说明随同一产品候选交付。主管授权047及工作台翻译成果保留。

# 发布与恢复

从合并跟踪源码构建linux/amd64；OCI内容逐blob SHA-256、配置revision和GHCR原始manifest核对，导入Rootless后精确RepoDigest验证。匿名推送/拉取曾失败；发布改用现有GitHub身份仅内存访问registry，门禁强制pull通过仅进程内credential-helper完成，未创建密钥/密码副本、未改全局Docker配置。首个Deploy停于helper拉取；同一候选补认证后Current/Candidate预检及Deploy通过，047、12服务、三公网健康、固定出口和实际模式通过。私有环境、PostgreSQL、MinIO与运行快照备份可读；未做恢复演练。

源公网Nginx路由未直接安装（原SSH私钥ACL被拒绝，未修改）；内层SSE及X-Accel-Buffering透传已实际发布，公网126草稿早于终态证明当前链路关闭缓冲有效。安全及两店人工发送范围保持，测试零真实外发。

# 持久模板、XBM与清理

从US已发布v13创建“订单物流 Agent 模板”v1，并批量创建、发布和启用XBM“订单物流Agent”。模型、用途、Agent类型、三项工具与七段提示词逐字段等同US源。模板增加可选的本店知识需求槽，不复制US文件。US仍为发布v13/草稿r29/启用。

本轮仅复用一份合成指南，完成真实解析/清洗/分块/BGE-M3/pgvector、内部审批和Agent绑定；三块可检索。中英文及店铺路由成功后，移除绑定并发布XBM v3，再通过产品软删除原指南；有效文件为0、绑定为0。模板与XBM Agent及模板关联均保留启用，审计和不可变旧版本保留。未创建合成买家、订单或会话，未删除真实业务资料。清理后物流只读回答再次通过。

# 证据

低敏机器证据：[统一部署与XBM验收](../../../release/evidence/staging/crm-staging-agent-debug-stream-xbm-20261031.json)。本轮控制事实及任务索引随证据合并；production未放行。
