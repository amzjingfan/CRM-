# 真实 TikTok 与 DeepSeek 运行面实施计划

| 项目 | 内容 |
| --- | --- |
| 计划编号 | `PLAN-002-REAL-FULLSTACK` |
| 版本 | `v1.0` |
| 状态 | 实施中（REAL-FS-01 仍有既有前端依赖安全阻断；REAL-FS-02～04 已完成当前确定性工程复测，真实店铺门禁仍待执行；REAL-FS-05 的 `DEF-REAL-FS05-001～003` 已由 002 号独立报告关闭，新增 `DEF-REAL-FS05-004` 已完成开发修复并待测试工程师独立复测；真实模型 50 客户端/五日稳定性仍待执行；REAL-FS-06 待执行） |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、AIAgent开发工程师Agent、测试工程师Agent |
| 产品代码目录 | `CRM智能聊天系统/` |
| 架构依据 | `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md` |

## 1. 目标和边界

完成真实 TikTok 店铺 OAuth、只读 API、Webhook、人工确认普通消息发送，以及 DeepSeek 服务端配置、SSE 生产运行面和部署保障。

不负责 Prompt、模型输出策略、结构化业务声明、安全语义判定和 AI 评测算法；不得开放自动回复、自动营销、发券或地址修改，除非前序生产门禁已有测试工程师正式通过证据。

## 2. 实施门禁

编码前必须读取共享记忆、代码编写手册、当前迁移、M00 002 和当前最新 M04 测试报告。先执行现有 Ruff、mypy、pytest、前端 lint/typecheck/test/build、Compose 配置和迁移回归，记录不可变基线。2026-08-26 开始 REAL-FS-02 时迁移 head 为 `019_tiktok_channel_unique`；截至 2026-09-04 当前 head 为 `023_marketing_review_idempotency`。发现实际 head 与最新共享记录不一致或跨模块模型冲突时暂停并提交架构师。

真实密钥只能由用户通过环境或密钥管理系统提供；不得写入代码、`.env.example` 的真实值、实施记录或命令输出。

## 3. 纵向实施任务

### REAL-FS-01：配置与基础设施

- 在现有配置体系增加 ADR 定义的生产开关和 DeepSeek/TikTok 配置，默认关闭。
- 复用现有 Compose、反向代理和健康检查，不新增编排系统。
- 增加 HTTPS、固定出口 IP、服务端密钥注入、结构化日志脱敏、备份和恢复说明。
- 启动时拒绝生产环境 Mock Adapter；健康接口只返回低敏状态。

验收：配置缺失时安全失败；日志和 API 不出现凭证；现有本地/Mock 测试不退化。

### REAL-FS-02：TikTok OAuth

实现：

```http
GET /v1/settings/channels/tiktok/oauth/start
GET /v1/integrations/tiktok/oauth/callback
```

- `start` 校验 `settings.channels` 和店铺权限，生成一次性随机 `state`，以带 TTL 的 Redis 记录绑定用户、店铺和回跳目标。
- callback 原子消费 `state`，交换 Token，读取真实店铺信息，校验 Scope 和店铺绑定，再加密保存到现有 `channel_accounts`。
- 授权失败不得保存半成品；刷新、过期和撤销后状态必须可追踪。
- 前端渠道页只展示连接状态、店铺名称、权限摘要和最后同步时间。

验收：正常、缺失、过期、重复和用户不匹配的 `state`；Token 刷新/撤销；跨店铺拒绝；敏感信息扫描。

### REAL-FS-03：TikTok 只读 API 和 Webhook

- 在现有 `PlatformAdapter` 契约中增加真实 TikTok 实现，复用已存在的超时、错误映射和标准化类型。
- 按官方规则实现 HMAC-SHA256 API 请求签名与 Webhook 原始请求体验签。
- 复用 `/v1/webhooks/tiktok`、`webhook_events` 和现有 Worker 链路；正文上限 1 MiB，先幂等落库后快速响应。
- 只开放店铺、订单、物流和消息读取；所有 Repository 查询继续按允许店铺集合过滤。
- 平台限流、无权限、Token 过期和字段变化转换为稳定错误码并保留低敏追踪字段。

