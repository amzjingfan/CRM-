---
record_id: TR-MVP-AGENT-LIVE-DEBUG-001-20261027-R03
record_type: test
revision: R03
status: PASS
task_id: MVP-AGENT-LIVE-DEBUG-001
tested_sha: 7e59ab743f29ca501890c52f7ba121f4268a6c44
implementation_record: docs/records/implementation/IR-MVP-AGENT-LIVE-DEBUG-001-20261027-R03.md
requirement_ids: [MVP-AGENT-LIVE-DEBUG-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows local, isolated PostgreSQL/pgvector, staging, authenticated Codex browser
created_at: 2026-10-27T08:39:12Z
updated_at: 2026-10-27T08:39:12Z
supersedes: docs/reports/tests/TR-MVP-AGENT-LIVE-DEBUG-001-20261027-R02.md
---

# 验证结果

- AC-01：已保存 Agent 配置后绑定并审批一份合成知识文件，预览与调试在登录浏览器实际调用模型并显示引用和追踪。trace `8f2ded2e-1154-498b-952a-da844648e83c`，状态 succeeded、检索候选 1、分数 0.7739、延迟 3518 ms；回答明确说明合成测试规则和七天窗口，审核动作 human_review，安全拦截原因无。
- AC-02：在用户授权的既有会话只读调试，`query_logistics` 成功，trace `3467d114-5007-4e79-9737-3e6b47d431a7`，延迟 3669 ms。由于无可核验追踪信息，回答要求人工确认；平台发送数零。移除绑定并软删除合成文件后，Agent 绑定文件数零、当前文件有效数零。
- AC-03：手动发布门禁 ValidateOnly/Deploy 通过，迁移 `034_agent_debug_runs`、12 容器、健康入口 200；Agent 调试开关保留，自动回复和通用 LLM 开关继续关闭，店铺与会话许可范围与部署前一致。
- AC-04：源提交 `b1053d4027266df3d334f67db3bae8aa5724e96e` 上后端 2404 passed/43 skipped，隔离 PostgreSQL/pgvector 2444 passed/3 skipped，Ruff/mypy 通过；前端契约 48/48、生产浏览器 113/113、typecheck/build 通过，lint 0 error、8 条既有 warning。合并提交的构建输入与源提交逐目录一致，部署镜像 OCI revision 指向合并提交；现场浏览器和只读数据库迹线复核通过。详见 [R02 本地记录](TR-MVP-AGENT-LIVE-DEBUG-001-20261027-R02.md)和[低敏现场证据](../../../release/evidence/staging/crm-staging-agent-dlp-20261027.json)。

# 适用范围与限制

本任务的分开两条现场链路 **PASS**。单轮同时提问物流与退货时当前路由优先工具，尚未证明同一轮工具和 RAG 联合综合回答；这不是本次 AC 的通过依据。物流缺少可信状态时安全回退，不能视为已核实送达。PR #564 两项 GitHub CI 均在零步骤失败，未执行测试；用户仅针对该 PR 批准以本地验证替代合并门禁，CI 不计通过。未执行 production 发布或真实平台发送。
