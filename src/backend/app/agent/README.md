# M04 Agent 内部契约与 Prompt 版本

## 模块边界

`app.agent` 负责意图分类、FAQ 检索编排、受控工具选择/解释、回复生成、翻译、安全决策和低敏追踪。它不负责公开 HTTP 认证、店铺授权、业务表写入、平台 SDK 调用或前端展示。

```text
可信全栈服务
→ AgentWorkflowCommand
→ AgentWorkflowService
→ RAG / AgentToolService / 结构化 LLM
→ 确定性安全门禁 + 模型依据复核
→ AgentWorkflowResult(send_performed=false)
```

## 内部输入与输出

`AgentWorkflowCommand` 使用由调用方已验证的 `store_id`、`conversation_id`、`trigger_message_id`、当前消息、最多 10 条历史、`trace_id`、可选可信工具上下文和 `reply_profile`。Agent 不从客户文本抽取权威订单/客户 ID。

`AgentWorkflowResult` 在原有意图、引用、工具、置信度和动作字段上增加：

- `detected_language`：`zh-CN | en | mixed | unknown`。
- `reply_language`：最终回复使用的 `zh-CN | en`。
- `customer_translation`：可选翻译关联结果，包含触发消息 ID 和原文摘要，不复制业务消息。
- `safety_reason_codes`：确定性门禁或模型复核的稳定原因码。
- `send_performed=false`：始终固定，公开发送属于全栈工具层。

## 店铺回复配置

`AgentReplyProfile` 只接受固定枚举和简短品牌名：

```json
{
  "tone": "friendly",
  "reply_language": "auto",
  "operator_language": "zh-CN",
  "brand_name": "Example Brand"
}
```

内部将它放在 `agent_configs.knowledge_scope.reply_profile`。不存在时使用友好语气、自动客户语言和中文客服工作语言。公开 Agent 管理 API 只允许写这个强类型子对象，继续拒绝任意 Prompt、模型和阈值。

## 回复与安全策略

回复 Prompt 只接收解析后的语言、固定语气指令和清洗品牌名。FAQ 与营销输出继续携带 `BusinessClaimInventory(complete=true)` 供纵深检查；订单、物流、客户画像、地址请求、优惠券和平台消息的对象级声明由服务端执行层根据强类型工具结果生成，且声明、固定模板和证据提取边界都会再次执行工具输出 Schema 校验。模型必须返回空清单且不得猜测脱敏 ID。模型自报声明和独立模型复核都只能增加门禁，不能授予自动回复权限。

外部 Provider 共用 `prompt-dlp-v1.3.0` 三态完整信封门禁。明确完整地址和结构化地址字段为 `blocked`；客户自由文本、带前缀 JSON、未知字段及未知嵌套结构为 `uncertain`；任意层级重复 JSON 键以 `JSON_DUPLICATE_KEY_REJECTED` 失败关闭并清除原始载荷。当前只有 `provider-contract-v1.1.0` 不可变 Provider 工程控制系统提示与纯 JSON 固定控制 DTO 的组合可为 `allowed`，且 DTO 会从已验证字段重新规范化序列化，禁止复用原始 JSON。工程提示显式要求返回 `json` 对象并提供无业务数据示例，以满足 DeepSeek JSON Output 契约；调用方不能通过动态自由文本补齐该条件。系统 Prompt 与用户 Prompt 任一字段非 `allowed` 时，三家 Provider 均不得调用 SDK。地址正则只做纵深阻断，不再以“未命中”证明可外发。日志只记录策略版本、状态和稳定原因码，不记录 Prompt 或客户正文。架构师批准本地 PII/DLP 能力和版本化业务 Prompt 注册表前，包含真实客户文本的回复、翻译和营销调用均保持失败关闭。

当前 FAQ 数据没有“政策/实例事实”类型和发布审批字段，因此 `published + ready + 逐字一致` 只证明内容来源，不证明自动交付权限。所有 FAQ 草稿最高进入 `HUMAN_REVIEW`。只有代码根据单次真实 `query_order/query_logistics` 结果生成的有限状态模板，并通过对象、店铺和证据绑定后，才可能进入 `AUTO_REPLY_READY`。