验收：真实只读冒烟；合法/非法签名；重复事件；平台重试；Worker 失败；未知事件；消息与订单幂等。

### REAL-FS-04：人工确认普通消息

- 将现有人工消息接口切换到真实适配器时，仍经统一工具执行层。
- 强制权限、店铺白名单、二次确认、`Idempotency-Key`、`tool_calls` 和 `audit_logs`。
- 发送状态只使用平台真实结果；超时不可确认时记录 `unknown` 并停止自动重试。
- 前端明确区分 Mock、真实待确认、已发送、失败和未知，不把 AI 建议自动发送。

验收：同键同请求重放、同键不同请求冲突、平台失败、超时未知、人工对账和开关回滚。

### REAL-FS-05：DeepSeek 配置和 SSE 运行面

- 复用现有 DeepSeek Provider 和服务端配置，负责限流、超时、取消、SSE 和可观测性运行面；Provider 语义加固由 AI Agent 负责。
- 复用现有 `/v1/chat/query` 事件契约，不新增第二套 SSE 协议。
- 保持当前“安全草稿校验完成后再按传输层分块”的 SSE 边界；本阶段不引入未经安全校验的模型原生 Token 直出。
- 401/403/429、模型超时、连接取消和依赖错误必须以既有 SSE `error/done` 语义结束。
- 记录模型名、Prompt 版本、首输出、总耗时、Token 和脱敏摘要；不记录原始模型响应。
- 压测门禁使用完整样本的 P99：首个安全 `delta` 严格 `<3000ms`、总耗时严格 `<5000ms`；等于或超过阈值时必须输出失败并以非零状态退出，CLI 只能收紧不能放宽架构上限。

验收：内部草稿模式、前端取消/断线、Provider 错误、50 授权客户端压测和五日稳定性。

### REAL-FS-06：部署、备份和回滚

- 固定代码/归档哈希、镜像摘要、迁移 head 和配置版本。
- 提供 PostgreSQL、Redis、MinIO 的备份恢复步骤以及授权/Key 撤销步骤。
- 演练独立关闭只读、Webhook、消息写入、DeepSeek 和全部真实能力。
- 实施完成后生成共享实施记录，但正式测试结论只由测试工程师生成。

## 4. 配置契约

至少支持：

```text
TIKTOK_APP_KEY
TIKTOK_APP_SECRET
TIKTOK_OAUTH_REDIRECT_URI
TIKTOK_WEBHOOK_SECRET
TIKTOK_CREDENTIAL_ENCRYPTION_KEY
REAL_TIKTOK_READ_ENABLED=false
REAL_TIKTOK_WEBHOOK_ENABLED=false
REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false
REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY
DEEPSEEK_THINKING_ENABLED=false
LLM_ENABLED=false
LLM_LIVE_EVAL=false
LLM_PRIMARY_PROVIDER=deepseek
LLM_PRIMARY_MODEL
LLM_TIMEOUT_SECONDS=30
LLM_MAX_ATTEMPTS=2
AI_TRANSLATION_ENABLED=false
AI_MARKETING_ENABLED=false
AUTO_REPLY_ENABLED=false
ALLOW_MOCK_PLATFORM_ADAPTERS=false
```

变量名若与现有配置冲突，必须复用现有名称并在共享记忆登记差异，不得保留两套同义开关。

## 5. 交付和停止条件

交付代码、迁移（如确有需要）、OpenAPI、前端状态、环境变量模板、部署/恢复文档、测试和实施记录。建议实施记录命名：

```text
共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-真实TikTok与DeepSeek运行面-001.md
```

发现 Scope 不明确、凭证无法加密、Webhook 验签不稳定、真实写结果未知无法对账、日志泄露敏感数据或需改变 AI 契约时立即停止，并提交架构师评审。

## 6. 实施进度

### 2026-08-25：REAL-FS-01 测试缺陷修复完成，待独立复测

