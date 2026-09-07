# Phase 4 REAL-FS-02 TikTok OAuth 授权与凭证生命周期第二次综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-FS-02` |
| 模块编号 | M00（真实平台接入跨模块基线） |
| 模块名称 | TikTok OAuth 授权与凭证生命周期 |
| 被测主责 Agent | 全栈开发工程师Agent |
| 被测协作 Agent | 架构师Agent、测试工程师Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 上一轮报告 | `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTokOAuth授权与凭证生命周期-综合测试-001.md` |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTokOAuth测试缺陷修复-008.md` |
| 被测计划 | `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 `REAL-FS-02` |
| 测试类型 | 综合测试、修复验证、接口测试、集成测试、安全测试、回归测试、配置测试 |
| 执行日期 | 2026-08-26 |
| 测试结论 | **不通过；`DEF-REAL-FS02-001～005` 全部关闭，但新增 `DEF-REAL-FS02-006`（P2/Open）** |

最终结论：001 号报告发现的 TikTok 通用渠道 OAuth 绕过、刷新主体错绑、刷新无运行入口、同店铺双 TikTok 渠道和宽松 `return_to` 五项缺陷均已完成根因修复并通过独立复测。专项 48 项、默认后端 560 项、隔离 PostgreSQL 573 项和前端 24 项测试通过；019 迁移对历史重复授权能够失败关闭，清理隔离测试数据后可恢复到 head，部分唯一索引和双会话 `SKIP LOCKED` 均生效。

完整审查新增一个生产配置缺陷：应用在全部真实 TikTok 业务开关保持关闭、但 OAuth 端点已可使用的当前阶段，只检查 `TIKTOK_OAUTH_REDIRECT_URI` 非空；生产配置可接受 `http://attacker.example/callback`，且该变量没有参与 OAuth URL 或 callback 路由的一致性校验。这与 ADR 和部署文档固定的 `https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback` 不一致，无法在应用侧发现 TikTok Partner Center 与部署声明的回调漂移。

因此本轮不建议验收 REAL-FS-02，也不放行 REAL-FS-03。真实店铺 OAuth、真实 Scope、真实 Token 刷新和平台侧撤销仍未执行；本报告只证明当前工程实现和隔离数据库行为，不以 Mock 或假凭证代替真实平台结论。

## 2. 测试依据、范围与边界

### 2.1 测试依据

- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- `共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.7 节及渠道管理接口。
- `共享记忆文档/开发任务拆解（按人天分配）.md`。
- `共享记忆文档/MVP范围与验收标准.md`。
- `共享记忆文档/代码编写手册.md`。
- `共享记忆文档/项目团队职责说明.md`。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.0.md`。
- `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md`。
- 项目全部 8 份适用 `AGENTS.md`、实施记录规范和测试报告命名规范。

官方契约核对依据：

