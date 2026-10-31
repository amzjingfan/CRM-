# 当前 API 契约

## 店铺多 Agent 自动建议预演（2026-10-31 本地候选）

`GET/PUT /v1/agents/auto-reply-preview?store_id=` 读取或修改当前店铺预演策略。读取需 `agent.view`；修改需 `agent.manage`、CSRF，开启时还需当前操作者拥有 `workspace.view` 且店铺已有已发布、已启用 Agent。PUT body 为 `{enabled,expected_revision}`，冲突返回 409。返回 `{store_id,enabled,revision,mode:"review_preview",send_performed:false}`。默认关闭；开启者身份用于后台按实时权限执行，撤权、停用或关闭后任务取消。

`GET /v1/workspace/sessions/{id}/auto-preview` 需 `workspace.view` 和当前会话店铺权限，返回当前会话最新预演任务或 `null`；结果含 `task_id,trigger_message_id,agent_run_id,status,content,processed_at,send_performed:false`。客户端只展示与当前买家消息 ID 一致的草稿，坐席可手动填入编辑框。入站任务按平台消息去重，预演调用店铺已发布多 Agent、已授权只读工具及绑定知识；不写买家消息，也不触发平台发送。现有真实发送开关不因该策略改变。

## 回复偏好与内部译文（2026-10-31 本地候选，未部署）

现有 Agent 配置 `reply_profile={tone,reply_language,operator_language,brand_name?}` 请求字段不变；发布后冻结偏好，保存草稿不改变运行。模板仍不复制该字段，批量发布保留本店值。

Agent 调试结果兼容新增 `customer_translation: TranslationBundleResult|null`、`customer_translation_error_code: string|null`。正式工作台沿用 `translation` 内部视图，兼容新增 `translation_error_code: string|null`；不向正式视图暴露 Provider/模型/用量。买家正文 `content`、`draft_reply`、`reply_parts` 与未复核流式草稿不混入坐席译文。译文错误为 `translation_unavailable` 或 `deadline_exceeded`，不会抹除已安全通过的买家正文；无偏好、同语或无共识跳过时为 NULL。认证、CSRF、店铺范围、权限和发送确认保持原契约。

## Agent 模板与后台批量应用（2026-10-30 本地候选，未部署）

模板是配置复用入口，店铺运行仍读取自己的已发布 AgentConfigVersion。以下后端接口已实现；完整批量 UI 与最终联合验收仍按实施任务推进，不把接口就绪当作上线。

| 接口（均位于 /v1） | 契约 |
|---|---|
| GET/POST /agents/templates；GET/PATCH /agents/templates/{id} | 共享已发布库及管理员草稿；编辑带 expected_revision。GET列表返回 items/can_manage |
| GET /agents/templates/catalog | 无店铺依赖的已配置原生工具模型、七段标题及全部注册工具元数据，不推断店铺授权 |
| POST /agents/templates/from-agent | source_agent_id，并明确 source_version 或 source_draft_revision 二选一；只提取通用字段 |
| GET /agents/templates/{id}/versions；POST /publish、/archive、/restore | 不可变模板版本；写操作需精确 expected_revision，发布不改变店铺运行 |
| GET /agents/templates/application-stores | 逐店 agent.manage 的 active/未删除店及候选 Agent；page/page_size/search，返回 items/pagination |
| GET /agents/templates/application-stores/{store_id}/knowledge-files | 同店 agent.manage 与 knowledge.view；返回本店文件当前有效版本、审批和 can_publish，无正文/存储路径 |
| POST /agents/templates/{id}/application-previews | template_version、逐店 create/adopt/update 请求和可选 parent_batch_id；返回持久 preview_id/hash、完整目标、A/B/C差异、issues/warnings |
| POST /agents/template-batches | 只接受 preview_id 和严格 confirmation:true，加稳定 Idempotency-Key；激活同一预览，HTTP不执行模型 |
| GET /agents/template-batches；GET /agents/template-batches/{id} | 列表默认20项、详情默认50项，最大100；本人或系统管理员可见，店铺详情再按现时权限隐藏 |
| POST /agents/template-batches/{id}/retry-failed、/cancel | 临时故障相同冻结配置重试；改配置必须重新预览。取消不回滚已成功项 |
| GET /agents/{id}/template-source；POST /agents/{id}/detach-template | 逐店 agent.view/manage；来源区分 draft 与 published；解除请求仅 expected_revision，不改变运行版本 |

TemplateConfig包含默认名称/建议编码、类型、职责、模型提供方与模型名、七段提示词、工具集合、知识需求槽；实际文件ID、reply_profile、凭证、会话和记忆不进入模板。名称/编码仅create可改，enable_after_publish仅显式发布新Agent时合法。ApplicationItemRequest.fields=null表示首轮建议，{}表示此次不更新管理字段；字段选择为template/local/manual，仅manual接收完整value（包括显式null）。知识需求按同店logical file ID映射，发布资格检查当前有效版本ready、approved_for_internal_review且审批人/时间非空。

预览不写店铺配置；确认和执行重验当前权限、Agent revision/运行版本/启停、模板归档、模型/工具目录和知识依赖。输入变化返回冲突或需重新预览，不静默替换版本。相同创建者/key和preview返回原批次；同key不同preview或已激活preview换key返回409。客户端遇未知结果先查询同preview ID，不生成新key重建。批次queued/running/completed/partial_failed/cancelled，逐店pending/running/succeeded/failed/needs_repreview/skipped/cancelled；partial_failed仅代表结束且含错误，须结合counts区分全失败和部分成功。

逐店结果的 `old_published_version` 来自预览时冻结的 `expected_published_version`，新建无旧版本为null，不随Agent后续发布改变；`result_version` 沿用本次项目的结果版本，保存草稿时可能保持旧运行版本。两者都按当前逐店权限隐藏为null，界面不能从现时Agent推测旧批次历史，也不能把草稿成功当作新运行版本已生效。

来源draft.fields的aligned、local_override、pending_review独立可重叠，不能相加充当字段总数，也不能把部分字段更新标作全面V2。published保存原运行版本的不可变来源；detach只清草稿关联、revision加一和审计，不自动发布。模板维护只允许数据库系统级admin；写操作继续CSRF，知识和业务工具权限不因模板共享扩大。

## 有序回复与物流通知（2026-10-30）

