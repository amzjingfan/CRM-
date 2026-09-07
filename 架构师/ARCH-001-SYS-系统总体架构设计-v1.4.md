# CRM 智能聊天系统总体架构设计 v1.4 增量说明

状态：已确认

## 1. 版本关系

本文件继承 `ARCH-001-SYS-系统总体架构设计-v1.3.md` 的全部未变更内容，新增真实 TikTok 店铺和 DeepSeek 生产接入架构，并同步当前权威数据库迁移与测试状态。v1.3 保留为历史版本，不删除、不覆盖。

本版本的生产安全决策以 `ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md` 为准。

## 2. 生产接入上下文

```text
TikTok Shop
  ├─ OAuth / Read API ───────────────┐
  └─ Webhook ────────────────────────┤
                                     ↓
Next.js → FastAPI → integrations → 业务 Service/Repository
                    ↑                    ↓
                    └── tools ← Agent Workflow ← DeepSeek Provider
                                      ↓
                              BGE-M3 / pgvector RAG
```

- `integrations` 负责 OAuth、凭证生命周期、平台签名、Webhook 验签和平台错误归一化。
- `tools` 是全部平台写操作的唯一业务入口，负责权限、店铺隔离、参数、幂等、超时和审计。
- `agent` 负责 AI 工作流、结构化声明、安全判断、Prompt 和工具选择，不直接访问平台 SDK。
- DeepSeek 负责语言生成；PostgreSQL、可信工具结果和已发布 FAQ 才是业务事实来源。
- BGE-M3 本地检索架构保持不变，不因接入 DeepSeek 改为外部 Embedding。

## 3. 环境与流量路径

```text
local        Mock/确定性测试，禁止真实店铺凭证
integration 真实店铺 OAuth、只读 API、Webhook
staging     人工确认消息、DeepSeek 草稿和性能验证
production 按独立开关逐级灰度
```

各环境隔离数据、缓存、对象存储、授权、模型 Key、认证密钥、日志和审计。生产环境必须使用 HTTPS、固定出口 IP、受限入站端口和服务端密钥注入；`ALLOW_MOCK_PLATFORM_ADAPTERS=false`。

## 4. 关键链路

### 4.1 OAuth

```text
管理员发起授权
→ 后端生成 Redis 一次性 state
→ TikTok 授权页
→ 固定 callback 校验并消费 state
→ 后端交换 Token
→ 加密保存 channel_accounts
→ 读取店铺信息并绑定内部 store
→ 写入低敏审计
```

### 4.2 Webhook

```text
原始请求体 ≤ 1 MiB
→ 验签与摘要
→ webhook_events 幂等落库
→ 200 快速响应
→ Worker 认领
→ 标准化事件
→ 更新订单/客户/会话/消息
→ 审计和指标
```

### 4.3 AI 建议与发送

```text
可信会话上下文
→ 脱敏
→ RAG/可信工具证据
→ DeepSeek 生成结构化草稿
→ 确定性安全门禁
→ 草稿/人工复核/转人工
→ 人工确认
→ tools
→ TikTok Adapter
```

AI 结果不等于平台发送成功；发送状态以工具执行和平台确认结果为准。

## 5. 当前数据库与可观测性基线

- 当前权威 Alembic head 为 `018_ai_observability`，替代 v1.3 中记录的 `015_vector_ops` 当前状态。
- BGE-M3 向量维度仍为 1024，Dense、词法、RRF 和 Reranker 架构不变。
- `018_ai_observability` 已增加 Agent 首输出耗时和指标聚合所需字段。
- 真实接入优先复用 `channel_accounts`、`webhook_events`、`tool_calls`、`audit_logs`、`messages` 和 `agent_runs`。
- 新迁移只能从 `019` 开始；是否需要迁移必须由实现时的字段差异证明，禁止为未来场景预建平行表。

## 6. 生产开关与故障隔离

TikTok 只读、Webhook、普通消息、高风险写入、DeepSeek、公开回复、营销内容和自动回复使用独立开关，默认全部关闭。任何开关只能扩大一个能力维度。

- OAuth 或 Token 异常：关闭对应店铺平台能力并要求重新授权。
- Webhook 验签异常：拒绝事件，不进入业务标准化。
- 平台写入结果未知：标记 `unknown`，停止自动重试并人工对账。
- DeepSeek 异常：结束 SSE、保留失败运行记录并转人工，不触发发送。
- 数据泄漏或高风险事实漏放：立即关闭全部公开 AI 与 AI 营销开关。

## 7. 当前验收状态

- Phase 3 业务工具和营销仅在契约级 Mock 范围通过。
- Phase 4 SSE、看板、部署和稳定性工程范围有条件通过，不代表真实模型生产验收。
- `DEF-P4-AI-008` 为 P1/Open，`DEF-P4-AI-009` 为 P2/Open；二者关闭前禁止公开 AI 回复和 AI 营销发送。
- DeepSeek 真实质量评测、公开 SSE 50 授权客户端测试和五日稳定性仍未完成。
- TikTok OAuth、只读 API、Webhook 和人工消息尚未真实联调。
- 因此当前总体状态为“架构已确认，工程实施待执行，生产未放行”。

## 8. 后续拆分边界

MVP 继续采用 FastAPI 模块化单体。只有真实流量证明存在独立扩缩容或故障隔离需求时，才按现有边界拆分 `integrations/webhook-worker`、`agent/model-runtime` 或 `jobs`；不因本次接入提前建设微服务或新增 Java 主服务。