- 已补齐生产开关、TikTok/DeepSeek 服务端配置、生产启动安全校验和日志脱敏。
- 已增加生产 Compose 约束、Nginx HTTPS/SSE 反向代理、密钥注入、固定出口 IP 和备份恢复说明。
- 已针对 `DEF-REAL-FS01-001～004` 完成日志/OAuth 查询参数脱敏、Settings 安全表示、生产密钥显式映射、开发 `.env` 隔离、CORS Origin 严格校验和文档路径修正。
- 所有真实平台、真实模型和自动化开关继续固定为关闭；未执行 TikTok OAuth、真实写操作或 DeepSeek 生产调用。
- 原测试结论仍以 `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-真实环境配置与基础设施-综合测试-001.md` 为准；缺陷关闭必须等待测试工程师独立复测。
- 修复证据：`共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-真实环境基础设施测试缺陷修复-004.md`。

### 2026-08-25：REAL-FS-01 二次测试缺陷修复完成，待独立复测

- 权威复测报告已更新为 `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-真实环境配置与基础设施-综合测试-002.md`；报告中的 `DEF-REAL-FS01-001/002` 仍为 Open。
- 已修复未加引号多词 `message=`、带业务前缀的消息/地址字段、`MINIO_ACCESS_KEY` 和 `TIKTOK_CREDENTIAL_ENCRYPTION_KEY` 的日志脱敏绕过，并覆盖最终 `JsonFormatter` 出口。
- 已将生产 Compose 拆分为公共、TikTok 平台和 DeepSeek 模型三个配置域；集成 Worker 不再获得 DeepSeek Key，Agent Worker 不再获得 TikTok 凭据，检索模型服务重置开发 `.env` 且不接收业务系统密钥。
- 普通与 AI Profile 的实际合并配置、21 项专项测试、后端默认 495 项、隔离 PostgreSQL 503 项以及前端 22 项测试和生产构建均通过。
- 所有真实平台、真实模型和自动化开关仍固定为关闭；正式缺陷关闭和进入后续联调仍需测试工程师独立复测。
- 修复证据：`共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-真实环境基础设施二次测试缺陷修复-005.md`。

### 2026-08-25：REAL-FS-01 第三次测试缺陷修复完成，待独立复测

- 权威复测报告已更新为 `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-真实环境配置与基础设施-综合测试-003.md`；`DEF-REAL-FS01-002/003/004` 已关闭，`DEF-REAL-FS01-001` 仍为 P1/Open。
- 已复用统一敏感字段名和值边界，将文本日志规则从仅识别 `key=value` 扩展为同时识别未加引号的 `key: value`，覆盖 HTTP Header 和第三方诊断文本中的 `X-API-Key`、`TIKTOK_APP_SECRET`。
- 已在帮助函数和最终 `JsonFormatter` 两层增加报告反例，专项 23 项、后端默认 497 项、隔离 PostgreSQL 505 项以及前端 22 项测试和生产构建均通过。
- 普通与 AI 生产 Profile 已重新动态合并验证，密钥矩阵、检索服务隔离和高风险开关继续通过；未重复修改已关闭的 Compose 缺陷。
- 所有真实平台、真实模型和自动化开关仍保持关闭；正式缺陷关闭和进入后续联调仍需测试工程师独立复测。
- 修复证据：`共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-真实环境基础设施第三次测试缺陷修复-006.md`。

### 2026-08-26：REAL-FS-02 首次测试缺陷修复完成，待独立复测

- 权威测试报告为 `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTokOAuth授权与凭证生命周期-综合测试-001.md`，结论仍为不通过，缺陷状态只能由测试工程师复测关闭。
- 通用渠道 Schema 和 Service 已拒绝 TikTok，真实 TikTok 记录只能由 OAuth callback 创建或更新。
- Token 刷新已校验 `open_id` 和唯一授权店铺连续性；不一致时保留旧密文、标记 `expired` 并写失败审计。
- Jobs Worker 已接入可配置的提前刷新周期，使用 PostgreSQL `FOR UPDATE SKIP LOCKED` 防止并发重复刷新。
- 新增可逆迁移 `019_tiktok_channel_unique`，以部分唯一索引强制一个内部店铺只能绑定一个 TikTok 渠道；迁移发现历史重复项时失败关闭，不自动删除授权证据。
- `return_to` 现只接受精确字符串 `/settings/channels`。
- 所有真实 TikTok、平台写入、公开 AI 回复、营销和自动回复开关仍保持关闭；真实店铺 OAuth 与 Token 刷新尚未执行。
- 修复证据：`共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTokOAuth测试缺陷修复-008.md`。

