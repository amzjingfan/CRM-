---
record_id: TR-MVP-AGENT-TOOL-SUITE-001-20261028-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-AGENT-TOOL-SUITE-001
tested_sha: 6f40179ceab9ace571232b94a158366c592aed19
implementation_record: docs/records/implementation/IR-MVP-AGENT-TOOL-SUITE-001-20261028-R01.md
requirement_ids: [MVP-AGENT-TOOL-SUITE-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows, Python3.11.15, Node24.19.0, Next16.4.2, isolated PostgreSQL-pgvector
created_at: 2026-10-28T19:23:59+08:00
updated_at: 2026-10-28T19:23:59+08:00
supersedes: null
---

# 范围与本次命令

TEST_LAYOUT=centralized；临时日志、JUnit、截图及导出依赖位于src/tests/.artifacts/agent-tool-suite，不入仓。仅本机合成数据和确定性模型/平台端口，不连接staging，不发送平台消息。

| 命令 | 本次结果 |
| --- | --- |
| python -m pytest -q --tb=short --junitxml=测试临时目录/backend-junit.xml | 最终subject：2375 passed / 3 POSIX平台条件跳过，221.50秒；包括真实隔离PostgreSQL/pgvector集成 |
| ruff check/format --check app scripts migrations ../tests/backend ../tests/integration/postgres | PASS；465文件已格式化 |
| mypy app scripts | 252源文件PASS |
| npm run lint / typecheck / test / build | 0 lint error / 8既有warning；类型、48契约及生产构建PASS |
| UI_BASE_URL=本机3102 UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui | 最终subject运行121 passed，0跳过；API合成拦截 |
| alembic upgrade head → downgrade039_agent_run_hierarchy → upgrade head | 独立临时数据库040头/唯一约束/索引PASS；验证后仅删除本次创建的空测试库 |
| scripts.evaluate_dynamic_agents，agent-dynamic-contract-v1.0.0.jsonl | 16/16 PASS；live_model_evaluation=false |
| scripts.evaluate_phase4，agent-phase4-v1.0.0.jsonl | 237/237 PASS；危险漏放0 |
| uv lock --check | 187依赖解析PASS |
| uv export --frozen --no-dev --no-emit-project --format requirements-txt --no-hashes；uvx pip-audit --disable-pip --no-deps -r 导出文件 | 锁定运行依赖无已知漏洞 |
| 最终候选diff强密钥模式扫描 | 0命中；有限模式检查，非完整gitleaks |

生产构建/前端lint/契约与迁移往返在4ef62d52执行，最终subject仅修复后端物流DLP及其断言；前端树b096d22f111b5d825a97684bcaba3d4f912f82c6、前端测试树db460113d89258aa4e1523eb21604e9850ee9531、迁移树becb98244bac2d854034fdae8983306b13c48729与最终subject逐一相同。最终subject重跑完整后端、生产浏览器、mypy、AI评测及依赖审计，格式检查覆盖最后改动。

# 验收映射与失败闭环

AC-01：test_agent_tool_suite验证12业务+4提议、6类、10只读/2内部写/4确认，所有@toolSchema及未知名称拒绝。AC-02：test_agent_business_tools/product_details/tiktok_read覆盖多订单选单、伪造引用、全包裹/轨迹、长描述与JSON转义连续分页、售后订单归属与记录、商品参数/HTML、优惠条件。AC-03：真实PostgreSQL并发重试只留一条内部记录，含审计、跨店/客户拒绝、无消息/转交变化。AC-04：6项Agent浏览器覆盖分组、搜索、保存、知识跳转、迟到目录/跨店记录清空；原生完整路由/工具+绑定RAG/汇总与最终撤权、冻结历史、记忆范围均通过。AC-05：上表全量本地门禁与040往返通过。

首次完整后端2368通过/3跳过、1旧迁移头断言失败，已更新040并保留祖先校验；首次浏览器120通过/1保存请求同步race，等待真实PATCH响应后最终121通过。两轴审查发现候选澄清丢失、事件单号错误、售后旧门禁和组合长字段分页，均先补失败断言后修正。二次D5全量2375/3通过；4ef全量因审查发现双DLP时间问题而主动中止，不计通过；最终6f完整重跑结果如上。2项后端warning为既有Starlette/httpx和argon2弃用提示。

# 限制与复测条件

本地PASS不代表真实模型语义路由、独立复核可靠性、官方店铺字段完整性或现场时延通过。官方OAS只有旧Search Returns202309，202602路径/scope来自官方docv2，真实站点需部署获批后验收。没有真实模型/TikTok联合调用、Linux跳过项、G5/G6现场或production放行；公开文档UI不可用记录UI_UNAVAILABLE。展示截图已本地检查，未作为现场证据。