- `POST /v1/chat/query` 新增可选 `reply_mode: single|review_plan`，默认single兼容旧调用。review_plan的SSE新增draft：`{part_index,text,replace:true,unverified:true,sendable:false,trigger_message_id}`，text为当前整段快照；原result新增 `reply_parts/logistics_order_numbers/trigger_message_id/reason_codes`，content仍为首段，所有可用段均经复核。done completed不代表非空可用答复。
- `GET /v1/workspace/sessions/{id}/logistics-card-preview?order_id=` 需workspace.view及orders.view，返回 `{card,packages,enhanced_available,selected}[]`；订单为TikTok外部数字ID，必须再核对当前买家，预览不依赖发送开启，不创建消息。
- `POST /v1/workspace/sessions/{id}/reply-batches` 需workspace.reply、CSRF及Idempotency-Key；body为 `{trigger_message_id:null|UUID,parts:[{kind:text,content}|{kind:logistics_card,order_id,package_id?}],preview_only:true,confirmed:false}`。文字在卡片之前，每段2000 UTF-16、计划16000预算。实际人工发送需preview_only=false且confirmed为严格JSON true；卡片另需orders.view。返回 `{id,preview_only,status,parts:[{index,kind,status,message_id,error_code}],messages}`；parent状态previewed/completed/partial/failed/unknown。相同key必须完整同body，已成功文字跳过，已知失败可明确重试，unknown先对账。预演key不能变成真实发送key。
- `GET/PATCH /v1/agents/logistics-notifications/policy?store_id=` 读取/保存当前店铺策略；PATCH `{enabled,agent_id,mode:preview|external,expected_revision}`，乐观revision防覆盖。返回store_id、agent_id、enabled、mode、enabled_at、revision、global_enabled、real_delivery_enabled、last_scan_at。保存策略不等于全局开启或发送成功。
- `GET /v1/agents/logistics-notifications?store_id=&conversation_id=&offset=` 及 `GET /v1/agents/logistics-notifications/{key}?store_id=` 只返回授权范围低敏台账和已复核preview_text。
- `POST /v1/agents/logistics-notifications/preview` 需CSRF及当前店铺workspace.reply/orders.view，body `{store_id,conversation_id,order_id,package_id?}`；此order_id为CRM UUID。返回status previewed/blocked/rejected及reason、preview_text、event_at、buyer_language。不消费通知基线、不启动jobs、不向平台发送。预演必须有已核验CRM订单UUID，不能用外部ID替代；临时工作台预演入口已移除，协议保留供内部受控验收。

新物流通知的真实投递为独立默认关闭能力；通用公开自动回复仍关闭。本轮审阅、工具与RAG已有零外发现场验收；不代表买家原生流或真实通知已验收。

Agent 回答的本轮内部契约更新不改变 HTTP 路径或请求字段：调试和工作台人工建议共用语义事实/隐私复核，只返回过滤、重组并重新复核的纯文本正文；保留授权工具核实的正常业务编号，按买家原始语言与问题详略表达。工具完成后生成失败、超时或取消，运行记录仍保留真实工具状态及逐轮已知用量。`send_performed=false` 仍是固定边界，启用正式建议不等于授权发送。

仅规范 UUID 的 `POST /v1/agents/{agent_id}/debug` 与 `POST /v1/workspace/sessions/{session_id}/suggest` 请求使用通用请求预算加 Agent 预算的外层期限，内部 Agent 仍受原绝对期限限制；其他路由、方法及无效路径仍使用通用预算。工作台建议超过平台2000字符时完整保留草稿，可展开编辑与预览，精简前禁止翻译、送审和发送；后端发送长度及人工确认校验保持。

2026-10-29 统一 Agent 与多店授权发布已将当前管理 API 部署至 staging `45d872c0`，041 合流迁移生效。调试入口已开启，正式建议保持关闭；原店铺/渠道/工作台只读兼容通过，Agent 业务回答仍待验收。未新增真实授权或发送。当前发布范围和限制见[部署说明](../operations/DEPLOYMENT.md)。

Agent 发布接口在既有授权、revision和模型配置校验后执行一次语义隐私复核；返回422表示配置需修改，503/504表示模型检查未完成，原发布版本保持。编译或保存草稿不代表通过发布复核。成功审计只含版本、哈希、复核版本和数值用量，不写配置正文。

## 通用约定

- 业务接口位于 `/v1`，响应使用统一 `code/message/data/request_id` 信封；流式接口使用 SSE 事件。
- 登录态、店铺范围和权限由服务端判定；写操作同时执行 CSRF、幂等和审计要求。
- 客户端不得在普通对话/运行请求提交任意 Prompt、模型名、阈值或跨店铺标识。`agent.manage` 的 Agent 草稿配置是独立授权入口；模型必须属于服务端当前配置，七段式 Prompt 发布前须校验并形成不可变版本。
- 真实密钥、Token、凭证引用和内部错误正文不进入公开响应。
- 响应带服务端生成的 `X-Trace-Id` 和低敏 `Server-Timing: app;dur=<毫秒>, tiktok;dur=<毫秒>`；TikTok 耗时为本请求内只读 HTTP 尝试累计值，可能因并发大于应用墙钟耗时。后端日志仅记录路由模板、方法、状态、两段耗时和调用次数，不记录 URL 参数、订单 ID 或请求体；前端仅对耗时超过 1.5 秒的 API 在浏览器控制台输出固定分组、状态、耗时和 Trace ID。

## 已实现接口族

### 认证

- `POST /auth/login`、`GET /auth/me`、`POST /auth/refresh`、`POST /auth/logout`。
- 浏览器会话接口提供 HttpOnly Cookie 与 CSRF 保护；失败统一返回认证/权限错误。
- 前端同一页面中并发请求遇到 401 时共用一次浏览器 Cookie 刷新；已在本批次刷新后才返回 401 的 GET/HEAD 及已确认只读的会话搜索、客户侧栏搜索/订单详情/通用与增强物流 POST 直接重试。其他写请求仍经刷新后重试，不能据此省略刷新。每个原请求最多重试一次，POST/PATCH 等复用原幂等键；刷新失败保持未认证结果，不保存 Token 或扩大权限。

### 看板

- `GET /dashboard/metrics|trend|channels|alerts|top-queries`。
- 数据按授权店铺聚合，时间范围、空数据和分页参数由服务端校验。

### 客服工作台与 AI