### 2026-08-26：REAL-FS-02 第二次测试缺陷修复完成，待第三次独立复测

- 权威复测报告为 `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTokOAuth授权与凭证生命周期-综合测试-002.md`；`DEF-REAL-FS02-001～005` 已关闭，`DEF-REAL-FS02-006` 仍为 P2/Open。
- 已将 TikTok callback 路由、真实环境固定 Redirect URI、生产启动校验和 OAuth start/callback 运行校验统一到同一契约。
- integration、staging 和 production 只接受 `https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback`；HTTP、错误主机、错误路径、query 和 fragment 均在授权跳转前失败关闭。

> 2026-09-09 勘误：此条历史跨环境相同地址约定由 `架构师/ADR-007-INFRA-Rootless-Staging部署边界-v1.0.md` 取代。staging 仅接受 `https://staging.hophorsefit.com/v1/integrations/tiktok/oauth/callback`；integration/production 继续仅接受 `https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback`。接口结构和其余失败关闭规则不变，真实门禁待执行。

> 2026-09-10 更新：经用户批准，当前 staging 仅接受 `https://staging.overselfx.com/v1/integrations/tiktok/oauth/callback`；旧 staging 域名不再有效，integration/production 契约保持不变。

- 生产 Compose 已将 `TIKTOK_OAUTH_REDIRECT_URI` 改为必填，部署文档明确其是 Partner Center 外部配置断言，仍需发布人员人工核对平台后台实际值。
- 所有真实 TikTok、平台写入、公开 AI 回复、营销和自动回复开关继续保持关闭；未执行真实店铺授权或 REAL-FS-03。
- 开发验证证据将记录于 `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTokOAuth固定回调缺陷修复-009.md`；缺陷正式关闭必须等待测试工程师第三次独立复测。

### 2026-08-31：REAL-FS-03 真实只读 API 与 Webhook 工程实现完成

- 新增固定官方域名的 TikTok 真实只读客户端，覆盖有效店铺、订单列表、202507 订单详情、物流轨迹、客服会话、会话消息和当前 Webhook 订阅核对。
- 所有 API 请求复用 OAuth 加密凭证、`shop_cipher` 和官方 HMAC-SHA256 请求签名；Token 只进入 `x-tts-access-token` Header，限流、Token 过期、无权限和契约漂移转换为稳定错误。
- 真实 Webhook 使用官方 `Authorization` Header 和 App Secret 对原始正文验签；通知 ID、shop ID 和已确认数值主题进入既有幂等、渠道映射和审计链路。
- 1 号订单事件先调用只读详情补全，14 号可见买家消息进入统一消息模型，6/7 号授权生命周期事件停用凭证或要求重新授权，未知主题只保留摘要并标记忽略。
- `REAL_TIKTOK_READ_ENABLED`、`REAL_TIKTOK_WEBHOOK_ENABLED` 可以在前置配置完整时启用；普通消息和高风险写开关继续由 REAL-FS-04 启动门禁拒绝。
- 本轮未注入真实 App/店铺凭证，未执行 Partner Center 真实投递或只读冒烟，不能宣称真实联调通过。开发证据记录于 `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTok只读API与Webhook-010.md`。

### 2026-08-31：REAL-FS-03 首次测试缺陷完成开发修复，待独立复测

