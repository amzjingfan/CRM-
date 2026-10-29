---
record_id: IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R10
record_type: implementation
revision: R10
status: FINAL
task_id: MVP-AGENT-STAGING-DEPLOY-001
final_sha: 7fce34ef954d398af29de8ef36c62978fa58f8c2
created_at: '2026-10-29T21:43:38+08:00'
updated_at: '2026-10-29T21:43:38+08:00'
supersedes: docs\records\implementation\IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R09.md
base_sha: aa6366d27f7621967407c44725b3df2b58976501
test_record: docs\reports\tests\TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R10.md
review_record: docs\reports\reviews\RR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R10.md
requirement_ids:
- MVP-AGENT-STAGING-DEPLOY-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
- AC-04
---

# 实际发布

PR641合入0c5667272d438af15406be34fe173ee49b7cc4e8，src树与subject相同。新后端linux/amd64按不可变摘要发布；前端src和测试树与aa完全一致，复用aa精确镜像。私有PG/MinIO/配置备份、pg_restore列表/gzip、镜像源与所有blob hash、ValidateOnly/Deploy、041、12服务及三公网健康通过。没有Actions部署，production未放行。

# 现场配置与验收

Codex浏览器分别测试中英debug、正式工作台和无政策依据负例；四正例真实订单列表/详情/物流/绑定文件RAG、正确语言、正文与文件事实均可见。debug使用v6；正式建议在v6超长失败后，经正常UI保存/语义复核发布v7表达策略，明确长度优先、证据不是字段展示清单。英文1668、中文834字，仍包括8条节点与知识流程名称/三证据项。完整编辑与发送栏逐字相同；2676字旧稿完整编辑证明前端能力，旧超限发送防护保留。

# 最终恢复与边界

全部现场验证后一次性移除同一测试文件绑定、发布v8；prompt_hash、模型及三业务工具与v7完全相同。该文件软删除，版本/对象/审计保留；唯一精确标记合成入站及其派生记忆rev20恢复性清理，真实消息0改动，原出站8/8/10三类计数不变，平台发送0。原分类保留。测试知识已撤除，实际文件RAG需再绑定业务方已审批文件。

首次EN过长和CN复核格式失败、物流首次失败后重试均保留，不承诺模型/上游每次成功。新提出的逐条/分批、真正流式、最新物流+原生卡片、物流更新主动通知属于下一实现范围；本R10不声称这些能力已完成。
