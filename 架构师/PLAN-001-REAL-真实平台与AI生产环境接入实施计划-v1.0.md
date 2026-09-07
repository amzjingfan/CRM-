# CRM 智能聊天系统真实平台与 AI 生产环境接入实施计划 v1.0

状态：已确认；架构设计已落地，工程实施待执行，生产未放行

## 1. 计划概述

本计划用于指导 CRM 智能聊天系统从当前契约级 Mock 和确定性工程测试，逐步接入：

- 用户提供的真实 TikTok Shop 店铺；
- TikTok Shop OAuth、只读 API 和 Webhook；
- 人工确认后的真实平台消息发送；
- DeepSeek 厂商 API；
- 真实模型翻译、回复和 AI 营销文案质量评测；
- 公开 SSE 真实模型性能、五天稳定性和生产灰度。

本计划不先准备测试店铺。真实店铺作为首个接入对象；只有真实店铺无法获得必要权限、无法安全联调或平台限制高风险测试时，才切换测试店铺。

执行顺序固定为：

```text
项目基线复核
→ 真实店铺授权
→ 真实店铺只读 API
→ TikTok Webhook
→ 人工确认的低风险消息发送
→ DeepSeek API 接入
→ 真实模型质量评测
→ 公开 SSE 性能与稳定性
→ 地址/发券/营销写操作
→ 内部灰度
→ 生产启用
```

## 2. 当前状态和硬性阻断项

### 2.1 已具备

- Phase 3 M03 在契约级 Mock 范围通过第六次复测。
- Phase 3 M04 业务工具与安全接管在契约级 Mock 范围通过。
- BGE-M3 检索模型质量、50 并发容量、迁移和依赖安全门禁已通过。
- Phase 4 SSE、看板、部署和稳定性工程范围有条件通过。
- Phase 4 已具备 SSE 错误关闭、看板、Agent 运营、生产 Compose、运行时健康检查和压测脚本。
- 用户已有已启用的 TikTok Shop 自定义应用和真实店铺。
- DeepSeek API 作为回复、翻译和营销文案的外部模型供应商已确认。

### 2.2 当前不能直接进入生产的原因

- `DEF-P4-AI-008`（P1）仍未关闭：高风险业务事实存在同义表达漏放。
- `DEF-P4-AI-009`（P2）仍未关闭：合法政策、否定、条件和非业务表达误杀。
- 真实模型翻译、回复语气和营销质量尚未独立评测。
- 公开 SSE 尚未完成 50 个真实授权客户端的首分块、P99 和成功率测试。
- 五天连续稳定性和 99.5% 可用性尚无正式报告。
- DeepSeek 密钥轮换尚无可核验的生产记录。
- TikTok 真实平台写操作尚未联调。
- 项目当前无 Git 不可变基线，生产发布前需补充版本基线。

在以上阻断项关闭前，以下开关必须保持关闭：

```text
LLM_ENABLED=false
LLM_LIVE_EVAL=false
AI_TRANSLATION_ENABLED=false
AI_MARKETING_ENABLED=false
AUTO_REPLY_ENABLED=false
REAL_TIKTOK_READ_ENABLED=false
REAL_TIKTOK_WEBHOOK_ENABLED=false
REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false
REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false
```

## 3. 目标环境和安全边界

### 3.1 环境划分

至少划分：

```text
local       本地开发，不连接真实店铺
integration 真实店铺只读和 Webhook 联调环境
staging     真实模型、人工确认写操作和灰度验证环境
production  生产环境，按门禁逐步开放
```

本计划不要求测试店铺，但每套环境必须隔离：

- 数据库和 Redis 实例或命名空间；
- MinIO Bucket；
- TikTok OAuth 授权记录；
- DeepSeek API Key；
- JWT、Cookie、CSRF 和内部服务 Token；
- 日志、指标和审计数据。

### 3.2 真实店铺安全原则

