# Agent 对话编排实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase2 |
| 任务编号 | P2-07 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、架构师Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-08-20 |
| 完成日期 | 未完成 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：PRD V2.0 中“意图→RAG→LLM→置信度→回复/转人工”。
- 接口依据：管理端接口文档第 11.4 节内部 AI 交接契约。
- 架构依据：系统总体架构 v1.1 中单 Agent 显式状态、受控工具和平台隔离。
- 任务依据：开发任务拆解 P2-07。
- 验收依据：MVP 范围中的 0.80/0.60 置信度规则、低置信度和无知识转人工。
- 代码规范：共享代码编写手册。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 使用 LangGraph 编排意图、工具门禁、RAG、回答、复核、置信度和终态。
- 一次工作流只创建一条 `agent_runs`，记录安全链路摘要。
- 高分只返回 `AUTO_REPLY_READY`，不执行平台发送。

### 3.2 实施范围

- 内部 `AgentWorkflowCommand/Result`。
- FAQ 回答和依据复核 Prompt。
- 确定性工具需求识别、三项最小值置信度和保守转人工。
- Agent 工厂、运行追踪、失败/超时/取消记录和确定性测试。

### 3.3 非目标

- 不新增 `/suggest`、`/chat/query` 或 SSE。
- 不执行任何工具，不写会话、消息、订单或平台数据。
- 不实现翻译、AI 营销或多 Agent。

## 4. 实施前确认

- [x] 已读取共享记忆、代码手册、AI 计划和相关 Skill。
- [x] 已读取 Phase2、Phase3 全栈交接及 Phase1 AI 测试结论。
- [x] 已确认 M04 编号和现有 `agent_runs` 字段足够，不新增迁移。
- [x] 已确认 `/suggest` 由全栈工程师后续负责。
- [x] 已确认自动回复只能返回就绪决策。

## 5. 实施方案

### 5.1 方案说明

LangGraph 使用无循环显式节点：上下文、意图、工具门禁/RAG、草稿、安全复核、置信度和三个终态。Phase1 分类器新增不创建运行记录的 `infer`，原有独立分类入口保持兼容。

答案必须引用本次 Top 5，代码先验证引用子集，随后用独立复核 Prompt 检查依据和安全。最终分数为意图、检索和复核分数最小值。未知、混合、上下文不足、拒绝、工具需求、无知识、非法引用和安全失败强制转人工。

### 5.2 依赖关系

