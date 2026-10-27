---
record_id: IR-MVP-AGENT-LIVE-DEBUG-001-20261027-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-AGENT-LIVE-DEBUG-001
base_sha: 9302bb6d4d16b67d942f23251e58d7356e116ac5
final_sha: b1053d4027266df3d334f67db3bae8aa5724e96e
requirement_ids: [MVP-AGENT-LIVE-DEBUG-001]
acceptance_ids: [AC-02, AC-04]
test_record: docs/reports/tests/TR-MVP-AGENT-LIVE-DEBUG-001-20261027-R02.md
review_record: docs/reports/reviews/RR-MVP-AGENT-LIVE-DEBUG-001-20261027-R02.md
created_at: 2026-10-27T07:01:49Z
updated_at: 2026-10-27T07:01:49Z
supersedes: docs/records/implementation/IR-MVP-AGENT-LIVE-DEBUG-001-20261026-R01.md
---

# 实施目标与变更

授权买家 `polojunky65` 的只读物流工具在 TikTok US staging 已实际调用，未发送平台消息。批准并绑定的合成知识文件已命中检索，但回答阶段的本地 DLP 将“测试编号、商品、7 天、人工复核”组合误判为地址，阻止知识正文进入 DeepSeek；运行摘要中的 `model_refusal` 并不表示模型拒答。

在 `src/backend/app/agent/security.py` 的注册 FAQ 业务 Prompt 中，仅对 `knowledge` 字段的地址形态扫描排除“编号、型号、订单号”等业务词尾的“号”；原始知识文本仍用于高风险地址检测。非知识字段、工具草稿和其他 Prompt 继续使用原规则。额外保留“门牌”地址信号，防止“门牌编号：7”被误放行。DLP 策略版本升至 `prompt-dlp-v1.3.1`，同步 AI 架构与 Agent 说明。

合并 `origin/main` 的 staging IP 迁移文档时保留双方任务、证据索引及部署资料；当前候选索引标记为 `CANDIDATE_VIEW`。没有修改生产运行设置、客户数据或平台发送逻辑。

# 恢复与未完成项

测试文件已软删除，Agent 文件绑定移除并恢复启用；按用户本次明确授权，空测试分类已永久删除。此修复仍需合并和手动部署 staging 后，再经 Codex 浏览器验证真实知识回答；production G8 不放行。
