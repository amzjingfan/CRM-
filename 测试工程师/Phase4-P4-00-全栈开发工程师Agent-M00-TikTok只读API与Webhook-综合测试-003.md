# TikTok 只读 API 与 Webhook 第三次综合复测报告

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
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTok物流数组契约缺陷修复-012.md` |
| 前序报告 | `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTok只读API与Webhook-综合测试-002.md` |
| 测试类型 | 综合测试、修复验证、契约测试、接口测试、集成测试、安全测试、数据库测试、回归测试、运行态检查 |
| 执行日期 | 2026-08-31 |
| 测试结论 | **有条件通过当前确定性工程范围；DEF-REAL-FS03-001～003 全部关闭，无新增缺陷，真实平台门禁未执行** |

## 2. 测试依据、目标与边界

### 2.1 测试依据

- `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-03。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- `架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`。
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- `共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.15 节。
- `共享记忆文档/开发任务拆解（按人天分配）.md`、`共享记忆文档/MVP范围与验收标准.md`。
- `共享记忆文档/项目团队职责说明.md`、`共享记忆文档/代码编写手册.md`。
- 项目全部适用 `AGENTS.md`、测试报告命名规范、002 号正式报告和 012 号修复实施记录。

本轮继续核对以下 TikTok Shop Partner Center 官方入口：

- [TikTok Shop API 请求签名](https://partner.tiktokshop.com/docv2/page/sign-your-api-request)
- [TikTok Shop Webhook 概览与验签](https://partner.tiktokshop.com/docv2/page/tts-webhooks-overview)
- [Get Logistics Tracking 202604](https://partner.tiktokshop.com/docv2/page/get-logistics-tracking-202604)
- [物流 202604 升级公告](https://partner.tiktokshop.com/docv2/page/8syhoy40)

官方 docv2 页面在本轮仍以 JavaScript 应用壳返回，自动化读取只能确认官方入口存在，不能取得完整字段正文。项目已冻结的 202604 契约与第 11.15 节继续作为确定性复测基线；本地 Skill 附带的 OAS 快照仅覆盖较旧物流候选，未覆盖 202604，因此未据此回退旧端点。真实兼容性仍必须由真实店铺冒烟证明。

### 2.2 测试目标

1. 独立复测 `DEF-REAL-FS03-003`，确认关键数组缺失与显式空数组已得到不同处理。
2. 验证缺失、错误别名、`null` 和错误类型均失败关闭，且契约错误不触发重试。
3. 回归 `DEF-REAL-FS03-001/002` 的 202604 路径、Scope、多包裹和瞬时错误白名单。
4. 回归 Webhook 验签、幂等、Worker、授权生命周期、迁移、前后端和基础设施。
5. 明确确定性工程通过与真实店铺、真实 Webhook 验收之间的边界。

### 2.3 未执行范围

- 未读取、输出或导出 App Secret、Access Token、Refresh Token、OAuth Code、`shop_cipher` 或凭证密文。
- 未打开真实 TikTok 读取、Webhook、普通写入或高风险写入开关。
- 未调用真实 TikTok Shop API，未接收 Partner Center 真实 Webhook 投递。
- 未修改真实应用的 Scope、Webhook、IP 白名单或店铺授权。
- 未执行平台写操作、公开 AI 回复、AI 营销或自动回复。
- 未把 MockTransport、自动化测试或本报告解释为真实店铺联调成功。

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
| 外部调用 | 使用假凭证与 `httpx.MockTransport`；未调用真实 TikTok API |
| 代码库状态 | 当前目录不是 Git 仓库，无法提供提交哈希或不可变发布版本 |

Node.js 24.19.0 与计划中的 Node.js 20 LTS 不一致，但本轮前端质量检查和生产构建通过；目标生产镜像仍应按 Node 20 固定基线复验。

## 4. 总体结果

| 测试域 | 实际结果 | 结论 |
| --- | --- | --- |
| `DEF-REAL-FS03-003` 修复 | 关键数组已改为必填，独立 10 项矩阵通过 | **通过并关闭** |
| 202604 路径与多包裹 DTO | 路径、订单归属、多包裹和历史单号通过 | 通过 |
| `seller.logistics` Scope | 配置、OAuth 必需 Scope 和请求前失败关闭通过 | 通过 |
| 稳定/瞬时错误分类 | 稳定错误 1 次；网络、5xx、429、36009003 最多 2 次 | 通过 |
| API 签名、Token Header、固定域名 | 聚焦测试通过 | 通过 |
| Webhook 验签、幂等与生命周期 | 聚焦测试和全量回归通过 | 通过 |
| Webhook 1 MiB 限制 | 运行态超大正文返回 413 | 通过 |
| 数据库与迁移 | 001→019、019→018→019、隔离 PostgreSQL 全量通过 | 通过 |
| 后端回归 | 105 项聚焦、786 项默认、796 项隔离数据库通过 | 通过 |
| 前端回归 | lint、typecheck、29 项测试和生产构建通过 | 通过 |
| 依赖审计 | 124 个锁定依赖未发现已知漏洞或不利项目状态 | 通过 |
| 真实店铺只读冒烟 | 未使用真实凭证和开关 | **未执行** |
| 真实 Webhook 投递 | 未打开真实 Webhook 开关 | **未执行** |

当前代码满足 REAL-FS-03 已定义的确定性工程契约，未发现新的 P0/P1/P2/P3 缺陷。由于计划验收还包含真实只读冒烟和真实 Webhook，结论为“有条件通过当前确定性工程范围”，不是完整生产验收通过。

## 5. 缺陷复测结论

| 缺陷编号 | 优先级 | 本轮验证 | 当前状态 |
| --- | --- | --- | --- |
| `DEF-REAL-FS03-001` | P1 | 202604 路径、多包裹、订单归属和 `seller.logistics` 回归保持通过 | **Closed** |
| `DEF-REAL-FS03-002` | P2 | 瞬时白名单与稳定业务错误请求次数回归保持通过 | **Closed** |
| `DEF-REAL-FS03-003` | P2 | 缺失/错误字段失败关闭，显式空数组合法 | **Closed** |

### 5.1 DEF-REAL-FS03-003 独立关闭证据

实现检查：

- `TikTokLogisticsData.logistics_details` 已改为没有默认值的必填 `list[TikTokLogisticsDetail]`。
- `TikTokLogisticsDetail.track_list` 已改为没有默认值的必填 `list[TikTokTrackingEntry]`。
- 两个字段仍保留最大长度限制，显式 `[]` 合法。
- `get_tracking()` 继续把 Pydantic `ValidationError` 转换为统一 `THIRD_PARTY_ERROR`。

独立探针覆盖 10 个场景：

| 场景 | 预期 | 实际 |
| --- | --- | --- |
| 缺少 `logistics_details` | 第三方契约错误，1 次请求 | 通过 |
| 只提供错误别名 `logisticsDetails` | 第三方契约错误，1 次请求 | 通过 |
| `logistics_details=null` | 第三方契约错误，1 次请求 | 通过 |
| `logistics_details={}` | 第三方契约错误，1 次请求 | 通过 |
| 包裹缺少 `track_list` | 第三方契约错误，1 次请求 | 通过 |
| 只提供错误别名 `trackList` | 第三方契约错误，1 次请求 | 通过 |
| `track_list=null` | 第三方契约错误，1 次请求 | 通过 |
| `track_list={}` | 第三方契约错误，1 次请求 | 通过 |
| `logistics_details=[]` | 合法空包裹结果 | 通过 |
| `track_list=[]` | 合法空轨迹结果 | 通过 |

探针结果为 `10 passed`。这证明字段完全缺失或类型异常不会再伪装成业务空结果，同时显式空数组没有被误拒绝。临时探针执行后已删除，未进入正式产品测试套件。

## 6. TikTok 只读与 Webhook 回归

### 6.1 只读 API

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 固定官方域名 | 调用方不能注入任意 URL | 通过 |
| API 请求签名 | 路径、query、精确正文和 App Secret 参与 HMAC-SHA256 | 通过 |
| Access Token | 只进入 `x-tts-access-token` Header | 通过 |
| 订单详情 | 使用 `/order/202507/orders` | 通过 |
| 物流轨迹 | 使用 `/logistics/202604/orders/{order_id}/tracking` | 通过 |
| 多包裹与历史单号 | 内部 DTO 完整保留 | 通过 |
| Scope | 缺少 `seller.logistics` 时请求前拒绝 | 通过 |
| 响应订单归属 | 不匹配时失败关闭 | 通过 |
| 关键数组字段 | 缺失/错误类型失败，显式空数组成功 | 通过 |
| 轨迹节点字段 | 缺少必填动作字段时失败且不重试 | 通过 |
| 错误重试 | 仅瞬时白名单有限重试 | 通过 |
| 只读冒烟入口 | `python -m scripts.verify_tiktok_readonly --help` 正常 | 通过 |

同一真实订单每 8 小时最多查询一次的规则仍由 README 和联调操作规程约束，当前只读脚本不持久化限频状态。它目前只用于人工批准的一次性冒烟，因此不作为本轮代码缺陷；若后续将远程物流读取接入工作台、Worker 或定时任务，必须先实现跨进程限频。

### 6.2 Webhook

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 官方原始正文 HMAC | 正确签名通过，正文变化失败，真实模式拒绝旧 Mock Header | 通过 |
| 请求体上限 | 超过 1 MiB 返回 HTTP 413 | 通过 |
| 事件幂等 | 通知 ID/正文摘要和数据库唯一性通过 | 通过 |
| 订单事件 | 只读详情补全和幂等更新通过 | 通过 |
| 买家消息 | 可见 BUYER 文本标准化通过 | 通过 |
| 授权生命周期 | 即将到期和撤销事件处理通过 | 通过 |
| 未知事件 | 保留追踪状态，不猜测业务写入 | 通过 |
| Worker | 异步认领、失败保留和有限重试通过 | 通过 |
| 真实 Partner Center 投递 | 开关未启用 | 未执行 |

## 7. 自动化、迁移与运行态结果

### 7.1 后端、数据库与安全

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check --offline` | 解析 125 个包 | 通过 |
| Ruff 检查 | `All checks passed` | 通过 |
| Ruff 格式检查 | 215 个正式 Python 文件已格式化 | 通过 |
| mypy | 160 个源文件无类型错误 | 通过 |
| 独立契约矩阵 | 10 passed | 通过 |
| REAL-FS-03 聚焦回归 | 105 passed、1 个既有弃用警告 | 通过 |
| 默认后端全量 | 786 passed、10 skipped、2 个既有弃用警告 | 通过 |
| 隔离 PostgreSQL 全量 | 796 passed、0 skipped、2 个既有弃用警告 | 通过 |
| 空库升级 | 001→019 成功 | 通过 |
| 回滚与恢复 | 019→018→019 成功，最终 head 为 019 | 通过 |
| `uv audit --locked` | 124 个锁定依赖未发现已知漏洞或不利项目状态 | 通过 |