- 会话列表/详情、消息记录、状态更新和受控工具均位于 `/workspace`。
- 已授权 TikTok 店铺的会话和历史经内部只读同步写入现有会话/消息表；列表和详情仍通过原 `/workspace` 接口按店铺权限读取。工作台会话列表每页取 30 条，触底按列表返回的 `pagination` 自动加载更多，店铺与平台筛选在每一页保持一致。详情消息按时间升序分页，前端先取最新页，可继续加载较早历史。TikTok 消息只读调用请求 `need_data=true` 和 `need_plaintext=true`；Webhook 与历史同步统一提取图片、表情、视频及原生卡片的展示字段，消息 `message_type` 保留平台类型，媒体 URL 与卡片摘要写入现有 `raw_payload`，不保存完整平台载荷。`MessageView.media` 可返回平台原始 `url/cover/vid/width/height/duration/expire_time` 的安全展示子集；`rich_card` 可返回类型、标题、图片、金额、状态、商品/订单/包裹标识及物流摘要及多包裹列表。外链只接受 HTTPS。旧 `[TikTok 类型]` 记录可由 staging 只读同步脚本的 `--refresh-rich` 模式按平台消息 ID 幂等补齐，不新增未读或外发。
- 原生 TikTok `logistics_card` 的聊天记录仅在卡片带有明确 `order_id` 时显示“查看详情”；点击后复用当前会话的订单详情只读接口，按同店、同买家核验后按需读取物流轨迹。缺少订单标识时不根据相邻订单猜测卡片身份；查看不触发消息发送。
- 工作台标签页可见时每 5 秒重新读取列表与当前会话最新消息；按消息 ID 合并并保留已加载的历史、选中会话及草稿，避免每次刷新重置界面。
- `GET /workspace/sessions` 支持 `filter=all|unread|mine|starred|closed`；默认列表不含本地已关闭会话，`closed` 仅列出已关闭会话。列表响应额外返回 `unread_messages_total`，汇总当前用户有权访问的未关闭会话未读数，不受搜索和分页影响；列表和详情的 `session` 均返回 `unread_count`、`is_starred` 和 UTC `closed_at`。前端打开会话定位最新消息；读取较早页保持阅读位置，新消息不会把正在阅读历史的坐席拉到底部，并提供“到最新消息”。
- 会话列表与详情的 `customer.buyer_stage_override` 为 `pre|during|after|null`；`null` 时前端按最近一笔已同步订单状态推断阶段，未知状态显示待判断。`PATCH /workspace/sessions/{session_id}/buyer-stage` 需 `workspace.reply` 与 CSRF，body 为 `{"stage":"pre|during|after"}` 或 `{"stage":null}`；服务端先按会话授权核对店铺，再锁定同店客户行，更新客户 `metadata.buyer_stage_override` 并审计。此接口不发送平台消息，也不修改订单。
- `POST /workspace/sessions/search` 要求 `workspace.view` 和 CSRF，body 可带 `filter/platform/store_id/status/page/page_size/search_scope/q/terms`。`search_scope=all|buyer|order|tracking|product`；`q` 为单项搜索，`terms` 为批量任一命中，二者互斥，最多 20 项、每项 1～120 字符。结果仍按授权店铺稳定分页；订单、物流和商品仅通过同店同平台同买家订单关联。搜索词置于 body，避免 URL 访问日志收集买家及订单标识。普通无搜索列表仍使用 GET。前端在同一搜索框按逗号、分号或换行分词：单项用 `q`，多项用 `terms`；无独立批量弹窗。
- `POST /workspace/sessions/{session_id}/sidebar/search` 要求 `workspace.view`、CSRF 和该会话所在店铺权限；body 的 `section=orders|products|coupons` 决定结果结构。真实 TikTok `orders` 先按授权店铺读取官方 202601 单会话，核对唯一 BUYER 的 IM ID，再使用官方订单域 `buyer_user_id` 搜索并逐条核对返回身份；其他模式仅查同店、同平台、同买家的已同步订单。TikTok 202309 订单搜索若省略 `orders`，仅在 `total_count` 为整数 0 且 `next_page_token` 为空串时按零订单处理；其余缺失、类型错误或非空分页仍失败关闭。支持状态、订单号、物流号、商品名、商品 ID、SKU ID、卖家 SKU 筛选及页码；仅返回平台实际提供的金额拆分、商品和物流字段，缺失项为 `null`，不推断。单买家超过 2000 笔订单或分页身份异常时明确失败，不返回伪完整结果。`products` 与 `coupons` 只接受 TikTok 已连接的有效店铺，分别按官方只读目录分页返回；商品需要 `seller.product.basic`，优惠券需要 `seller.customer_service` 或 `seller.promotion.info`。商品名和优惠券编码按当前平台页过滤，`partial_search` 与 `next_page_token` 告知后续页可能还有结果；搜索词仅置于 body，不进入访问 URL。缺授权、平台错误和上游结构异常均失败关闭，不用示例数据代替。
- 真实 TikTok 订单的 `items[]` 仅在官方订单行提供时附带 `package_id` 与 `tracking_number`，用于将卡片草稿的商品与选中包裹对应；映射不唯一时卡片不推造商品信息。
- 订单搜索只缓存已核验平台买家 ID 和不含收件信息的列表投影 20 秒；键含店铺、会话、CRM 买家、渠道、shop cipher 和加密授权版本。最多 64 个买家、每个投影最多 100 笔订单；更大列表只短存核验买家 ID，过滤与分页仍重新从平台读取以保证完整性。`refresh=true` 绕过缓存，失效后重新核验；异常、429 和未核验结果不缓存。本地候选的 Agent 订单列表复用该核验边界，详情与物流重新核实所选订单，不默认最新订单。此缓存仅在当前后端进程内有效，重启或跨进程不共享。
- `GET /workspace/sessions/{session_id}/sidebar/products/{product_id}` 要求 `workspace.view`、会话店铺权限及 Product Basic 授权；仅接受数字商品 ID，使用官方商品详情只读接口取得图片、规格和库存，核对返回商品 ID。商品卡片进入可见区域且列表缺图片时自动读取详情，展开 SKU 也可读取尚缺的详情；商品列表触底自动加载后续页。侧栏优惠券与商品的“填入回复草稿”只修改前端草稿，不调用消息发送、优惠券发放或退款接口。
- 工作台商品搜索、按 ID 查询及详情与 Agent 的 `search_products`、`query_product` 共用上架且有正库存的筛选；详情读取时再次核验，若商品已下架或无库存则返回 404。工作台优惠券目录与 Agent 的 `query_available_coupons` 共用进行中且处于领取时间窗的筛选，不承诺买家个人可领。目录分页 `total_count` 是平台原始总数，`next_page_token` 可在当前筛选页为空时继续存在；直查商品 ID 的总数按实际可见结果返回。
- `POST /workspace/sessions/{session_id}/sidebar/orders/detail` 要求 `workspace.view`、CSRF 和当前会话店铺权限；数字订单 ID 仅放在请求体。服务端先以官方会话参与者核对 CRM 买家 IM ID，再读取当前店铺订单详情并逐条核对订单 ID 与订单域买家 ID；不匹配返回 404，绝不向前端返回其他买家数据，缺授权或上游异常失败关闭。请求体的 `include_tracking` 默认 `true`，兼容原响应；卡片和详情页传 `false` 时先返回付款方式、`recipient_address`（`name`、`phone_number`、`full_address`）及承运商，`tracking_loaded=false`，不等待物流接口。收件字段仅来自核验后的官方订单详情；平台掩码和 `null` 原样保留，不落库、不写日志、不在订单列表接口返回，也不调用解密接口。
- `POST /workspace/sessions/{session_id}/sidebar/orders/standard-tracking` 以相同数字订单 ID 请求体读取通用 `202309` 物流节点，按时间降序返回最新描述/UTC 时间及全部节点。要求同一 `workspace.view`、CSRF、会话店铺权限和 `seller.logistics`；使用当前店铺、会话买家、授权渠道及订单的 20 秒进程内核验结果，证明失效时重新核验官方会话与订单身份。通用接口不提供可靠包裹分组，不按商品行推造包裹。客户卡片可见时自动详情读取最多两笔并发，摘要立即可见，基础详情与物流独立显示加载和错误；中文物流状态只依据官方订单状态或明确的轨迹描述。详情视图默认只显示最新两条轨迹，坐席可展开全部。所有读取不触发履约、退款或消息写入。
- `POST /workspace/sessions/{session_id}/sidebar/orders/enhanced-tracking` 使用同一数字订单 ID 请求体，要求 `workspace.view`、CSRF、同店会话及官方买家/订单身份核对；仅 OAuth 店铺类型 `CROSS_BORDER` 调用 `202604` 只读轨迹。按店铺 cipher 摘要与订单 ID 用 Redis 原子占位，成功响应或失败冷却均保持八小时，避免并发或刷新突破平台每单频率限制。响应按官方 `logistics_details[]` 返回包裹、最新单号、承运商及全部节点，历史节点保留原单号。增强接口失败时前端继续显示详情接口的通用轨迹，不把通用事件分配给虚构包裹。
- `POST /workspace/sessions/{session_id}/sidebar/orders/tracking-translation` 使用同一数字订单 ID 请求体，要求 `workspace.view`、CSRF、翻译开关及速率限制。默认翻译经买家核对的最新物流描述；传入节点描述、UTC 时间、节点单号与 `enhanced` 标志时，必须在重新核对后的通用轨迹或增强缓存中精确命中，才能按坐席点击逐条调用现有翻译节点。敏感描述拒绝送入模型，失败保留前端原文；审计元数据不含原文，不发送消息、不修改平台或订单。
- `POST /workspace/sessions/{session_id}/sidebar/orders/tracking-timeline-translation` 请求体为数字 `order_id` 与 `enhanced` 布尔值；要求 `workspace.view`、CSRF、翻译开关和一次接口限流。服务端重新核对会话买家与订单，仅从核对后的通用轨迹或跨境增强缓存读取全部节点，不接受客户端提供节点原文；无节点、超过 40 条或任一节点含需脱敏内容时拒绝整批。现有翻译节点以最多三个并发调用模型，按节点原文、UTC 时间及单号返回译文；任一失败时不展示部分译文，审计只保存条数和用量。前端一次替换全部包裹节点，可切回原文或重新翻译；弹窗中的“发送物流卡片”只创建本地卡片草稿，不调用发送接口。
- 客户侧栏订单列表的 `paid_at` 仅从官方订单 `paid_time` 或现有本地订单支付时间投影为 UTC，缺失为 `null`；不由订单状态推断付款时间。优惠券列表的 `discount_value` 将已识别的金额对象转换为币种加金额的字符串，无法解析时为 `null`，不向前端透传 Python 字典文本。订单状态对应的截止、取消或退款字段当前未在只读模型中提供，工作台仅显示空值。
- TikTok 买家 Webhook 消息按平台消息 ID 幂等增加未读；只读同步补入晚于上次成功同步时间的买家新消息时也增加未读，首次历史回填不把旧消息算成新未读。
- 工作台会话列表和详情按同一店铺角色过滤：管理员与本店主管可看全部，普通客服仅看自己负责的会话及待领取队列；未领取时发送模式为 `disabled`。`session.can_manage` / `can_claim` 由服务端按该店实际授权计算，详情的 `needs_takeover` 标记原手动负责人失去资格；主管详情可见最近 20 条低敏 `assignment_events`。`POST /workspace/sessions/{session_id}/assign` 允许主管分配、普通客服仅领取给本人；普通客服转交本人会话须使用带原因与幂等键的 `POST /workspace/sessions/{session_id}/transfer`，目标必须在职且具有本店回复权限。星标、关闭、翻译、媒体和发送同样在服务端及工具执行时复核逐店权限和会话归属；跨店或他人会话返回 404。
- `PATCH /workspace/sessions/{session_id}/star` 接收 `{ "starred": true|false }`，只标记 CRM 内部差评风险；`PATCH /workspace/sessions/{session_id}/closed` 接收 `{ "closed": true|false }`，只更新 CRM 工作流；`GET /workspace/sessions/{session_id}/assignees` 只列出同店、在职且拥有 `workspace.reply` 的坐席。三者按授权店铺定位会话；写接口要求 `workspace.transfer`、CSRF 和状态变更审计。重复设置同一状态不重复审计。转交目标同样须在职、有当前店铺回复权限；关闭会话拒绝新发送和转交，未结清出站消息拒绝关闭。已关闭会话遇到晚于关闭时间的真实买家新消息会重新进入活跃列表，历史回填不触发重开。
- `POST /chat/query` 的安全建议结果在坐席主动生成或刷新后直接填入本地可编辑草稿，替换当前草稿；使用建议不会自动触发平台发送。人工确认、真实发送白名单及 `unknown` 对账仍按现有契约执行。
- `POST /workspace/sessions/{session_id}/suggest` 返回 AI 建议。
- `POST /workspace/sessions/{session_id}/messages` 仅发送人工确认的普通文本；TikTok 真实发送要求 `seller.customer_service` Scope、CSRF 和 `Idempotency-Key`。
- `POST /workspace/sessions/{session_id}/messages/media/upload` 接收单个 multipart `file` 和 `Idempotency-Key`，要求 `workspace.reply`、CSRF、会话所属店铺权限、已连接且具备 `seller.customer_service` 的 TikTok 渠道和真实发送目标白名单。服务端校验文件头、MIME 与大小；图片限 JPG/PNG/GIF/WebP ≤10 MiB，视频限 MP4/MOV/WebM 10–100 MiB。图片经官方 `202309/images/upload` 获取 URL/宽高；视频经官方 `open/202512/file/init` 和固定出口顺序分片获取 `vid`。只返回绑定坐席、店铺、会话及后续发送幂等键且 20 分钟过期的签名上传凭据，不向买家发送消息；上传成功记低敏审计。较小视频明确拒绝。
- `POST /workspace/sessions/{session_id}/messages/media` 接收 `{kind,image|video; upload_token; confirmed:true}`，另需与上传时相同的 `Idempotency-Key`。工具层核对凭据签名、有效期和坐席/店铺/会话/发送幂等键绑定；仅真实 TikTok 人工发送，复用同店未结清消息熔断、处理状态、幂等、审计和 `unknown` 人工对账。官方 `202606` Send Message 使用 `IMAGE` 的 URL/宽高或 `VIDEO` 的 `vid`；不接受客户端自填媒体 URL/ID。上传可留下未绑定资源，但取消或上传失败绝不发送买家消息。
- `POST /workspace/sessions/{session_id}/messages/logistics-card` 仅在坐席审阅卡片并显式提交 `confirmed=true` 后接受数字 `order_id` 与可选数字 `package_id`；要求 `workspace.reply`、CSRF 与 `Idempotency-Key`。服务端重新核对会话买家和该店订单；包裹 ID 必须来自核对后的订单行或官方增强轨迹，多包裹已知时必须指定包裹。客户端不能提交卡片正文或图片。返回消息含 `message_type=logistics_card` 与供 CRM 展示的已核对卡片快照；详情点击仍按原只读接口重新读取轨迹。
- TikTok 写客户端按官方 `POST /customer_service/202606/conversations/{conversation_id}/messages` 契约发送一次 `TEXT`、`IMAGE`、`VIDEO` 或 `LOGISTICS_CARD`，后者的序列化 `content` 只含订单 ID 与可选包裹 ID，`sender_role=CUSTOMER_SERVICE`；传输或平台内部结果不确定时记录 `unknown`，不自动重试。四种类型共用真实发送白名单、店铺未结清消息熔断、审计与人工对账。
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
- 通用文件使用 `/v1/knowledge/files` 列表、详情、版本和原文件下载；`POST /v1/knowledge/files/imports` 接收 `multipart` 的文件、店铺、可选分类、配置 JSON 和显式 `replace_file_id`，返回 202 与新版本状态。
- 文件元数据可通过 `PATCH /v1/knowledge/files/{file_id}` 调整到同店铺启用分类；`POST .../archive` 与 `POST .../restore` 维护可恢复归档，`DELETE /v1/knowledge/files/{file_id}` 设置软删除时间。历史版本、原文件和审计不被改写。归档文件仍在管理列表显示，删除文件从列表和详情隐藏；有排队、解析或索引中的版本时拒绝归档/删除。写接口沿用 `knowledge.manage`、CSRF、幂等键和店铺隔离；跨店铺文件返回 404。文件编辑 UI 的“替换文件”复用显式替换导入，要求同名并沿用分类。
- `GET /v1/knowledge/entries` 与 `GET /v1/knowledge/files` 新增可选 `categorized_only=true` 查询参数：仅返回当前授权店铺内归属启用分类的记录，在数据库分页和总数统计前筛选。省略或传 `false` 保持原有含未分类数据的 API 行为；知识库管理页的“全部知识”、分类角标和列表显式传 `true`。历史未分类数据不删除，文件详情接口仍可按 ID 读取；上传 API 的分类字段继续可选以兼容既有调用，管理页要求用户先选分类。
- `POST /v1/knowledge/files/{file_id}/versions/{version_number}/units/{unit_index}/review` 对单元提交人工修订与确认；`.../retry` 只重试可恢复版本。`GET/PUT /v1/knowledge/file-settings` 读取和保存店铺级导入配置；每次上传冻结配置快照。写接口均要求店铺范围、`knowledge.manage`、CSRF 与幂等键，读接口要求 `knowledge.view`；跨店铺文件返回 404。
- `POST /v1/knowledge/files/{file_id}/versions/{version_number}/approve` 接受显式 `statement_type` 与 `customer_scope`，仅当前店铺、未归档/删除、当前有效且索引就绪的版本可由 `knowledge.manage` 审批为内部建议知识；`.../revoke` 撤销已批准版本。CSRF、幂等键和审计必需。未知类型与具体客户事实拒绝审批，替换文件须重新审批。文件列表与版本详情返回审批状态和语义元数据。
- 通用文件状态包括排队、处理中、待复核、失败和就绪；待复核版本没有任何新向量，旧有效版本保持可用。Agent 仅使用显式绑定、已审批且当前有效的文件版本；未绑定时不查询整店 FAQ，仅用本次授权工具，证据不足则澄清或转人工。新运行开关关闭时返回明确不可用，不回落旧 FAQ 执行器。
- 当前不开放 `approved_for_public_reply`，发布 FAQ 不等于允许自动发送。

