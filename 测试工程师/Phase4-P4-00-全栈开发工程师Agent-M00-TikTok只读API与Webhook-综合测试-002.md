# TikTok 只读 API 与 Webhook 修复后综合复测报告

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
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTok只读API测试缺陷修复-011.md` |
| 前序报告 | `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTok只读API与Webhook-综合测试-001.md` |
| 测试类型 | 综合测试、修复验证、契约测试、接口测试、集成测试、安全测试、数据库测试、回归测试、运行态检查 |
| 执行日期 | 2026-08-31 |
| 测试结论 | **不通过；原 DEF-REAL-FS03-001/002 已关闭，新增 1 个 P2 缺陷，真实平台门禁未执行** |

## 2. 测试依据、目标与边界

### 2.1 测试依据

- `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-03。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- `架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`。
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- `共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.15 节。
- `共享记忆文档/开发任务拆解（按人天分配）.md`、`共享记忆文档/MVP范围与验收标准.md`。
- `共享记忆文档/项目团队职责说明.md`、`共享记忆文档/代码编写手册.md`。
- 项目全部适用 `AGENTS.md`、测试报告命名规范、001 号正式报告及 011 号修复实施记录。

本轮继续核对以下官方入口：

- [TikTok Shop API 请求签名](https://partner.tiktokshop.com/docv2/page/sign-your-api-request)
- [TikTok Shop Webhook 概览与验签](https://partner.tiktokshop.com/docv2/page/tts-webhooks-overview)
- [Get Logistics Tracking 202604](https://partner.tiktokshop.com/docv2/page/get-logistics-tracking-202604)
- [物流 202604 升级公告](https://partner.tiktokshop.com/docv2/page/8syhoy40)

官方 docv2 页面在本轮自动化环境中以动态脚本渲染，未取得可稳定引用的完整正文；本轮修复复测以 001 号报告已冻结的当前官方契约、项目第 11.15 节已同步的接口契约和 011 号修复目标为确定性基线。仓库内本地 OAS 仍未覆盖 202604 物流版本，不能据此降级回旧端点。该限制不影响代码修复复测，但真实兼容性仍必须由真实店铺只读冒烟确认。

### 2.2 测试目标

1. 独立复测 `DEF-REAL-FS03-001/002`，确认路径、DTO、Scope 与重试分类修复是否有效。
2. 补充开发测试未覆盖的物流字段缺失、空列表和契约漂移边界。
3. 回归真实 Webhook 验签、幂等、Worker、授权生命周期和写能力关闭状态。
4. 验证迁移、后端、前端、Compose、运行态和锁定依赖无新增退化。
5. 区分确定性工程通过项与真实店铺、Partner Center 回调验收项。

### 2.3 未执行范围

- 未读取、打印或导出真实 App Secret、Access Token、Refresh Token、OAuth Code、`shop_cipher` 或凭证密文。
- 未打开真实 TikTok 读取、Webhook、普通写入或高风险写入开关。
- 未调用真实 TikTok Shop API，未接收 Partner Center 真实 Webhook 投递。
- 未修改真实应用 Scope、Webhook、IP 白名单或店铺授权。
- 未执行任何平台写操作、公开 AI 回复、AI 营销或自动回复。
- 未把 MockTransport、单元测试或本报告视为真实平台联调成功证据。

## 3. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统/终端 | Windows；PowerShell |
| Python | 3.11.15 |
| uv | 0.12.3；锁文件解析 125 个包 |
| Node.js/npm | Node.js 24.19.0、npm 11.17.0 |
| Docker/Compose | 独立 `docker-compose` 5.3.1 |
| 数据库 | PostgreSQL 16 + pgvector；隔离 `postgres-test` 使用 5433/tmpfs |
| 迁移基线 | `019_tiktok_channel_unique (head)` |
| 运行服务 | backend、frontend、postgres、redis、minio、worker、jobs 共 7 个服务 |
| 外部调用 | 契约测试使用假凭证与 `httpx.MockTransport`；未调用真实 TikTok API |
| 代码库状态 | 当前目录不是 Git 仓库，无法提供提交哈希或不可变发布版本 |

Node.js 24.19.0 与计划中的 Node.js 20 LTS 不一致，但本轮 lint、类型检查、29 项前端测试和生产构建均通过。目标生产镜像仍应按固定 Node 20 基线复验。

## 4. 总体结果

| 测试域 | 结果 | 结论 |
| --- | --- | --- |
| 202604 物流路径与多包裹 DTO | 当前路径、订单归属、多包裹和历史单号测试通过 | 通过 |
| `seller.logistics` Scope | 配置、OAuth 必需 Scope 和请求前失败关闭通过 | 通过 |
| 稳定/瞬时错误分类 | 稳定业务错误 1 次；网络、5xx、429、36009003 最多 2 次 | 通过 |
| 物流关键数组字段缺失 | 缺失字段被默认成空列表，没有返回契约错误 | **失败** |
| API 签名、Token Header、固定域名 | 聚焦测试通过 | 通过 |
| Webhook 验签、幂等与生命周期 | 聚焦测试及全量回归通过 | 通过 |
| Webhook 1 MiB 限制 | 运行态超大正文返回 413 | 通过 |
| 数据库与迁移 | 001→019、019→018→019、隔离 PostgreSQL 全量通过 | 通过 |
| 后端回归 | 101 项聚焦、782 项默认、792 项隔离数据库通过 | 通过 |
| 前端回归 | lint、typecheck、29 项测试和生产构建通过 | 通过 |
| 依赖审计 | OSV 检查 124 个锁定依赖，未发现已知漏洞或不利项目状态 | 通过 |
| 真实店铺只读冒烟 | 未使用真实凭证和开关 | **未执行** |
| 真实 Webhook 投递 | 未打开真实 Webhook 开关 | **未执行** |

原报告两个缺陷已完成代码层独立关闭，但新增契约漂移缺陷会把“字段缺失”静默解释为“业务空结果”。REAL-FS-03 仍不满足失败关闭要求，总体结论为不通过。

## 5. 前序缺陷修复验证

| 缺陷编号 | 原优先级 | 修复验证结果 | 当前状态 |
| --- | --- | --- | --- |
| `DEF-REAL-FS03-001` | P1 | 202604 路径、多包裹、历史单号、订单归属和 `seller.logistics` 前置校验均通过 | **Closed** |
| `DEF-REAL-FS03-002` | P2 | 重试已收敛至网络、5xx、429、36009003；稳定业务错误只请求一次 | **Closed** |

### 5.1 DEF-REAL-FS03-001 关闭证据

- `get_tracking()` 当前使用 `/logistics/202604/orders/{order_id}/tracking`。
- 返回值保留 `logistics_details[]` 多包裹结构、最新单号、承运商、历史 `tracking_no` 和动作码。
- 响应 `order_id` 与请求不一致时返回统一第三方错误。
- 缺少 `seller.logistics` 时在发出 HTTP 请求前返回权限错误。
- `TIKTOK_REQUIRED_SCOPES`、`.env.example`、生产 Compose 和文档均已加入物流 Scope。

该缺陷关闭只代表确定性工程修复通过；真实店铺重新授权和真实订单物流冒烟仍属于外部环境门禁。

### 5.2 DEF-REAL-FS03-002 关闭证据

- 平台稳定业务错误 `code=123456` 只请求 1 次并保留 1 条低敏失败日志。
- 官方瞬时内部错误 `36009003` 最多请求 2 次。
- 网络异常和 HTTP 5xx 最多请求 2 次。
- HTTP 429 使用有上限的 `Retry-After`，60 秒提示被限制为 5 秒。
- 非法 JSON、响应信封漂移及稳定错误不重试。

## 6. 新增缺陷

| 缺陷编号 | 优先级 | 缺陷摘要 | 状态 | 是否阻断 REAL-FS-03 |
| --- | --- | --- | --- | --- |
| `DEF-REAL-FS03-003` | P2 | 物流关键数组字段缺失被静默解释为空列表 | Open | 是 |

### DEF-REAL-FS03-003：物流关键数组字段缺失被静默解释为空列表

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 类型 | 平台契约、错误语义、失败关闭 |
| 影响范围 | TikTok 物流读取、客服查物流、真实店铺冒烟、平台字段变更诊断 |
| 是否阻断 | 是，需在真实只读联调前关闭 |
| 建议负责 Agent | 全栈开发工程师Agent |

复现步骤：

1. 使用 `MockTransport` 返回 HTTP 200、`code=0`、有效 `data.order_id`，但完全省略 `data.logistics_details`。
2. 调用 `TikTokReadClient.get_tracking()`，预期返回统一 `THIRD_PARTY_ERROR`。
3. 再返回一个包裹对象，但省略该包裹的 `track_list`，再次调用 `get_tracking()`。
4. 独立临时探针两项均失败，错误均为 `Failed: DID NOT RAISE AppError`。

实际结果：

- 缺少 `logistics_details` 时返回空包裹列表。
- 包裹缺少 `track_list` 时返回空轨迹列表。
- 平台字段移除、响应被截断和真实业务空列表在内部无法区分。

代码原因：

- `TikTokLogisticsData.logistics_details` 使用 `default_factory=list`。
- `TikTokLogisticsDetail.track_list` 使用 `default_factory=list`。
- `get_tracking()` 直接返回模型默认值，因此不会进入 `ValidationError → THIRD_PARTY_ERROR` 分支。

预期结果：

- 字段明确存在且值为 `[]` 时允许表示无包裹或无轨迹。
- 契约中的关键数组字段完全缺失时失败关闭并返回稳定第三方错误。
- 不记录原始响应、Token、订单号或客户数据，只保留低敏 request ID 和稳定错误码。

修复验收：

1. 将上述两个关键字段改为必填数组，不再用默认空列表掩盖缺失。
2. 增加“字段缺失失败”和“字段存在但显式空数组成功”的成对测试。
3. 保留现有多包裹、历史单号、订单不匹配和缺少 Scope 测试。
4. 修复后执行 REAL-FS-03 聚焦、默认全量和隔离 PostgreSQL 全量回归。

## 7. 契约、安全与运行态明细

### 7.1 TikTok 只读 API

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 固定官方域名 | 调用方不能注入任意 URL | 通过 |
| API 请求签名 | 路径、query、精确正文和 App Secret 参与 HMAC-SHA256 | 通过 |
| Access Token | 只进入 `x-tts-access-token` Header | 通过 |
| 订单详情 | 使用当前 `/order/202507/orders` | 通过 |
| 物流轨迹 | 使用 `/logistics/202604/orders/{order_id}/tracking` | 通过 |
| 多包裹与历史单号 | 结构完整保留 | 通过 |
| Scope | 缺少 `seller.logistics` 时请求前拒绝 | 通过 |
| 响应订单归属 | 不匹配时失败关闭 | 通过 |
| 必需轨迹节点字段 | 缺少 `action_code_name` 时失败关闭且不重试 | 通过 |
| 必需数组字段 | 缺失时被默认为空 | **失败，见 DEF-REAL-FS03-003** |
| 错误重试 | 仅瞬时白名单有限重试 | 通过 |
| 冒烟入口 | `python -m scripts.verify_tiktok_readonly --help` 正常 | 通过 |

同一真实订单每 8 小时最多查询一次的限制目前由 README 和联调操作规程约束，内部脚本本身不持久化限频状态。当前脚本仅用于人工批准的单店铺冒烟，因此本轮不另建代码缺陷；若后续把远程物流查询接入 Worker、工作台或定时任务，必须先增加跨进程 Redis/数据库限频门禁。

### 7.2 Webhook

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 官方原始正文 HMAC | 正确签名通过，正文变化失败，真实模式拒绝旧 Mock Header | 通过 |
| 请求体上限 | 超过 1 MiB 返回 HTTP 413 | 通过 |
| 事件幂等 | 通知 ID/正文摘要与数据库唯一性测试通过 | 通过 |
| 订单事件 | 只读详情补全和幂等更新通过 | 通过 |
| 买家消息 | 可见 BUYER 文本标准化通过 | 通过 |
| 授权生命周期 | 即将到期和撤销事件处理通过 | 通过 |
| 未知事件 | 保留追踪状态，不猜测业务写入 | 通过 |
| Worker | 异步认领、失败保留和有限重试通过 | 通过 |
| 真实 Partner Center 投递 | 开关关闭，未执行 | 未执行 |

## 8. 自动化、迁移与基础设施结果

### 8.1 后端与安全

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check --offline` | 解析 125 个包 | 通过 |
| Ruff 检查 | app/tests/scripts/migrations 通过 | 通过 |
| Ruff 格式检查 | 215 个正式 Python 文件已格式化 | 通过 |
| mypy | app/scripts 共 160 个源文件无类型错误 | 通过 |
| REAL-FS-03 聚焦回归 | 101 passed、1 个既有弃用警告 | 通过 |
| 默认后端全量 | 782 passed、10 skipped、2 个既有弃用警告 | 通过 |
| 隔离 PostgreSQL 全量 | 792 passed、0 skipped、2 个既有弃用警告 | 通过 |
| 独立契约探针 | 2 failed，稳定复现 DEF-REAL-FS03-003 | 发现缺陷 |
| `uv audit --locked` | 124 个锁定依赖未发现已知漏洞或不利项目状态 | 通过 |

