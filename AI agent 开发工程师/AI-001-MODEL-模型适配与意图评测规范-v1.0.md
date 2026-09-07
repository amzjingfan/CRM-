# CRM 智能聊天系统模型适配与意图评测规范

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档编号 | AI-001-MODEL |
| 版本 | v1.0 |
| 主责 Agent | AI Agent 开发工程师 Agent |
| 对应任务 | P2-01、P2-02 |
| Prompt 版本 | `intent-classifier-v1.0.1` |
| 生效日期 | 2026-08-20 |

## 2. 模块边界

`backend/app/agent/` 是 AI Agent 工程师负责的独立模块。调用方必须传入已经完成店铺权限校验的 `store_id`、`conversation_id` 和触发消息上下文。

- Agent 不查询或修改订单、会话、消息等业务表。
- Agent 不调用 TikTok、Shopee、Amazon 适配器。
- Phase 1 只写 `agent_runs`，并且只保存摘要、分类结果、稳定错误码和资源统计。
- Phase 1 不提供 `/suggest`、SSE、RAG、工具调用、回复生成或自动发送。
- 所有高置信度结果仍进入 `human_review`，不得转换为 `auto_reply`。

## 3. Provider 契约

统一异步接口为：

```text
LLMProvider.generate_structured(request, response_schema)
→ ProviderResult[Schema]
```

当前白名单 Provider：

| Provider | SDK 范围 | API | SDK 重试 |
| --- | --- | --- | --- |
| OpenAI | `openai>=2.51,<3` | Responses API 原生结构化输出 | 关闭 |
| Anthropic | `anthropic>=0.120,<0.121` | Messages API 原生结构化输出 | 关闭 |
| DeepSeek | 复用 `openai>=2.51,<3` | OpenAI 兼容 Chat Completions + JSON Output | 关闭 |

DeepSeek 默认使用 `https://api.deepseek.com`，当前模型配置为 `deepseek-v4-flash` 主模型和 `deepseek-v4-pro` 备用模型。DeepSeek 的 JSON Output 仍必须经过本地 Pydantic 校验；`finish_reason=length` 视为截断并转换为 `LLM_OUTPUT_INVALID`。短意图分类通过 `DEEPSEEK_THINKING_ENABLED=false` 关闭 V4 默认思考模式，避免推理 Token 在最终 JSON 生成前耗尽；后续任务不得在未重新评测的情况下开启。

应用层总调用预算最多三次：主模型首次、主模型一次重试或结构重生成、备用模型一次。认证、权限、非法参数和配置错误立即失败；拒绝不得通过换模型绕过。

稳定错误码：`LLM_TIMEOUT`、`LLM_RATE_LIMITED`、`LLM_CONNECTION_ERROR`、`LLM_AUTHENTICATION_ERROR`、`LLM_PERMISSION_DENIED`、`LLM_INVALID_REQUEST`、`LLM_PROVIDER_ERROR`、`LLM_OUTPUT_INVALID`、`LLM_REFUSAL`、`LLM_CONFIGURATION_ERROR`。

## 4. 意图和决策规则

五类意图为：

- `logistics_query`
- `return_policy`
- `size_guide`
- `price_inquiry`
- `general`

拒判状态为 `unknown`、`mixed`、`insufficient_context`、`model_refusal`。只有 `classified` 可以携带意图，其他状态的 `intent` 必须为 `null`。

最终动作由代码计算：

```text
classified 且 confidence >= 0.6 → human_review
其余全部 → transfer_human
```

模型输出的动作字段不可信，也不在结构化响应契约中。

## 5. 隐私与可观测性

- 当前消息限制 1–4000 字符，历史最多 10 条，总上下文最多 12000 字符。
- 调用模型前屏蔽邮箱、手机号、订单号、物流号等标识信息。
- `input_summary` 只含消息数、字符数和 SHA-256 摘要。
- `output_summary` 只含意图和分类状态。
- 日志只记录 Provider、模型、尝试序号、Token、耗时、稳定错误码和 `agent_run_id`，不记录客户原文、Prompt、模型正文或 API Key。
- `agent_runs.status=running` 必须在外部调用前提交；成功、失败和超时分别提交终态。

## 6. 评测规范

版本化数据集：`backend/evals/intent-classifier-v1.0.0.jsonl`。

- 五类意图各 20 条，共 100 条。
- `unknown`、`mixed`、`insufficient_context` 各 10 条，共 30 条。
- 覆盖中英文、口语、错别字、短上下文和 Prompt 注入。
- 五类准确率门槛为 85%，边界正确拒判率门槛为 90%。
- 报告包含各类 precision/recall/F1、混淆矩阵、Token 和平均端到端耗时。
- 单条 Provider 失败继续执行剩余样本，在报告中计入 `error` 和错误码分布；任何 Provider 失败都使质量门禁失败，不得误算为正确拒判。
- 失败样本定位只记录合成 `case_id`、期望标签和实际标签，不记录样本原文或模型正文。
- 默认 pytest 不访问公网；只有 `LLM_LIVE_EVAL=true` 才允许运行真实模型评测。
- Fake/Scripted Provider 仅用于确定性测试，不得冒充正式模型评测通过。

真实评测命令：

```powershell
cd CRM智能聊天系统/backend
uv run python -m scripts.evaluate_intents --output evals/results/intent-classifier-live.md
```

正式 AI 评测报告由测试工程师按项目测试报告命名规范生成。

## 7. Phase 2 交接

后续 FAQ RAG 和 Agent 工作流可以复用 Provider、Prompt 版本、运行追踪和保守动作枚举，但必须新增以下设计后才能开放客服建议：

- 店铺级已发布知识检索和来源引用。
- 检索分数、最终置信度及阈值校准。
- 工具白名单契约、权限、参数、超时、幂等和审计。
- 回复安全检查、人工复核与平台发送隔离。
- `/suggest` 的全栈接口契约和端到端测试。
