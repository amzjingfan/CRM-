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
- 工作台标签页可见时每 5 秒重新读取列表与当前会话最新消息；按消息 ID 合并并保留已加载的历史、选中会话及草稿，避免每次刷新重置界面。
- `GET /workspace/sessions` 支持 `filter=all|unread|mine|starred|closed`；默认列表不含本地已关闭会话，`closed` 仅列出已关闭会话。列表和详情的 `session` 均返回 `unread_count`、`is_starred` 和 UTC `closed_at`。前端打开会话定位最新消息；读取较早页保持阅读位置，新消息不会把正在阅读历史的坐席拉到底部，并提供“到最新消息”。
- `POST /workspace/sessions/search` 要求 `workspace.view` 和 CSRF，body 可带 `filter/platform/store_id/status/page/page_size/search_scope/q/terms`。`search_scope=all|buyer|order|tracking|product`；`q` 为单项搜索，`terms` 为批量任一命中，二者互斥，最多 20 项、每项 1～120 字符。结果仍按授权店铺稳定分页；订单、物流和商品仅通过同店同平台同买家订单关联。搜索词置于 body，避免 URL 访问日志收集买家及订单标识。普通无搜索列表仍使用 GET。
- `POST /workspace/sessions/{session_id}/sidebar/search` 要求 `workspace.view`、CSRF 和该会话所在店铺权限；body 的 `section=orders|products|coupons` 决定结果结构。真实 TikTok `orders` 先按授权店铺读取官方 202601 单会话，核对唯一 BUYER 的 IM ID，再使用官方订单域 `buyer_user_id` 搜索并逐条核对返回身份；其他模式仅查同店、同平台、同买家的已同步订单。TikTok 202309 订单搜索若省略 `orders`，仅在 `total_count` 为整数 0 且 `next_page_token` 为空串时按零订单处理；其余缺失、类型错误或非空分页仍失败关闭。支持状态、订单号、物流号、商品名、商品 ID、SKU ID、卖家 SKU 筛选及页码；仅返回平台实际提供的金额拆分、商品和物流字段，缺失项为 `null`，不推断。单买家超过 2000 笔订单或分页身份异常时明确失败，不返回伪完整结果。`products` 与 `coupons` 只接受 TikTok 已连接的有效店铺，分别按官方只读目录分页返回；商品需要 `seller.product.basic`，优惠券需要 `seller.customer_service` 或 `seller.promotion.info`。商品名和优惠券编码按当前平台页过滤，`partial_search` 与 `next_page_token` 告知后续页可能还有结果；搜索词仅置于 body，不进入访问 URL。缺授权、平台错误和上游结构异常均失败关闭，不用示例数据代替。
- `GET /workspace/sessions/{session_id}/sidebar/products/{product_id}` 要求 `workspace.view`、会话店铺权限及 Product Basic 授权；仅接受数字商品 ID，使用官方商品详情只读接口取得图片、规格和库存，核对返回商品 ID。侧栏优惠券与商品的“填入回复草稿”只修改前端草稿，不调用消息发送、优惠券发放或退款接口。
- `POST /workspace/sessions/{session_id}/sidebar/orders/detail` 要求 `workspace.view`、CSRF 和当前会话店铺权限；数字订单 ID 仅放在请求体。服务端先以官方会话参与者核对 CRM 买家 IM ID，再读取当前店铺订单详情并逐条核对订单 ID 与订单域买家 ID；不匹配返回 404，绝不向前端返回其他买家数据，缺授权或上游异常失败关闭。响应仅含平台实际给出的付款方式、承运商和最新一条通用物流描述/UTC 时间，物流轨迹要求 `seller.logistics`。客户卡片进入可见区域时自动按需读取一次，失败保留手动重试；物流阶段优先显示订单列表的独立 `tracking_status`，没有时仅映射能表示物流阶段的官方订单状态。此读取不触发履约、退款或消息写入。
- 客户侧栏订单列表的 `paid_at` 仅从官方订单 `paid_time` 或现有本地订单支付时间投影为 UTC，缺失为 `null`；不由订单状态推断付款时间。优惠券列表的 `discount_value` 将已识别的金额对象转换为币种加金额的字符串，无法解析时为 `null`，不向前端透传 Python 字典文本。订单状态对应的截止、取消或退款字段当前未在只读模型中提供，工作台仅显示空值。
- TikTok 买家 Webhook 消息按平台消息 ID 幂等增加未读；只读同步补入晚于上次成功同步时间的买家新消息时也增加未读，首次历史回填不把旧消息算成新未读。
- `PATCH /workspace/sessions/{session_id}/star` 接收 `{ "starred": true|false }`，只标记 CRM 内部差评风险；`PATCH /workspace/sessions/{session_id}/closed` 接收 `{ "closed": true|false }`，只更新 CRM 工作流；`GET /workspace/sessions/{session_id}/assignees` 只列出同店、在职且拥有 `workspace.reply` 的坐席。三者按授权店铺定位会话；写接口要求 `workspace.transfer`、CSRF 和状态变更审计。重复设置同一状态不重复审计。转交目标同样须在职、有当前店铺回复权限；关闭会话拒绝新发送和转交，未结清出站消息拒绝关闭。已关闭会话遇到晚于关闭时间的真实买家新消息会重新进入活跃列表，历史回填不触发重开。
- `POST /chat/query` 的安全建议结果只填入空的本地可编辑草稿，已有人工草稿保留；使用建议不会自动触发平台发送。人工确认、真实发送白名单及 `unknown` 对账仍按现有契约执行。
- `POST /workspace/sessions/{session_id}/suggest` 返回 AI 建议。
- `POST /workspace/sessions/{session_id}/messages` 仅发送人工确认的普通文本；TikTok 真实发送要求 `seller.customer_service` Scope、CSRF 和 `Idempotency-Key`。
- TikTok 写客户端按官方 `POST /customer_service/202606/conversations/{conversation_id}/messages` 契约发送一次 `TEXT`，`content` 为 JSON 序列化字符串，`sender_role=CUSTOMER_SERVICE`；传输或平台内部结果不确定时记录 `unknown`，不自动重试。
- 真实发送开启时必须且只能配置单个 `TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID`，或经审核的 `TIKTOK_MESSAGE_WRITE_ALLOWED_STORE_IDS`（标准 UUID、英文逗号分隔）；空范围、混用和重复店铺均拒绝启动。工作台详情只对范围内、店铺有效且 TikTok 渠道已连接并具备 `seller.customer_service` 与有效凭证的会话返回 `send_mode=real`；其他会话的 POST 返回 403，工具层与写客户端在平台 HTTP 调用前再次校验范围。目标 ID 只经部署门禁注入，不放在仓库或低敏证据中。
- 同店铺已有未结清的 TikTok `processing` 或 `unknown` 出站消息时，新真实发送返回冲突并保持零次新平台调用；旧 `processing` 不能作为确定失败自动重发。现有管理员对账接口只接受 `unknown`，中断遗留的 `processing` 须先经受审恢复路径收敛。
- `POST /workspace/messages/{message_id}/reconcile` 对账 `unknown` 消息，不能通过重复平台发送猜测结果。
- `POST /workspace/sessions/{session_id}/messages/{message_id}/translation` 供已授权坐席按需把 TikTok 单条文本译成中文；要求登录、`workspace.view`、CSRF、店铺/会话匹配与模型限流。服务端从已授权消息读取原文，不接受客户端正文；仅在 staging 专用开关开启时可调用 DeepSeek，响应只返回消息 ID、目标语言和译文，不改变消息或平台状态。会话详情的 `translation_enabled` 控制前端是否显示翻译按钮。
- `POST /workspace/sessions/{session_id}/draft/translation` 接收 `source_text`（1～2000 字符）与 `target_language=en|id|fil|ms|th|my|vi|pt|es|pl|fr|zh-TW|zh-CN`，要求 `workspace.reply`、CSRF、店铺权限、可发送的未关闭 TikTok 会话、现有 staging 翻译开关和模型限流。输入与输出需通过现有 DLP；只返回原稿 SHA-256、目标语言和译文，不修改消息或触达 TikTok。会话详情的 `draft_translation_enabled` 决定前端是否开放翻译菜单。坐席修改草稿或目标语言后旧译文失效；选择“翻译后发送”时可生成当前译文，审阅框显示准确外发内容；选择“直接发送”审阅原文。两种方式均须人工确认才调用原 `POST /messages`，沿用发送白名单、幂等和 unknown 对账。
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
- G2 真实重投诊断仅可在 staging 的精确店铺与受控买家会话中显式开启。已验签、已绑定且结构有效的首个新消息通知可在落库前或落库后返回一次 HTTP 503；Redis 原子一次性标记与绝对失效时间阻止再次触发。后续同一正文重投仍走原有幂等回执，诊断审计仅保留正文 SHA-256、固定结果和内部资源引用。默认及 production 不开启；503/200 聚合数不能代替同一通知的真实重投证据。
- 内部只读适配器覆盖有效店铺、订单、订单详情、客服会话、消息和 Webhook 订阅核对；普通承运商订单的物流轨迹读取固定为 `GET /fulfillment/202309/orders/{order_id}/tracking`，要求 `seller.logistics`、当前授权渠道签名与 `shop_cipher`，并校验 `data.tracking[]`。CBT 首程增强读取保留独立的 `GET /logistics/202604/orders/{order_id}/tracking` 契约，不用前者的证据声称后者通过。

## 错误与状态

客户端应按 HTTP 状态和稳定业务码处理：参数错误、未认证、权限不足、资源不存在、版本/状态冲突、限流和内部错误。平台写入可能返回业务状态 `unknown`；该状态要求对账，不代表失败，也不允许自动重试写入。

## 规划但未放行

Shopee/Amazon 真实接口、公开自动回复、无需人工确认的发送、自动营销、高风险工具和生产翻译仍是规划能力。早期 `/marketing/flows`、无确认发送或宽泛 PUT 更新草案不构成当前公开契约；以运行代码生成的 OpenAPI 和本文件为准。
