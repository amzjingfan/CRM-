# TikTok OAuth 授权与凭证生命周期实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-02 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-25 |
| 完成日期 | 2026-08-25 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的渠道接入和多店铺隔离要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 的系统配置接口及本轮新增 11.7 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`。
- 任务依据：`全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-02。
- 验收依据：REAL-FS-02 的 state、Token、店铺绑定、刷新/撤销、租户隔离和敏感信息要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。
- 前置测试：`测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-真实环境配置与基础设施-综合测试-004.md` 已确认 REAL-FS-01 工程范围通过。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 完成 TikTok Shop 卖家 OAuth 的发起、回调、Token 交换、真实店铺校验和安全存储。
- 让授权的正常、拒绝、过期、重复、跨用户、跨租户、刷新和撤销状态可追踪。
- 前端只提供服务端 OAuth 入口和低敏授权状态展示。

### 3.2 实施范围

- `GET /v1/settings/channels/tiktok/oauth/start`。
- `GET /v1/integrations/tiktok/oauth/callback`。
- Redis 一次性 state、TikTok Token/Get Authorized Shops 客户端、AES-256-GCM 凭证存储。
- 现有 `channel_accounts` 和 `audit_logs` 的授权、刷新、过期、撤销生命周期。
- 渠道设置页、生产配置、OpenAPI 路由和自动化测试。

### 3.3 非目标

- 不实现 REAL-FS-03 的真实订单/物流/消息只读 API 和 Webhook。
- 不实现真实消息发送、发券、修改地址、主动营销或自动回复。
- 不在本轮使用真实 App Secret、Token、店铺数据或执行公网 TikTok 联调。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及代码时已读取代码编写手册和 Ponytail Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

复用现有 FastAPI、HttpOnly Cookie、RBAC、店铺授权、Redis、`channel_accounts` 和 `audit_logs`。授权开始前校验服务端最小配置与内部店铺权限，生成随机 state；Redis 只保存 state 哈希键并通过 `GETDEL` 原子消费。回调在数据库写入前完成 Token 契约、卖家身份、Scope、过期时间、唯一真实店铺和跨租户绑定校验，之后才使用带认证上下文的 AES-256-GCM 保存 Access/Refresh Token 密文。

### 5.2 依赖关系

