# Phase 4 AI 二次测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；关联 P4-08、P4-10 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、架构师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-22 |
| 完成日期 | 2026-08-22 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中智能回复、数据看板和安全接管要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 中 Agent 与 `/dashboard/metrics` 契约。
- 架构依据：现有 M04、模块化单体、`agent_runs/metric_daily` 可观测边界；本次未改变平台写边界。
- 任务依据：`AI agent 开发工程师/PLAN-001-AI-Agent工程实施计划-v1.0.md` Phase 4，以及 `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-002.md` 中 DEF-P4-AI-006、DEF-P4-AI-007。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 和测试报告中的二次回归要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 消除安全退款流程说明被误判为未授权退款承诺的问题，同时保持危险退款执行话术零漏放。
- 让看板 1/7/30 天首输出 P95 使用周期内原始样本计算，避免“每日 P95 最大值”放大少量异常样本。

### 3.2 实施范围

- M04 确定性回复安全规则、版本化 Phase 4 安全评测集。
- 看板周期首输出 P95 查询、PostgreSQL 集成测试、店铺时区边界。
- README、AI 规范、共享接口说明和实施记录同步。

### 3.3 非目标

- 不修改 Prompt、模型、RAG、工具 Schema、公开 API 字段或前端。
- 不新增数据库迁移，不改变 `metric_daily` 每日聚合口径。
- 不执行真实模型、真实平台、50 并发或五天稳定性正式门禁。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及代码时已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase4、P4-00、M04 和 AIAgent开发工程师Agent 主责。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

安全门禁将“已退款、将直接退款、为您办理退款”等执行或完成语义，与“说明政策、指导申请、告知流程、协助提交申请”等信息/申请语义分开。危险执行承诺仍返回 `UNAUTHORIZED_COMMITMENT`；安全流程说明继续进入后续依据复核。

周期 P95 不再从 `metric_daily` 的每日 P95 取最大值。服务按店铺 IANA 时区计算周期 UTC 边界，并通过 PostgreSQL `percentile_disc(0.95)` 对周期内非空 `agent_runs.first_output_latency_ms` 原始样本执行 nearest-rank 聚合。每日指标仍用于其他可加权或可汇总指标。

### 5.2 依赖关系

- 前置依赖：迁移 `018_ai_observability`、Phase 4 回复安全策略、看板服务和测试工程师综合测试报告 002。
- 后续依赖：测试工程师独立复测并生成新的正式测试报告；架构师依据正式结论维护生产门禁。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 放宽中文退款规则导致危险承诺漏放 | 客服越权承诺退款 | 仅允许政策、条件、流程和申请协助语义；保留既有危险样本并运行 35 条版本化回归 |
| 周期原始样本查询增加数据库开销 | 看板查询延迟上升 | 使用店铺与时间范围过滤、数据库内百分位聚合，不把原始样本加载到应用内存 |
| 店铺时区边界错误 | 统计跨日污染 | 集成测试覆盖 UTC 与 Asia/Shanghai 日界线前后样本 |
| 工程回归被 Fake/Mock 误当正式门禁 | 错误开放生产能力 | 明确区分确定性回归与真实模型/平台/并发/稳定性测试 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/agent/reply_safety.py` | 修改 | 收窄中文退款承诺规则，区分执行承诺与政策/申请流程说明 | AIAgent开发工程师Agent |
| `backend/app/dashboard/service.py` | 修改 | 使用原始 AgentRun 样本计算周期 P95，并遵循店铺时区 | AIAgent开发工程师Agent |
| `backend/evals/agent-phase4-v1.0.0.jsonl` | 修改 | 增加 5 条安全退款流程说明样本 | AIAgent开发工程师Agent |
| `backend/evals/results/agent-phase4-deterministic.json` | 新增 | 保存 35 条确定性安全回归的低敏汇总结果 | AIAgent开发工程师Agent |
| `backend/tests/test_agent_phase4.py` | 修改 | 增加报告给出的 5 条中文正向防误杀用例 | AIAgent开发工程师Agent |
| `tests/integration/test_phase4_ai_observability_postgres.py` | 修改 | 覆盖原始周期 P95、1/7/30 天、空数据、单样本和时区边界 | AIAgent开发工程师Agent |
| `README.md`、`backend/app/agent/README.md` | 修改 | 同步安全语义、周期 P95 口径、评测数量和迁移头 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.0.md` | 修改 | 同步安全规则与周期百分位规范 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 同步后端既有字段的统计和安全语义口径 | AIAgent开发工程师Agent |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记本次实施记录 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无字段或路由变更；明确 `/dashboard/metrics` 的周期首输出 P95 计算口径。
- 数据库：无迁移、表、字段或索引变更；迁移头保持 `018_ai_observability`。
- 配置项：无。
- AI：Prompt、模型、RAG、工具和阈值均未改变；仅收窄确定性中文安全规则并增加版本化正向样本。

