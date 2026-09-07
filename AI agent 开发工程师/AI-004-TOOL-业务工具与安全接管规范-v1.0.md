# M04 业务工具调用与安全接管规范

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档编号 | AI-004-TOOL |
| 模块编号 | M04 |
| 版本 | v1.0 |
| 日期 | 2026-08-21 |
| 适用阶段 | AI Agent Phase 3 |
| 代码基线 | Python 3.11.15、数据库迁移 `015_vector_ops` |

本规范承接 `AI-002-RAG-FAQ检索与Agent工作流规范-v1.4.md`。Phase 2 仅声明工具需求；Phase 3 允许 Agent 通过全栈 `tools` 边界执行受控工具，但不授权 Agent 直接访问第三方平台或绕过工具层写业务表。

## 2. 模块边界

```text
AgentWorkflowService
→ AgentToolService
→ SqlAlchemyToolExecutor
→ 业务 Repository / PlatformAdapter
→ tool_calls / audit_logs
```

- `AgentWorkflowService`：确定性选择工具、解释结果、安全复核和动作决策。
- `AgentToolService`：只使用可信上下文组装参数，拒绝未批准写操作。
- `SqlAlchemyToolExecutor`：执行权限、店铺、参数、超时、幂等、审计和稳定错误映射。
- Agent 不从客户文本提取订单、客户、会话等权威资源 ID。
- Agent 不直接调用平台 SDK；平台写入只能由执行器调用 `PlatformAdapter`。
- 当前没有新增公开 HTTP API、SSE 或数据库迁移。

## 3. 白名单工具契约

| 工具 | 输入 Schema | 输出 Schema | 权限 | 超时 | 幂等 | 审计动作 |
| --- | --- | --- | --- | ---: | --- | --- |
| `query_order` | `QueryOrderArguments` | `OrderToolData` | `orders.view` | 5000 ms | 否 | `order.query` |
| `query_logistics` | `QueryLogisticsArguments` | `LogisticsToolData` | `orders.view` | 5000 ms | 否 | `logistics.query` |
| `query_customer_profile` | `QueryCustomerProfileArguments` | `CustomerProfileToolData` | `workspace.view` | 5000 ms | 否 | `customer.query` |
| `update_shipping_address` | `UpdateShippingAddressArguments` | `ShippingAddressToolData` | `orders.address.update` | 10000 ms | 是 | `order.address.update` |
| `send_coupon` | `SendCouponArguments` | `CouponToolData` | `coupons.issue` | 10000 ms | 是 | `coupon.issue` |
| `transfer_to_human` | `TransferToHumanArguments` | `TransferToolData` | `workspace.transfer` | 5000 ms | 是 | `conversation.transfer` |
| `send_platform_message` | `SendPlatformMessageArguments` | `PlatformMessageToolData` | `workspace.reply` | 15000 ms | 是 | `message.send` |

所有输入和成功输出均使用 `extra=forbid` 的 Pydantic Schema。未知工具、字段缺失、额外字段、非法 UUID、越界文本或输出结构错误都必须在 Agent 使用结果前失败关闭。

## 4. 可信上下文与批准写操作

`AgentWorkflowCommand.tool_context` 由全栈服务生成：

```text
order_id             可信店铺内订单 ID 或平台订单号
customer_id          可信店铺内客户 UUID
available_tools      当前调用允许使用的白名单子集
permissions          当前调用已验证权限集合
approved_actions     写工具的精确参数和幂等键
```

规则：

- 订单、物流和客户画像查询只能使用上述可信 ID。
- 地址修改、发券和平台发送必须存在同名 `ApprovedToolAction`，参数和幂等键原样使用。
- `send_platform_message` 不允许由客户自然语言直接选择。
- `transfer_to_human` 是安全动作；可信上下文开放工具并提供权限后，可由工作流自动执行。
- 同一写工具只能存在一个批准对象，避免参数选择歧义。

## 5. 工作流与决策

```text
INTENT_CLASSIFIED
→ TOOL_REQUIRED
→ TOOL_EXECUTED
→ TOOL_RESPONSE_DRAFTED
→ TOOL_SAFETY_CHECKED
→ CONFIDENCE_EVALUATED
→ AUTO_REPLY_READY / HUMAN_REVIEW / HANDOFF_EXECUTED / TRANSFERRED
```

- 工具选择由确定性代码完成，模型不能创造工具名称。
- 只有所有必需工具均成功时才进入结果解释。
- 工具草稿必须引用本次成功的 `tool_call_id`，非法或跨运行引用直接拒绝。
- `tool-answer-v1.0.0` 只依据成功结果解释，不得补写缺失事实。
- `tool-grounding-review-v1.0.0` 独立检查事实依据、安全性和完成声明。
- 成功工具链的最终置信度为 `min(intent_confidence, grounding_confidence)`。
- `>= 0.80` 可进入 `AUTO_REPLY_READY`，`0.60～0.80` 进入人工复核，低于 `0.60` 转人工。
- 任一失败、超时、权限拒绝、未解析工具、模型拒绝或复核失败都会把最终置信度置零并转人工。
- Mock 结果即使高置信度也最高进入 `HUMAN_REVIEW`。
- 所有结果固定 `send_performed=false`；工作流不得隐式调用平台发送。

## 6. 幂等、超时和失败语义

- 每次工具尝试先写入 `tool_calls.status=running`，再执行业务动作。
- 同店铺、同幂等键、同请求返回原终态并设置 `replayed=true`。
- 同键不同请求返回 `TOOL_IDEMPOTENCY_CONFLICT`，关联原工具调用，不重复副作用。
- 查询或本地写操作超时返回 `TOOL_TIMEOUT`，不生成成功话术。
- 平台发送超时可能已被对端接收，必须返回 `unknown/TOOL_RESULT_UNKNOWN`，禁止自动重试。
- 工具输出结构错误返回 `TOOL_OUTPUT_INVALID`；平台发送后的结构不确定仍按 `TOOL_RESULT_UNKNOWN` 处理。
- 工具失败不允许被模型改写成成功；工作流必须进入安全接管。

## 7. 数据隔离、审计和可观测性

- 资源查询同时约束资源 ID 和 `store_id`，跨店铺统一表现为资源不存在。
- 所有工具调用关联 `agent_run_id` 和 `trace_id`。
- 写操作、平台发送和转人工追加 `audit_logs`，不保存地址、消息正文、凭证或完整工具结果。
- `agent_runs.output_summary` 只保存节点路径、Prompt 版本和工具调用的 ID、名称、状态、稳定错误码。
- 工具输入摘要只保存资源 ID、字段名、国家码、优惠码或消息长度等低敏信息。
- 日志只记录工具名、调用 ID、稳定错误类别和耗时，不记录 SDK 异常正文、客户消息或密钥。

## 8. 当前限制和后续交接

- TikTok、Shopee、Amazon 仍是契约级 Mock；真实凭证、审核和沙箱联调未完成。
- 地址修改只产生 `pending_confirmation`，不覆盖权威订单地址。
- 优惠券和平台发送结果明确包含 `mocked=true`。
- 本阶段不提供 `/suggest`、SSE、前端展示、AI 营销话术或真实自动发送。
- 全栈工程师后续负责把可信会话/订单上下文与内部工作流入口连接到受认证 API。
- 测试工程师需独立验证工具成功、失败、超时、权限、幂等、跨店铺、审计、Mock 降级和转人工闭环。