### 8.2 迁移、前端与运行态

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| 空库升级 | 001→019 成功 | 通过 |
| 回滚与恢复 | 019→018→019 成功，最终 head 为 019 | 通过 |
| 前端 lint/typecheck | 通过 | 通过 |
| 前端自动化 | 29 passed | 通过 |
| Next.js 生产构建 | 14 个静态页面生成成功 | 通过 |
| 开发 Compose | 配置可解析，7 个服务状态可读取 | 通过 |
| 生产 Compose 叠加 | 使用非秘密占位配置可解析 | 通过 |
| `/v1/health` | HTTP 200，状态 ok | 通过 |
| `/v1/health/ready` | HTTP 200；数据库、Redis、对象存储均为 ok | 通过 |
| Webhook 超大正文 | HTTP 413、统一错误响应 | 通过 |

## 9. 真实店铺与生产门禁状态

本轮没有读取真实凭证或打开真实开关，因此以下项目仍无测试证据：

1. 真实店铺重新授权后是否实际包含 `seller.logistics`。
2. Active Shops、订单、物流、会话、消息和 Webhook 订阅读取是否与真实载荷一致。
3. Partner Center 的正确/错误签名、重复投递和平台重试。
4. 平台真实限流、Token 过期、权限拒绝、瞬时错误和 request ID 映射。
5. Webhook Worker 对真实订单、消息和授权生命周期载荷的处理结果。