- 前置依赖：P2-01/P2-02、P2-03、迁移 009、Phase3 白名单工具定义。
- 后续依赖：全栈建议接口、AI 工具执行、SSE 和正式端到端测试。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 模型决定动作 | 越权自动发送 | 动作和阈值完全由代码计算 |
| FAQ Prompt 注入 | 操纵答案 | 知识视为不可信数据，引用子集校验并独立复核 |
| 重复运行记录 | 链路割裂 | 完整工作流复用 `infer`，只创建一条 `agent_runs` |
| 高分被误认为已发送 | 产生业务副作用 | 使用 `AUTO_REPLY_READY` 和固定 `send_performed=false` |
| 实时订单使用静态 FAQ | 错误承诺 | 确定性识别 `required_tools` 并强制转人工 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/agent/workflow.py` | 新增 | LangGraph 状态、节点、路由和终态 | AIAgent开发工程师Agent |
| `backend/app/agent/workflow_prompt.py` | 新增 | FAQ 回答和依据复核 Prompt | AIAgent开发工程师Agent |
| `backend/app/agent/tool_routing.py` | 新增 | 实时业务和写操作工具门禁 | AIAgent开发工程师Agent |
| `backend/app/agent/generation.py` | 新增 | 回答/复核两次结构化调用预算 | AIAgent开发工程师Agent |
| `backend/app/agent/factory.py` | 新增 | 内部工作流和向量化服务构建入口 | AIAgent开发工程师Agent |
| `backend/app/agent/schemas.py` | 修改 | 工作流输入、输出、引用和模型结构 | AIAgent开发工程师Agent |
| `backend/app/agent/service.py` | 修改 | 提取无嵌套运行记录的意图 `infer` | AIAgent开发工程师Agent |
| `backend/app/agent/repository.py` | 修改 | 保存分数、节点路径、引用和 Prompt 版本 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无公开 HTTP 变化；新增内部 `build_agent_workflow` 和 `AgentWorkflowCommand/Result`。
- 数据库：不新增迁移；使用现有 `agent_runs` 的检索分数和最终置信度字段。
- 配置项：新增自动回复 0.80、人工复核 0.60 阈值。
- AI：Prompt 版本为 `faq-answer-v1.0.0`、`faq-grounding-review-v1.0.0`、`faq-agent-workflow-v1.0.0`。

### 6.3 关键实现说明

- 意图最多三次、回答最多两次、复核最多两次，整条链最多七次 LLM 请求。
- 模型拒绝不切换模型绕过；无草稿时不继续安全复核。
- 运行摘要只保存节点、引用 UUID、工具名称和 Prompt 版本，不保存消息和 FAQ 正文。
- `auto_reply`、`human_review` 和 `transfer_human` 均是建议动作；业务状态和平台发送仍由全栈服务负责。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 工作流单元测试 | `uv run pytest -q` | 正常、工具、无知识、非法引用和阈值通过 | 纳入 64 passed | 通过 |
| Phase1 回归 | 原分类测试 | 旧分类行为不变 | 全部通过 | 通过 |
| Ruff/格式 | 项目命令 | 无问题 | 通过 | 通过 |
| mypy | `uv run mypy app scripts` | 严格类型通过 | 110 个源文件无问题 | 通过 |
| 容器构建 | backend/jobs 镜像 | LangGraph/tiktoken 可安装 | 构建成功；1.2.11/0.13.0 | 通过 |
| 服务健康 | `/v1/health` | HTTP 200 | `status=ok` | 通过 |
| 数据库版本 | `alembic current` | 013 不变 | `013_marketing (head)` | 通过 |
| 真实回答评测 | 真实 Embedding + LLM | 满足 RAG 门禁 | 密钥轮换未确认，未执行 | 未执行 |

## 8. 实施结果

- 完成项：LangGraph、内部契约、Prompt、安全复核、置信度、运行追踪、容器和确定性测试。
- 未完成项：真实模型 RAG 回答质量复核；全栈公开建议接口和端到端发送链路不在本任务范围。
- 与原方案差异：终态使用 `AUTO_REPLY_READY`，避免把未发送建议误记为 `AUTO_REPLIED`。
- 当前状态：部分完成；工程能力已交付，真实模型正式测试待测试工程师执行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-AGENT-001 | 真实 FAQ 回答和复核模型质量未正式评测 | P0 | AIAgent开发工程师Agent、测试工程师Agent | Phase2/P2-07 |
| R-AGENT-002 | 公开 `/suggest` 尚未接入权限和店铺校验 | P1 | 全栈开发工程师Agent | 后续全栈任务 |
| R-AGENT-003 | 当前工具需求只能转人工，不能执行 | P1 | AIAgent开发工程师Agent | AI Phase3 |

## 10. 交接事项

- 交接给：全栈开发工程师Agent、测试工程师Agent。
- 后续任务：全栈用内部契约接入建议接口；测试工程师执行 AI 评测、安全和端到端测试。
- 必须注意：`send_performed=false` 不得在接口层改写；自动发送必须经受控工具和审计。

## 11. 文档同步

- [x] 已同步内部接口变化。
- [x] 已同步 Prompt 和 Agent 工作流规范。
- [x] 已同步任务实施状态和索引。
- [x] 已通知测试工程师需要覆盖的范围。
- [ ] 正式测试报告索引待测试工程师复核后更新。

## 12. 后续方案说明

2026-08-21 已下载 BGE-M3 和 `bge-reranker-large`，计划把知识检索升级为候选 Top 20 后重排序为最终 Top 5。当前 LangGraph 代码和置信度行为未改变；Reranker 分数在评测完成前只建议用于排序，不得直接进入最终置信度。

### 13.2 本地 BGE 接入后续记录

2026-08-21 后续实施已把 LangGraph 的知识检索节点接入本地 BGE-M3、Dense/词法混合召回、RRF 融合和 Reranker。Reranker 原始 logit 只用于排序；工作流继续用 Dense cosine、意图和依据复核分数计算最终置信度，且 `send_performed=false` 边界不变。当前实现与验证见 `Phase2-P2-03-AIAgent开发工程师Agent-BGE混合检索与重排序-002.md`。