### 营销

- `/marketing` 提供活动/任务的列表、新建、详情、受控更新、启停、预览/执行和报表能力。
- `GET/POST /marketing/reception/groups|replies|policies` 及 `PATCH/DELETE /marketing/reception/{groups|replies|policies}/{id}` 管理基础接待配置，统一使用 `/v1` 前缀。列表返回 `items,total,page,page_size`；分组与回复必须按 `store_id`、`scope=personal|team` 查询。分组返回 `enabled` 和 `reply_count`，`PATCH /groups/{id}` 可切换 `enabled`；回复还可按 `group_id`、`q` 模糊查找或 `shortcut` 精确查找。回复列表默认排除停用分组，管理页可传 `include_disabled=true` 查看和编辑，仍按原权限与店铺隔离；工作台及快捷键查询不传该参数。策略按必填 `kind=timeout|welcome` 查询，可选 `store_id` 限定单店；省略时只返回当前账号对所有关联店铺均有 `marketing.view` 权限的策略，按策略去重后分页。新建和更新策略还需对全部关联店铺同时具备 `marketing.manage` 与 `marketing.view`。回复只接受文本 `messages`、快捷键、最多三个标签及站点展示码；策略包含文本、适用店铺、有效期、配置开关和顺序；`schedule` 可为空以兼容旧版 `valid_from/valid_to` UTC 时间，新增配置用 `schedule.mode=long_term|date_range|fixed_hours`，后两种要求本地起止日期，固定时段还要求同一天内的每日起止时间，均按各店铺时区解释；响应固定 `delivery_enabled=false`。写入要求 Cookie CSRF、幂等键及审计；个人回复绑定当前用户，团队写入与策略写入要求 `marketing.manage`，所有资源先核对服务端店铺范围。该组接口没有执行或平台发送操作。
- 当前能力用于内部管理和验证；自动营销与真实高风险写入未放行。

