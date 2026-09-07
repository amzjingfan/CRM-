# 业务工具与安全接管实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase3 |
| 任务编号 | P3-00 阶段汇总；关联业务工具和人工接管任务 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、架构师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-21 |
| 完成日期 | 2026-08-21 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中智能回复、人工接管和安全审计要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 中工作台、业务工具和 AI 工程师交接边界。
- 架构依据：`架构师/ARCH-001-SYS-系统总体架构设计-v1.2.md`、`架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.1.md`。
- 任务依据：`AI agent 开发工程师/PLAN-001-AI-Agent工程实施计划-v1.0.md` 中 Phase 3。
- 全栈交接：`共享记忆文档/实施记录/Phase3-P3-00-全栈开发工程师Agent-知识库业务工具与主动营销阶段汇总-001.md`。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 中工具调用、人工接管和可审计要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 通过全栈工具边界接入七个白名单工具。
- 完成工具结果解释、安全复核、置信度决策和转人工闭环。
- 确保工具权限、店铺隔离、超时、幂等、审计和运行追踪可验证。

### 3.2 实施范围

- Agent 工具运行上下文、批准写操作和低敏结果契约。
- SQLAlchemy 工具执行器及强类型输入/输出校验。
- LangGraph 工具执行、解释、复核、接管节点。
- `agent_runs → tool_calls → audit_logs` 追踪关系。
- 单元测试、隔离 PostgreSQL 集成测试、README 和内部规范同步。

### 3.3 非目标

- 不新增公开 HTTP API、`/suggest`、SSE 或前端功能。
- 不新增数据库迁移，迁移头保持 `015_vector_ops`。
- 不实现真实 TikTok、Shopee、Amazon 平台联调或 AI 营销话术。
- 不由本记录生成正式测试报告或正式验收结论。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及代码时已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

采用 `AgentWorkflowService → AgentToolService → SqlAlchemyToolExecutor` 单一执行边界。工作流用确定性代码选择工具；查询参数来自可信业务上下文，写工具使用预批准参数和幂等键。执行器统一创建 `tool_calls`，完成店铺、权限、参数、输出、超时、幂等和审计处理。成功结果进入独立解释和复核 Prompt；任一失败、未知结果或无依据完成声明都隐藏草稿并转人工。

### 5.2 依赖关系

