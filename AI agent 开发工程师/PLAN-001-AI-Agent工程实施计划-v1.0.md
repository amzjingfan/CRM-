# CRM 智能聊天系统 AI Agent 工程实施计划

| 项目 | 内容 |
| :--- | :--- |
| 计划编号 | `PLAN-001-AI` |
| 版本 | `v1.0` |
| 状态 | 待执行 |
| 主责 Agent | AI Agent 开发工程师 |
| 产品代码目录 | `CRM智能聊天系统/` |
| 依据文档 | `ARCH-001-SYS...v1.1.md`、`ARCH-003-DATA...v1.0.md`、PRD、管理端接口文档 |

## 1. 角色目标

负责项目中全部 AI 能力：模型接入、Agent 工作流、Prompt、意图识别、RAG、工具调用、置信度、人工接管、翻译、营销话术和 AI 评测。

AI 设计和实现必须落在正式产品代码目录；方案、Prompt 说明、评测集和交接记录保存在本目录或共享记忆文档中。

## 2. 不负责的内容

- 不负责前端页面和普通业务 API 的实现。
- 不直接访问第三方平台 SDK，不直接修改订单、消息、会话等业务表。
- 不绕过全栈工程师提供的工具层直接执行发券、发消息或地址修改。
- 不擅自更改数据库模型、部署方式和公共接口；需要变更时提交架构师评审。

## 3. 实施阶段

### Phase 0：需求、架构和评测准备

开始前必须阅读：

- 最新 PRD、管理端接口文档和任务拆解。
- `架构师/ARCH-001-SYS-系统总体架构设计-v1.1.md`。
- `架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.0.md`。
- `开发工具/skills/` 中 Agent、Python、RAG、测试、安全和可观测性 Skill。

输出：

- AI 模块边界和状态机草图。
- Agent 输入、输出和错误结构。
- 5 类意图评测集初版。
- 工具清单、工具参数、权限和错误码需求。
- Prompt 版本管理规则。

### Phase 1：模型适配层和意图识别

- 实现统一 LLM Provider 接口，兼容 OpenAI/Claude 风格调用。
- 统一模型配置、超时、重试、Token 统计、错误分类和降级策略。
- 实现结构化输出解析和非法输出修复/失败处理。
- 实现 MVP 五类意图：
  - `logistics_query`
  - `return_policy`
  - `size_guide`
  - `price_inquiry`
  - `general`
- 设计意图 Prompt、示例集、边界样本和未知意图处理。
- 保存 `model_name`、`prompt_version`、意图分数和 trace_id 到 `agent_runs`。

验收：

- 可通过配置切换模型 Provider。
- 非法 JSON、超时、限流和模型错误不会导致接口崩溃。
- 五类意图测试集准确率达到 85% 以上。
- 未知、混合和上下文不足的问题不会被强行归类。

### Phase 2：FAQ RAG 和 Agent 工作流

- 实现 FAQ 文档读取、查询向量生成、Top-5 检索和 score 返回。
- 只检索当前 `store_id` 下已发布且向量化完成的知识。
- 实现文档版本、分类、引用依据和无结果处理。
- 建立显式 Agent 状态：

```text
RECEIVED
→ CONTEXT_LOADED
→ INTENT_CLASSIFIED
→ KNOWLEDGE_RETRIEVED
→ TOOL_REQUIRED / RESPONSE_DRAFTED
→ SAFETY_CHECKED
→ CONFIDENCE_EVALUATED
→ AUTO_REPLIED / HUMAN_REVIEW / TRANSFERRED / FAILED
```

- 用 LangGraph 或同类框架实现单 Agent 节点编排。
- 支持上下文窗口控制、历史消息裁剪和敏感信息脱敏。
- 记录 `agent_runs` 的输入摘要、检索结果、最终置信度和动作。

实施更新（2026-08-21）：架构师已确认将本阶段检索实现升级为本地 BGE-M3 1024 维 Dense Top 20 + PostgreSQL `pg_trgm` Top 20，经 RRF 融合候选 Top 20 后由 `bge-reranker-large` 重排序为最终 Top 5。当前规范见 `AI-002-RAG-FAQ检索与Agent工作流规范-v1.2.md`，数据库依据见 `架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.1.md`。

验收：

- RAG 返回 Top-5 结果、相似度 score 和来源文档。
- 草稿、归档、未向量化的知识不参与正式回答。
- 无检索结果时进入保守回复或转人工路径。
- Agent 节点失败可定位，且不会重复发送回复。

### Phase 3：业务工具和安全接管

