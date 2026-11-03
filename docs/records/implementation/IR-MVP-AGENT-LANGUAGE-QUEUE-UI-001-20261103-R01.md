---
record_id: IR-MVP-AGENT-LANGUAGE-QUEUE-UI-001-20261103-R01
record_type: implementation
revision: R01
status: FINAL

task_id: MVP-AGENT-LANGUAGE-QUEUE-UI-001
base_sha: 3a37611da8eb4a272efb90fc9d9921b7a09d230e
final_sha: 70293cc68d803670345826cf2892d0ff209d0869
requirement_ids: [AGENT_REPLY_LIVENESS_AND_ASSISTANT_VOICE]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08]
test_record: docs/reports/tests/TR-MVP-AGENT-LANGUAGE-QUEUE-UI-001-20261103-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-LANGUAGE-QUEUE-UI-001-20261103-R01.md
created_at: 2026-11-03T10:14:54.034992+00:00
updated_at: 2026-11-03T10:14:54.034992+00:00
supersedes: null
---

# 实施目标与范围

修复用户报告的英语买家收到中文、自动建议长期生成、Agent不回复、人工发送长期忙碌、机器人回复清未读；统一五模板的人工客服助手身份与人工跟进语义。保留店铺、工具、知识、审批、DLP与unknown发送边界，不向受影响真实买家试发或重放历史消息。

# 实际变更及原因

1. 真实中文答复的触发是ORDER_CARD中文展示占位。非文字卡片/媒体仍保留上下文，但不触发Agent/接待定时；正式建议遇到该触发返回422，等待买家文字。
2. 自动队列误把同触发的60分钟接待投递当作Agent前序回执。前序等待仅约束Agent自身投递，真实unknown仍阻断；UI区分等待、生成、延迟和失败。
3. 后台可见会话轮询在滚到底时调用mark-read。删除该调用，保留人工主动打开或明确查看；后端实际自动投递测试证明未读4不被机器人清零。
4. 人工发送仅在可证明尚未进入适配器时将超时记确定失败；已进入/未跟踪仍unknown。客户端完整等待45秒后释放忙碌并保留草稿，提示先核对历史，不自动重发。
5. 统一表达策略1.1.1覆盖旧无reply_profile版本；避免第一人称单数和要求买家另找客服。无真实接管时仅说明待人工核实，不虚称已转交；未提供的退货、取消、退款状态保持未知。
6. 首轮发布后现场定位jobs整店补查持有订单写锁，阻塞订单Webhook及配置GET。仅重启已确认持锁的jobs进程释放未提交事务；补充修复逐买家独立session提交/回滚，重读策略/现权/绑定Agent/会话归属；配置GET不申请写锁，PUT仍行锁及版本检查。

# 关键决定与偏差

源码分两次完成：PR#728合并ecb59a49，PR#729合并976aa94d；最终候选为70293cc6，前端保持已发布af2组件。主线#726/#727的051已纳入精确镜像，未谎称仍只有050。实时回读发现XBM策略已为off，最新任务因AUTOMATION_POLICY_CHANGED取消；保留该状态，没有覆盖用户当前配置。

# 数据、配置、接口、迁移或 Prompt 影响

五个在用共享模板分别由v1正式发布v2，保持七段结构、模型、工具和知识槽；只更新身份、语气、升级和事实表达。旧发布快照保留，店铺Agent配置不被批量覆盖，运行共享表达策略统一生效。auto-preview增加可选状态/模式，原字段保持兼容。修复本身无新迁移，发布包含已合并051。

# 验证交接

见TR/RR及[低敏机器证据](../../../release/evidence/staging/crm-staging-agent-language-queue-20261103.json)。最终后端3711/5条件跳过、前端86契约/90浏览器及生产构建、五模板10个中英文表达案例、实际CI和独立审查均有记录。

# 限制、风险与回滚

现场浏览器绑定超时，标记UI_UNAVAILABLE；未对真实买家补发、未重新声称工具/RAG全链路或真人送达通过。模型表达检查是合成事实生成及语义评审，不调用业务工具。保留两轮模型失败，最终10条由执行者逐条阅读，不表示用户人工审阅。私有数据库/环境/恢复资料备份保留；回退镜像必须保留业务增量、051及当前用户开关，不能恢复旧整库或重放unknown。
