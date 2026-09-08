# TikTok 人工辅助首版发布范围

状态：已确认

## 1. 决策摘要

CRM 智能聊天系统 v0.1 采用“TikTok 人工辅助首版”作为首个真实发布范围。首版只对 TikTok Shop 的 OAuth、只读 API、Webhook、人工确认普通消息发送，以及 AI 建议、RAG、客服工作台、知识库和数据看板进行真实环境验收。

产品仍保持 TikTok、Shopee、Amazon 三平台定位，现有 PRD、管理端接口和三平台 UI 不改为 TikTok-only。Shopee 与 Amazon 继续保留统一平台枚举、适配器契约和界面入口，但不在 v0.1 实现真实连接，也不得被发布材料描述为已接入或可用。

本决策只确定首版范围，不代表任何真实环境门禁已经通过。生产放行仍以 `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md` 的实际证据为准。

## 2. 背景与约束

- 当前产品文档和 UI 已按 TikTok、Shopee、Amazon 三平台设计，保留该产品方向可以避免不必要的界面与契约返工。
- TikTok 已具备 OAuth、只读、Webhook 和人工确认普通消息的工程实现；真实店铺联调和服务器门禁尚未执行。
- Shopee 与 Amazon 当前仅有契约级 Mock 或统一接口边界，不具备真实生产适配器和独立验收证据。
- AI 已具备建议回复、FAQ RAG、工作台、知识库和看板工程能力，但公开自动回复、高风险写入、主动营销自动发送和生产稳定性尚未放行。
- v0.1 的目标是先完成可控、可回滚的人工辅助闭环，不扩大到无人值守自动客服。

## 3. v0.1 必须验收的能力

| 能力 | 首版验收边界 |
| --- | --- |
| TikTok OAuth | 真实店铺授权、Scope、Token 交换/刷新/撤销和店铺隔离 |
| TikTok 读取 | 授权店铺、订单、物流、会话、消息和 Webhook 订阅只读冒烟 |
| TikTok Webhook | 真实签名、重复通知、平台重试、幂等入库和 Worker 恢复 |
| 人工发送 | 单店铺、单账号、单操作员二次确认发送；失败和 `unknown` 可对账 |
| AI 建议 | 只生成内部安全草稿，由人工决定是否采用，不自动发送 |
| RAG | 当前店铺、当前版本、已审批知识的 BGE 检索和 Top-5 重排 |
| 客服工作台 | 会话、消息、客户摘要、AI 建议、人工发送和转人工闭环 |
| 知识库 | FAQ 分类、增删改查、导入、审批、向量化和检索状态 |
| 数据看板 | 会话量、转人工率、平均响应、挽回 GMV、趋势和渠道分布 |

## 4. 保留但不纳入 v0.1 真实实现的能力

- Shopee 和 Amazon 的真实 OAuth、Webhook、读取、回复和营销能力。
- TikTok 发券、改地址、自动营销以及其他高风险真实写操作。
- AI 自动回复、自动发送、无人值守营销和全自动客服运营。
- 公开 AI 回复、生产翻译和营销质量在各自门禁通过前不得对外开放。

Shopee 和 Amazon 界面必须保持现有产品入口，但应以未连接、配置中或尚未开放的真实状态呈现。服务端生产环境固定 `ALLOW_MOCK_PLATFORM_ADAPTERS=false`，不得用 Mock 数据伪装成真实平台结果。

## 5. 首版业务闭环

```text
TikTok OAuth 授权
→ 只读 API / Webhook 接收客户与订单上下文
→ 工作台展示会话
→ RAG 检索已审批 FAQ
→ AI 生成内部建议
→ 客服人工确认并发送普通消息，或转人工
→ 日志、审计和看板记录结果
```

AI 建议进入输入框不等于发送授权。任何真实普通消息仍必须经过服务端权限、店铺隔离、CSRF、二次确认和 `Idempotency-Key` 检查；平台超时或结果不确定时记录 `unknown` 并停止同店铺后续发送，等待人工对账。

## 6. 配置与安全边界

生产基础配置固定关闭：

```text
ALLOW_MOCK_PLATFORM_ADAPTERS=false
REAL_TIKTOK_READ_ENABLED=false
REAL_TIKTOK_WEBHOOK_ENABLED=false
REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false
REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false
AI_TRANSLATION_ENABLED=false
AI_MARKETING_ENABLED=false
AUTO_REPLY_ENABLED=false
```

真实能力只能按“OAuth → 只读 → Webhook → AI 内部建议 → 人工普通消息”顺序逐项放行。高风险写入和自动回复不能借普通消息开关开启。

## 7. 验收和发布规则

- 每项真实能力必须有独立、可复现的测试证据；确定性测试、Mock 和 `ValidateOnly` 不能替代真实环境证据。
- v0.1 可以在 Shopee/Amazon 尚未实现时完成，但发布说明必须明确“产品保留三平台，当前真实接入仅 TikTok”。
- 任一 P0/P1/P2 生产阻断项未关闭时，不得签署最终生产放行。
- 首版通过不自动授权后续平台、高风险工具、自动回复或无人值守营销；这些能力必须单独走新的设计、测试和灰度流程。

## 8. 影响与责任

- 架构师 Agent 维护发布范围、能力边界和逐级放行顺序。
- 全栈开发工程师 Agent 负责 TikTok 真实接入、工作台、人工发送、部署和可观测性整改。
- AI Agent 开发工程师负责 AI 建议、RAG、模型安全和质量门禁。
- 测试工程师 Agent 负责真实店铺、服务器、回滚、安全、性能和稳定性独立验收。
- 产品负责人最终批准真实店铺和操作员范围；本 ADR 不代替产品放行。