- 先只读，后写入。
- 先人工确认，后自动化。
- 先消息发送，后地址、发券和营销。
- 所有写操作保留 `tool_calls` 和 `audit_logs`。
- 平台超时或结果未知时标记 `unknown`，禁止自动重试。
- AI 不直接访问 TikTok API，必须通过全栈受控工具层。
- 生产环境禁止使用 Mock Adapter。

## 4. Phase A：TikTok 真实店铺授权准备

### 4.1 Partner Center 操作

使用用户现有的已启用自定义应用，不创建测试店铺。

在 Partner Center 中确认：

```text
App Key
App Secret
应用状态
店铺授权状态
API Scope
Webhook 管理权限
IP 白名单权限
```

先申请或确认只读权限：

```text
店铺信息读取
订单读取
物流查询
客户消息读取
Webhook 接收
```

地址修改、发券和自动发送权限先不用于业务操作，待后续人工写操作门禁通过后再开启。

TikTok 官方开发流程包括创建应用、配置 Scope、授权店铺和配置 Webhook。[TikTok Shop Developer Guide](https://partner.tiktokshop.com/docv2/page/tts-developer-guide)

### 4.2 OAuth 回调接口

当前截图中的重定向地址为网站首页，不作为正式 OAuth 回调地址。项目新增：

```http
GET /v1/settings/channels/tiktok/oauth/start
GET /v1/integrations/tiktok/oauth/callback
```

Partner Center 重定向地址改为：

```text
https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback
```

OAuth 规则：

- 后端生成一次性 `state`，保存 Redis，设置短期过期时间。
- callback 必须校验 `state`，不得接受缺失或重复 state。
- 授权 code 只能由后端兑换 Token。
- access token 和 refresh token 不进入前端、日志或测试报告。
- 授权记录按店铺保存，并记录过期时间和最后刷新时间。
- 授权失败返回脱敏错误码。
- 撤销授权后，所有平台调用必须被阻断。

### 4.3 授权验收

必须完成：

- 真实店铺授权成功；
- 真实店铺信息读取成功；
- Token 刷新成功；
- Token 过期后能被识别；
- 撤销授权后调用被拒绝；
- 跨店铺资源访问返回资源不存在；
- 凭证未出现在前端、日志和审计内容中。

## 5. Phase B：真实店铺只读 API 和 Webhook

### 5.1 只读 API 顺序

先接通：

```text
查询店铺
查询订单
查询物流
查询客户关联信息
```

每个适配器必须处理：

```text
请求签名
店铺隔离
请求超时
限流响应
平台错误码映射
trace_id
安全日志
```

### 5.2 Webhook 地址

Partner Center Webhook 地址配置为：

```text
https://www.hophorsefit.com/v1/webhooks/tiktok
```

Webhook 链路：

```text
限制请求体 ≤ 1 MiB
→ 原始请求体验签
→ 写入 webhook_events
→ external_event_id/payload_hash 幂等
→ 200 快速响应
→ Worker 异步处理
→ 标准化事件
→ 更新客户/订单/会话/消息
→ 写入审计
```

TikTok 请求签名采用 HMAC-SHA256，Webhook 失败可能触发平台重试，因此必须先完成幂等落库。[TikTok API 签名说明](https://partner.tiktokshop.com/docv2/page/sign-your-api-request)、[TikTok Webhook 官方说明](https://partner.tiktokshop.com/docv2/page/tts-webhooks-overview)

### 5.3 Webhook 验收样本

使用真实店铺产生低风险事件，并补充脱敏固定样本：

```text
合法签名
非法签名
重复事件
平台重试
字段缺失
未知事件
过期时间戳
超大请求体
Worker 失败重试
消息重复
订单状态重复更新
```

## 6. Phase C：人工确认的真实平台写操作

### 6.1 第一阶段只允许普通消息

真实店铺第一条写操作只能是客服手工确认的普通文本：

```text
不包含优惠承诺
不包含退款承诺
不包含地址修改
不包含营销内容
不触发 AI 自动发送
```

调用链：

```text
客服输入
→ 二次确认
→ Idempotency-Key
→ tool_calls pending
→ TikTok Adapter
→ 平台结果
→ 消息 sent/failed/unknown
→ audit_logs
```

### 6.2 高风险写操作顺序

依次开放：

```text
普通消息发送
→ 人工确认的优惠券
→ 人工确认的地址修改
→ 人工确认的营销消息
→ 低风险自动回复
→ 自动营销
```

高风险操作必须具备：

- 权限校验；
- 店铺白名单；
- 参数校验；
- 二次确认；
- 幂等键；
- 工具调用审计；
- 平台响应确认；
- 超时 `unknown` 保护；
- 失败转人工；
- 可关闭功能开关。

## 7. Phase D：DeepSeek API 接入

### 7.1 API 账号准备

创建独立 DeepSeek API Key：

```text
integration key
staging key
production key
```

配置余额、调用额度、账单告警、Key 轮换负责人和撤销流程。

DeepSeek API 使用 Bearer 认证，官方兼容入口为 `https://api.deepseek.com`。[DeepSeek API 文档](https://api-docs.deepseek.com/api/deepseek-api)

### 7.2 服务配置

建议配置：

```env
LLM_ENABLED=false
LLM_LIVE_EVAL=false
LLM_PRIMARY_PROVIDER=deepseek
LLM_PRIMARY_MODEL=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=
DEEPSEEK_THINKING_ENABLED=false
LLM_TIMEOUT_SECONDS=30
LLM_MAX_ATTEMPTS=2
LLM_MAX_OUTPUT_TOKENS=
```

模型名称以 DeepSeek 当前账号可用模型为准，禁止写死在业务代码中。

### 7.3 模型接入顺序

```text
最小文本请求
→ 结构化回复请求
→ 翻译请求
→ FAQ/RAG 上下文请求
→ 回复建议
→ 人工确认发送
→ 营销文案草稿
→ 人工确认营销发送
```

DeepSeek 请求必须经过脱敏：

- 姓名、手机号脱敏；
- 详细地址、支付信息和完整凭证禁止发送；
- 只发送订单状态摘要和必要 FAQ 上下文；
- API Key 不进入浏览器、日志或 `agent_runs` 明文内容。

## 8. Phase E：真实模型质量、安全和性能门禁

### 8.1 必须先关闭的缺陷

在真实模型自动回复、真实翻译和真实营销发送前，必须关闭：

```text
DEF-P4-AI-008（P1）：高风险业务事实同义表达漏放
DEF-P4-AI-009（P2）：合法政策/否定/条件/非业务表达误杀
```

固定样本通过不等于缺陷关闭，必须重新执行独立同义改写和合法表达评测。

### 8.2 真实模型质量评测

使用脱敏评测集验证：

```text
回复语气
中文回复
英文回复
中英翻译
FAQ 引用
订单/物流回答
转人工判断
敏感内容拦截
营销文案安全性
营销文案事实准确性
```

必须输出：

```text
模型版本
Prompt 版本
评测集版本
通过率
漏放率
误杀率
首字延迟
P95/P99
Token 成本
失败和超时数量
```

### 8.3 公开 SSE 50 并发

准备 50 个真实授权测试客户端或等效独立授权会话，在不执行高风险写工具的前提下测试：

```text
成功率
认证拒绝
429
首分块耗时
总耗时
P95/P99
连接断开
取消请求
模型超时
重试
```

BGE 检索模型的 50 并发报告不能替代公开 SSE 真实模型性能报告。

### 8.4 五天稳定性

连续五天记录：

```text
请求总数
成功数
失败数
超时数
P95/P99
模型供应商错误
Redis/PostgreSQL 状态
Worker 重启
内存和 GPU 使用
审计链路完整性
```

正式生产门禁要求形成 99.5% 可用性报告；不能用一次压测结果替代。

## 9. Phase F：内部灰度和生产启用

### 9.1 灰度顺序

```text
只读查询
→ AI 建议但不自动发送
→ 人工修改后发送
→ 低风险自动回复
→ 人工确认营销发送
→ 小范围自动营销
```

每一步都要有独立开关和回滚方式。

### 9.2 生产启用前置条件

以下条件全部满足后，才允许生产启用：

- TikTok OAuth、只读 API、Webhook 和人工消息发送通过；
- 真实平台写操作有独立测试报告；
- `DEF-P4-AI-008/009` 已关闭；
- DeepSeek 真实模型翻译、回复和营销质量评测通过；
- 公开 SSE 50 并发首分块和 P99 门禁通过；
- 五天稳定性和 99.5% 可用性报告通过；
- DeepSeek 和 TikTok 密钥完成轮换并留存审计证据；
- 生产镜像 UID、TLS、备份和恢复演练通过；
- 生产环境 Mock Adapter 禁止启动；
- 测试工程师无未关闭 P0/P1/P2 生产阻断项；
- 架构师完成真实环境技术验收；
- 产品负责人批准灰度范围和自动化策略。

## 10. 失败回退到测试店铺的条件

只有出现以下情况才准备测试店铺：

- 真实店铺缺少必要 API Scope；
- OAuth 无法完成或无法撤销；
- Webhook 无法公网到达或验签不稳定；
- 平台不允许真实店铺进行高风险写测试；
- 无法保证地址、发券和营销操作可回滚；
- 真实店铺业务风险高于当前灰度承受能力。

切换测试店铺时不修改业务契约，只替换：

```text
店铺授权
店铺 ID
Access Token
Webhook 配置
测试数据
```

## 11. Agent 分工和交付物

### 架构师Agent

- 确认真实平台写操作边界。
- 评审 TikTok OAuth、Webhook、凭证和回滚方案。
- 评审 DeepSeek 数据出境、脱敏和生产使用边界。
- 维护真实环境架构决策和验收标准。

### 全栈开发工程师Agent

- 实现 TikTok OAuth 回调和授权保存。
- 实现真实 TikTok 适配器、只读 API 和 Webhook。
- 实现人工确认写操作、工具审计和开关。
- 实现 DeepSeek Provider 配置入口和 SSE 生产运行面。
- 完成生产部署、日志、备份和恢复。

### AIAgent开发工程师Agent

- 实现 DeepSeek Provider。
- 修复并验证 `DEF-P4-AI-008/009`。
- 完成真实模型回复、翻译和营销评测。
- 提供 Prompt、模型、评测集和安全门禁版本。

### 测试工程师Agent

- 测试真实店铺 OAuth、只读 API、Webhook 和人工消息。
- 生成真实模型质量报告。
- 生成 SSE 50 并发报告。
- 生成五天稳定性和 99.5% 可用性报告。
- 按测试报告命名规范保存正式结论。

## 12. 最终验收报告

真实环境接入完成后必须形成以下独立报告：

```text
真实 TikTok OAuth 与只读 API 测试报告
真实 TikTok Webhook 与幂等测试报告
真实 TikTok 人工消息发送测试报告
DeepSeek 真实模型回复/翻译/营销质量报告
真实模型公开 SSE 50 并发性能报告
五天连续稳定性与 99.5% 可用性报告
真实环境生产灰度验收报告
```

任何一项 P1 生产门禁未通过，都不得将系统标记为真实生产环境已完成。

## 13. 实施交付索引（2026-08-24）

架构师已完成本计划的架构决策、总体架构增量、生产放行检查表和执行 Agent 任务计划：

- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`
- `架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`
- `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.0.md`
- `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md`
- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`

当前只完成架构师职责和工程交接。真实 OAuth、只读 API、Webhook、人工写操作、DeepSeek Provider、AI 缺陷修复、真实模型评测、SSE 性能和五日稳定性仍由对应 Agent 后续实施并提交正式证据。
