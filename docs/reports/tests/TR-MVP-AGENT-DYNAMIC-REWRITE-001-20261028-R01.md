---
record_id: TR-MVP-AGENT-DYNAMIC-REWRITE-001-20261028-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-AGENT-DYNAMIC-REWRITE-001
tested_sha: 7594a1a53ede8e0b65f8987e352d78662bb04c41
implementation_record: docs/records/implementation/IR-MVP-AGENT-DYNAMIC-REWRITE-001-20261028-R01.md
requirement_ids: [MVP-AGENT-DYNAMIC-REWRITE-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows, Python3.11, Node, Chrome, isolated PostgreSQL-pgvector
created_at: 2026-10-28T16:00:24+08:00
updated_at: 2026-10-28T16:08:00+08:00
supersedes: null
---

# 范围与环境
TEST_LAYOUT=centralized；Windows、Python3.11、Node、Next生产构建、本机Chrome；隔离 PostgreSQL/pgvector test profile。无真实模型或TikTok调用，无staging或production变更。新 Agent 的协议链路使用确定性模型端口；这不测真实语义路由准确率。
# 已产生的本次事实
- 定向路由/工具+文件RAG/独立依据/最终撤权/记忆权限/并发/冻结历史20项通过；两轴审查者另独立运行10项和9项通过。
- 最新预算及部署脚本模拟155项通过。此前全量出现11个脚本失败，原因是Windows全局临时部署锁与其他工作树竞争；fake-Docker TEMP/TMP已隔离，产品锁语义未改。失败日志保留，不计通过。
- 前端契约48、生产浏览器114、typecheck/build通过；lint无错误，8项既有warning。浏览器曾因轨迹样例在预取后改变而1项超时，已修复样例时序并全量114通过。
- Ruff check/format、mypy app scripts245文件、uv lock检查通过；迁移034降到并升回039 head通过。初次输入不存在的034标识未改变数据库，校正到034_agent_debug_runs后通过。
- 16条动态协议边界与237条既有安全评测通过；前者数据集SHA256=5d2794b04ed7fac51ac318a1114398745a1ecde21207f1f6dc5113935637e77e，live_model_evaluation=false。
- pip-audit 对锁定运行依赖报告无已知漏洞；候选diff强密钥模式扫描0命中，仅属于有限模式检查。
# 最终候选全套
最终 tested_sha 完整 pytest：2335 passed, 3 skipped, 2 warnings，214.56秒；包括50项真实隔离PostgreSQL/pgvector集成测试。两项warning是既有Starlette/httpx与argon2弃用提示。相同最终候选的静态、前端、构建和评测见下表。本次结论仅为本地范围PASS。
# AC映射
AC-01：多候选容量分批、动态配置与路由；AC-02：原生协议、全部配置工具、参数/权限/无写入；AC-03：显式绑定文件、撤权和无FAQ路径；AC-04：七段、快照、预算、逐字事实、关闭重开及隔离记忆；AC-05：完整后端/数据库、前端、迁移、静态、安全及评测。
# 限制
真实 DeepSeek/TikTok 联合链路、模型误选率/复核可靠性、G5 50客户端P99及G6/G8现场未运行。3项POSIX bash进程等待测试在Windows按平台条件跳过，不能声称已验证Linux行为。没有自动平台发送或生产放行。

# 最终命令与结果

命令从 src/backend 或 src/frontend 执行；Python使用与本锁文件同步的共享reviewed venv，TEST_DATABASE_URL指向本机隔离5433测试库，不连接开发或staging。

| 命令 | 本次结果 |
| --- | --- |
| python -m pytest -q -rs | 2335 passed / 3 POSIX平台条件跳过 |
| ruff check . ../tests/backend ../tests/integration/postgres | PASS |
| ruff format --check . ../tests/backend ../tests/integration/postgres | 453 files PASS |
| mypy app scripts | 245 source files PASS |
| uv lock --check | 187 packages，PASS |
| alembic downgrade 034_agent_debug_runs → upgrade head → current | 039_agent_run_hierarchy head，PASS；隔离测试库 |
| npm run lint / typecheck / test / build | 0 lint errors / 8既有warning；类型、48契约及生产构建PASS |
| UI_BASE_URL=本地3102，UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui | 114 passed，零跳过；API使用合成拦截 |
| python -m scripts.evaluate_dynamic_agents --dataset ../tests/ai/datasets/agent-dynamic-contract-v1.0.0.jsonl --output ../tests/.artifacts/ai/agent-dynamic-contract-final.json | 16/16，live_model_evaluation=false |
| python -m scripts.evaluate_phase4 --dataset ../tests/ai/datasets/agent-phase4-v1.0.0.jsonl --output ../tests/.artifacts/ai/agent-phase4-final.json | 237/237，危险漏放0 |
| uv export --frozen --no-dev --no-emit-project --format requirements-txt --no-hashes；pip-audit --disable-pip --no-deps -r 导出文件 | No known vulnerabilities found；只覆盖锁定运行依赖 |
| 最终候选diff的强密钥模式扫描 | 0命中，不输出原值；不是完整gitleaks扫描 |

普通临时输出位于 src/tests/.artifacts/，完整pytest与浏览器日志保留。真实模型/平台未运行是本次明确边界，不能用上述结果宣称现场链路、延迟或production通过。
