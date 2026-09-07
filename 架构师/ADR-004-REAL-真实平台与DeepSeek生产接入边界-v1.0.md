# 真实平台与 DeepSeek 生产接入边界

状态：已确认

## 1. 决策摘要

CRM 智能聊天系统采用“真实 TikTok 店铺优先、只读先行、人工确认写入、AI 分级放行”的生产接入策略。DeepSeek 作为外部生成模型供应商，但不成为业务事实来源；TikTok 平台写操作只能由全栈 `tools` 模块执行，AI Agent 不能直接访问平台 SDK、凭证或业务数据库写接口。

本决策自 2026-08-24 起生效。当前仅确认架构边界，不表示真实 OAuth、Webhook、平台写操作或 DeepSeek 生产质量已经验收。

## 2. 背景与约束

- 用户已有一个启用状态的 TikTok Shop 自定义应用和真实店铺，首轮不准备测试店铺。
- 当前 TikTok、Shopee、Amazon 写操作只通过契约级 Mock 验证。
- DeepSeek 真实模型评测、公开 SSE 50 个授权客户端性能和五日稳定性尚未完成。
- `DEF-P4-AI-008` 仍存在高风险业务事实漏放，`DEF-P4-AI-009` 仍存在合法非业务表达误杀。
- 当前正式数据库迁移 head 为 `018_ai_observability`。
- 项目目录不是 Git 仓库，生产发布前必须建立可追溯的不可变版本基线。

## 3. 架构决策

### 3.1 环境与店铺

环境固定划分为 `local`、`integration`、`staging`、`production`。真实店铺首先只授权给 `integration`，通过只读和 Webhook 门禁后才能进入 `staging` 的人工消息发送验证。各环境必须隔离数据库或命名空间、Redis、对象存储、TikTok 授权、DeepSeek Key、认证密钥和审计数据。

只有真实店铺缺少必要 Scope、OAuth 无法撤销、Webhook 无法稳定验签、平台禁止高风险联调或业务动作无法回滚时，才切换测试店铺。切换只替换店铺授权和测试数据，不改变业务契约。

### 3.2 平台调用边界

```text
前端/Jobs/Agent
→ FastAPI Service
→ 受控 ToolExecutionService
→ TikTok PlatformAdapter
→ TikTok Shop API
```

- OAuth、Token 刷新、请求签名、Webhook 验签和平台错误映射归 `stores/integrations`。
- 店铺、订单、会话、消息和审计写入归对应全栈业务 Service 和 Repository。
- Agent 只提交结构化工具请求，不持有 TikTok Token，不直接调用适配器。
- 所有真实写工具强制校验权限、店铺范围、参数、二次确认和 `Idempotency-Key`。
- 平台超时且结果不可确认时记录 `unknown`，禁止自动重试写操作。

### 3.3 DeepSeek 与业务事实边界

```text
可信业务上下文/FAQ
→ 最小化与脱敏
→ AI Agent 工作流
→ DeepSeek Provider
→ 结构化输出校验
→ 确定性安全门禁
→ 草稿/人工复核/转人工
```

- DeepSeek 只负责语言理解、回复、翻译和营销草稿，不负责证明订单、物流、退款、优惠和地址修改是否真实完成。
- 高风险业务事实必须绑定可信工具证据，至少包含对象、动作、时态、极性、条件和证据来源。
- 姓名和手机号按需脱敏；完整地址、支付信息、平台凭证、OAuth Code、Token 和 API Key 禁止发送给模型。
- DeepSeek API Key 只通过服务端密钥注入，不保存到浏览器、业务数据库明文字段、日志、`agent_runs` 或测试报告。
- 模型失败、输出非法、安全复核失败或工具证据不足时，必须转人工或返回草稿失败，不得触发平台发送。

### 3.4 生产开关

所有新开关默认关闭：

