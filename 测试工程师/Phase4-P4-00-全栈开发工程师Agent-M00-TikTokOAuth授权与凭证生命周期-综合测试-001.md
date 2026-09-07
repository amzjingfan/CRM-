# Phase 4 REAL-FS-02 TikTok OAuth 授权与凭证生命周期综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-FS-02` |
| 模块编号 | M00（真实平台接入跨模块基线） |
| 模块名称 | TikTok OAuth 授权与凭证生命周期 |
| 被测主责 Agent | 全栈开发工程师Agent |
| 被测协作 Agent | 架构师Agent、测试工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTokOAuth授权与凭证生命周期-007.md` |
| 被测计划 | `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 `REAL-FS-02` |
| 测试类型 | 综合测试、接口测试、集成测试、安全测试、回归测试、配置测试 |
| 执行日期 | 2026-08-26 |
| 测试结论 | **不通过；新增 `DEF-REAL-FS02-001～005`，其中 P1 三项、P2 一项、P3 一项** |

最终结论：OAuth 授权地址、官方 Token 参数、API HMAC-SHA256 签名、一次性 Redis `state`、AES-256-GCM 凭证加密、卖家/Scope/过期时间校验、外部店铺跨租户拒绝、前端低敏展示和日志脱敏等开发正向路径通过；工程回归无退化。

但独立负向审查确认三个生产阻断问题：通用 `POST /v1/settings/channels` 仍允许绕过 OAuth 创建 TikTok `connected` 渠道；Token 刷新接受与原授权不同的 `open_id` 并覆盖凭证；刷新函数没有任何 Worker、定时任务、公开接口或真实 Adapter 调用入口，授权默认约 7 天后不会自动刷新且状态可能继续显示 `connected`。另外，数据库允许同一内部店铺同时存在两个 TikTok 渠道，`return_to` 也未严格限制为文档声明的唯一值。

因此 REAL-FS-02 不建议验收，不得进入真实店铺 OAuth 生产联调或 REAL-FS-03 放行。即使修复上述缺陷，真实店铺 OAuth、真实 Scope、平台侧撤销和真实 Token 刷新仍需在仓库外安全注入凭证后单独复测，本报告不以 Mock 结果冒充真实平台结论。

## 2. 测试依据、范围与边界

### 2.1 测试依据

- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- `共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.7 节。
- `共享记忆文档/开发任务拆解（按人天分配）.md`。
- `共享记忆文档/MVP范围与验收标准.md`。
- `共享记忆文档/代码编写手册.md`。
- `共享记忆文档/项目团队职责说明.md`。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- `架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`。
- `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.0.md`。
- `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md`。
- `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-真实环境配置与基础设施-综合测试-004.md`。
- 项目全部适用的 `AGENTS.md` 和 `测试工程师/测试报告命名规范.md`。

官方契约核对依据：

- [TikTok Shop Authorization overview](https://partner.tiktokshop.com/docv2/page/authorization-overview-202407)。
- [TikTok Shop Sign your API request](https://partner.tiktokshop.com/docv2/page/sign-your-api-request)。
- [TikTok Shop Get Authorized Shops](https://partner.tiktokshop.com/docv2/page/get-authorized-shops)。
- [TikTok Shop Connecting shops](https://partner.tiktokshop.com/docv2/page/connecting-shops)。

### 2.2 测试范围

- OAuth `start` 和 callback 的路由、认证、RBAC、店铺权限及 OpenAPI 契约。
- 随机 `state`、Redis TTL、哈希键、原子消费、缺失/过期/重复/用户不匹配路径。
- 官方卖家授权域名、`service_id`、`authorized_code`、Token 刷新和已授权店铺 API。
- Token 的卖家身份、Scope、过期时间、授权主体和店铺绑定连续性。
- Access/Refresh Token AES-256-GCM 加密、上下文绑定、防篡改和日志脱敏。
- `channel_accounts`、`audit_logs`、撤销、刷新、过期、并发和唯一约束。
- 渠道前端入口、低敏状态、Token 不进入浏览器可读存储。
- 后端、前端、隔离 PostgreSQL、Compose、依赖审计和源码凭据扫描。

### 2.3 未执行和结论边界

- 未读取、打印或使用仓库 `.env` 的值；所有动态测试仅使用无价值假凭证。
- 未提供真实 TikTok App Secret、真实店铺 Token 和目标环境 TLS，因此未执行真实店铺 OAuth。
- 未测试 REAL-FS-03 的真实订单/消息只读 API、Webhook 或后续平台写操作。
- 未执行平台后台真实撤销、凭证轮换、目标主机固定出口 IP 和真实备份恢复。
- 当前目录不是 Git 仓库，无法给出不可变提交哈希；测试基于 2026-08-26 当前工作区。

## 3. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell 7.6.4，Asia/Shanghai |
| Python | 3.11.15，uv 0.12.3；锁文件解析 125 个包 |
| 前端 | Node.js 24.19.0、npm 11.17.0；Next.js 15.5.23 |
| Docker | Docker Engine 29.7.2、Docker Compose 5.3.1 |
| 数据库 | 隔离 PostgreSQL 16 + pgvector；空库迁移到 `018_ai_observability` |
| 代码状态 | 非 Git 工作区；测试工程师未修改产品代码 |

## 4. 测试结果摘要

| 测试项 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| Ruff | All checks passed | 通过 |
| Ruff format | 209 files already formatted | 通过 |
| mypy | 155 个源文件无问题 | 通过 |
| OAuth/生产配置专项 | 38 passed | 通过 |
| 默认后端全量回归 | 536 passed、8 skipped、2 个既有弃用警告 | 通过 |
| 隔离 PostgreSQL 全量回归 | 544 passed、0 skipped、2 个既有弃用警告 | 通过 |
| 空库迁移 | 001→018 | 通过 |
| 前端 lint/typecheck | 无错误 | 通过 |
| 前端自动化 | 24 passed | 通过 |
| 前端生产构建 | 14 个静态页面构建成功 | 通过 |
| OpenAPI | 两个 OAuth GET 路由存在 | 通过 |
| 未认证访问 | start/callback 均返回 HTTP 401 + `40101` | 通过 |
| 生产 Compose | 8 个服务安全解析，未展开密钥 | 通过 |
| 锁定依赖审计 | 124 个包无已知漏洞或不良状态 | 通过 |
| 高风险凭据源码扫描 | 200 个代码/配置文本文件，0 命中 | 通过 |
| 独立 OAuth 负向探针 | 4/4 复现非预期行为 | **失败** |
| 数据库重复绑定探针 | 同一 `store_id + tiktok` 成功写入 2 条记录，事务已回滚 | **失败** |
| 真实 TikTok 店铺 OAuth | 无真实凭证，未执行 | 未执行 |

两个既有非阻断警告未变化：Starlette TestClient/httpx 弃用提示、passlib 读取 argon2 版本弃用提示。默认跳过的 8 项数据库相关测试已在隔离 PostgreSQL 回归中覆盖。

## 5. 详细测试场景

### 5.1 OAuth 官方契约与正向安全路径

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| Seller 授权域名 | US/ROW 使用官方 `services.*.tiktokshop.com/open/authorize` | 通过 |
| 授权地址参数 | 只包含 `service_id` 和随机 `state`，不含 App Secret | 通过 |
| Token 交换 | GET `/api/v2/token/get`，`grant_type=authorized_code` | 通过 |
| Token 刷新请求 | GET `/api/v2/token/refresh`，`grant_type=refresh_token` | 通过 |
| Get Authorized Shops | 202309 路径、HMAC-SHA256、`x-tts-access-token` | 通过 |
| Token 时间语义 | 按 Unix epoch 解析 Access/Refresh 过期时间 | 通过 |
| 卖家身份 | 接受 user_type 0/4/5，拒绝 Creator/Partner | 通过 |
| Scope | 缺少 `seller.authorization.info` 时拒绝 | 通过 |
| 唯一真实店铺 | Token 返回 0 个或多个店铺时拒绝 | 通过（代码/开发测试） |
| 外部店铺跨租户 | 同一外部店铺绑定其他内部店铺时返回冲突 | 通过 |

### 5.2 state、认证和重定向

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| Redis 键 | state 经 SHA-256 后进入键名，不保存可直接使用的明文键 | 通过 |
| TTL | 默认 600 秒，配置范围 60～1800 秒 | 通过 |
| 原子消费 | 使用 Redis `GETDEL`，重复回调失效 | 通过 |
| 缺失/过期/重复 state | 返回统一校验错误，不交换 Token | 通过 |
| state 用户不匹配 | 返回权限错误 | 通过 |
| start 权限 | 要求 `settings.channels` 并在 Service 校验目标店铺访问权 | 通过（代码审查/专项测试） |
| 未认证 start/callback | HTTP 401、错误码 `40101` | 通过 |
| 回调日志 | code/state 在统一 JSON Logger 中显示为 `[REDACTED]` | 通过 |
| `return_to` 精确白名单 | `/settings/channels?unexpected=1` 被接受 | **失败** |

### 5.3 凭证、刷新、撤销和数据库

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| AES-256-GCM | Token 密文不含明文；错误密钥、上下文或篡改密文失败 | 通过 |
| 凭证上下文 | 绑定内部店铺、外部店铺和 access/refresh 类型 | 通过 |
| 正常授权保存 | 校验完成后才保存密文、Scope、店铺摘要和审计 | 通过 |
| 失败无半成品 | 已覆盖业务冲突/校验失败回滚和失败审计 | 通过（确定性路径） |
| 刷新成功 | 更新 Token 密文、Access 过期时间、Scope 和审计 | 通过（函数级） |
| 刷新授权主体连续性 | 新 Token 的 `open_id` 与原哈希不一致仍标记 `connected` | **失败** |
| 刷新运行入口 | 仅存在函数定义和开发测试，没有生产调用方 | **失败** |
| 本地撤销 | 清除本地 Refresh Token，Access 引用改为 revoked，保留审计 | 通过（函数级） |
| 同店铺同平台唯一性 | 实际 PostgreSQL 允许两条 TikTok 渠道 | **失败** |
| 外部店铺唯一性 | `(platform, external_store_id)` 唯一约束存在 | 通过 |

### 5.4 前端与生产配置

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| TikTok 授权入口 | 调用服务端 start 后跳转 `authorization_url` | 通过 |
| 浏览器 Token | TikTok 卡片不接受 Token；页面不使用 localStorage | 通过 |
| 低敏展示 | 展示名称、状态、Scope 和最后同步时间 | 通过 |
| Mock 表单 | 可见选项仅 Shopee/Amazon | 通过 |
| 后端绕过 | 通用 ChannelCreate 和 POST Service 仍接受 TikTok | **失败** |
| 功能开关 | 四个 REAL_TIKTOK 开关继续为 false，FS03 前启用会失败关闭 | 通过 |
| 配置注入 | Service ID、市场、TTL、Scope、App Secret、加密密钥只在服务端 | 通过 |

## 6. 缺陷与观察

### DEF-REAL-FS02-001：通用渠道接口可绕过 OAuth 创建 TikTok 已连接记录

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 服务端授权绕过、生产数据真实性 |
| 影响范围 | `/v1/settings/channels`、`channel_accounts`、后续 REAL-FS-03/04 |
| 状态 | Open |
| 是否阻断 | 是 |
| 建议负责 Agent | 全栈开发工程师Agent |

复现与证据：

1. `ChannelCreate.platform` 仍允许 `tiktok`。
2. `create_channel()` 直接将请求构造成 `ChannelAccount`，没有检查 `APP_ENV`、`ALLOW_MOCK_PLATFORM_ADAPTERS` 或 TikTok 必须通过 OAuth。
3. 使用具备 `settings.channels` 和店铺权限的账号调用 `POST /v1/settings/channels`，提交 `platform=tiktok`、任意外部店铺 ID 和凭证引用。
4. 请求可进入创建与 `channel.authorize` 成功审计路径，不需要 state、auth_code、Token 交换、Scope 或真实店铺校验。

实际结果：前端虽然隐藏 TikTok Mock 选项，但后端仍允许绕过 OAuth。伪造记录还会阻断同一内部店铺后续绑定真实 TikTok 店铺。

预期结果：TikTok 渠道必须由 OAuth callback 创建或更新；通用 POST 在服务端拒绝 `platform=tiktok`，或仅在显式、非生产 Mock 模式允许，并且不得写成真实 `connected` 状态。

### DEF-REAL-FS02-002：Token 刷新未校验授权主体 open_id 连续性

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 凭证主体错绑、租户安全 |
| 影响范围 | `refresh_tiktok_channel_token()`、后续真实只读和写操作 |
| 状态 | Open |
| 是否阻断 | 是 |
| 建议负责 Agent | 全栈开发工程师Agent |

复现与证据：

1. 创建已保存原授权 `open_id_hash` 的 TikTok 渠道。
2. 独立假 Provider 在 Refresh 响应中返回不同 `open_id`，但保持合法卖家 `user_type`、Scope 和未来过期时间。
3. 调用 `refresh_tiktok_channel_token()`。
4. 函数成功提交新 Token，状态为 `connected`，原 `open_id_hash` 保持不变。

实际结果：数据库中的授权主体摘要和实际保存的新凭证不再一致。官方建议每次刷新重新验证 `user_type`、`open_id` 和 Scope；当前只验证 user_type、Scope 和过期时间。

预期结果：刷新前后 `open_id` 哈希必须一致；还应确认授权店铺仍包含当前 `external_store_id`。任何不一致都不得覆盖旧凭证，应标记需要重新授权并写入低敏失败审计。

### DEF-REAL-FS02-003：Token 刷新与过期状态没有运行时触发链路

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 授权生命周期、生产可用性 |
| 影响范围 | Token 默认约 7 天有效期、渠道状态、REAL-FS-03 |
| 状态 | Open |
| 是否阻断 | 是 |
| 建议负责 Agent | 全栈开发工程师Agent |

复现与证据：

1. 全项目检索 `refresh_tiktok_channel_token` 和 `token_expires_at`。
2. 除函数定义、模型和开发测试外，没有 Worker、Jobs、定时任务、公开管理接口或 Adapter 调用该刷新函数。
3. 构造即将过期/已经过期的渠道，不存在运行任务主动刷新或将状态改为 `expired`。

实际结果：函数级刷新测试通过，但生产 OAuth 连接不会自动进入该函数；Access Token 到期后渠道仍可能显示 `connected`。

预期结果：明确并实现唯一运行策略，例如数据库 Worker 提前刷新，或 REAL-FS-03 Adapter 在读取前采用行锁执行惰性刷新。必须避免并发刷新，记录成功/失败审计，并在 Refresh Token 过期时提示重新授权。

### DEF-REAL-FS02-004：同一内部店铺可并发绑定多个 TikTok 渠道

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 类型 | 数据一致性、并发竞态 |
| 影响范围 | `channel_accounts`、OAuth callback、渠道选择 |
| 状态 | Open |
| 是否阻断 | 是 |
| 建议负责 Agent | 全栈开发工程师Agent、架构师Agent |

复现与证据：

1. 迁移和 ORM 只有 `(platform, external_store_id)` 唯一约束。
2. 在隔离 PostgreSQL 事务中创建一个内部店铺。
3. 同时插入两个 `platform=tiktok`、外部店铺 ID 不同的渠道。
4. 两条记录均成功，查询 `store_id + platform` 得到 `duplicate_bindings=2`；随后事务已回滚。

实际结果：Service 的“先查询再插入”只能阻止顺序请求，两个并发 callback 可同时通过查询并成功插入。后续 `find_channel_by_store_platform` 选择结果不确定。

预期结果：若首期坚持一个内部店铺对应一个 TikTok 渠道，应新增可逆迁移和 `(store_id, platform)` 唯一约束，并在迁移前处理历史重复项；如架构允许多账号，必须先调整数据模型、选择键和所有查询契约，不能依赖当前单值 Repository。

### DEF-REAL-FS02-005：return_to 未严格限制为唯一允许值

| 项目 | 内容 |
| --- | --- |
| 优先级 | P3 |
| 类型 | 输入校验、接口契约 |
| 影响范围 | OAuth start/callback 重定向 |
| 状态 | Open |
| 是否阻断 | 否；随阻断缺陷一并修复 |
| 建议负责 Agent | 全栈开发工程师Agent |

复现步骤：调用 `validate_return_to("/settings/channels?unexpected=1")`。

实际结果：函数只比较 `parsed.path`，因此保留任意查询参数；callback 再拼接第二个 `?oauth=...`，生成与文档不一致的重定向地址。

预期结果：当前契约只允许字符串精确等于 `/settings/channels`；应同时拒绝 query、params 和 fragment，或使用安全 URL 构造器显式合并受控查询字段。

### OBS-REAL-FS02-001：真实平台撤销和密钥轮换仍是生产门禁

本地 `DELETE /settings/channels/{id}` 只销毁数据库中的本地 Token 可用性，不会替用户在 TikTok Seller Center 取消应用授权。实施记录已将此列为已知风险，不重复升级为本轮新缺陷。正式生产放行前仍需形成可执行的卖家后台撤销、App Secret/加密主密钥轮换和重授权演练证据。

## 7. 验收结论与后续门禁

- REAL-FS-02 当前结论为不通过。
- `DEF-REAL-FS02-001/002/003` 为 P1，`004` 为 P2，均阻断真实 OAuth 和 REAL-FS-03。
- `DEF-REAL-FS02-005` 为 P3，不单独阻断，但必须同步修复。
- 全量工程回归通过不能覆盖负向授权、凭证主体和并发一致性失败。
- 修复后必须执行第二次独立综合复测，至少覆盖后端 TikTok Mock 创建拒绝、刷新主体一致性、并发刷新、提前刷新/过期调度、数据库唯一迁移升级回滚以及严格 return_to。
- 所有 `REAL_TIKTOK_*`、平台写操作、公开 AI 回复、AI 营销和自动回复开关继续保持关闭。
- 上述工程缺陷关闭后，再在目标 HTTPS 环境安全注入真实凭证，执行真实店铺授权、真实 Scope、Get Authorized Shops、Token 刷新和平台侧撤销测试。

## 8. 执行证据摘要

主要命令和方法：

```text
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run mypy app scripts
uv run pytest tests/test_tiktok_oauth.py tests/test_real_runtime_config.py -q
uv run pytest -q
scripts/run-postgres-integration-tests.ps1 -KeepDatabase
隔离 PostgreSQL 事务内双 TikTok 渠道插入与 ROLLBACK
测试工程师独立 OAuth 负向探针（假凭证、无公网、无产品数据）
uv audit --locked
npm run lint
npm run typecheck
npm run test
npm run build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml config --services
OpenAPI 路由和未认证 401/40101 探针
不读取 .env 的高风险凭据源码模式扫描
```

清理说明：独立负向探针文件已删除；隔离数据库写入在事务内回滚，`postgres-test` 容器已停止并删除。测试工程师仅新增本报告并更新测试报告索引，没有修改产品代码。