### 6.3 关键实现说明

- 安全策略不依赖模型自报安全状态，继续使用确定性原因码失败关闭。
- P95 使用 PostgreSQL `percentile_disc(0.95)`，与测试报告要求的 nearest-rank 口径一致。
- 时间范围统一使用半开区间 `[start_utc, end_utc)`，避免跨店铺时区日界线重复或遗漏。
- 聚合只读取首输出延迟、店铺和时间字段，不读取客户消息、知识正文、模型响应或密钥。
- 空周期返回 `null`，单样本周期返回该样本值。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯：退款指导 | 报告 5 条中文样本调用 `ReplySafetyPolicy.evaluate` | 原缺陷可复现 | 5 条均错误命中 `UNAUTHORIZED_COMMITMENT` | 通过 |
| TDD 红灯：周期 P95 | 100×100ms + 1×9000ms PostgreSQL 场景 | 原缺陷可复现 | 原实现返回 9000ms，正确值为 100ms | 通过 |
| Phase 4 聚焦回归 | `pytest tests/test_agent_phase4.py tests/test_phase4_domain.py -q` | 全部通过 | 47 passed、1 warning | 通过 |
| 确定性安全评测 | `python -m scripts.evaluate_phase4 ...` | 无危险漏放 | 35 条；安全准确率 100%；原因码准确率 100%；危险漏放 0 | 通过 |
| 静态与类型检查 | `uv lock --check`、`ruff check`、`ruff format --check`、`mypy app scripts` | 全部通过 | 197 个文件格式通过；mypy 147 个源文件无问题 | 通过 |
| 后端默认回归 | `uv run --frozen pytest -q` | 无退化 | 167 passed、7 skipped、2 warnings | 通过 |
| 隔离 PostgreSQL 全量 | `scripts/run-postgres-integration-tests.ps1` | 数据库测试全部执行 | 174 passed、0 skipped、2 warnings | 通过 |
| P95 扩展边界 | PostgreSQL 定向集成测试 | 1/7/30 天、空、单样本、时区均正确 | 1 passed | 通过 |
| Compose 与迁移头 | `docker compose config --quiet`、`alembic heads` | 配置有效且 head 不变 | `018_ai_observability (head)` | 通过 |

## 8. 实施结果

- 完成项：DEF-P4-AI-006、DEF-P4-AI-007 的代码修复、自动化测试、版本化安全评测和文档同步。
- 未完成项：测试工程师独立复测；真实模型、真实平台、50 并发和五天稳定性正式门禁。
- 与原方案差异：无数据库迁移；周期 P95 直接复用已有 `agent_runs.first_output_latency_ms` 原始事实字段。
- 当前状态：工程修复已完成，等待测试工程师依据权威报告执行独立复测。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-P4-AI-008 | DEF-P4-AI-006/007 尚未由测试工程师独立复测 | P2 | 测试工程师Agent | Phase4 P4-00 复测 |
| R-P4-AI-009 | 真实模型质量、真实平台写、50 并发和五天稳定性门禁尚未完成 | P1 | 测试工程师Agent、架构师Agent | 生产启用前 |
| R-P4-AI-010 | PostgreSQL 周期百分位查询需在生产数据量下持续观察尾延迟 | P2 | 全栈开发工程师Agent、测试工程师Agent | Phase4 运营监控 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、全栈开发工程师Agent。
- 后续任务：对综合测试报告 002 的 DEF-P4-AI-006/007 执行独立复测并生成新的正式测试报告。
- 必须注意：全局自动回复、AI 翻译、AI 营销和真实平台写门禁继续保持关闭；本记录不是正式测试结论。

## 11. 文档同步

- [x] 已同步接口变化（无字段变化，仅同步语义和统计口径）。
- [x] 已同步架构决策（无新增 ADR，保持既有数据边界）。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [ ] 测试报告索引将在正式测试完成后更新。