### Agent 运营

- `GET/POST /agents`、`GET/PATCH/DELETE /agents/{agent_id}`。
- 迁移 035～039 后，Agent 响应增加 `draft_revision`、可空 `published_version`、草稿 `model_provider/model_name/prompt_sections`，运行记录增加 `parent_run_id/config_version/phase`。`POST/PATCH /agents` 可保存模型及七段式 Prompt 草稿；`PATCH` 可传 `expected_revision` 做并发检查。`POST /agents/{agent_id}/publish` 需 `agent.manage`、CSRF 和 `expected_revision`，生成不可变版本及摘要。发布不自动启用或部署。新版正式执行开关默认关闭，开启时同店所有启用 Agent 均进入模型路由候选。
- `POST /agents/{agent_id}/enable|disable|toggle`、`GET /agents/{agent_id}/logs`。
- 普通 Agent 列表、详情及运行日志按目标店铺 `agent.view` 过滤；创建、修改、发布、启停、删除及调试按目标店铺 `agent.manage` 校验。部门会话监督范围不授予其他店铺 Agent 配置权限；工作台正式建议维持既有会话权限。

- `POST /agents/{agent_id}/debug/stream` 使用相同请求体及 agent.manage、CSRF、店铺/会话/绑定文件权限校验和 AI 限流，另申请当前用户 SSE 并发租约。按 accepted → draft* → result|error → done 交付；draft 包含 part_index、text 完整快照、unverified=true、sendable=false，只供坐席查看。result 是原 AgentDebugView 的完整复核终态，包含全部已复核答复段、路由、工具和引用；失败或断线清除草稿，不自动重发。连接关闭取消模型运行并记录 DYNAMIC_RUN_CANCELLED，finally 释放本请求租约。原 JSON 调试接口保留兼容；runtime.token_streaming=true 表示支持调试草稿流，不代表自动发送已开启。
- `POST /agents/{agent_id}/debug` 接收 `message`、可选 `conversation_id` 和 `mode=single|store`，需要 `agent.manage`、CSRF 和 AI 查询限流。新版调试开关开启时，`single` 可调试该店铺已发布的停用 Agent；`store` 从该店所有启用 Agent 的发布版本中路由一个或多个。服务端再次校验店铺及文件绑定；绑定文件需 `knowledge.view`，会话需 `workspace.view` 且同店。响应返回人工建议、`routed_agents/tool_events/reason_code`、有效文件引用和追踪号；没有会话时订单和客户工具缺少可信对象，执行会返回明确的上下文缺失状态。TikTok 会话经已验证买家身份返回订单候选，模型选择后才查询对应详情或物流。商品、优惠及绑定知识可独立于买家会话查询；两个明确配置的内部写入可保存 AI 协作记录。调试不创建客户消息、不执行平台写入或发送。
- `reply_profile` 仅接受固定语气、回复语言、坐席语言和经清洗的品牌名；阈值字段仍拒绝。模型及 Prompt 仅能经 Agent 草稿与发布接口配置，不由调试或正式运行请求覆盖。
- Agent 新建与修改支持 `agent_type=service|operations` 和当前授权店铺的 `knowledge_file_ids`。新增或改变非空文件绑定还需 `knowledge.view`；新版执行器由职责描述而非固定类型决定参与路由。文件绑定保存时校验店铺，运行时再校验版本审批、有效状态、归档/删除和模型门禁。文件 RAG 的查询向量化、SQL 与重排共用 12 秒总时限，总 Agent 运行另受同一绝对截止时间限制。
- 只读 `runtime.model_options` 与旧 `available_models` 列出当前服务端配置的模型；发布时只接受支持原生 function calling 的 provider/model 组合。已保存七段草稿和已发布版本分离；未发布配置不能启用。旧版本 1 可在固定保守七段模板与当前主模型下运行，仍只用原配置工具及绑定文件，管理员发布新版后替换。`knowledge_scope` 规范值为 `bound_files_only`；旧请求的 `store_ready_faq` 字面值只作为输入别名归一化。本地候选尚未部署。