```text
REAL_TIKTOK_READ_ENABLED=false
REAL_TIKTOK_WEBHOOK_ENABLED=false
REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false
REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false
LLM_ENABLED=false
LLM_LIVE_EVAL=false
AI_TRANSLATION_ENABLED=false
AI_MARKETING_ENABLED=false
AUTO_REPLY_ENABLED=false
ALLOW_MOCK_PLATFORM_ADAPTERS=false
```

AI 开关复用当前代码已有命名，不建立第二套同义配置。开关必须在服务端强制执行。前端隐藏按钮不能替代后端门禁；高风险写操作不得复用普通消息发送开关。

## 4. 公共接口决策

新增接口：

```http
GET /v1/settings/channels/tiktok/oauth/start
GET /v1/integrations/tiktok/oauth/callback
```

复用接口：

```http
POST /v1/webhooks/tiktok
POST /v1/workspace/sessions/{session_id}/messages
POST /v1/chat/query
```

固定外部地址：

```text
OAuth callback: https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback
Webhook:        https://www.hophorsefit.com/v1/webhooks/tiktok
```

OAuth `start` 只允许具有渠道管理权限且具有目标店铺访问权的用户调用。后端生成一次性 `state` 并写入 Redis；callback 校验并消费 `state` 后才能交换 Token。响应和重定向不得包含 Token 或平台原始错误详情。

## 5. 凭证、审计与数据存储

- 优先复用 `channel_accounts` 保存授权元数据和加密后的凭证，不新增并行凭证表。
- 复用 `webhook_events`、`tool_calls`、`audit_logs`、`messages` 和 `agent_runs` 保留链路追踪。
- 凭证加密主密钥必须来自服务端密钥管理；数据库备份不得包含可单独解密凭证的主密钥。
- 审计只保存低敏请求摘要、操作者、店铺、动作、幂等键、平台请求 ID、状态和耗时，不保存完整消息、地址或凭证。
- 若实现需要改变公共表结构，必须先提交新的 DATA/ADR 并提供可逆 Alembic 迁移，不得直接修改 `018` 及以前迁移。

## 6. 放行与回滚

放行顺序固定为：

```text
部署与密钥检查
→ OAuth
→ 只读 API
→ Webhook
→ 人工确认普通消息
→ DeepSeek 离线评测
→ 内部 AI 建议
→ 公开 SSE
→ 五日稳定性
→ 发券/地址/营销灰度
→ 低风险自动回复
```

回滚优先关闭最小功能开关，再撤销对应店铺授权或 Provider Key；不得通过删除业务数据回滚。写操作出现 `unknown` 时停止同店铺同工具后续写入并人工对账。发生凭证泄漏时立即撤销和轮换凭证，保留脱敏审计证据。

## 7. 验收门禁

生产放行必须同时满足：

- TikTok OAuth、Token 刷新、撤销、只读 API、Webhook 验签、重试和幂等通过独立测试。
- 普通人工消息发送的成功、失败、重复、超时、未知结果和审计通过。
- `DEF-P4-AI-008/009` 由测试工程师独立复测关闭。
- DeepSeek 回复、翻译、营销和敏感信息评测通过，模型、Prompt、策略和数据集版本可追溯。
- 真实模型公开 SSE 首输出小于 3 秒，50 个授权客户端测试 P99 小于 5 秒。
- 连续五日稳定性和 99.5% 可用性形成正式报告。
- TikTok 和 DeepSeek 凭证完成轮换演练，数据库备份恢复和功能开关回滚通过。
- 无未关闭 P0/P1/P2 生产阻断缺陷，并取得架构师和产品负责人放行。

## 8. 影响与责任

- 全栈开发工程师 Agent 负责 OAuth、真实平台适配器、Webhook、工具执行、运行配置、SSE 传输和部署。
- AI Agent 开发工程师负责 DeepSeek Provider、结构化业务声明、安全门禁、Prompt 和真实模型评测。
- 测试工程师 Agent 负责独立功能、安全、性能、稳定性和恢复测试。
- 架构师 Agent 负责边界变更评审、逐级放行和最终技术验收，不代替执行 Agent 编写产品代码。