两个警告来自既有 Starlette TestClient 兼容提示和 argon2 版本访问弃用，不是本次修复引入的功能失败。

### 7.2 前端、Compose 与运行态

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| 前端 lint/typecheck | 通过 | 通过 |
| 前端自动化 | 29 passed | 通过 |
| Next.js 生产构建 | 14 个静态页面构建成功 | 通过 |
| 开发 Compose | 配置可解析，7 个现有服务状态正常 | 通过 |
| 生产 Compose 叠加 | 使用非秘密占位配置可解析 | 通过 |
| `/v1/health` | HTTP 200，状态 ok | 通过 |
| `/v1/health/ready` | HTTP 200；数据库、Redis、对象存储均为 ok | 通过 |
| Webhook 超大正文 | HTTP 413，统一错误响应 | 通过 |

## 8. 真实环境与项目级门禁

### 8.1 REAL-FS-03 尚未执行的真实门禁

以下项目仍无测试证据：

1. 真实店铺授权是否实际包含 `seller.logistics`。
2. Active Shops、订单、202604 物流、会话、消息和 Webhook 订阅读取是否匹配真实载荷。
3. Partner Center 正确/错误签名、重复投递和平台重试。
4. 平台真实限流、Token 过期、权限拒绝、瞬时错误和 request ID 映射。
5. Webhook Worker 对真实订单、消息和授权生命周期载荷的处理及恢复。

