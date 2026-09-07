# TikTok 只读 API 与 Webhook 综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-03 |
| 模块编号 | M00 |
| 模块名称 | TikTok 只读 API 与 Webhook |
| 被测主责 Agent | 全栈开发工程师Agent |
| 被测协作 Agent | 架构师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTok只读API与Webhook-010.md` |
| 前序报告 | 无，本报告为 REAL-FS-03 首次独立综合测试 |
| 测试类型 | 综合测试、契约测试、接口测试、集成测试、安全测试、数据库测试、回归测试、运行态检查 |
| 执行日期 | 2026-08-31 |
| 测试结论 | **不通过；1 个 P1、1 个 P2 未关闭，真实店铺联调门禁未执行** |

## 2. 测试依据、目标与边界

### 2.1 测试依据

- `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-03。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- `架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`。
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- `共享记忆文档/智能客服平台 — 管理端接口文档.md`。
- `共享记忆文档/开发任务拆解（按人天分配）.md`。
- `共享记忆文档/MVP范围与验收标准.md`。
- `共享记忆文档/项目团队职责说明.md`、`共享记忆文档/代码编写手册.md`。
- 项目全部适用 `AGENTS.md`、测试报告命名规范和测试报告索引。
- REAL-FS-01、REAL-FS-02 既有正式测试结论和本阶段 010 号实施记录。

本轮核对的官方契约：

