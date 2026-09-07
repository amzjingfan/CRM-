# TikTok OAuth 授权与凭证生命周期第三次综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-02 |
| 模块编号 | M00 |
| 模块名称 | TikTok OAuth 授权与凭证生命周期 |
| 被测主责 Agent | 全栈开发工程师Agent |
| 被测协作 Agent | 架构师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTokOAuth固定回调缺陷修复-009.md` |
| 前序报告 | `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTokOAuth授权与凭证生命周期-综合测试-002.md` |
| 测试类型 | 综合测试、修复验证、接口测试、集成测试、安全测试、回归测试、配置测试 |
| 执行日期 | 2026-08-26 |
| 测试结论 | **有条件通过当前工程范围** |

## 2. 测试依据、目标与边界

### 2.1 测试依据

- `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-02。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- `共享记忆文档/智能客服平台 — 管理端接口文档.md`。
- `共享记忆文档/开发任务拆解（按人天分配）.md`。
- `共享记忆文档/MVP范围与验收标准.md`。
- `共享记忆文档/项目团队职责说明.md`、`共享记忆文档/代码编写手册.md`。
- 项目全部适用 `AGENTS.md`、测试报告命名规范及测试报告索引。
- 前序 001、002 号正式报告及本轮 009 号修复实施记录。

官方契约链接：