### 团队与渠道

- `GET /settings/team` 与 `GET /settings/team/{user_id}` 对所有已认证账号提供只读账号目录；旧邮箱登录账号无独立登录名时，非管理员响应将该邮箱作为登录标识显示，同时隐藏独立邮箱、手机和上次登录字段。`POST/PATCH/DELETE /settings/team` 仍要求系统级管理员和 CSRF，普通删除表示禁用。
- 员工读取响应中的 `assignments[].role` 保留数据库已有角色编码（包括受控测试角色），避免历史账号使整个列表失败；新建和修改账号的角色写入仍只接受 `admin`、`supervisor`、`agent`，且继续校验系统级／店铺级范围。账号页将一个或多个所选店铺映射为现有 `assignments` 数组；系统管理员使用 `store_id=null`，普通客服和客服主管逐店授权。编辑基本资料未改角色或店铺时不提交 `assignments`，以免覆盖既有权限。
- `POST /auth/login` 与 `/auth/browser/login` 接受 `identifier`（登录账号或邮箱），旧 `email` 请求字段继续兼容；新界面登录名 6–16 位且创建后不可修改，旧 API 调用仍可仅用邮箱创建。`POST /settings/team` 可保存可选邮箱、手机号码、工作时区、账号并发数、初始部门；`PATCH /settings/team/{user_id}/password` 修改密码并使旧 Access/Refresh Token 失效。账号并发数不施加运行限制。`DELETE /settings/team/{user_id}/permanent` 仅系统管理员持有效 CSRF 可用，要求目标已停用、不是当前用户且没有受保护业务引用；否则返回 409，成功返回 204 并记审计。页面仅对已停用账号提供二次确认入口。
- `GET/POST /settings/departments`、`GET/PATCH/DELETE /settings/departments/{department_id}`、`GET/POST /settings/departments/{department_id}/members` 和 `DELETE /settings/departments/{department_id}/members/{member_id}` 管理部门与组织成员。已认证账号按可见店铺读取部门及成员，写入只限系统级管理员并要求 CSRF、审计。部门成员增删不改变逐店角色，空部门才可删除；部门页账号目录由全体账号列表构成，标注当前部门成员关系。
- `GET/PUT /settings/departments/{department_id}/reception` 读取或一次保存部门全部负责店铺的自动派单开关和部门成员参与资格；GET 要求 `settings.team` 且校验部门店铺范围，PUT 只限系统级管理员并要求 CSRF、审计。响应包含成员对哪些店铺可回复、登录会话在线状态和待领取数；系统级管理员覆盖全部有效店铺，主管覆盖所属部门全部店铺，普通客服须有对应店铺 `workspace.reply`。管理员仍须属于部门并由管理员显式勾选参与，登录有效后才进入派单候选。旧逐店配置和工作台接待心跳路由已移除；数据库旧表保留供迁移审计。登录、刷新、退出维护可过期登录会话，派单不发送平台消息。
- `DELETE /settings/team/{user_id}/permanent` 仅能删除已禁用且无受保护业务引用的用户。
- 店铺与渠道位于 `/settings/stores`、`/settings/channels`；`GET /settings/store-authorizations` 和 `GET /settings/channels` 要求 `settings.store_authorize`，在同一次服务端授权范围核验后返回当前用户可见且未被本地删除的 TikTok 店铺及其渠道展示字段，供店铺页一次请求回显；主管仅可见所属部门负责店铺，平台侧撤权仍保留异常行。权限由迁移 `047_supervisor_store_auth` 赋予主管，系统管理员保留全局权限，不扩展通用 `settings.channels` 写操作。通用渠道创建仅用于 Shopee/Amazon 契约级 Mock，禁止创建 TikTok 真实记录。`PATCH /settings/stores/{store_id}/alias` 仅更新目标店铺的展示别名，要求系统级或目标店铺管理员、CSRF 与审计；店铺列表返回别名，TikTok 渠道列表返回站点、平台授权与刷新凭证两者更早的到期时间、低敏授权状态及最近授权时间，无数据时为 `null`。