- 权威首测报告为 `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTok只读API与Webhook-综合测试-001.md`；报告中的 `DEF-REAL-FS03-001/002` 状态仍由测试工程师维护。
- 物流读取已切换为 `GET /logistics/202604/orders/{order_id}/tracking`，按订单与多包裹结构校验，并在请求前强制 `seller.logistics`；OAuth 必需 Scope、环境模板和生产 Compose 已同步。
- 重试已由“非零未知错误默认重试”收敛为瞬时错误白名单：网络、5xx、429 和官方瞬时内部错误 `36009003`；其他稳定平台业务错误只请求一次。429 采用有上限的 `Retry-After` 退避。
- 自动化补充了当前 202604 契约、多包裹、历史单号、Scope 失败关闭、响应订单不匹配、稳定/瞬时错误次数、低敏 request ID、传输失败、5xx、429 退避和非法响应不重试场景。
- 所有真实读取、真实 Webhook、普通写入、高风险写入、营销和自动回复开关继续关闭；已授权真实店铺若缺少 `seller.logistics`，需在架构师核准后重新授权再执行单店铺只读冒烟。
- 开发修复证据记录于 `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTok只读API测试缺陷修复-011.md`；不得据此把正式缺陷标记为已关闭。

### 2026-08-31：REAL-FS-03 第二次测试缺陷完成开发修复，待独立复测

- 权威复测报告为 `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTok只读API与Webhook-综合测试-002.md`；报告已关闭 `DEF-REAL-FS03-001/002`，新增 `DEF-REAL-FS03-003` 仍由测试工程师维护为 P2/Open。
- `TikTokLogisticsData.logistics_details` 和 `TikTokLogisticsDetail.track_list` 已改为必填数组；字段明确存在且为 `[]` 时继续表示合法空结果，字段完全缺失时由 Pydantic 契约校验转换为统一 `THIRD_PARTY_ERROR`，且不触发重试。
- 新增两组缺失/显式空数组成对测试，覆盖顶层 `logistics_details` 和包裹 `track_list`，同时保留 202604 多包裹、历史单号、订单归属、Scope 和重试分类回归。
- 开发侧验证通过：105 项 REAL-FS-03 聚焦、786 项默认后端、796 项隔离 PostgreSQL、29 项前端、迁移回滚恢复、开发/生产 Compose、健康检查和锁定依赖审计。
- 所有真实读取、真实 Webhook、普通写入、高风险写入、营销和自动回复开关继续关闭；正式缺陷关闭和真实店铺冒烟仍须按测试及架构门禁执行。
- 开发修复证据记录于 `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTok物流数组契约缺陷修复-012.md`。

### 2026-09-02：REAL-FS-04 工程实现完成，待独立测试与真实灰度

- 复用现有人工消息接口和统一 `SqlAlchemyToolExecutor`，新增可信人工确认上下文；Agent/Job 不能把普通消息写开关用于自动发送。
- TikTok 文本消息使用当前适用的 202309 官方接口和 `seller.customer_service` Scope，固定单次请求。传输异常、5xx、内部错误和成功响应契约缺失统一记录 `unknown`，禁止自动重试。
- 消息、工具调用和审计保留同一幂等链路；同键同请求重放、同键不同请求冲突。迁移 `021_message_unknown` 补齐可人工对账的消息终态。
- 同店铺出现 `unknown` 后自动暂停后续真实消息；管理员依据 TikTok 后台事实通过对账接口关闭消息和工具终态，保留审计后才解除熔断。
- 前端增加真实/模拟交付模式、二次确认、2000 字真实消息上限以及发送成功、失败、未知提示；AI 建议仍只填充输入框。
- 生产基础开关仍默认关闭；只有经评审叠加 `docker-compose.tiktok-manual.yml` 才能让 backend 读取人工消息开关，Worker、高风险动作和自动回复固定关闭。
- 本轮没有注入或输出真实 TikTok 凭证，没有向真实客户发送消息。确定性工程验证完成后仍须测试工程师独立测试、真实单店铺发送和人工对账/回滚演练。

### 2026-09-02：REAL-FS-04 首次测试缺陷完成开发修复，待独立复测