- [TikTok Shop API 请求签名](https://partner.tiktokshop.com/docv2/page/sign-your-api-request)
- [TikTok Shop Webhook 概览与验签](https://partner.tiktokshop.com/docv2/page/tts-webhooks-overview)
- [Get Order Detail 202507](https://partner.tiktokshop.com/docv2/page/get-order-detail-202507)
- [Get Conversations 202309](https://partner.tiktokshop.com/docv2/page/get-conversations-202309)
- [Get Conversation Messages 202309](https://partner.tiktokshop.com/docv2/page/get-conversation-messages-202309)
- [Get Logistics Tracking 202604](https://partner.tiktokshop.com/docv2/page/get-logistics-tracking-202604)
- [物流 202604 升级公告](https://partner.tiktokshop.com/docv2/page/8syhoy40)
- [TikTok Shop API 版本规则](https://partner.tiktokshop.com/docv2/page/api-versioning)

官方物流升级公告发布于 2026-05-13，并要求自 2026-06-30 起使用 `202604` 或更高版本访问新增跨境首公里物流数据。本轮执行日期为 2026-08-31，因此不能继续把仓库内较旧的 `202309` OAS 快照作为唯一权威契约。

### 2.2 测试目标

1. 验证真实 TikTok 只读客户端的域名、路径、版本、签名、Token Header、Scope、DTO 和稳定错误映射。
2. 验证店铺、订单、物流、会话、消息和 Webhook 订阅只读能力不包含平台写操作。
3. 验证真实 Webhook 的原始正文验签、1 MiB 限制、事件落库、幂等、异步 Worker、失败重试和授权生命周期。
4. 验证既有 Phase 1～4 后端、前端、迁移和 Compose 无回归。
5. 明确确定性工程测试与真实店铺、真实平台回调之间的边界。

### 2.3 未执行范围

- 未读取、打印或导出 `.env` 中的 App Secret、Access Token、Refresh Token、OAuth Code 或凭证密文。
- 未调用真实 TikTok Shop API；运行环境中 `REAL_TIKTOK_READ_ENABLED=false`。
- 未接收真实 TikTok Webhook；运行环境中 `REAL_TIKTOK_WEBHOOK_ENABLED=false`。
- 未登录或修改 TikTok Partner Center，未修改真实应用的 Scope、Webhook 或 IP 白名单。
- 未执行人工消息、发券、修改地址、营销或自动回复；普通写入和高风险写入开关均为 `false`。
- 未把 MockTransport、单元测试或本报告视为真实店铺联调成功证据。
- 未替代 REAL-FS-01、REAL-FS-02、REAL-AI 或架构师最终生产放行结论。

## 3. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统/终端 | Windows；PowerShell 7.6.4 |
| Python | 3.11.15 |
| uv | 0.12.3；锁文件解析 125 个包 |
| Node.js/npm | Node.js 24.19.0、npm 11.17.0 |
| Docker/Compose | Docker 29.7.2；独立 `docker-compose` 5.3.1 |
| 后端 | FastAPI、SQLAlchemy Async、Alembic |
| 数据库 | PostgreSQL 16 + pgvector；隔离 `postgres-test` 使用 5433/tmpfs |
| 迁移基线 | `019_tiktok_channel_unique (head)` |
| 运行服务 | backend、frontend、postgres、redis、minio、worker、jobs 共 7 个服务运行 |
| TikTok 运行开关 | 真实只读、真实 Webhook、普通写入、高风险写入和 Mock 均为 `false` |
| 渠道数据 | 数据库存在 1 条 connected TikTok 渠道记录；未读取其凭证或客户数据 |
| 外部调用 | 契约测试使用假凭证与 `httpx.MockTransport`；未调用真实 TikTok API |
| 代码库状态 | 当前目录不是 Git 仓库，无法提供提交哈希或不可变构建版本 |

Node.js 24.19.0 与计划中的 Node.js 20 LTS 不一致，但本轮前端 lint、类型检查、29 项测试和生产构建均通过。目标生产镜像仍应按固定 Node 20 基线复验。

## 4. 总体结果

| 测试域 | 结果 | 结论 |
| --- | --- | --- |
| API 签名、Token Header、固定域名 | 现有自动化通过 | 通过 |
| 店铺、订单、会话、消息、Webhook 订阅读取 | 现有契约测试通过 | 通过 |
| 物流读取 | 使用旧 `fulfillment/202309` 且缺少 `seller.logistics` 门禁 | **失败** |
| 平台错误重试 | 未识别的稳定业务错误被重试 2 次 | **失败** |
| Webhook 原始正文 HMAC | 正确签名、正文变化和旧 Mock Header 的确定性测试通过 | 通过 |
| Webhook 1 MiB 限制 | 运行态超大正文返回 413 | 通过 |
| Webhook 幂等、标准化和生命周期 | 消息、订单、授权到期、撤销和未知事件测试通过 | 通过 |
| Worker、失败保留和重试 | 既有专项及全量回归通过 | 通过 |
| 数据库和迁移 | 001→019、019→018→019、隔离 PostgreSQL 全量通过 | 通过 |
| 前后端回归 | 后端 772/782、前端 29 项及构建通过 | 通过 |
| 真实店铺只读冒烟 | 真实开关关闭，未发起调用 | **未执行** |
| 真实 Webhook 投递 | 真实开关关闭，未接收平台回调 | **未执行** |

本阶段确定性工程主体无大范围回归，但 REAL-FS-03 的物流验收项存在 P1 阻断，且真实平台门禁尚无执行证据，因此总体结论为不通过。

## 5. 缺陷清单

| 缺陷编号 | 优先级 | 缺陷摘要 | 状态 | 是否阻断 REAL-FS-03 |
| --- | --- | --- | --- | --- |
| `DEF-REAL-FS03-001` | P1 | 物流读取未实现当前 202604 契约且未强制 `seller.logistics` Scope | Open | 是 |
| `DEF-REAL-FS03-002` | P2 | 稳定平台业务错误被当作瞬时错误重复请求 | Open | 是 |

### 5.1 DEF-REAL-FS03-001：物流读取版本和 Scope 不符合当前官方契约

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 平台契约、权限、安全失败关闭、真实联调阻断 |
| 影响范围 | TikTok 物流查询、真实店铺 Scope、客服工作台查物流、REAL-FS-03 只读冒烟 |
| 是否阻断 | 是 |
| 建议负责 Agent | 全栈开发工程师Agent；架构师Agent评审版本迁移边界 |

复现步骤：

1. 打开 `backend/app/integrations/tiktok_read.py` 的 `get_tracking()`。
2. 可见请求路径固定为 `/fulfillment/202309/orders/{order_id}/tracking`，返回值按 `data.tracking[]` 解析。
3. 该方法调用前没有执行 `_require_scope("seller.logistics")`。
4. 打开 `.env.example` 与 REAL-FS-03 测试配置，可见必需 Scope 只有授权、订单和客服，不包含 `seller.logistics`。
5. 执行独立契约探针；预期路径为 `/logistics/202604/orders/{order_id}/tracking`，实际仍为旧路径；移除 `seller.logistics` 后，客户端仍向平台发起 HTTP 请求而没有在本地失败关闭。

实际结果：

- 物流读取仍调用 `fulfillment/202309`。
- 未解析 202604 的 `data.logistics_details[]`、多包裹和 `track_list[]` 结构。
- 缺少 `seller.logistics` 时不会在发出平台请求前返回稳定权限错误。
- OAuth/部署最小 Scope 未保证物流权限，真实店铺即使完成授权也不能证明物流能力可用。

预期结果：

- 采用当前适用的 `/logistics/202604/orders/{order_id}/tracking` 契约。
- 增加 202604 DTO 与统一内部物流模型，正确处理多包裹、承运商和轨迹列表。
- 在客户端、OAuth 必需 Scope、`.env.example`、接口文档和联调清单中统一加入 `seller.logistics`。
- 缺少 Scope 时请求前失败关闭，不消耗平台配额。
- 已授权真实店铺若缺少新增 Scope，应明确要求重新授权，不得把 403 伪装成物流为空。

修复验收：

1. 增加 202604 官方样例、空轨迹、多包裹、字段漂移和缺少 Scope 的确定性测试。
2. 旧 202309 兼容仅可作为架构师批准的显式降级策略，不能作为默认当前契约。
3. 使用真实店铺完成授权 Scope 核对和一笔可追踪订单的只读冒烟。
4. 全程保持普通写入、高风险写入、营销和自动回复关闭。

### 5.2 DEF-REAL-FS03-002：稳定平台业务错误被重复请求

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 类型 | 可靠性、限流配额、错误语义 |
| 影响范围 | TikTok 全部只读 API、请求时延、平台配额和问题诊断 |
| 是否阻断 | 是，需在真实平台灰度前关闭 |
| 建议负责 Agent | 全栈开发工程师Agent |

复现步骤：

1. 使用 `MockTransport` 返回 HTTP 200、平台 Envelope `code=123456` 的稳定业务错误。
2. 调用 `get_order_details()`。
3. 统计平台请求次数。

实际结果：平台请求执行 2 次，日志同样记录 2 次失败。

代码原因：`TikTokReadClient._request()` 对所有不属于少数 Token/权限集合的非零平台错误码统一进入第二次尝试，未区分稳定业务错误和瞬时错误。

预期结果：

- 仅网络异常、HTTP 5xx 和 HTTP 429 进入有限重试。
- Token、权限、参数、资源归属和其他稳定业务错误只请求一次，并映射稳定低敏错误码。
- 429 应尊重可用的重试提示并采用有界退避。
- 查询重试应记录一次逻辑调用及每次尝试，但不得把业务失败伪装成服务暂不可用。

修复验收：增加瞬时错误与稳定错误分类测试，分别断言请求次数、最终错误码、日志次数和 `provider_request_id` 低敏记录。

## 6. 契约与安全测试明细

### 6.1 TikTok 只读 API

| 场景 | 预期 | 实际 |
| --- | --- | --- |
| 固定官方域名 | 调用方不能注入任意 URL | 通过 |
| API 签名 | 路径、排序后 query、App Secret 和精确正文参与 HMAC-SHA256 | 通过 |
| Access Token | 仅在 `x-tts-access-token` Header，签名 query 不含 Token | 通过 |
| POST 订单搜索 | 紧凑 JSON 正文与签名正文完全一致 | 通过 |
| 订单详情 | 使用 `/order/202507/orders`，逗号分隔订单 ID | 通过 |
| 店铺读取 | `/seller/202309/shops` 不附加 `shop_cipher` | 通过 |
| 会话读取 | `seller.customer_service` 前置校验，GET 且不改未读 | 通过 |
| 消息读取 | GET，只读，不调用 Read Message | 通过 |
| Webhook 订阅读取 | GET，不创建、更新或删除订阅 | 通过 |
| 物流读取 | 当前 202604 路径、DTO 和 Scope | **失败，见 DEF-REAL-FS03-001** |
| 429/401/403 | 映射稳定限流、过期和权限错误 | 通过 |
| 稳定业务错误 | 不重试 | **失败，见 DEF-REAL-FS03-002** |
| 敏感日志 | 不记录 Token、Secret、正文和平台原始消息 | 代码审查及测试通过 |

### 6.2 Webhook

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 官方 `Authorization` HMAC | App Key + 原始正文，以 App Secret 计算 SHA-256 | 通过 |
| 正文被修改 | 验签失败 | 通过 |
| 旧 Mock Header | 真实模式拒绝 | 通过 |
| 超过 1 MiB | 运行态返回 413 | 通过 |
| 事件 ID | 优先 `tts_notification_id`，缺失时使用稳定正文摘要 | 通过 |
| 重复投递 | 数据库幂等并返回 duplicate 语义 | 通过 |
| 新消息 type 14 | 只接收可见 BUYER 文本并标准化 | 通过 |
| 订单状态 type 1 | 通过只读订单详情补全并标准化 | 通过 |
| 授权即将到期 type 7 | 生成生命周期事件 | 通过 |
| 撤销授权 type 6 | 销毁本地 Token、禁用渠道并保留审计 | 通过 |
| 未知事件 | 不写业务实体，保留可追踪失败状态 | 通过 |
| Worker | 异步认领、失败保留、有限重试和事件状态更新 | 通过 |

TikTok 官方明确建议不要只依赖 Webhook，应通过计划任务与 API 对关键业务数据进行对账。本轮实现已有读取客户端和 Worker，但尚未提供真实平台上的漏投对账证据；该项列入真实联调门禁，不在本报告中另建代码缺陷。

## 7. 自动化、迁移与运行态结果

### 7.1 后端

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check --offline` | 解析 125 个包 | 通过 |
| `ruff check .` | `All checks passed` | 通过 |
| Ruff 格式（源代码目录） | app/tests/scripts/migrations 共 215 个文件已格式化 | 通过 |
| `mypy app scripts` | 160 个源文件无类型错误 | 通过 |
| REAL-FS-03 聚焦回归 | 91 passed、1 个既有弃用警告 | 通过 |
| 默认后端全量 | 772 passed、10 skipped、2 个既有弃用警告 | 通过 |
| 独立当前契约探针 | 3 failed；均稳定复现本报告两个缺陷 | **发现缺陷** |

`ruff format --check .` 在扫描项目根级历史测试临时目录时触发 Ruff 内部 `Expected a ruff source file` 崩溃；对全部正式 Python 源目录执行同一格式检查通过。独立探针执行后已删除，未修改产品代码或正式测试套件。

### 7.2 PostgreSQL 与迁移

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| 空库升级 | 001→019 成功 | 通过 |
| 019 回滚 | 019→018 成功 | 通过 |
| 恢复 head | 018→019 成功，最终 `019_tiktok_channel_unique (head)` | 通过 |
| 隔离 PostgreSQL 全量 | 782 passed、0 skipped、2 个既有弃用警告 | 通过 |
| 测试库清理 | 精确停止并删除 `postgres-test`；未触碰开发数据库 | 通过 |

第一次迁移回滚命令误用了不存在的修订名 `018_production_ai_runtime`，Alembic 正确拒绝；按迁移文件实际修订 `018_ai_observability` 重跑后回滚与恢复均成功。该现象属于测试命令更正，不是产品缺陷。

### 7.3 前端、Compose 与运行态

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| 前端 lint | 通过 | 通过 |
| 前端 typecheck | 通过 | 通过 |
| 前端自动化 | 29 passed | 通过 |
| Next.js 生产构建 | 14 个静态页面生成成功 | 通过 |
| Compose 配置 | 独立 `docker-compose` 可解析 7 个服务 | 通过 |
| 服务状态 | backend/frontend/postgres/redis/minio 健康；worker/jobs 运行 | 通过 |
| `/v1/health` | HTTP 200，版本 0.1.0 | 通过 |
| `/v1/health/ready` | HTTP 200；数据库、Redis、对象存储均为 ok | 通过 |
| Webhook 超大正文 | HTTP 413 | 通过 |
| 非法签名运行态 | HTTP 503，因为真实 Webhook 开关关闭，未进入验签分支 | 未执行真实模式 |
| 真实读/Webhook 开关 | 均为 false | 符合未放行状态 |
| 平台写入开关 | 普通写入和高风险写入均为 false | 通过 |

当前 Docker CLI 未安装 `docker compose` 插件命令，但独立 `docker-compose` 5.3.1 可正常解析和管理项目。生产基线应统一 Compose 调用方式，避免部署脚本与目标主机不一致。

### 7.4 依赖审计限制

`uv audit --locked` 已解析锁文件，但访问漏洞数据库时持续重试，未在本轮窗口内得到完整审计结论。因此本报告不宣称 Python 依赖审计通过，也不覆盖既有 REAL-FS-01 生产依赖门禁。

## 8. 真实店铺联调状态

只读检查确认数据库存在 1 条 connected TikTok 渠道记录，但运行容器中：

```text
REAL_TIKTOK_READ_ENABLED=false
REAL_TIKTOK_WEBHOOK_ENABLED=false
REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false
REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false
ALLOW_MOCK_PLATFORM_ADAPTERS=false
```

因此本轮没有发起真实 API 请求。以下验收项仍无证据：

1. 真实 App/店铺的实际 Scope，尤其是 `seller.logistics`。
2. 真实 Active Shops、订单列表、订单详情、物流、会话和消息读取。
3. 真实 Webhook 的正确签名、错误签名、重复投递和平台重试。
4. 真实平台返回的 request ID、限流、权限、Token 过期和业务错误映射。
5. Worker 处理真实消息与订单载荷时的失败保留和恢复。
6. 官方 Webhook 与定时读取对账后的漏投检测。

在两个缺陷关闭前，不应仅通过打开开关补做真实联调。

## 9. 验收结论与后续门禁

### 9.1 正式结论

- REAL-FS-03 当前 **不通过**。
- 新增 `DEF-REAL-FS03-001`（P1/Open）和 `DEF-REAL-FS03-002`（P2/Open）。
- 现有 91 项聚焦、772 项默认后端、782 项隔离 PostgreSQL、29 项前端测试、迁移、构建、健康和大部分 Webhook 契约通过。
- 确定性测试通过不能覆盖当前物流契约缺口，也不能替代真实店铺和真实平台 Webhook 验收。
- 当前真实读取、真实 Webhook、普通写入和高风险写入开关应继续保持关闭。

### 9.2 修复后复测顺序

1. 全栈开发工程师升级物流到 202604，并补齐 `seller.logistics` Scope、DTO、文档和测试。
2. 全栈开发工程师把重试收敛到网络、5xx 和 429，补齐请求次数断言。
3. 测试工程师执行两个缺陷的独立确定性复测和全量回归。
4. 架构师核准真实只读开关后，只开放单店铺真实读取，先验证店铺和订单，再验证物流、会话和消息。
5. 只读验收通过后再开放真实 Webhook，验证有效/无效签名、重复投递、平台重试和 Worker 失败恢复。
6. REAL-FS-03 通过前，任何平台写操作、公开 AI 回复、AI 营销和自动回复不得随之开放。

### 9.3 停止条件

出现以下任一情况，应立即关闭对应真实开关并停止联调：

- 真实 Scope 不包含所需权限或无法确认店铺归属。
- 当前官方路径、响应 DTO 或签名与实现不一致。
- Webhook 验签、1 MiB 限制、事件幂等或 Worker 重试失败。
- Token、Secret、完整消息、完整地址或客户隐私进入日志、响应或测试报告。
- 平台错误被伪装成成功、空数据或已完成状态。
- 任何未批准的平台写操作被触发。

## 10. 执行证据与清理

主要命令：

```text
uv lock --check --offline
uv run ruff check .
uv run ruff format --check app tests scripts migrations
uv run mypy app scripts
uv run pytest tests/test_tiktok_read.py tests/test_platform_adapters.py tests/test_real_runtime_config.py tests/test_phase4_domain.py tests/test_health.py -q
uv run pytest -q
npm run lint
npm run typecheck
npm run test
npm run build
docker-compose config --quiet
docker-compose ps
docker-compose exec -T backend uv run alembic current
alembic upgrade head
alembic downgrade 018_ai_observability
alembic upgrade head
Invoke-WebRequest http://localhost:8000/v1/health
Invoke-WebRequest http://localhost:8000/v1/health/ready
```

清理结果：

- 独立契约探针已删除。
- 隔离 `postgres-test` 已停止并删除，测试数据不可恢复且不影响开发数据库。
- 未修改产品代码、迁移、配置模板或前端代码。
- 未输出或保存真实 TikTok 凭证。