### TikTok OAuth 与 Webhook

- `POST /settings/stores/tiktok/oauth/start` 要求 `settings.store_authorize` 和 CSRF。系统管理员可全局新增；客服主管须属于唯一负责部门且在该部门的有效店铺有主管角色。平台仅返回一家店时沿用自动连接；返回多家店时 worker 进入 `selection_required`，限时加密保存本次卖家授权，不自动创建店铺。原发起人明确勾选后才原子创建或复用各店铺与渠道；主管新增店铺同时关联其负责部门。取消、失败和重复授权不留下空店。已断开的同一平台店铺复用原系统 ID，仍须核对目标店铺权限；已连接的其他卖家店铺拒绝覆盖。
- `GET /settings/channels/tiktok/oauth/start` 用于原店铺重新添加；发起、排队、进度读取及完成均重新校验系统级或目标店铺的渠道管理权限，主管的 `settings.store_authorize` 只覆盖所属部门负责店铺，不能借用其他店铺的角色。若重新授权或新增店铺会轮换卖家共享凭证，还须具备每家受影响已连接店铺的管理权限。两种入口均创建默认 600 秒随机 `state`，哈希键绑定发起用户、可选店铺与白名单站内回跳地址。公开 callback 不依赖 CRM Cookie；成功路径只创建一次短期加密任务并立即 303 至对应设置页的 `?oauth=tiktok&status=processing&job=<UUID>`，不等待 TikTok 外部 API。已有任务的重复 callback 不二次交换 Token。拒绝/缺失 code 沿用即时失败回跳。
- `GET /settings/channels/tiktok/oauth/jobs/{job_id}` 需要 `settings.store_authorize`、原发起用户，以及原店铺管理权或新店授权时仍符合唯一负责部门条件；状态增加 `selection_required`，此时仅返回店铺 ID、名称、编码、站点、卖家类型和选择到期时间，不返回 Token、`shop_cipher` 或 `open_id`。jobs worker 原子消费 `state`；单店完成或多店待选择时清除一次性 state/code 密文，失败或中断要求重新授权，不重放 code。
- 授权任务失败时，原发起人可在低敏进度响应中读取稳定 `error_code`；原店铺重授权任务还返回已受访问权核验的 `store_id`，用于精确恢复入口。成功、待处理和待选店铺不返回失败原因。管理端以店铺页“添加店铺”发起新授权、在异常或断开行上对指定店铺重新授权；授权页只显示结果并兼容旧回跳地址，不提供不绑定店铺的全局 OAuth 入口。店铺页须刷新店铺与渠道列表后再显示连接成功。
- `POST /settings/channels/tiktok/oauth/jobs/{job_id}/shops` 需要 CSRF、`settings.store_authorize` 和原任务发起人，并复核主管唯一负责部门条件；请求 `shop_ids` 为不重复的本次候选店铺 ID，单次最多 200 家。服务端解密限时 Token，重新核对卖家、实际授予 Scope、最新授权店铺、站点和已有租户绑定；复用店铺及共享卖家凭证影响的已连接店铺均须在当前操作者管理范围，再以单事务连接勾选的店铺。重复提交或过期返回冲突，不跨店部分成功。
- Token 刷新是内部能力，没有公开 Refresh API；多店渠道引用同一卖家级加密凭证，按卖家行锁轮换一次，再逐店核对当前平台授权清单；失去授权的店铺单独过期，旧单店渠道继续按原店铺级密文读取与刷新。解密、刷新或契约校验失败时受影响渠道转为 `expired`。
- `DELETE /settings/channels/{channel_id}` 对 TikTok 渠道要求系统级或目标店铺管理员，撤销该店本地 Token 可用性并保留渠道绑定、系统店铺、历史订单/会话及审计；共享授权仍有其他已连接店铺时不影响它们，最后一家删除时销毁卖家级本地凭证。店铺列表只隐藏用户主动删除的渠道，平台侧解除授权仍显示异常以供重新添加。未来同店再授权可复用系统 ID。该操作不调用 TikTok 平台的远端取消授权接口。
- `POST /webhooks/tiktok` 在真实模式只接受官方 `Authorization` 签名，以原始请求体进行常量时间校验；签名失败在数据库查询/写入前返回 401，不占用通知 ID。相同通知 ID 只有原始正文摘要一致且已绑定店铺时返回成功的重复回执；不同正文返回 409，未知店铺的首次及重复通知均返回 404 且不保存载荷。乱序送达的旧消息照常入库，但不覆盖较新消息的会话排序字段。公网版本前缀为 `/v1`。
- G2 真实重投诊断仅可在 staging 的精确店铺与受控买家会话中显式开启。已验签、已绑定且结构有效的首个新消息通知可在落库前或落库后返回一次 HTTP 503；Redis 原子一次性标记与绝对失效时间阻止再次触发。后续同一正文重投仍走原有幂等回执，诊断审计仅保留正文 SHA-256、固定结果和内部资源引用。默认及 production 不开启；503/200 聚合数不能代替同一通知的真实重投证据。
- 内部只读适配器覆盖有效店铺、订单、订单详情、客服会话、消息和 Webhook 订阅核对；普通承运商订单的物流轨迹读取固定为 `GET /fulfillment/202309/orders/{order_id}/tracking`，要求 `seller.logistics`、当前授权渠道签名与 `shop_cipher`，并校验 `data.tracking[]`。CBT 首程增强读取保留独立的 `GET /logistics/202604/orders/{order_id}/tracking` 契约，不用前者的证据声称后者通过。

