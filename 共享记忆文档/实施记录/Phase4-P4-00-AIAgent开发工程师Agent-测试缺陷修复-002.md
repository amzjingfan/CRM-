# Phase 4 AI 测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；关联 P2-10、P3-11、P3-13、P4-08、P4-10 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、架构师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-22 |
| 完成日期 | 2026-08-22 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的智能回复、翻译、营销和数据指标要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 的 Agent、建议、SSE 和看板接口。
- 架构依据：现有 M04、模块化单体、`agent_runs/tool_calls/metric_daily` 可观测边界；本次未改变平台写边界。
- 任务依据：`AI agent 开发工程师/PLAN-001-AI-Agent工程实施计划-v1.0.md` Phase 4。
- 缺陷依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-001.md` 的 DEF-P4-AI-001～005。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 和上述测试报告回归要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 关闭测试报告中的五项工程缺陷，并提供可独立复测的代码、迁移和低敏证据。

### 3.2 实施范围

- 回复安全规则、公开翻译契约、店铺回复画像、线上 AI 指标、营销统一运行追踪。
- Alembic 018、后端自动化测试、共享接口和 AI 规范同步。

### 3.3 非目标

- 不执行真实模型、真实平台、50 并发和五天稳定性门禁。
- 不修改前端页面；后端已经提供翻译、回复画像和指标字段，前端展示由全栈工程师接入。
- 不从无标签线上流量伪造意图准确率。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase4、P4-00、M04 和 AIAgent开发工程师Agent 主责。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

```text
回复草稿 → 动作/时态/证据规则矩阵 → 不安全清空草稿
工作流翻译 → 低敏 SuggestionView.translation → JSON/SSE result
受限 reply_profile → Agent 管理 API → knowledge_scope.reply_profile
agent_runs/tool_calls → metric_daily v2 → dashboard metrics
营销 AI → agent_runs → 同 agent_run_id 的受控 tool_calls
```

### 5.2 依赖关系

- 前置依赖：Phase 4 原实现、迁移 017、现有 Agent/SSE/营销/看板模块。
- 后续依赖：测试工程师独立复测；全栈工程师接入前端展示；架构师继续管理真实平台与生产门禁。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 安全规则误杀政策说明 | 正常 FAQ 无法使用 | 增加条件句、政策说明和真实查询证据正向用例 |
| 翻译公开字段泄露模型元数据 | 隐私和供应商信息暴露 | 公开类型只映射消息关联、语言和译文 |
| 准确率被无标签流量伪造 | 指标误导 | 仅保留标签计数；无标签时公开准确率为 `null` |
| 营销追踪缺少会话外键 | 无法创建合法 AgentRun | 模型调用前要求同店铺客户会话，缺失则失败关闭 |
| 成本估算与账单不一致 | 预算误判 | 单价必须显式配置，默认 0 并返回未配置状态 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/agent/reply_safety.py` | 修改 | 增加退款、地址、送达和物流中英文动作证据矩阵 | AIAgent开发工程师Agent |
| `backend/app/chat/schemas.py`、`service.py` | 修改 | 增加低敏公开翻译类型和映射 | AIAgent开发工程师Agent |
| `backend/app/agent_management/schemas.py`、`service.py`、`router.py` | 修改 | 增加受限回复画像写入、读取和审计 | AIAgent开发工程师Agent |
| `backend/app/agent/models.py`、`repository.py` | 修改 | 增加首输出字段和营销运行终态记录 | AIAgent开发工程师Agent |
| `backend/app/marketing/worker.py` | 修改 | 营销生成创建 AgentRun，工具调用关联同一运行 ID | AIAgent开发工程师Agent |
| `backend/app/dashboard/models.py`、`aggregation.py`、`schemas.py`、`service.py` | 修改 | 聚合并公开 RAG、工具、TTFT、Token、成本和标签口径 | AIAgent开发工程师Agent |
| `backend/app/shared/config/settings.py`、`.env.example` | 修改 | 增加显式输入/输出 Token 单价配置 | AIAgent开发工程师Agent |
| `backend/migrations/versions/018_add_phase4_ai_observability.py` | 新增 | 可逆增加首输出与 AI 每日指标字段 | AIAgent开发工程师Agent |
| `backend/evals/agent-phase4-v1.0.0.jsonl` | 修改 | 纳入测试报告六条独立高风险样本 | AIAgent开发工程师Agent |
| `backend/tests/test_agent_phase4.py`、`test_phase4_domain.py` | 修改 | TDD 覆盖缺陷、正向防误杀和公开契约 | AIAgent开发工程师Agent |
| `tests/integration/test_phase4_ai_observability_postgres.py` | 新增 | PostgreSQL 指标和营销链路测试 | AIAgent开发工程师Agent |
| `README.md`、`backend/app/agent/README.md`、共享接口文档、`AI-005` | 修改 | 同步迁移、接口、指标和追踪边界 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：`SuggestionView` 增加可空 `translation`；Agent 创建/更新增加受限 `reply_profile`；`DashboardMetrics` 增加 AI 在线指标。
- 数据库：迁移头升级为 `018_ai_observability`；`agent_runs.first_output_latency_ms`；`metric_daily` 增加 RAG、工具、首输出、Token、成本和有标签意图计数。
- 配置项：`LLM_INPUT_COST_PER_MILLION_USD=0`、`LLM_OUTPUT_COST_PER_MILLION_USD=0`。
- AI：Prompt 版本未改变；确定性安全策略和版本化回归样本增强。