- 前置依赖：REAL-FS-01、现有浏览器 Cookie 认证、Redis、渠道账号和审计表。
- 后续依赖：REAL-FS-03 使用加密渠道凭证读取真实 TikTok 数据；REAL-FS-04 使用同一渠道生命周期执行人工确认消息。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| state 重放或冒用 | Token 被绑定到错误用户/店铺 | 随机 state、哈希 Redis 键、TTL、GETDEL、用户和店铺二次校验 |
| Token 明文泄漏 | 真实店铺被接管 | AES-256-GCM、认证上下文、服务端密钥注入、日志脱敏、前端不返回凭证 |
| 外部店铺跨租户绑定 | 多店铺数据泄漏 | 外部店铺全局绑定校验和内部店铺平台唯一绑定校验 |
| 平台返回多店铺或 Scope 不完整 | 错误授权范围 | 首期只接受唯一店铺、卖家 user_type 和显式必需 Scope |
| 当前无真实凭证 | 无法证明真实 OAuth 成功 | 保持生产开关关闭，交给测试工程师在受控真实环境独立联调 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/integrations/oauth_router.py` | 新增 | OAuth 发起与回调路由 | 全栈开发工程师Agent |
| `backend/app/integrations/oauth_service.py` | 新增 | state、租户绑定、授权、刷新和审计编排 | 全栈开发工程师Agent |
| `backend/app/integrations/tiktok_oauth.py` | 新增 | 官方授权、Token、刷新、店铺读取和 API 签名客户端 | 全栈开发工程师Agent |
| `backend/app/integrations/oauth_schemas.py` | 新增 | TikTok OAuth Pydantic 契约 | 全栈开发工程师Agent |
| `backend/app/integrations/credential_crypto.py` | 新增 | AES-256-GCM 凭证认证加密 | 全栈开发工程师Agent |
| `backend/app/shared/database/redis.py` | 修改 | 一次性 OAuth state 保存和原子消费 | 全栈开发工程师Agent |
| `backend/app/stores/repository.py`、`backend/app/stores/service.py` | 修改 | 渠道绑定查询和真实 OAuth 本地撤销 | 全栈开发工程师Agent |
| `backend/app/shared/config/settings.py`、`.env.example`、`docker-compose.prod.yml` | 修改 | Service ID、市场、TTL、Scope 和生产注入契约 | 全栈开发工程师Agent |
| `backend/pyproject.toml`、`backend/uv.lock` | 修改 | 将已锁定的 PyCryptodome 声明为直接依赖 | 全栈开发工程师Agent |
| `backend/tests/test_tiktok_oauth.py` | 新增 | OAuth、加密、租户和生命周期专项测试 | 全栈开发工程师Agent |
| `frontend/app/settings/channels/page.tsx`、`frontend/lib/api.ts` | 修改 | 服务端 OAuth 入口和低敏状态展示 | 全栈开发工程师Agent |
| `frontend/tests/tiktok-oauth.test.mjs` | 新增 | 前端 OAuth 安全契约测试 | 全栈开发工程师Agent |
| `README.md`、`deploy/production/README.md` | 修改 | OAuth 配置、回调、开关和运维边界 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：新增两个 REAL-FS-02 GET 接口；接口详情已同步管理端接口文档 11.7。
- 数据库：不新增迁移；复用 `channel_accounts` 和 `audit_logs`，迁移 head 保持 `018_ai_observability`。
- 配置项：新增 `TIKTOK_SERVICE_ID`、`TIKTOK_OAUTH_MARKET`、`TIKTOK_OAUTH_STATE_TTL_SECONDS`、`TIKTOK_REQUIRED_SCOPES`；不记录真实值。
- AI：不适用；未修改 Agent、Prompt、RAG、模型或 AI 开关。

### 6.3 关键实现说明

- TikTok 授权地址只包含 Service ID 和 state，不包含 App Secret。
- Token API 使用官方 `grant_type=authorized_code`；授权店铺请求按路径、排序参数和 HMAC-SHA256 规则签名。
- 授权失败不保存半成品渠道；数据库异常或业务校验失败先回滚，再追加低敏失败审计。
- Token 刷新成功继续保存密文；刷新失败标记 `expired`。渠道撤销销毁本地 Token 可用性并保留审计证据。
- 所有 `REAL_TIKTOK_*`、AI 和营销开关继续保持关闭，OAuth 完成不自动扩大平台能力。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 后端锁与静态检查 | `uv lock --check`、Ruff、format、mypy | 全部通过 | 全部通过 | 通过 |
| OAuth 专项 | `uv run pytest tests/test_tiktok_oauth.py tests/test_real_runtime_config.py -q` | state、Token、加密、隔离、刷新/撤销通过 | 38 passed | 通过 |
| 后端全量 | `uv run pytest -q` | 既有能力不退化 | 512 passed，8 skipped，2 个既有依赖弃用警告 | 通过 |
| PostgreSQL 集成 | `scripts/run-postgres-integration-tests.ps1` | 空库迁移到 head 并全量通过 | 迁移到 018；520 passed | 通过 |
| 前端 | lint、typecheck、test、build | 全部通过 | 24 passed；14 个静态页面构建成功 | 通过 |
| 生产 Compose | `docker-compose ... config --services` | 安全解析且不展开密钥 | 8 个生产服务解析成功 | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包未发现已知漏洞或不良状态 | 通过 |
| 真实 TikTok OAuth | 真实店铺受控联调 | 成功授权并读取唯一店铺 | 未执行：本轮未注入真实凭证 | 未执行 |

## 8. 实施结果

- 完成项：OAuth 发起/回调、一次性 state、Token/店铺契约、凭证加密、租户绑定、刷新/撤销、前端入口、配置、文档和自动化回归。
- 未完成项：真实店铺授权与平台侧回调联调，必须在安全生产配置和测试工程师监督下执行。
- 与原方案差异：未新增数据库迁移，因为现有 `channel_accounts` 字段可安全承载密文和生命周期元数据。
- 当前状态：REAL-FS-02 工程实现完成；生产能力未放行，四个真实 TikTok 开关仍关闭。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-FS02-001 | 真实店铺 OAuth、Scope 和平台返回字段尚未现场验证 | P1 | 全栈开发工程师Agent、测试工程师Agent | REAL-FS-02 真实联调 |
| R-REAL-FS02-002 | 本地撤销不能替代用户在 TikTok 后台撤销应用授权 | P2 | 全栈开发工程师Agent | REAL-FS-03/06 运维流程 |
| R-REAL-FS02-003 | 真实只读 Adapter 未完成，授权后仍不能读取订单/消息 | P1 | 全栈开发工程师Agent | REAL-FS-03 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent。
- 后续任务：先对 REAL-FS-02 做独立安全和真实店铺联调；通过后进入 REAL-FS-03。
- 必须注意：真实密钥只能由服务端安全注入；TikTok 后台回调必须与配置完全一致；联调前保持全部真实写入、AI 回复和营销开关关闭。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构决策（实现遵循 ADR-004，无新增冲突决策）。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引将在正式测试完成后更新。
