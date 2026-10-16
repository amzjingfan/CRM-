# 当前 API 契约

## 通用约定

- 业务接口位于 `/v1`，响应使用统一 `code/message/data/request_id` 信封；流式接口使用 SSE 事件。
- 登录态、店铺范围和权限由服务端判定；写操作同时执行 CSRF、幂等和审计要求。
- 客户端不得提交任意 Prompt、模型名、阈值或跨店铺标识。
- 真实密钥、Token、凭证引用和内部错误正文不进入公开响应。

## 已实现接口族

### 认证

- `POST /auth/login`、`GET /auth/me`、`POST /auth/refresh`、`POST /auth/logout`。
- 浏览器会话接口提供 HttpOnly Cookie 与 CSRF 保护；失败统一返回认证/权限错误。

### 看板

- `GET /dashboard/metrics|trend|channels|alerts|top-queries`。
- 数据按授权店铺聚合，时间范围、空数据和分页参数由服务端校验。

### 客服工作台与 AI

- 会话列表/详情、消息记录、状态更新和受控工具均位于 `/workspace`。
- 已授权 TikTok 店铺的会话和历史经内部只读同步写入现有会话/消息表；列表和详情仍通过原 `/workspace` 接口按店铺权限读取。工作台会话列表每页取 30 条，按列表返回的 `pagination` 加载更多，店铺与平台筛选在每一页保持一致。详情消息按时间升序分页，前端先取最新页，可继续加载较早历史。
- `POST /workspace/sessions/{session_id}/suggest` 返回 AI 建议。
- `POST /workspace/sessions/{session_id}/messages` 仅发送人工确认的普通文本；TikTok 真实发送要求 `seller.customer_service` Scope、CSRF 和 `Idempotency-Key`。
- 同店铺已有未结清的 TikTok `processing` 或 `unknown` 出站消息时，新真实发送返回冲突并保持零次新平台调用；旧 `processing` 不能作为确定失败自动重发。现有管理员对账接口只接受 `unknown`，中断遗留的 `processing` 须先经受审恢复路径收敛。
- `POST /workspace/messages/{message_id}/reconcile` 对账 `unknown` 消息，不能通过重复平台发送猜测结果。
- `POST /chat/query` 使用 `accepted/status/delta/result/error/done` SSE 事件；`delta` 是安全草稿完成后的传输分块，不表示模型原生 Token。

### 知识库

- 分类与条目的查询、新建、更新、删除、批量导入和发布位于 `/knowledge`。
- `POST /knowledge/entries` 和 `PATCH /knowledge/entries/{entry_id}` 支持语义类型、客户范围和文档版本。
- `POST /knowledge/entries/{entry_id}/publish` 只批准精确版本供内部复核；正文、语义类型或客户范围变化会递增版本并撤销审批。
- 当前不开放 `approved_for_public_reply`，发布 FAQ 不等于允许自动发送。

### 营销

- `/marketing` 提供活动/任务的列表、新建、详情、受控更新、启停、预览/执行和报表能力。
- 当前能力用于内部管理和验证；自动营销与真实高风险写入未放行。

### Agent 运营

- `GET/POST /agents`、`GET/PATCH/DELETE /agents/{agent_id}`。
- `POST /agents/{agent_id}/enable|disable|toggle`、`GET /agents/{agent_id}/logs`。
- `reply_profile` 仅接受固定语气、回复语言、坐席语言和经清洗的品牌名；任意 Prompt、模型和阈值字段拒绝。

### 团队与渠道

- `GET/POST /settings/team`、`GET/PATCH/DELETE /settings/team/{user_id}`；普通删除表示禁用。
- `DELETE /settings/team/{user_id}/permanent` 仅能删除已禁用且无受保护业务引用的用户。
- 店铺与渠道位于 `/settings/stores`、`/settings/channels`；通用渠道创建仅用于 Shopee/Amazon 契约级 Mock，禁止创建 TikTok 真实记录。

### TikTok OAuth 与 Webhook

- `GET /settings/channels/tiktok/oauth/start` 创建默认 600 秒的随机 `state`，哈希键绑定用户、店铺与固定站内回跳地址。公开 callback 不依赖 CRM Cookie；成功路径只创建一次短期加密任务并立即 303 至 `/settings/channels?oauth=tiktok&status=processing&job=<UUID>`，不等待 TikTok 外部 API。已有任务的重复 callback 不二次交换 Token。拒绝/缺失 code 沿用即时失败回跳。
- `GET /settings/channels/tiktok/oauth/jobs/{job_id}` 需要 `settings.channels`、原发起用户和仍有效的店铺访问权；仅返回 `pending/processing/connected/denied/failed`。现有 jobs worker 原子消费 `state`，完成 Token 与店铺校验并清除临时密文；失败或中断要求重新授权，不重放 code。
- Token 刷新是内部能力，没有公开 Refresh API；解密、刷新或契约校验失败时渠道转为 `expired`。
- `DELETE /settings/channels/{channel_id}` 撤销本地 Token 可用性并保留审计，不物理删除授权证据。
- `POST /webhooks/tiktok` 在真实模式只接受官方 `Authorization` 签名，以原始请求体进行常量时间校验；签名失败在数据库查询/写入前返回 401，不占用通知 ID。相同通知 ID 只有原始正文摘要一致且已绑定店铺时返回成功的重复回执；不同正文返回 409，未知店铺的首次及重复通知均返回 404 且不保存载荷。乱序送达的旧消息照常入库，但不覆盖较新消息的会话排序字段。公网版本前缀为 `/v1`。
- 内部只读适配器覆盖有效店铺、订单、订单详情、物流、客服会话、消息和 Webhook 订阅核对。

## 错误与状态

客户端应按 HTTP 状态和稳定业务码处理：参数错误、未认证、权限不足、资源不存在、版本/状态冲突、限流和内部错误。平台写入可能返回业务状态 `unknown`；该状态要求对账，不代表失败，也不允许自动重试写入。

## 规划但未放行

Shopee/Amazon 真实接口、公开自动回复、无需人工确认的发送、自动营销、高风险工具和生产翻译仍是规划能力。早期 `/marketing/flows`、无确认发送或宽泛 PUT 更新草案不构成当前公开契约；以运行代码生成的 OpenAPI 和本文件为准。