### 6.3 关键实现说明

- 六条独立危险样本全部由代码门禁阻断；普通退货政策、条件句和真实物流查询结果保持允许。
- Mock 地址、发券和发送即使工具成功，也不能描述为真实平台完成。
- 翻译公开对象不包含 Provider、模型、Token、耗时或模型原始输出。
- 回复画像只允许四种语气、三种回复语言策略、两种客服语言和最长 80 字符清洗品牌名。
- 线上意图准确率必须来自人工/评测标签；当前无标签时计数为 0、准确率为 `null`。
- 营销运行摘要只保存事件 ID、Prompt、安全状态、错误码、Token 和时延，不保存客户消息、评价或文案正文。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯 | Phase 4 聚焦测试 | 原缺陷可复现 | 首轮 8 项失败；Mock 地址另有 1 项失败 | 通过 |
| Phase 4 聚焦 | `pytest tests/test_agent_phase4.py tests/test_phase4_domain.py` | 全部通过 | 42 passed、1 warning | 通过 |
| 后端默认回归 | `uv ... run pytest` | 无退化 | 162 passed、6 skipped、2 warnings | 通过 |
| 隔离 PostgreSQL 全量 | `scripts/run-postgres-integration-tests.ps1` | 迁移和数据库项通过 | 168 passed、0 skipped、2 warnings | 通过 |
| 迁移回滚 | `upgrade head → downgrade 017 → upgrade head → current` | 可逆且 head 正确 | `018_ai_observability (head)` | 通过 |
| Ruff | `ruff check app migrations scripts tests` | 无违规 | All checks passed | 通过 |
| mypy | `mypy app scripts` | 无类型错误 | 147 source files 通过 | 通过 |
| 真实模型/平台/性能 | 需轮换后密钥与候选环境 | 正式生产证据 | 未执行，不使用 Fake 冒充 | 未执行 |

## 8. 实施结果

- 完成项：DEF-P4-AI-001～005 的代码、迁移、测试和文档修复。
- 未完成项：前端展示、真实模型/平台、50 并发和五天稳定性正式门禁。
- 与原方案差异：为避免新增营销追踪实体，复用合法会话外键的统一 `agent_runs`；无会话时模型调用前失败关闭。
- 当前状态：缺陷修复开发验证完成，等待测试工程师独立复测；Phase 4 生产放行状态不因本记录自动改变。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-P4-FIX-001 | 测试工程师尚未独立复测五项缺陷 | P1 | 测试工程师Agent | Phase4/P4-00 复测 |
| R-P4-FIX-002 | 真实模型翻译、营销和安全评测未执行 | P1 | 测试工程师Agent、AIAgent开发工程师Agent | Phase4/P4-08 |
| R-P4-FIX-003 | SSE 50 并发和五天稳定性未执行 | P1 | 测试工程师Agent | Phase4/P4-10 |
| R-P4-FIX-004 | 前端尚未展示回复画像、翻译和新增指标 | P2 | 全栈开发工程师Agent | 后续全栈增量 |
| R-P4-FIX-005 | 三个平台写仍为 Mock | P0 | 架构师Agent、全栈开发工程师Agent | 真实平台接入任务 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent、架构师Agent。
- 后续任务：测试工程师复测 DEF-P4-AI-001～005；全栈工程师接入前端；架构师维持生产发布门禁。
- 必须注意：迁移 head 已变为 018；单价为 0 表示未配置；意图准确率为空不是 0 分；Mock 发送不得解释为真实触达。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步现有架构边界；未新增独立 ADR。
- [x] 已同步实施状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [ ] 测试报告索引将在测试工程师正式复测后更新。
