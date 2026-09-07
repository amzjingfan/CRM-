# CRM 智能聊天系统 FAQ RAG 与单 Agent 工作流规范

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档编号 | AI-002-RAG |
| 版本 | v1.0 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 对应任务 | P2-03、P2-07 |
| 生效日期 | 2026-08-20 |
| 当前状态 | 历史基线，已由 v1.2 替代 |

> 当前生效实现见 `AI-002-RAG-FAQ检索与Agent工作流规范-v1.2.md`。本文件保留 OpenAI 1536 维单阶段检索的历史设计，不作为新代码或数据库迁移依据。

## 2. 模块边界

- Agent 只接收全栈业务服务完成权限校验后的 `store_id`、会话 ID、触发消息 ID 和对话上下文。
- Agent 只能通过知识库内部端口认领文档、替换向量和执行租户安全检索。
- Agent 不直接写会话、消息、订单、平台账号、审计或营销表，不直接调用平台适配器。
- Phase 2 不执行工具；实时订单、物流和写操作只返回白名单 `required_tools` 并转人工。
- `auto_reply` 表示达到自动回复条件，工作流终态为 `AUTO_REPLY_READY`；返回值固定 `send_performed=false`。
- HTTP 认证、店铺权限、`/suggest`、SSE 和平台发送由全栈工程师后续接入。

## 3. Embedding 与向量化

生产基线：

```text
provider: openai
model: text-embedding-3-small
dimensions: 1536
chunk max: 800 tokens
overlap: 80 tokens
batch size: 32
max attempts: 3
```

向量化 Worker 使用 `FOR UPDATE SKIP LOCKED` 原子认领 `published + pending` FAQ，并立即提交 `processing`。外部 Embedding 不占用数据库行锁。每个片段重复问题前缀，答案按 Token 窗口切分。

只有文档版本仍等于认领版本且状态仍为 `processing` 时，知识端口才原子替换切片并标记 `ready`。旧任务不能覆盖新版本；失败只把本次认领的当前版本标记为 `failed`，不会无限自动重试。

稳定错误码：

- `EMBEDDING_TIMEOUT`
- `EMBEDDING_RATE_LIMITED`
- `EMBEDDING_CONNECTION_ERROR`
- `EMBEDDING_AUTHENTICATION_ERROR`
- `EMBEDDING_PERMISSION_DENIED`
- `EMBEDDING_INVALID_REQUEST`
- `EMBEDDING_PROVIDER_ERROR`
- `EMBEDDING_OUTPUT_INVALID`
- `EMBEDDING_CONFIGURATION_ERROR`

## 4. RAG 检索规则

检索条件固定为：

```text
store_id = 可信调用上下文店铺
document.status = published
document.vectorization_status = ready
chunk.document_version = document.document_version
document.deleted_at IS NULL
top_k = 5
minimum cosine score = 0.70
maximum context = 6000 tokens
```

返回引用包含文档、片段、分类、版本、片段序号、归一化分数和来源标签。无结果或所有结果低于阈值时不得调用回答模型，直接转人工。

查询发送 Embedding 前复用 Phase 1 脱敏规则，屏蔽邮箱、手机号、订单号和物流标识。日志不记录查询正文、知识正文、向量或供应商响应。

## 5. LangGraph 工作流

```text
RECEIVED
→ CONTEXT_LOADED
→ INTENT_CLASSIFIED
→ TOOL_REQUIRED 或 KNOWLEDGE_RETRIEVED
→ RESPONSE_DRAFTED
→ SAFETY_CHECKED
→ CONFIDENCE_EVALUATED
→ AUTO_REPLY_READY / HUMAN_REVIEW / TRANSFERRED / FAILED
```

Prompt 版本：

| 用途 | 版本 |
| --- | --- |
| 意图识别 | `intent-classifier-v1.0.1` |
| FAQ 回答 | `faq-answer-v1.0.0` |
| 依据与安全复核 | `faq-grounding-review-v1.0.0` |
| 工作流 | `faq-agent-workflow-v1.0.0` |

单次工作流模型预算最多 7 次：意图最多 3 次、回答最多 2 次、复核最多 2 次。模型拒绝不得通过备用模型绕过；结构和瞬时供应商错误才允许在节点预算内重试。

最终置信度由代码计算：

```text
min(intent_confidence, top_retrieval_score, grounding_confidence)
```

- `>= 0.80`：`auto_reply` / `AUTO_REPLY_READY`。
- `>= 0.60 且 < 0.80`：`human_review`。
- `< 0.60`：`transfer_human`。
- 未知、混合、上下文不足、模型拒绝、工具需求、无知识、非法引用或安全失败强制转人工。

模型输出的动作和工具不得被信任。回答引用必须是本次 Top 5 的子集；引用为空、越界或重复时失败关闭。

## 6. 内部交接契约

全栈工程师通过以下工厂构建工作流：

```python
workflow = build_agent_workflow(session, settings)
result = await workflow.run(session, command)
```

`AgentWorkflowCommand`：`store_id`、`conversation_id`、`trigger_message_id`、`message`、最多 10 条 `history`、`language`、`trace_id`。

`AgentWorkflowResult`：运行 ID、终态、意图、分类状态、引用、草稿、工具需求、三项置信度、最终置信度、动作、人工标记、Provider/模型、Prompt 版本、Token、耗时和 `send_performed=false`。

工作流只创建一条 `agent_runs`。运行记录保存输入摘要、节点路径、引用 UUID、Prompt 版本、分数、Token、耗时和动作，不保存消息正文、FAQ 正文或模型完整输出。

## 7. 测试与评测

- 默认 pytest 使用确定性 Provider，不访问公网。
- PostgreSQL 集成测试必须验证店铺、发布状态、ready 状态、当前版本和并发认领。
- `backend/evals/faq-rag-v1.0.0.jsonl` 包含 50 条有目标 FAQ 查询和 20 条无答案/越权/Prompt 注入查询。
- 真实评测要求 `LLM_LIVE_EVAL=true`、`EMBEDDING_ENABLED=true` 和已轮换的 OpenAI Key。
- 门禁：`Recall@5 >= 90%`、无答案正确拒判率 `>= 90%`、引用合法率 `100%`。
- Fake Provider 结果不得作为正式 AI 评测通过结论；正式报告由测试工程师生成。

## 8. 已知风险

- 当前真实 RAG 质量尚未在轮换后的 OpenAI Key 上执行 live gate。
- `tiktoken` 首次加载编码表需要缓存；Docker 镜像构建阶段已预热，本地开发需允许首次下载。
- DeepSeek Phase 1 意图准确率接近门槛，工作流仍可能因分类波动增加转人工率。
- 当前没有公开 `/suggest`，全栈接入前只能通过内部 Python 契约调用。
