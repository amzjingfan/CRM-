# 结构化业务声明测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-AI-02 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-27 |
| 完成日期 | 2026-08-27 |
| 代码位置 | `CRM智能聊天系统/backend/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.13 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 REAL-AI-02。
- 缺陷依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-结构化业务声明-综合测试-001.md`。
- 验收依据：上述正式报告中的 `DEF-REAL-AI02-001/002` 和非阻断安全观察。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复工具证据来源店铺在证据生成前丢失的问题。
- 阻断 Mock 地址提交声明被解释为真实平台写入完成。
- 对可信工具模板缺少结构化声明的低层入口执行失败关闭。

### 3.2 实施范围

- Agent 工具执行封装、可信证据构建、结构化声明策略和回复安全策略。
- 产品回归测试、固定确定性评测、全量与隔离 PostgreSQL 回归。
- REAL-AI-02 内部契约、计划状态和实施记录同步。

### 3.3 非目标

- 不修改公开 HTTP、SSE、前端或公共业务 DTO。
- 不新增数据库迁移、依赖、模型、Prompt 或生产开关。
- 不替代测试工程师关闭正式缺陷，不放行公开回复、翻译、营销或自动回复。
- 不使用自然语言关键词扩张去判定所有“空声明”模型文本，避免重新引入合法文本误杀；模型输出仍无自动交付资格并进入人工复核。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册和适用的 TDD、安全及最小实现 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

工具调用创建时，由 `AgentToolService` 把可信 `ToolInvocation.context.store_id` 固定为 `ExecutedAgentTool.source_store_id`。可信证据构建只读取这一执行来源；当前工作流店铺只在安全策略中作为 `expected_store_id` 独立比较，不能参与证据重新贴标。旧测试替身或替代端口未携带来源时不生成可信证据，从而失败关闭。

结构化声明策略将 `submit_request` 与 `send/update` 一并视为 Mock 写动作。地址修改的 `pending_confirmation` 仍保留审计声明，但安全结果返回 `MOCK_COMPLETION_CLAIM`，不能作为真实平台完成事实。

可信工具模板只有同时携带非空、已校验的对象级声明，才可能取得自动交付资格；声明缺失或为空时返回 `BUSINESS_CLAIM_INVENTORY_MISSING`。

### 5.2 依赖关系

