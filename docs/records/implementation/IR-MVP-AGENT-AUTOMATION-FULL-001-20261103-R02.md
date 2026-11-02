---
record_id: IR-MVP-AGENT-AUTOMATION-FULL-001-20261103-R02
record_type: implementation
revision: R02
status: FINAL
base_sha: ad71ae18d99fcc44de06990b0137979366ccb481
final_sha: 20c9103cac541ed43c164a68e7ed2abe03430370
test_record: docs/reports/tests/TR-MVP-AGENT-AUTOMATION-FULL-001-20261103-R02.md
review_record: docs/reports/reviews/RR-MVP-AGENT-AUTOMATION-FULL-001-20261103-R02.md
task_id: MVP-AGENT-AUTOMATION-FULL-001
requirement_ids: [USER-AGENT-FULL-CHAIN]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
created_at: 2026-11-02T16:13:25Z
updated_at: 2026-11-02T16:13:25Z
supersedes: IR-MVP-AGENT-AUTOMATION-FULL-001-20261102-R01
---

# 实际交付

统一收集现场问题后，由 PR #719 一次合并并手动部署这一批修复，合并提交 f71fca80703d1abab0d735a4a28e9c1f5061aca3。原功能与迁移050来自已合并 PR #716。本记录补充并取代 R01 的待现场验收状态，不改写历史失败。

- 路由原生 schema 按当前候选 UUID 枚举，模型仍自主选择已启用 Agent；中英文识别以实际问题为主。
- Search Returns 202602 明确 total_count=0 且无后页才接受缺省空列表；未知和畸形数据仍失败。通用物流履约服务不再冒充承运商。
- 兜底缺少实际绑定的历史、接管或备注步骤时，反馈缺项让模型继续 native function calls；重复无进展和失败不会被当成完成。
- 无绑定文件的物流事件不强制知识检索；有文件仍要求真实引用和独立复核。
- 两店实际中英文 debug、正式 suggest、知识与选单场景完成；物流更新使用明确标注的隔离模拟，调用真实模型、BGE 与重排。

# 清理与启用

通过正式 API 软删除10个测试 Agent、8个合成文件，精确删除139条自有临时入站和12条内部协作；US恢复原会话记忆内容并递增版本，XBM恢复原无记忆状态。审计、运行证据及私有备份保留；5个原 Agent 草稿/发布版本未改。两店现各有5类永久 Agent，未绑定合成知识。

先在全局关闭状态停用旧重叠接待策略，随后同一精确镜像切换 customer automation profile，并用正式认证/CSRF/权限 API 启用及回读：两店 Agent auto、物流 external且3600秒轮询、24小时新咨询段欢迎、60分钟未答超时且每段一次。新店默认关闭；生产、营销、高风险写入未放行。

# 恢复与限制

保持原预检、店铺隔离、权限、幂等、unknown不重发及发送证明。优先关逐店/全局自动化并保留050和投递账本，再按精确摘要恢复镜像；私有发布前数据库/环境备份保留，不以恢复旧库覆盖新业务增量。长复杂自由文本仍可能被保守输入DLP拒绝，模型错误参数会失败关闭；本轮没有声称每一种问法均成功。完整低敏事实见发布证据。

[低敏发布与现场证据](../../../release/evidence/staging/crm-staging-agent-automation-20261103.json)。