- 前置依赖：Phase 1 意图分类、Phase 2 RAG/LangGraph、全栈 Phase 3 `tool_calls/audit_logs` 和业务模型。
- 后续依赖：全栈工程师接入受认证的工作台 AI 建议接口；测试工程师执行独立工具和 Agent 回归。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 客户文本诱导越权工具调用 | 跨店铺读取或未授权写入 | 工具名由确定性规则选择，资源 ID、权限和写参数只取可信上下文 |
| 平台写超时后真实结果未知 | 重试导致重复消息 | 返回 `unknown/TOOL_RESULT_UNKNOWN`，禁止自动重试并转人工 |
| 模型虚构工具成功 | 错误承诺或客户损失 | 只解释成功结果，引用本次调用 ID，并执行独立完成声明复核 |
| Mock 被误认为真实结果 | 错误自动回复 | Mock 结果最高进入人工复核，结果和审计均保留 `mocked` |
| 追踪数据泄露客户信息 | 隐私和合规风险 | 摘要只保存调用元数据，不保存地址、消息、物流号或原始结果 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/tools/contracts.py` | 修改 | 七工具强类型输入/输出、权限、超时、幂等、错误和审计元数据 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/tools/executor.py` | 新增 | SQLAlchemy 白名单执行器、店铺隔离、权限、超时、幂等和审计 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/tool_execution.py` | 新增 | 可信上下文到工具调用的确定性组装服务 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/workflow.py` | 修改 | LangGraph 工具执行、解释、复核、置信度和接管节点 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/schemas.py` | 修改 | 工具上下文、批准动作、工具答案和工作流结果契约 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/workflow_prompt.py` | 修改 | 工具解释与完成声明复核 Prompt，递归脱敏工具数据 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/repository.py` | 修改 | `agent_runs` 增加低敏工具调用摘要 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/factory.py` | 修改 | 装配 Agent 工具服务和 SQLAlchemy 执行器 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/`、`CRM智能聊天系统/tests/integration/` | 新增/修改 | 工具契约、工作流、安全、超时、幂等和 PostgreSQL 集成测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/README.md` | 修改 | 同步 Phase 3 能力、边界和风险 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/AI-004-TOOL-业务工具与安全接管规范-v1.0.md` | 新增 | 正式工具与接管规范 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 更新内部 Agent 命令、结果和执行边界 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：未新增或修改公开 HTTP API。
- 数据库：未新增迁移；继续使用 `agent_runs`、`tool_calls`、`audit_logs`，迁移头为 `015_vector_ops`。
- 配置项：未新增环境变量，未记录或输出真实密钥。
- AI：工作流版本升级为 `faq-agent-workflow-v1.1.0`，新增 `tool-answer-v1.0.0` 和 `tool-grounding-review-v1.0.0`。

### 6.3 关键实现说明

- 七个工具输入和成功输出均拒绝额外字段；输出异常不能进入 Agent 上下文。
- 查询使用可信订单/客户 ID；地址、发券和平台发送必须有精确批准对象。
- 平台发送不由客户文本直接选择；工作流固定 `send_performed=false`。
- 同键同请求重放原记录，同键不同请求返回稳定冲突且不重复业务动作。
- 平台发送超时返回 `unknown`；其他超时返回 `timeout`，均转人工。
- 转人工工具实际成功时返回 `transfer_performed=true`；失败时仍保留转人工建议但明确为 `false`。
- 低敏摘要只记录工具调用 ID、名称、状态和错误码。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 锁文件 | `uv --offline --cache-dir .uv-cache lock --check` | 锁文件一致 | 解析 124 个包，无变化 | 通过 |
| Ruff | `uv ... run ruff check app migrations scripts tests` | 无 lint 错误 | All checks passed | 通过 |
| 格式 | `uv ... run ruff format --check app migrations scripts tests` | 全部已格式化 | 最终检查通过 | 通过 |
| 类型检查 | `uv ... run mypy app scripts` | 无类型错误 | 118 个源文件通过 | 通过 |
| 后端回归 | `uv ... run pytest -q` | 原能力无回归 | 109 passed，4 skipped，2 个依赖弃用警告 | 通过 |
| PostgreSQL 集成 | 设置隔离 `TEST_DATABASE_URL` 后运行 `test_agent_tools_postgres.py` | 店铺、权限、幂等、审计通过 | 2 passed | 通过 |
| 数据库迁移 | 隔离库 `alembic upgrade head && alembic current` | 空库升级到 head | `015_vector_ops (head)` | 通过 |
| Compose | `docker-compose config --quiet` | 配置可解析 | 最终检查通过 | 通过 |

## 8. 实施结果

- 完成项：七工具契约、受控执行、结果解释、安全复核、人工接管、低敏追踪、单元和数据库集成验证。
- 未完成项：真实平台联调、公开 AI API、前端展示、SSE 和 AI 营销话术，均不属于本阶段。
- 与原方案差异：无数据库迁移；在既有 `015` 表结构上完成。
- 当前状态：已完成工程实现和主责 Agent 验证，等待测试工程师独立复测并形成正式测试报告。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-AI-TOOL-001 | 三个平台仍为契约级 Mock，不能视为真实发送完成 | P1 | 全栈开发工程师Agent | 真实平台接入任务 |
| R-AI-TOOL-002 | `/suggest`、SSE 和前端工具结果展示尚未接入 | P1 | 全栈开发工程师Agent | 后续工作台 AI 接入任务 |
| R-AI-TOOL-003 | 正式独立安全、并发和端到端报告尚未生成 | P1 | 测试工程师Agent | Phase3 独立复测 |
| R-AI-TOOL-004 | Starlette TestClient 和 argon2 依赖存在弃用警告 | P2 | 全栈开发工程师Agent | 依赖维护任务 |

## 10. 交接事项

- 交接给：全栈开发工程师Agent、测试工程师Agent、架构师Agent。
- 后续任务：把可信 `tool_context` 接入受认证工作台 AI 建议入口；执行独立工具、审计和端到端复测。
- 必须注意：不得从客户消息构造权威资源 ID；不得移除写工具批准、Mock 降级、`unknown` 状态或 `send_performed=false` 约束。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构边界；本次无新架构决策或迁移。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引将在正式测试完成后更新。
