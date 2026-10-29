---
record_id: TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R04
record_type: test
revision: R04
status: PARTIAL
task_id: MVP-AGENT-STAGING-DEPLOY-001
tested_sha: 39d09e1ace21493c847930ee79a76cd979042335
created_at: '2026-10-29T13:08:25+08:00'
updated_at: '2026-10-29T13:08:25+08:00'
supersedes: docs/reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R03.md
implementation_record: docs/records/implementation/IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R04.md
requirement_ids:
- MVP-AGENT-STAGING-DEPLOY-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
environment: isolated PostgreSQL/pgvector + local frontend + authorized isolated candidate
  DeepSeek process
---

# 测试范围、环境与 TEST_LAYOUT

Windows/Python3.11、本地隔离 PostgreSQL/pgvector test profile；centralized。所有临时输出仅 src/tests/.artifacts。测试最终 subject，未对业务数据库执行全量 pytest。

# 命令和逐项结果

- 临时端口覆盖的独立 postgres-test：alembic upgrade head →041；pytest -c pyproject.toml -q -rs --tb=short → **2438 passed,3 skipped,2 warnings,211.56秒**。三项跳过均需POSIX bash process waiter；两个警告为依赖弃用。自己的测试服务已停止/移除，其他任务服务未触碰。
- backend cwd：ruff check/format --check app scripts ../tests/backend ../tests/integration/postgres ../tests/ai/evaluate_output_review.py →全部通过/427文件；mypy app scripts --no-incremental →252源文件通过；uv lock --check 通过。
- frontend：npm run lint、typecheck、test、build 全部通过，52契约测试。前端源码未变化，未重复完整134项合成浏览器套件；发布后执行目标真实UI验收。
- evaluate_dynamic_agents →16/16；evaluate_phase4 →237/237、unsafe_escape=0。后者覆盖保留的共享旧服务，不冒充新动态语义质量。
- 真实 DeepSeek语义复核合成集→10/10，包含正常字段/日期/金额、联系方式、精确私人地址、公共物流城市、重复隐私值、完整标识及无依据退款/送达保证。该次grounding源码SHA与最终subject相同；不代表任意自然语言零漏报。
- 同一真实授权上下文、Agent v3、候选独立进程：订单列表1047字符，详情1112字符，完整物流970字符，正式建议1309字符；四项review_ready，三工具均succeeded；一包裹八轨迹、无下一页；outbound_delta=0。运行服务文件和开关未改。此前使用旧代码/词法门禁的失败记录保留，不覆盖历史。

# REQ/AC 或门禁与证据映射

本地机器清单：release/evidence/staging/crm-agent-detailed-local-20261029.json。AC-02实现与当前候选验证通过；AC-01发布和AC-03实际UI须统一部署后记录新修订。不得把独立进程成功当作公网已更新。

# 缺陷、未执行项与残余风险

独立审查的三项Important已同批修复：汇总/复核失败、入口外层超时、已知失败用量。先观察9项RED，再38项GREEN，最终完整套件2438/3通过。真实公开页面仍运行45d872c0；未发送真实消息，未发起退款/修改/新OAuth。RAG现有八文件为draft，未作为审批文件现场验收。无production放行。

# 结论和复测条件

本地门禁 PASS，任务总体 PARTIAL；完成单点受审部署后，以Codex浏览器测试三工具详细正文、工作台草稿、无外发并清理已授权合成触发，才能更新任务完成状态。
