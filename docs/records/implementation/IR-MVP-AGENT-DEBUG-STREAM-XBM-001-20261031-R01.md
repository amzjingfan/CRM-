---
record_id: IR-MVP-AGENT-DEBUG-STREAM-XBM-001-20261031-R01
revision: R01
record_type: implementation
status: FINAL
base_sha: 230923b110d66a9fefce7210be3e0454817dc517
final_sha: 63b69216ccaa82a48a6bf18786d4f8876f7fec73
test_record: docs/reports/tests/TR-MVP-AGENT-DEBUG-STREAM-XBM-001-20261031-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-DEBUG-STREAM-XBM-001-20261031-R01.md
requirement_ids: [MVP-AGENT-DEBUG-STREAM-XBM-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-06]
task_id: MVP-AGENT-DEBUG-STREAM-XBM-001
created_at: 2026-10-31T02:50:53.526328+00:00
updated_at: 2026-10-31T02:50:53.526328+00:00
supersedes: null
---

# 实际变更及原因

调试新增 POST /agents/{id}/debug/stream，复用真实原生模型答复计划，accepted/draft/result/error/done 协议与完整快照队列；JSON 接口兼容保留。草稿仅坐席可见、不可发送，最终全部已复核段替换草稿。提交立即清空，保留下一条输入；切店、切Agent、清空或离页均取消并隔离迟到事件。取消审计及并发租约释放用 AnyIO shield 保护真实 ASGI 重复取消。

路由模型从当前 question 返回 question_language，冻结后贯穿各专家、普通汇总和流式答复计划；正式/调试统一报告 agent-router-v2.1.0。知识工具强调完整语义与 no_hits 后改写重查，不把零命中误说成无审批文件。未改变绑定、审批、隐私过滤或召回阈值。内层SSE路由透传 X-Accel-Buffering，源公网配置增加明确调试路由。

# 数据、配置及主线整合

未新增迁移。整合已合并主管授权与047迁移，无冲突覆盖；不扩展agent权限。测试脚本改为独立Compose项目/端口、固定pytest配置与IPv4回环；临时库URL禁止query覆盖，仅允许显式隔离目标。短生命周期测试明确启用它验证的处理器，完成断言与原轮询时限保持。

# 现场及回滚边界

US v13生成持久订单物流模板v1，应用XBM并启用。XBM临时绑定一份自有合成指南（3块、内部审批）用于同轮工具与知识测试；模板/Agent最终保留，测试文件验收后清理。旧版本英文现场四工具+引用通过，中文现场发现问题后归入同一修复。此记录不宣称新候选已部署或XBM新版本验收完成。

已备份staging PostgreSQL、MinIO和环境及运行快照；回滚保留现场8d296主管授权前后端摘要、翻译overlay及两店人工发送范围。公网SSH私钥原有ACL被OpenSSH拒绝，未修改；实际早片交付须部署后证明。production与真实消息发送未执行。