在 `DEF-REAL-FS03-003` 关闭前，不应打开真实读取或真实 Webhook 开关。缺陷关闭后仍应按“单店铺、只读、一次一个能力”的顺序执行真实冒烟；平台写入、公开 AI 回复、AI 营销和自动回复不得随之开放。

## 10. 正式结论与后续步骤

### 10.1 正式结论

- `DEF-REAL-FS03-001`：**Closed**。
- `DEF-REAL-FS03-002`：**Closed**。
- 新增 `DEF-REAL-FS03-003`：**P2/Open**。
- REAL-FS-03 当前仍为 **不通过**。
- 静态质量、既有测试、迁移、数据库、前端、Compose、健康检查和依赖审计均无新增回归。
- 真实 TikTok 店铺只读和真实 Webhook 尚未验收，不能宣称真实平台接入完成。

### 10.2 修复与复测顺序

1. 全栈开发工程师修复关键数组字段缺失的失败关闭语义，并增加缺失/显式空列表成对测试。
2. 测试工程师独立复测 `DEF-REAL-FS03-003` 并执行聚焦与全量回归。
3. 架构师确认 REAL-FS-01 的既有生产依赖/日志阻断处置和真实店铺授权范围。
4. 只打开单店铺真实读取，依次验证店铺、订单、物流、会话、消息和订阅。
5. 只读通过后再打开真实 Webhook，验证签名、幂等、重试和 Worker 恢复。
6. REAL-FS-03 正式通过前，REAL-FS-04 及任何高风险写入保持关闭。

## 11. 执行证据与清理

主要命令：

```text
uv lock --check --offline
uv run ruff check app tests scripts migrations
uv run ruff format --check app tests scripts migrations
uv run mypy app scripts
uv run pytest tests/test_tiktok_read.py tests/test_real_runtime_config.py tests/test_platform_adapters.py tests/test_phase4_domain.py tests/test_health.py -q
uv run pytest -q
uv audit --locked
npm run lint
npm run typecheck
npm run test
npm run build
docker-compose config --quiet
docker-compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
alembic upgrade head
alembic downgrade 018_ai_observability
alembic upgrade head
Invoke-WebRequest http://localhost:8000/v1/health
Invoke-WebRequest http://localhost:8000/v1/health/ready
python -m scripts.verify_tiktok_readonly --help
```

清理结果：

- 两项独立临时契约探针执行后已删除。
- 隔离 `postgres-test` 已精确停止并删除；tmpfs 测试数据不可恢复，未触碰开发数据库。
- 本轮测试缓存和 pytest 临时目录已删除。
- 未修改产品代码、迁移、配置模板、正式测试套件或真实平台配置。
- 未输出、保存或记录任何真实 TikTok 凭证和客户业务数据。