- 前置依赖：REAL-AI-01 当前 Provider 工程范围、现有全栈受控工具契约、019 数据库迁移基线。
- 后续依赖：测试工程师 REAL-AI-02 独立复测、REAL-AI-03/04 回归、REAL-AI-05 真实模型评测。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 当前工作流店铺覆盖工具事实来源 | 跨店铺证据可能被错误授权 | 固定执行来源并在策略层独立比较；缺失来源失败关闭 |
| Mock 地址提交未被视为写动作 | 模拟结果可能被描述为真实平台提交 | 结构化写动作集合加入 `submit_request` |
| 可信来源标签绕过声明清单 | 低层调用可能错误取得自动交付 | 缺少非空声明返回稳定错误码并失败关闭 |
| 旧测试证据未携带新增内部来源字段 | 原测试夹具无法表达来源店铺 | 产品契约测试已覆盖；测试工程师复测时应显式设置来源，不修改历史报告 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/tool_execution.py` | 修改 | 固定并传播工具执行来源店铺 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/reply_rendering.py` | 修改 | 可信证据只读取执行来源，来源缺失失败关闭 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/business_claims.py` | 修改 | Mock 写动作补充 `submit_request` | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/reply_safety.py` | 修改 | 可信工具模板缺少声明时失败关闭 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/workflow.py` | 修改 | 使用新的执行来源证据构建契约 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_business_claims.py` | 修改 | 增加来源、Mock 地址和缺失声明回归 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_tool_execution.py` | 修改 | 验证服务固定执行来源 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_workflow.py` | 修改 | 测试替身模拟生产来源固定行为 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/evals/results/agent-phase4-real-ai02-defect-fix.json` | 新增 | 保存 234 条固定确定性评测摘要 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步 REAL-AI-02 缺陷修复状态 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 同步内部证据来源和失败关闭契约 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：不适用；公开 HTTP/SSE 契约未变化。
- 数据库：无迁移、表、字段或索引变化。
- 配置项：无变化。
- AI：`ExecutedAgentTool` 增加内部可空 `source_store_id`；缺失时不生成可信工具证据。新增安全原因码 `BUSINESS_CLAIM_INVENTORY_MISSING`。

### 6.3 关键实现说明

- `source_store_id` 由受控调用上下文固定，模型、Prompt 和当前策略参数均不能覆盖。
- 字段为可空仅用于兼容不参与授权的旧替身；可信证据生成明确拒绝空来源。
- Mock 判断同时读取执行结果标志和强类型输出中的 `mocked`，防止替代端口只在数据内标记 Mock。
- 本轮没有扩大退款自然语言正则。报告中的空声明高风险文本观察仍由“模型不得自动交付 + 人工复核”控制，后续应在 REAL-AI-05 通过真实模型声明完整性评测继续验证。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯 | `uv run pytest tests/test_agent_business_claims.py -q` | 新增边界在修复前失败 | 68 通过、3 失败 | 通过 |
| 聚焦回归 | `uv run pytest tests/test_agent_business_claims.py tests/test_agent_tool_execution.py tests/test_agent_workflow.py -q` | Agent 声明与工作流通过 | 104 通过 | 通过 |
| 默认全量 | `uv run pytest -q --basetemp .pytest-real-ai02-defect-fix-final` | 无产品失败 | 737 通过、10 跳过 | 通过 |
| 隔离 PostgreSQL | 临时 pgvector PostgreSQL 16，空库升级后执行全量 | 无跳过 | 746 通过 | 通过 |
| 迁移升级 | `uv run alembic upgrade head` | 空库到 head | `019_tiktok_channel_unique (head)` | 通过 |
| 迁移回滚恢复 | `019 → 018 → 019` | 恢复 head | `019_tiktok_channel_unique (head)` | 通过 |
| 静态质量 | Ruff check、Ruff format check、mypy | 无问题 | 全部通过 | 通过 |
| 固定评测 | `scripts.evaluate_phase4` 234 条 | 危险漏放为 0 | 安全/原因码 100%，危险漏放 0；非 live | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞或不良状态 | 通过 |

## 8. 实施结果

- 完成项：开发侧已修复两项正式缺陷对应根因，并完成可信模板低层入口加固。
- 未完成项：测试工程师尚未执行修复后独立复测；正式缺陷不得由开发侧自行关闭。
- 与原方案差异：无公共 DTO 和数据库变更；店铺来源保留在 Agent 内部执行封装。
- 当前状态：开发修复已完成，`DEF-REAL-AI02-001/002` 待测试工程师独立复测确认。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-AI02-FIX-001 | 正式缺陷仍为 Open，需更新独立夹具并复测 | P1 | 测试工程师Agent | REAL-AI-02 复测 |
| R-REAL-AI02-FIX-002 | 真实 DeepSeek 对声明完整性的开放集服从率未评测 | P1 | AIAgent开发工程师Agent、测试工程师Agent | REAL-AI-05 |
| R-REAL-AI02-FIX-003 | 空声明的模型文本仍依赖人工复核；未建立独立语义完整性判定器 | P2 | AIAgent开发工程师Agent | REAL-AI-03、REAL-AI-05 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent。
- 后续任务：测试工程师使用显式 `source_store_id` 构造来源店铺 A、当前工作流店铺 B 的负向样本；复测 Mock 地址 `submit_request`、缺失来源和可信模板缺失声明。
- 必须注意：历史测试报告和证据不覆盖；旧独立样本中的 `origin_store_id` 未写入任何产品对象，修复后夹具必须通过新增内部字段表达真实执行来源。公开 AI 和平台写开关继续关闭。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构决策；本轮未产生新的跨模块架构决策，仅落实既有店铺证据边界。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引将在正式复测完成后由测试工程师更新。