与全栈工程师共同确定工具契约，AI 侧实现工具选择、参数组装、结果解释和错误处理。

MVP 工具：

```text
query_order
query_logistics
query_customer_profile
update_shipping_address
send_coupon
transfer_to_human
send_platform_message
```

每个工具必须包含：

```text
tool_name
input_schema
output_schema
permission
timeout_ms
idempotency_key
success_conditions
error_codes
audit_action
```

工具规则：

- 查询类工具可以自动调用，但必须校验店铺和客户上下文。
- 发券、改地址、发送消息属于外部写操作，必须通过权限、频控、幂等和审计。
- 工具失败时 Agent 不得生成“已完成”的回复。
- 工具超时进入重试或转人工，不无限重试。
- 转人工必须更新会话动作和原因。

验收：

- 工具成功、失败、超时、重复调用和权限拒绝均有明确结果。
- 业务工具调用全部产生 `tool_calls` 记录。
- 外部写操作全部产生 `audit_logs` 记录。
- 低置信度、敏感问题、工具失败能正确转人工。

### Phase 4：回复、翻译、营销和评测闭环

- 实现回复 Prompt、语气、语言和店铺级配置。
- 实现中英文识别和实时互译，保留原文和译文关联。
- 实现 AI 建议回复和 `/chat/query` 的流式输出事件设计。
- 实现弃单挽回和中差评跟进的话术生成，但发送必须调用全栈工具层。
- 实现安全检查：敏感内容、越权承诺、虚构订单状态、无依据退款/补偿。
- 建立离线评测和线上指标：意图准确率、RAG 命中率、工具成功率、转人工率、首字延迟、平均延迟和 Token 成本。
- 建立回归集，每次 Prompt、模型、检索策略和工具契约变更都重新评测。

验收：

- AI 首字延迟目标小于 3 秒。
- 回复能正确区分自动回复、人工复核和转人工。
- 线上运行日志可以还原一次完整 Agent 链路。
- Prompt 或模型升级不会降低核心评测集指标。

## 4. Agent 输入输出契约

建议内部状态输入：

```json
{
  "conversation_id": "conv_001",
  "store_id": "store_001",
  "customer_id": "cust_001",
  "message_id": "msg_001",
  "message": "我的订单到哪里了？",
  "language": "zh-CN",
  "history": [],
  "available_tools": ["query_order", "query_logistics", "transfer_to_human"]
}
```

建议内部结果：

```json
{
  "answer": "我正在为您查询物流信息。",
  "intent": "logistics_query",
  "confidence": 0.92,
  "action": "auto_reply",
  "citations": [],
  "tool_calls": [],
  "requires_human": false,
  "agent_run_id": "run_001"
}
```

动作枚举：

```text
auto_reply | human_review | transfer_human | failed
```

## 5. 与全栈开发工程师的交接

AI Agent 工程师提供：

- Agent 输入、输出、状态和错误类型。
- 工具调用契约、字段校验、超时和幂等需求。
- `agent_configs` 所需模型、Prompt、阈值和工具配置字段。
- SSE 事件类型和流式结束/错误事件。
- `agent_runs`、`tool_calls` 所需日志字段。

全栈工程师提供：

- 会话历史和店铺知识范围读取接口。
- FAQ 发布状态和向量检索接口。
- 订单、物流、优惠券、地址、转人工和平台发送工具执行接口。
- 消息发送、会话状态更新、审计和异步任务能力。

接口变更流程：

```text
发现变更需求
→ 在共享记忆文档登记
→ 架构师确认边界
→ 双方更新契约
→ 代码实现
→ 集成测试
```

## 6. 测试与交付物

必须提供：

- Prompt 版本和模型配置说明。
- 意图分类评测集及准确率、召回率、混淆矩阵。
- RAG 检索测试、引用依据和无结果测试。
- Agent 状态机正常、异常、超时、重试和中断测试。
- 工具调用成功、失败、权限拒绝、幂等和超时测试。
- 幻觉、越权、敏感内容、注入攻击和低置信度转人工测试。
- AI 运行日志字段和成本/延迟统计。
- 修改文件、验证命令、测试结果和已知风险。

## 7. 最终完成标准

- 五类意图识别准确率达到 85% 以上。
- FAQ RAG 返回 Top-5、score 和来源依据。
- Agent 不直接访问第三方平台和业务数据库写接口。
- 所有业务动作都通过白名单工具并可审计。
- 高/中/低置信度动作符合架构定义。
- 模型、Prompt、工具、检索和评测结果均可追溯。
- 能与全栈工程师的 API、数据库和 SSE 实现完成端到端联调。