- [TikTok Shop Authorization overview](https://partner.tiktokshop.com/docv2/page/authorization-overview-202407)。
- [TikTok Shop Connecting shops](https://partner.tiktokshop.com/docv2/page/connecting-shops)。
- [TikTok Shop Sign your API request](https://partner.tiktokshop.com/docv2/page/sign-your-api-request)。
- [TikTok Shop Get Authorized Shops](https://partner.tiktokshop.com/docv2/page/get-authorized-shops)。

### 2.2 本轮范围

- 独立复测 `DEF-REAL-FS02-001～005`。
- 审查 OAuth start/callback、Token 交换、刷新、撤销、店铺绑定和低敏展示。
- 审查 Jobs Worker 周期刷新入口及生产 Compose 配置注入。
- 验证迁移 `018_ai_observability ↔ 019_tiktok_channel_unique`。
- 验证历史重复授权的迁移失败关闭、数据库唯一约束和并发认领。
- 执行后端、前端、配置、依赖和敏感信息回归。
- 重新对照 TikTok 官方 Seller OAuth、Token、签名和授权店铺契约。

### 2.3 未执行范围

- 未读取或输出项目 `.env` 的真实值。
- 未使用用户真实 TikTok App Secret、Access Token、Refresh Token 或授权码。
- 未执行真实店铺 OAuth、真实 Scope、真实 Token 刷新和平台后台撤销。
- 未执行 REAL-FS-03 的真实只读 Adapter、Webhook 或任何平台写操作。
- 未放行 DeepSeek、公开 AI 回复、AI 营销和自动回复。
- 未进行目标公网 TLS、Partner Center 回调配置、固定出口 IP 白名单和密钥轮换演练。

## 3. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统/终端 | Windows；PowerShell 7.6.4 |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Node.js/npm | Node.js 24.19.0、npm 11.17.0 |
| Docker/Compose | Docker 29.7.2、Docker Compose 5.3.1 |
| 后端 | FastAPI、SQLAlchemy Async、Alembic |
| 数据库 | 隔离 `postgres-test`，PostgreSQL 16 + pgvector，端口 5433 |
| 迁移基线 | `019_tiktok_channel_unique (head)` |
| 外部调用 | 官方文档只读核对；TikTok API 使用 MockTransport/假凭证，不访问真实店铺 |
| 代码库状态 | 当前目录不是 Git 仓库，无法提供提交哈希 |

本机 Node.js 为 24.19.0，与计划的 Node.js 20 LTS 基线不同；本轮 lint、类型检查、24 项测试和 Next.js 生产构建均通过，但目标部署仍应使用 Dockerfile 固定的 Node 20 镜像复验。

## 4. 缺陷复测汇总

| 缺陷 | 原优先级 | 本轮独立结果 | 状态 |
| --- | --- | --- | --- |
| `DEF-REAL-FS02-001`：通用渠道接口绕过 OAuth 创建 TikTok 渠道 | P1 | `ChannelCreate` 仅接受 Shopee/Amazon，Service 对内部构造的 TikTok 请求再次拒绝 | **关闭** |
| `DEF-REAL-FS02-002`：刷新接受变化的授权主体 | P1 | `open_id` 哈希、唯一授权店铺和 Scope 均重新校验；变化时旧密文不覆盖、渠道进入 `expired` 并审计 | **关闭** |
| `DEF-REAL-FS02-003`：Token 刷新没有运行入口 | P1 | Jobs Worker 启动即进入周期调度，生产 jobs 服务获得轮询/提前量/批量配置，单次失败不阻断后续渠道 | **关闭** |
| `DEF-REAL-FS02-004`：数据库允许同店铺多 TikTok 渠道 | P2 | 019 部分唯一索引生效；历史重复项使迁移非零失败并停留 018；双 Worker 只有一个取得行锁 | **关闭** |
| `DEF-REAL-FS02-005`：`return_to` 接受额外 query | P3 | 仅精确接受 `/settings/channels`，query、fragment、外部 URL 和其他路径均拒绝 | **关闭** |
| `DEF-REAL-FS02-006`：固定 OAuth 回调配置未失败关闭 | P2 | 生产 Settings 与 OAuth 运行校验接受 HTTP 外部回调声明 | **新增/Open** |

## 5. 测试执行结果

### 5.1 静态质量与专项测试

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check --offline` | 解析 125 个包 | 通过 |
| Ruff 检查 | `All checks passed` | 通过 |
| Ruff 格式 | 对 `app tests scripts migrations ../tests/integration` 共 214 个 Python 文件检查通过 | 通过 |
| mypy | 155 个源文件无类型错误 | 通过 |
| OAuth/真实配置专项 | 48 passed | 通过 |
| 五项缺陷定向服务测试 | 6 passed | 通过 |
| 数据库唯一性与行锁定向测试 | 2 passed | 通过 |

沙箱无法读取用户级 uv/pytest 临时目录，导致第一次 `uv` 缓存初始化和一次 pytest 会话清理非零退出；改用项目内隔离缓存与 `--basetemp` 后重跑成功。`ruff format --check .` 仍会因沙箱不可访问的缓存目录触发 Ruff panic，因此使用覆盖全部 214 个产品/测试 Python 文件的显式目录检查形成可信证据。该项记录为测试环境限制，不作为产品缺陷。

### 5.2 后端、数据库和迁移

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| 默认后端全量 | 560 passed、10 skipped、2 个既有弃用警告 | 通过 |
| 隔离 PostgreSQL 全量 | 573 passed、0 skipped、2 个既有弃用警告 | 通过 |
| 空库升级 | 001→019，最终 `019_tiktok_channel_unique (head)` | 通过 |
| 019 回滚 | 019→018 成功 | 通过 |
| 历史重复授权门禁 | 018 中构造同店铺 2 个 TikTok 渠道后，019 升级退出码 1，版本保持 018 | 通过 |
| 数据治理后恢复 | 精确删除探针店铺后 018→019 成功 | 通过 |
| 唯一索引 | 第二条同店铺 TikTok 渠道触发 `uq_channel_accounts_store_tiktok` | 通过 |
| 并发认领 | 两个独立数据库会话仅第一个认领即将过期渠道，第二个返回空 | 通过 |

既有两个警告为 Starlette TestClient/httpx 兼容弃用提示和 passlib 读取 argon2 版本弃用提示，本轮没有新增测试失败。

### 5.3 五项修复的独立行为验证

1. 使用 `ChannelCreate.model_validate` 提交 `platform=tiktok`，Schema 拒绝；使用 `model_construct` 绕过 Pydantic 后调用 Service，仍返回“TikTok 渠道必须通过 OAuth”。
2. 刷新返回不同 `open_id` 时，渠道进入 `expired`，`oauth_status=reauthorization_required`，旧 Access/Refresh Token 密文保持不变并写失败审计。
3. 刷新后授权店铺 ID 变化或店铺数量不为 1 时拒绝继续绑定。
4. `app.jobs.worker` 实际导入并周期调用 `process_tiktok_token_refresh_cycle`；Compose 的 `jobs` 命令为 `python -m app.jobs.worker`。
5. Jobs 默认注入刷新周期 300 秒、提前量 86400 秒、批量 20；所有真实读取、写入和 Mock 开关继续为 `false`。
6. `return_to` 仅允许精确 `/settings/channels`。

### 5.4 API、前端、Compose 和安全

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| OpenAPI | start/callback 均仅注册 GET | 通过 |
| 未认证访问 | 两个 OAuth 端点均返回 HTTP 401 / `40101` | 通过 |
| 前端 lint/typecheck | 通过 | 通过 |
| 前端自动化 | 24 passed | 通过 |
| Next.js 生产构建 | 14 个静态页面生成成功 | 通过 |
| TikTok 页面 | 仅调用服务端 OAuth，页面不读取或保存 Token | 通过 |
| 生产 Compose | 8 个服务解析；jobs 获得刷新配置；真实写入和 Mock 均关闭 | 通过 |
| Python 依赖审计 | 124 个锁定包无已知漏洞和不良状态 | 通过 |
| 生产源码凭据扫描 | 扫描 190 个生产文本文件，高风险 Token/Key 字面量 0 | 通过 |
| 日志 | OAuth query 探针只产生统一脱敏事件，不输出 code/state | 通过 |

### 5.5 官方契约复核

- Seller 授权入口继续使用 US/ROW 的 `services.*.tiktokshop.com/open/authorize`，并携带不可预测 `state`。
- callback 参数使用 `code`，交换 Token 时映射为 `auth_code`，`grant_type=authorized_code`。
- Token 刷新使用 `/api/v2/token/refresh` 和 `grant_type=refresh_token`。
- Token 过期字段按 Unix 时间戳处理；刷新后重新校验 `user_type`、`open_id`、Scope 和授权店铺。
- Get Authorized Shops 使用 `/authorization/202309/shops`、HMAC-SHA256 签名及 `x-tts-access-token` Header。
- 019 的“一个内部店铺绑定一个 TikTok 渠道”符合项目选择的单店铺连接模型。

## 6. 新增缺陷

### DEF-REAL-FS02-006：OAuth 运行配置未强制固定 HTTPS 回调地址

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 类型 | 生产配置、安全门禁、部署一致性 |
| 影响范围 | TikTok OAuth start、Partner Center 回调配置、生产验收 G1 |
| 是否阻断 | 阻断 REAL-FS-02 和真实店铺 OAuth 放行 |
| 建议负责 Agent | 全栈开发工程师Agent；架构师Agent评审 |
| 状态 | Open |

复现步骤：

1. 以无价值哨兵构造 `APP_ENV=production` 的 `Settings`，满足数据库、JWT、Cookie、CORS、固定出口 IP、TikTok App Key、Service ID、App Secret 和凭证加密密钥要求。
2. 将 `TIKTOK_OAUTH_REDIRECT_URI` 设置为 `http://attacker.example/callback`，所有 `REAL_TIKTOK_*` 开关保持 `false`。
3. 创建 Settings 后调用 `validate_oauth_runtime(settings)`。
4. 搜索该配置项的运行引用。

实际结果：Settings 构造和 OAuth 运行校验均成功，探针输出 `unsafe_oauth_redirect_runtime_accepted=true`。该字段只在 OAuth 服务中检查非空；生产 HTTPS 校验位于 `_validate_real_tiktok_prerequisites`，而当前所有真实业务开关必须为 `false`，因此 OAuth 已可使用时不会触发该校验。字段没有参与授权 URL 构造或 callback 路由一致性检查。

预期结果：

- production/staging/integration 的 OAuth 启动前必须校验回调为 HTTPS，且与架构固定值 `https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback` 完全一致；或由受控 `PUBLIC_BASE_URL + 固定路径` 唯一推导。
- TikTok Partner Center 的实际 Redirect URL 必须作为外部部署门禁核对，不能只依赖未使用的环境变量。
- 增加 HTTP、外部主机、错误路径、query、fragment 和正确固定地址的配置测试。
- 错误配置必须在 OAuth start 前失败关闭，不得进入用户授权跳转。

说明：TikTok 实际重定向目标由 Partner Center 配置决定，本缺陷不是当前应用中的直接开放重定向；风险在于应用接受并展示一个不受执行链路约束的回调声明，无法发现目标环境的错误或恶意配置漂移。

## 7. 验收结论与后续门禁

- `DEF-REAL-FS02-001～005` 全部关闭。
- `DEF-REAL-FS02-006` 为 P2/Open，REAL-FS-02 整体仍不通过。
- 修复 006 后必须生成第三次独立综合测试报告，不覆盖 001/002 历史报告。
- 第三次复测至少覆盖固定 HTTPS 回调、错误主机/路径/query/fragment、生产 Settings、OAuth start 失败关闭以及现有 48 项专项和迁移回归。
- 工程缺陷关闭后，仍必须在目标 HTTPS 环境由用户安全注入真实凭证，完成真实店铺授权、真实 Scope、Get Authorized Shops、Token 刷新、过期识别和平台侧撤销。
- 在真实门禁通过前，REAL-FS-03、真实平台写操作、公开 AI 回复、AI 营销和自动回复继续禁止放行。
- 当前项目其他生产门禁和缺陷状态以各自最新权威报告为准，本报告不替代 REAL-FS-01、REAL-AI-01 或最终架构验收。

## 8. 执行证据与清理

主要命令和方法：

```text
uv lock --check --offline
ruff check .
ruff format --check app tests scripts migrations ../tests/integration
mypy app scripts
pytest tests/test_tiktok_oauth.py tests/test_real_runtime_config.py -q
pytest -q --basetemp=<项目内隔离目录>
隔离 PostgreSQL：alembic upgrade head / downgrade 018_ai_observability / upgrade head
隔离 PostgreSQL：历史重复授权失败关闭探针、唯一索引探针、双会话 SKIP LOCKED
npm run lint
npm run typecheck
npm run test
npm run build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml config --services
uv audit --locked
OpenAPI 路由和未认证 401/40101 探针
不读取 .env 的生产源码高风险凭据字面量扫描
生产 OAuth 回调错误配置独立负向探针
```

清理说明：数据库探针只操作隔离 `postgres-test`，历史重复项在恢复迁移前已精确删除；其他唯一性写入在事务中回滚。临时 Python 探针、项目内 pytest/uv 测试缓存和 `postgres-test` 容器均已删除。测试工程师仅新增本报告并更新测试报告索引，没有修改产品代码。
