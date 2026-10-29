---
record_id: TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R05
record_type: test
status: PARTIAL
revision: R05
task_id: MVP-AGENT-STAGING-DEPLOY-001
created_at: '2026-10-29T17:11:09+08:00'
updated_at: '2026-10-29T17:11:09+08:00'
tested_sha: ff4d5e262bed31f07d9ec04a7c021c1a2b7fa9ba
final_sha: ff4d5e262bed31f07d9ec04a7c021c1a2b7fa9ba
implementation_record: docs/records/implementation/IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R05.md
requirement_ids:
- MVP-AGENT-STAGING-DEPLOY-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
supersedes: docs/reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R04.md
---

# 测试范围与结论

本地门禁 PASS；任务总体 PARTIAL，因为用户要求等待部署批准，新页面和v4配置尚未进入运行服务。subject=ff4d5e262bed31f07d9ec04a7c021c1a2b7fa9ba，应用树与完整测试source=fa18072e9ab550ffe33627f107cb91c3e0bbd756相同。机器证据：release/evidence/staging/crm-agent-output-ui-local-20261029.json。

# 命令、环境和实际结果

- 独立 Compose postgres-test/tmpfs、临时回环端口，Alembic到041后完整 pytest：2514 passed/3 skipped；三个跳过只涉及Windows没有POSIX进程等待器。容器已仅按本任务项目名清理，未触碰其他任务数据库。
- 最终subject仅新增评测统计脚本/测试，应用树未变；最终subject新统计回归8 passed，含实际异步评测在expected=false时遇Timeout必须报告失败。不是一次2522项全量运行。
- Ruff check/format：437文件；mypy app scripts：255；uv lock --check通过。命令路径见src/tests/README.md，临时日志均src/tests/.artifacts/agent-http-output-final-20261029。
- 前端 npm lint/typecheck/test：0 errors/8既有warnings、52 passed；生产前端镜像构建通过。本地生产服务的workspace-experience与ui-regressions：105 passed，无平台发送。4视口长稿/译文、关闭/Esc保稿、4425字符完整保留、超限禁止送审发送均覆盖。第一次较早运行有一条分类URL异步断言失败，未改产品或降低断言，稳定构建后两轮105通过；原失败日志保留。
- 本地linux/amd64前后端镜像构建成功，隔离无网络的生产依赖导入冒烟通过；OCI revision为fa180，应用/前端内容与subject一致。没有推送 registry 或部署。
- deterministic dynamic 16/16、共享旧安全回归237/237；后者不冒充新动态语义准确率。

# 真实候选隔离模型与只读工具

fa180、已授权现有买家上下文、实际v4草稿仅内存投影：订单列表1638、详情1715、全物流1834、简短465、正式建议1745字符，五类均review_ready/英文；真实编号匹配，无Markdown/隐私占位/内部技术文案；一包裹八节点的说明、日期、时分和UTC均呈现。全物流正文未逐字展示秒，工具证据保留原秒，不能宣称秒级逐字输出。正式运行曾一次物流工具失败，模型在同次运行重查成功，原失败记录保留。5条运行的持久用量均与SDK逐轮记录一致。outbound_delta=0，发布版本仍3。

发布语义16/16（3e source），helper/script/dataset与subject逐项SHA相同，真实外层exit0，明确复用未重跑。输出v2.3原轮有14条完成、一条APITimeout；旧统计打印15通过属于误报，已修复并保留。使用新subject脚本仅按原冻结行补测unknown-order-identifier一次，明确unsupported/answer_not_grounded/semantic_review_completed=true，exit0。现覆盖15个不同样例，不声称一次15/15运行。原超时请求用量未知，未当作0或完整账单。

# 安全、未执行项和残余风险

前端依赖审计0报告项；新增Markdown依赖0报告项。全后端扫描报告既有Mako1.4.1 Windows TemplateLookup URI问题（CVE-2026-102991）；本轮未发现用户可控模板名入口且运行镜像Linux，这是适用性分析，不宣称所有依赖零漏洞。来源：https://nvd.nist.gov/vuln/detail/CVE-2026-102991 。本批不升级该无关传递依赖。

未做新候选公网UI/发布/production验收、真实平台发送或退款；未绑定RAG文件，不将本次三工具结果冒充文件检索验收。模型判定存在非确定性，旧失败如实保留；发布后必须重新现场验收，合成触发最终清理也等待现场成功。公开服务仍为e3fc，用户另批准前禁止切换。