## 错误与状态

客户端应按 HTTP 状态和稳定业务码处理：参数错误、未认证、权限不足、资源不存在、版本/状态冲突、限流和内部错误。平台写入可能返回业务状态 `unknown`；该状态要求对账，不代表失败，也不允许自动重试写入。

## 规划但未放行

Shopee/Amazon 真实接口、公开自动回复、无需人工确认的发送、自动营销、高风险工具和生产翻译仍是规划能力。早期 `/marketing/flows`、无确认发送或宽泛 PUT 更新草案不构成当前公开契约；以运行代码生成的 OpenAPI 和本文件为准。

## Agent 业务工具目录与内部协作（本地候选，未部署）

- `GET /agents/tool-catalog?store_id=...` 需要 `agent.view` 和当前店铺访问权，返回六类 `groups` 与十六项 `tools`（十二项业务工具、四项人工确认提议）。每项包含 name/title/description/category/operation/requires_context/availability/reason/missing_scopes，不返回凭证或原始渠道对象。配置写入接受目录中的名称，未知名称拒绝，保存时去重，不设置固定工具数。
- operation 为 `read`、`internal_write`、`confirmation`；availability 区分可用、缺权限或平台依赖、需会话、需绑定文件、仅人工确认。绑定知识的前端状态基于当前草稿文件数，审批和索引仍在实际运行时校验。
- `GET /agents/collaboration?conversation_id=...&offset=0` 需要 `workspace.view`，按当前同店同客户会话分页返回最多20条内部记录：id/kind/content/created_at/agent_run_id/is_ai_suggestion/send_performed/transfer_performed。后两字段恒为 false，kind 为 handoff_request/internal_note；不存在任何借此接口向平台发送或转交的能力。
- 模型函数名：search_customer_orders/query_order/query_logistics/search_products/query_product/query_available_coupons/query_aftersales/query_customer_profile/query_conversation_messages/search_knowledge/create_handoff_request/add_internal_note。原四项平台写能力仍只返回 human_confirmation_required。店铺/买家/会话 ID 不进入可填函数参数；订单、商品和售后使用本轮已发出的不透明引用，翻页引用同时绑定工具和搜索条件。
- 订单筛选包含状态、订单/物流/商品/SKU关键词、带时区的 created_after（包含）/created_before（不包含）及页码。共享侧栏搜索先过滤后分页；日期范围无效拒绝。商品/优惠结果的 platform_total_count 与 matches_this_page 明确分开，不能把当前平台页当成全店匹配集。
- 商品详情提供品牌、参数、SKU/价格/库存及去除脚本/样式后的描述，page/page_size 与 next_page 表示完整读取进度。售后先返回申请引用、类型、状态、平台给出的金额/期限/退回物流；include_records=true 读取所选申请的只读处理历史，多申请需 return_ref，商品明细及记录通过 next_detail_page 分页。缺失字段保持空值。
- 订单/售后需 orders.view，客户/历史/商品/优惠需 workspace.view，内部记录写入需 workspace.reply，知识需 knowledge.view。订单核验需 seller.order.info 与 seller.customer_service；物流另需 seller.logistics，售后另需 seller.return_refund.basic。商品需 seller.product.basic；优惠需 seller.customer_service 或 seller.promotion.info。不自动扩大 OAuth scope，也不改变原真实写入范围。
- 平台端点沿既有签名客户端：订单详情202507、订单搜索202309、商品搜索202502、商品详情202309、优惠搜索202406、通用轨迹202309/受支持跨境增强轨迹202604；新增 Search Returns 为 POST /return_refund/202602/returns/search，处理记录 GET /return_refund/202309/returns/{return_id}/records。官方参考：[Search Returns](https://partner.tiktokshop.com/docv2/page/search-returns-202602)。本机 OAS 仅覆盖 Search Returns 202309；202602 的路径、scope 和筛选来自官方 docv2，已有低敏金额/期限字段按 OAS强类型接收，缺失不补造。真实站点字段可用性与语义仍待获批后验收。

- 物流的event_offset与package_offset分别续读；事件与包裹按DLP后实际JSON大小分别限制9000/4000字符，每批最多10项，next_event_offset与next_package_offset告知下次精确位置，直到两者都为空；另一数组已读完时可传其总数event_count/package_count避免重复。单条记录超预算会明确失败，不冒充已完整读取。增强事件优先保留事件原运单号，空缺才使用当前包裹号；仍执行原有DLP投影。