- 邮箱、手机或长标识符泄露。
- 未授权的退款申请状态、审批决定、执行、资金移动或到账声明。当前没有退款事实工具，因此 FAQ 证据只能支持 `refund_policy/explain_policy`，不能支持具体客户结果。开放语言动词先由模型映射为有限动作，再由代码验证证据；文本扫描仅用于兼容入口和发现声明遗漏，不授予权限。
- FAQ/营销的 `business_claims` 缺失、主体动作组合非法、证据 ID 不属于本次运行，或独立复核认为正文与声明不一致。
- 工具证据的工具名、店铺或可信对象 ID 与代码声明不一致；订单 A 的结果不能支持订单 B。真实对象 ID 不进入 Prompt，模型的 `[SENSITIVE_ID]` 仅在工具调用、主体类型和动作完全匹配时绑定到服务端声明。
- 客户实例声明的否定或条件作用域不明确、当前状态被写成未来结果、同一主体动作借不同证据或时态形成重复/冲突命题，或没有专用证据端口却承诺送达/处理时间。承诺时效固定使用 `promise_time/promise`，当前没有放行工具，因此一律转人工。
- 没有 `query_order/query_logistics` 依据却声明订单/物流已完成。
- 将 Mock 发券或平台写描述为真实完成。
- 模型输出语言与已解析回复语言不一致。

## 翻译与营销

- `AI_TRANSLATION_ENABLED=false` 默认关闭，避免额外模型调用无意增加 SSE 首输出时延。显式启用后，只翻译经脱敏的客户消息和已通过安全门禁的草稿。翻译失败不改写主决策。
- `AI_MARKETING_ENABLED=false` 默认关闭。弃单文案只获取支付状态、币种和金额摘要；中差评文案只获取星级和经脱敏评价。生成后必须经过独立声明一致性复核；当前没有可审计人工批准状态，因此结果固定要求人工复核且不向 Jobs Worker 返回可发送正文。
- 两个开关启用时都必须同时启用 `LLM_ENABLED`。
- 公开建议与 SSE `result.translation` 只映射触发消息 ID、摘要、语言、译文和 Prompt 版本，不暴露 Provider、模型、Token 或模型原始输出。
- 营销生成写入统一 `agent_runs`；后续营销工具调用通过同一 `agent_run_id` 关联，输入/输出摘要不保存评价、消息或生成正文。

## Prompt 版本

| 用途 | 版本 |
| --- | --- |
| 工作流 | `faq-agent-workflow-v1.6.0` |
| FAQ 回答 | `faq-answer-v1.5.0` |
| FAQ 依据复核 | `faq-grounding-review-v1.5.0` |
| 工具结果解释 | `tool-answer-v1.5.0` |
| 工具依据复核 | `tool-grounding-review-v1.5.0` |
| 客户翻译 | `customer-translation-v1.0.0` |
| 营销文案 | `marketing-copy-v1.3.0` |
| 营销独立复核 | `marketing-copy-review-v1.0.0` |

Prompt、模型、检索策略、工具 Schema 或安全规则变更时，必须先运行版本化离线回归和全量测试。

## 评测与指标

```powershell
uv run python -m scripts.evaluate_phase4 --dataset ../tests/ai/datasets/agent-phase4-v1.0.0.jsonl --output ../tests/ai/results/agent-phase4-deterministic.json
```

确定性回归当前包含 234 条普通回复、翻译、弃单和中差评样本。额外单元测试覆盖报告 010～013 的业务资金结果、合法作用域、结构化声明绕过、污染 FAQ、营销复核、工具证据对象绑定和脱敏对象绑定。自由文本样本不并入固定评测集自证；测试必须分别检查人工复核资格和 `automatic_delivery_allowed`，旧 `is_safe` 二元值不再代表自动发送授权。离线有标签指标由 `calculate_phase4_metrics` 计算，线上 `metric_daily` 只从事实表聚合指标。

真实模型 SSE 50 并发、首输出小于 3 秒、真实平台写和 5 天稳定性必须由测试工程师在隔离环境中执行，不得用 Fake Provider 或传输分块冒充正式结论。