- [TikTok Shop Authorization overview](https://partner.tiktokshop.com/docv2/page/authorization-overview-202407)
- [TikTok Shop Connecting shops](https://partner.tiktokshop.com/docv2/page/connecting-shops)
- [TikTok Shop Sign your API request](https://partner.tiktokshop.com/docv2/page/sign-your-api-request)
- [TikTok Shop Get Authorized Shops](https://partner.tiktokshop.com/docv2/page/get-authorized-shops)

TikTok 官方页面当前为 JavaScript 动态站点，命令行只读访问未返回正文。本轮未把无法读取的页面内容作为新增事实；OAuth、Token、签名和授权店铺契约沿用 002 号报告已核验基线。本轮产品变更只涉及固定 callback 配置门禁，平台客户端协议代码未发生契约变更。

### 2.2 本轮目标

1. 独立复测 `DEF-REAL-FS02-006`，确认真实环境只接受固定 HTTPS callback。
2. 验证 HTTP、外部主机、错误路径、query、fragment 及等价 URL 变体均失败关闭。
3. 验证即使绕过 Pydantic Settings 构造，OAuth 运行入口仍在创建 Redis state、查询店铺或交换 Token 前拒绝错误配置。
4. 回归 `DEF-REAL-FS02-001～005`、OAuth 生命周期、数据库唯一约束、并发认领、迁移、前后端及生产 Compose。
5. 明确当前工程通过范围与真实店铺联调、生产放行之间的边界。

### 2.3 未执行范围

- 未读取或输出项目 `.env` 的真实值。
- 未使用真实 TikTok App Secret、OAuth Code、Access Token、Refresh Token 或真实店铺数据。
- 未执行真实店铺授权、真实 Scope、真实 Get Authorized Shops、真实 Token 刷新和平台侧撤销。
- 未登录或修改 TikTok Partner Center，未核对其后台 Redirect URL 实际值。
- 未实施或放行 REAL-FS-03 真实只读 Adapter、Webhook、平台写操作、公开 AI 回复、AI 营销或自动回复。
- 未把本报告作为 REAL-FS-01、REAL-AI-01 或最终生产架构验收的替代结论。

## 3. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统/终端 | Windows；PowerShell 7.6.4 |
| Python | 3.11.15 |
| uv | 项目锁文件解析 125 个包 |
| Node.js/npm | Node.js 24.19.0、npm 11.17.0 |
| Docker/Compose | Docker 29.7.2、Docker Compose 5.3.1 |
| 后端 | FastAPI、SQLAlchemy Async、Alembic |
| 数据库 | 隔离 `postgres-test`，PostgreSQL 16 + pgvector，端口 5433，tmpfs |
| 迁移基线 | `019_tiktok_channel_unique (head)` |
| 外部调用 | TikTok 使用 MockTransport/假凭证；依赖审计访问 OSV 与 npm 官方端点 |
| 代码库状态 | 当前目录不是 Git 仓库，无法提供提交哈希或不可变构建版本 |

本机 Node.js 24.19.0 与计划的 Node.js 20 LTS 基线不同。本轮 lint、类型检查、24 项前端测试和 Next.js 生产构建通过；目标部署仍需使用固定 Node 20 生产镜像复验。

## 4. 缺陷复测结论

| 缺陷 | 原优先级 | 本轮独立结果 | 状态 |
| --- | --- | --- | --- |
| `DEF-REAL-FS02-001`：通用渠道接口绕过 OAuth 创建 TikTok 渠道 | P1 | Schema 与 Service 双层拒绝路径回归通过 | **保持关闭** |
| `DEF-REAL-FS02-002`：刷新接受变化的授权主体 | P1 | `open_id`、授权店铺及 Scope 重新校验回归通过 | **保持关闭** |
| `DEF-REAL-FS02-003`：Token 刷新没有运行入口 | P1 | Jobs 周期入口、批量认领和单项失败隔离回归通过 | **保持关闭** |
| `DEF-REAL-FS02-004`：数据库允许同店铺多 TikTok 渠道 | P2 | 019 唯一约束和双会话 `SKIP LOCKED` 独立数据库测试通过 | **保持关闭** |
| `DEF-REAL-FS02-005`：`return_to` 接受额外 query | P3 | 仅精确接受 `/settings/channels`，额外 query/fragment/外部 URL 继续拒绝 | **保持关闭** |
| `DEF-REAL-FS02-006`：固定 OAuth 回调配置未失败关闭 | P2 | Settings、运行校验、实际路由和 start 前失败关闭均通过 | **关闭** |

本轮未发现新的 REAL-FS-02 范围 P0、P1、P2 或 P3 缺陷。

## 5. `DEF-REAL-FS02-006` 独立复测

### 5.1 配置启动门禁

对 `integration`、`staging`、`production` 三类真实环境分别执行以下回调变体：

| 回调变体 | 预期 | 实际 |
| --- | --- | --- |
| HTTP | Settings 构造失败 | 通过 |
| 外部攻击者主机 | Settings 构造失败 | 通过 |
| 错误路径 | Settings 构造失败 | 通过 |
| query 参数 | Settings 构造失败 | 通过 |
| fragment | Settings 构造失败 | 通过 |
| 显式 `:443` | 因非逐字固定值而失败 | 通过 |
| 尾斜杠 | 因非逐字固定值而失败 | 通过 |
| URL 内嵌凭证 | 失败 | 通过 |
| 固定地址 | 构造成功 | 通过 |

唯一接受值为：

```text
https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback
```

独立临时探针共 **28 passed**。探针执行后已删除，未写入产品测试套件或修改产品代码。

### 5.2 纵深防御

使用 `model_copy(update=...)` 模拟绕过 Pydantic 启动校验，将已构造 Settings 的环境改为 production，并注入外部攻击者 callback。调用 `validate_oauth_runtime()` 后：

- 返回稳定低敏 `503` 业务错误。
- 错误消息不回显攻击者主机或错误 URI。
- OAuth start 在店铺权限查询和 Redis state 写入前停止。
- callback 在消费 state、交换 Token 前同样执行运行校验。

结果符合失败关闭要求。

### 5.3 路由与部署一致性

- FastAPI callback 装饰器使用共享常量 `TIKTOK_OAUTH_CALLBACK_ROUTE`。
- 固定公开地址由 `/v1` 与实际 callback 路径共同构造。
- 生产 Compose 将 `TIKTOK_OAUTH_REDIRECT_URI` 设为必填。
- 合并后的生产 Compose 中 backend、worker、jobs 均获得固定 callback 声明。
- 应用仍不能读取 TikTok Partner Center 后台配置，因此发布人员必须人工逐字核对外部 Redirect URL；该外部门禁不能由代码测试替代。

## 6. 自动化与工程回归结果

### 6.1 后端静态质量和专项测试

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check --offline` | 解析 125 个包 | 通过 |
| Ruff 检查 | `All checks passed` | 通过 |
| Ruff 格式 | 214 个 Python 文件已格式化 | 通过 |
| mypy | 155 个源文件无类型错误 | 通过 |
| OAuth/真实配置专项 | 84 passed | 通过 |
| 第三轮独立 callback 探针 | 28 passed | 通过 |
| 默认后端全量 | 618 passed、10 skipped、2 个既有弃用警告 | 通过 |

两个既有警告分别来自 Starlette TestClient/httpx 兼容弃用提示和 passlib 读取 argon2 版本的弃用提示，本轮未产生新的运行失败。

### 6.2 PostgreSQL、迁移和并发

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| 空库升级 | 001→019，最终 `019_tiktok_channel_unique (head)` | 通过 |
| 019 回滚 | 019→018 成功 | 通过 |
| 恢复 head | 018→019 成功 | 通过 |
| 隔离 PostgreSQL 全量 | 628 passed、0 skipped、2 个既有弃用警告 | 通过 |
| TikTok OAuth 数据库专项 | 2 passed | 通过 |
| 同店铺 TikTok 唯一约束 | 第二条记录被数据库拒绝 | 通过 |
| Token 刷新并发认领 | 双会话中只有一个获得到期渠道 | 通过 |

第一次单独运行数据库专项时未显式指定 backend 的 pytest 配置，导致测试根目录选择错误并出现 `ModuleNotFoundError: app`；使用 `-c pyproject.toml` 按项目正式配置重跑后 2 项全部通过。该失败属于测试命令上下文，不是产品缺陷。

### 6.3 前端、接口与生产 Compose

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| 前端 lint | 通过 | 通过 |
| 前端 typecheck | 通过 | 通过 |
| 前端自动化 | 24 passed | 通过 |
| Next.js 生产构建 | 14 个静态页面生成成功 | 通过 |
| TikTok 渠道页面 | 仅调用服务端 OAuth，不读取/保存 Token，只展示低敏状态 | 通过 |
| OpenAPI | start/callback 均仅注册 GET | 通过 |
| 未认证访问 | 两个 OAuth 端点均返回 HTTP 401 / `40101` | 通过 |
| 生产 Compose 解析 | 8 个服务；固定 callback 生效 | 通过 |
| 真实平台开关 | 只读、Webhook、普通写入、高风险写入全部为 false | 通过 |
| Mock 开关 | `ALLOW_MOCK_PLATFORM_ADAPTERS=false` | 通过 |

### 6.4 安全与依赖

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| Python 锁定依赖审计 | 124 个包无已知漏洞或不良状态 | 通过 |
| 生产源码高风险凭据字面量扫描 | 171 个生产文本文件，命中 0 | 通过 |
| 前端生产依赖审计 | 3 个 High | **项目既有阻断** |

前端审计发现的 PostCSS 与 sharp/Next.js 依赖链 3 个 High 已由 `DEF-REAL-FS01-005` 跟踪，不是本轮 OAuth 修复引入的新缺陷，也不在本报告中重复编号。该缺陷仍阻断整体生产环境放行。

API 探针日志仍将普通 httpx 请求日志折叠为 `unstructured_log_redacted`，与已登记的 `DEF-REAL-FS01-006` 一致。本报告不重复建缺陷，但在该问题关闭前，生产可观测性验收仍未完成。

## 7. OAuth 生命周期回归摘要

本轮专项与全量测试继续覆盖：

1. `settings.channels` 权限和店铺范围校验。
2. 高熵 state、Redis TTL、哈希键和一次性原子消费。
3. 缺失、过期、重复及用户不匹配 state。
4. `code` 到 `auth_code` 的 Token 交换映射及平台错误低敏转换。
5. seller 用户类型、必需 Scope、唯一授权店铺和跨租户绑定拒绝。
6. Access/Refresh Token 仅以加密密文保存，前端和 API 不返回明文。
7. Token 刷新重新校验 `open_id`、Scope 和外部店铺；主体变化时保留旧密文并要求重新授权。
8. Jobs 周期刷新、批量认领、单项失败隔离和提前刷新配置。
9. 撤销后渠道保留审计证据、销毁本地 Token 并进入 disconnected/revoked 状态。
10. 同一内部店铺只能绑定一个 TikTok 渠道；并发刷新使用行锁避免重复处理。

上述行为在本轮无退化。

## 8. 验收结论与后续门禁

### 8.1 本轮正式结论

- `DEF-REAL-FS02-006` 已关闭。
- `DEF-REAL-FS02-001～005` 保持关闭。
- REAL-FS-02 的代码、配置、数据库、前端和自动化测试范围 **有条件通过**。
- 允许进入“真实店铺受控 OAuth 联调申请”，但本报告不等于真实 OAuth 成功或生产放行。

### 8.2 真实店铺联调前必须完成

1. 在目标 HTTPS integration 环境安全注入真实 TikTok App Key、Service ID、App Secret 和凭证加密密钥。
2. 在 TikTok Partner Center 将 Redirect URL 逐字配置为固定地址，并核对应用实际 callback 可公网访问。
3. 使用一个真实店铺完成授权，核对实际 Scope、seller 主体、唯一店铺及 Get Authorized Shops 返回。
4. 执行真实 Token 刷新、过期识别和平台侧撤销，确认本地状态同步。
5. 关闭 `DEF-REAL-FS01-005/006` 或由架构师明确限制性处置；生产发布不得绕过安全和可观测性门禁。
6. 真实联调期间所有 REAL-FS-03、Webhook、普通写入、高风险写入、AI 公开回复、营销和自动回复开关继续保持 false。

### 8.3 停止条件

出现以下任一情况，应立即停止真实联调并撤销/轮换对应凭证：

- Partner Center Redirect URL 与固定地址不一致。
- Scope、seller 主体或授权店铺数量不符合预期。
- Token 无法加密保存、刷新主体发生变化或撤销后仍可使用。
- 日志、响应、前端或测试证据出现 OAuth Code、Token、App Secret 或完整客户隐私。
- 数据库出现跨租户绑定、重复 TikTok 渠道或并发刷新重复执行。

## 9. 执行证据与清理

主要命令：

```text
uv lock --check --offline
uv run ruff check app tests scripts migrations ../tests/integration
uv run ruff format --check app tests scripts migrations ../tests/integration
uv run mypy app scripts
uv run pytest tests/test_tiktok_oauth.py tests/test_real_runtime_config.py -q
uv run pytest -q
uv run alembic upgrade head
uv run alembic downgrade 018_ai_observability
uv run alembic upgrade head
TEST_DATABASE_URL=<隔离测试库> uv run pytest -q
uv run pytest -c pyproject.toml ../tests/integration/test_tiktok_oauth_postgres.py -q
npm run lint
npm run typecheck
npm run test
npm run build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml config --services
uv audit --locked
npm audit --omit=dev --audit-level=high --registry=https://registry.npmjs.org
OpenAPI GET-only 与未认证 401/40101 探针
不读取 .env 的生产源码高风险凭据字面量扫描
```

清理结果：

- 本轮创建的 `postgres-test` 使用 tmpfs，已停止并删除。
- 第三轮独立 callback 临时测试文件已删除。
- 项目内本轮 pytest、uv 和 npm 临时缓存已删除。
- 测试工程师未修改产品代码、数据库迁移或历史 001/002 报告。
- 本轮正式变更仅为新增本报告并更新 `共享记忆文档/测试报告索引.md`。