- 权威首测报告为 `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTok人工确认普通消息-综合测试-001.md`；`DEF-REAL-FS04-001～004` 的正式状态仍由测试工程师维护。
- 真实写工具现强制 `actor_type=user`、有效 `actor_id` 和当次 `human_confirmed=true`；Agent、Job、缺失人工身份或未确认请求均在创建消息和调用平台前失败关闭。
- TikTok 客服写接口独立维护结果未知错误集合，官方 `45101001` 与 `36009003` 均映射为 `unknown`，保持单次请求并进入人工对账，避免误判失败后重复发送。
- `confirmed` 增加输入前严格校验，只接受 JSON 布尔值 `true`；数字、字符串、空值和容器类型全部拒绝。
- 人工发送接口的 `Idempotency-Key` 已通过依赖声明为 OpenAPI 必填；Bearer Token 与 HttpOnly Cookie 认证均声明为安全方案，发送和管理员对账接口补齐权限、店铺、CSRF、幂等及未知结果说明。
- 开发侧验证通过：121 项 REAL-FS-04 聚焦测试、1183 项默认后端、1193 项隔离 PostgreSQL、31 项前端、迁移 `021→020→021`、Compose 配置和静态类型检查均通过。真实 TikTok 写入未执行，所有生产写入开关保持关闭。
- 开发修复证据记录于 `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTok人工消息测试缺陷修复-015.md`；不得据此将正式缺陷标记为关闭。

### 2026-09-03：REAL-FS-05 工程实现完成，待真实模型性能与稳定性独立测试

- 复用现有 DeepSeek Provider 和 `/v1/chat/query`，增加独立 SSE 总超时、无业务数据心跳、浏览器断线取消和 Provider/Embedding/Reranker 稳定错误收敛；未修改 AI 工程师拥有的 Provider、Prompt、RAG 或安全决策。
- 新增 `docker-compose.deepseek-sse.yml`，只允许 backend 按需生成内部草稿；jobs、agent-worker、AI 翻译、AI 营销和自动回复固定关闭。
- `/v1/health/ready` 增加低敏 `llm_provider` 配置状态；运行日志只记录 trace/run ID、稳定错误码、首个安全输出耗时和总耗时，不记录模型正文。
- 前端增加显式取消、意外 EOF 检测和服务端错误保留；压测工具只有 `done.reason=completed` 才计成功，并支持输出仓库外低敏证据文件。
- 开发验证通过：Ruff、格式、mypy 162 个源文件、后端 1230 项（12 跳过）、前端 32 项、Next.js 生产构建、生产 AI Compose 叠加和锁定 Python 依赖审计。npm 官方审计仍报告 Next.js 间接依赖 PostCSS/Sharp 共 3 项 High，自动修复要求破坏性升级 Next 16，沿用 REAL-FS-01 生产阻断状态。本轮未使用真实 DeepSeek Key，未执行 50 个授权客户端、连续五日稳定性或公开回复测试。
- 实施证据记录于 `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-DeepSeek配置与SSE生产运行面-016.md`；正式放行结论必须由测试工程师和架构师给出。

### 2026-09-04：REAL-FS-05 首次测试缺陷完成开发修复，待独立复测

- 权威首测报告为 `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M02-DeepSeek配置与SSE生产运行面-综合测试-001.md`；`DEF-REAL-FS05-001～003` 的正式状态仍由测试工程师维护。
- 生产 LLM 启动校验和 ready 现在复用统一非空密钥规则，DeepSeek/OpenAI/Anthropic 的空字符串、空格和换行均失败关闭。
- SSE 用户并发从固定 180 秒计数器改为唯一 Redis 租约；租约时长由流超时加 60 秒清理余量推导，Lua 原子完成过期清理、容量判断和加入，释放只删除当前令牌。
- 新增仅供 integration/staging 单机压测的 `docker-compose.sse-load-test.yml`，默认将 IP 窗口容量设为 60；压测脚本要求声明服务端限额，50 个样本未全部完成或缺少首个安全 `delta` 时以非零状态退出。
- 所有生产 AI 和自动发送开关继续关闭；真实 DeepSeek、50 客户端和五日稳定性仍必须由测试工程师独立执行。