确定性工程通过后，可以由架构师按“单店铺、只读、一次一个能力”的顺序申请真实联调；本报告不授权直接打开真实开关。

### 8.2 继承的项目级阻断

- 测试报告索引仍将 REAL-FS-01 标记为不通过，并列出 `DEF-REAL-FS01-005/006` 为 Open。
- 索引引用的 `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-真实环境配置与基础设施-综合测试-005.md` 当前不存在，生产门禁证据不可完整追溯。
- 以上问题不重新归类为 REAL-FS-03 代码缺陷，但在处理完成前，不能据本报告放行生产环境。
- 平台普通写入、高风险写入、公开 AI 回复、AI 营销和自动回复继续保持关闭。

## 9. 正式结论与建议

### 9.1 正式结论

- `DEF-REAL-FS03-001/002` 保持 **Closed**。
- `DEF-REAL-FS03-003` 本轮独立复测通过，状态更新为 **Closed**。
- 未发现新的 REAL-FS-03 P0/P1/P2/P3 缺陷。
- REAL-FS-03 当前确定性工程范围 **有条件通过**。
- 真实店铺只读、真实 Webhook 和生产平台行为仍为 **未执行**，不得描述为完整 REAL-FS-03 或生产接入验收通过。

### 9.2 后续顺序

1. 先补齐或纠正 REAL-FS-01 005 号报告与索引，确认其生产阻断状态。
2. 架构师确认 integration 环境、固定出口 IP、凭证、回滚和真实店铺 Scope。
3. 单店铺打开真实只读，依次验证店铺、订单、物流、会话、消息和订阅；同订单物流查询间隔不少于 8 小时。
4. 只读通过后单独打开真实 Webhook，验证签名、幂等、重试和 Worker 恢复。
5. 完成真实证据后由测试工程师生成新的真实环境验收报告，再决定是否进入 REAL-FS-04。

## 10. 执行证据与清理

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

- 独立 10 项临时契约探针已删除。
- 隔离 `postgres-test` 已精确停止并删除；tmpfs 测试数据不可恢复，未触碰开发数据库。
- 本轮 pytest 临时目录和 uv 测试缓存已删除。
- 未修改产品代码、迁移、配置、正式测试套件或真实平台配置。
- 未输出、保存或记录任何真实 TikTok 凭证和客户业务数据。
