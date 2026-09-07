# TikTok 只读 API 测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-03 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、测试工程师Agent |
| 实施状态 | 已完成（开发修复和确定性验证完成；正式缺陷待测试工程师独立复测关闭） |
| 开始日期 | 2026-08-31 |
| 完成日期 | 2026-08-31 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中平台统一接入、订单、会话和物流查询范围。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 的 11.15 REAL-FS-03 增量。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`。
- 任务依据：`全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-03。
- 缺陷依据：`测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTok只读API与Webhook-综合测试-001.md` 的 `DEF-REAL-FS03-001/002`。
- 官方依据：[Get Logistics Tracking 202604](https://partner.tiktokshop.com/docv2/page/get-logistics-tracking-202604)、[物流 202604 升级公告](https://partner.tiktokshop.com/docv2/page/8syhoy40)、[API 版本规则](https://partner.tiktokshop.com/docv2/page/api-versioning)。
- 验收依据：当前物流契约、Scope 失败关闭、稳定/瞬时错误分类、低敏日志、完整回归和真实能力继续关闭。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复物流读取仍使用旧 202309 路径、扁平 DTO 和缺少 `seller.logistics` 前置权限校验的问题。
- 修复未知稳定平台业务错误被当作瞬时错误重复请求的问题。
- 补齐当前契约、失败关闭、重试次数、低敏追踪和部署配置的自动化证据。

### 3.2 实施范围

- TikTok 真实只读客户端的物流路径、202604 响应模型、订单归属校验和 Scope 校验。
- OAuth 必需 Scope、环境模板、生产 Compose、部署说明和只读冒烟说明。
- 网络、5xx、429、官方瞬时内部错误与稳定业务错误的重试分类。
- REAL-FS-03 测试、接口文档、任务状态和实施记录同步。

### 3.3 非目标

- 不调用真实 TikTok 店铺，不修改 Partner Center 授权、Webhook 或 IP 白名单。
- 不开放真实 Webhook、人工消息、发券、修改地址、营销或自动回复。
- 不新增业务 API、数据表、字段、索引或 Alembic 迁移。
- 不修改 AI Agent、Prompt、RAG、DeepSeek Provider 或 AI 评测。
- 不由全栈开发工程师把测试报告中的缺陷标记为关闭。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册、全部适用 `AGENTS.md`、TikTok OpenAPI Skill 和当前官方契约。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认迁移 head 为 `019_tiktok_channel_unique`，本轮无需迁移。
- [x] 已确认真实凭证、店铺数据和平台写操作不进入本轮验证。

## 5. 实施方案

### 5.1 方案说明

问题根因分为两类：

1. 首次实现把仓库内旧 OAS 快照当作唯一版本来源，导致物流路径停留在 `/fulfillment/202309/...`，同时沿用扁平 `tracking[]` DTO，且 OAuth 最小 Scope 未纳入 `seller.logistics`。
2. `_request()` 使用“已知认证/权限错误立即失败，其余非零错误默认重试”的反向分类，未知稳定业务错误因此被错误重试。正确边界应是只允许明确瞬时错误进入重试白名单。

修复后的物流链路为：

```text
校验 seller.logistics
→ GET /logistics/202604/orders/{order_id}/tracking
→ 校验 data.order_id
→ 保留 logistics_details[] 多包裹
→ 保留 newest_tracking_no/carrier_name/track_list[]
→ 保留重发前后的历史 tracking_no 和 action_code_name
```

修复后的重试链路为：

```text
网络异常 / HTTP 5xx / HTTP 429 / 官方 36009003
→ 最多两次并有界退避

Token / 权限 / 参数 / 资源 / 未知稳定业务错误 / 契约漂移
→ 单次请求后失败关闭
```

### 5.2 依赖关系

- 前置依赖：REAL-FS-01 配置基础设施、REAL-FS-02 OAuth、迁移 `019`、TikTok 真实店铺的 `seller.logistics` 授权。
- 后续依赖：测试工程师独立复测 `DEF-REAL-FS03-001/002`；架构师核准后执行单店铺真实只读冒烟和 Webhook 验收。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 已授权店铺缺少新增 Scope | 真实物流必然返回权限错误 | 配置启动校验、客户端请求前校验并要求重新授权 |
| 多包裹或重发轨迹被压平 | 客服看到错误或丢失的物流状态 | 保留包裹层和每个轨迹节点的历史单号，不合并为单一轨迹 |
| 平台稳定错误重复请求 | 消耗配额、放大时延和噪声 | 瞬时错误白名单；未知业务错误默认单次失败 |
| 429 提示导致长时间阻塞 | Worker 或接口资源占用 | 数字 `Retry-After` 优先但限制为最多 5 秒 |
| 当前官方契约继续变化 | 真实冒烟失败 | 真实联调前再次核对 Partner Center 当前文档；契约漂移失败关闭 |
| 误放开平台写操作 | 产生真实副作用 | 本轮所有真实读取、Webhook 和写开关继续保持关闭 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/integrations/tiktok_read.py` | 修改 | 202604 物流 DTO/路径、物流 Scope、响应订单校验、瞬时错误白名单和有界退避 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/shared/config/settings.py` | 修改 | 将 `seller.logistics` 纳入真实只读必需 Scope 和启动门禁 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_tiktok_read.py` | 修改 | 增加当前物流契约、多包裹、Scope、错误分类、重试次数、日志和退避测试 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_runtime_config.py` | 修改 | 增加生产真实读取缺少物流 Scope 时的启动失败测试 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/scripts/verify_tiktok_readonly.py` | 修改 | 低敏输出按物流包裹计数，避免把包裹误称为轨迹节点 | 全栈开发工程师Agent |
| `CRM智能聊天系统/.env.example` | 修改 | 默认必需 Scope 加入 `seller.logistics` 并修正文档注释 | 全栈开发工程师Agent |
| `CRM智能聊天系统/docker-compose.prod.yml` | 修改 | 生产必需 Scope 默认值加入 `seller.logistics` | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/production/README.md` | 修改 | 同步生产 Scope 清单 | 全栈开发工程师Agent |
| `CRM智能聊天系统/README.md` | 修改 | 同步 202604 路径、Scope 和同订单每 8 小时一次的真实查询限制 | 全栈开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 更新 11.15 的物流、权限、重试和 DTO 契约 | 全栈开发工程师Agent |
| `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` | 修改 | 同步首次缺陷修复状态和复测门禁 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：不新增公共 API；内部物流调用从 `/fulfillment/202309/orders/{order_id}/tracking` 更新为 `/logistics/202604/orders/{order_id}/tracking`。
- 数据库：不适用；没有迁移、表结构或数据变更。
- 配置项：`TIKTOK_REQUIRED_SCOPES` 默认值增加 `seller.logistics`；不记录任何真实 Key、Token 或店铺数据。
- AI：不适用；未修改 AI 代码或契约。

### 6.3 关键实现说明

- 物流响应必须包含与请求一致的十进制 `order_id`；不一致时返回统一第三方契约错误，防止跨订单展示。
- `logistics_details[]` 不被压平，每个包裹保留最新单号、承运商和全部轨迹；重发后的历史 `tracking_no` 继续保留。
- 缺少 `seller.logistics` 时在 HTTP 请求前返回权限拒绝，避免消耗平台配额或把 403 解释为空数据。
- 只有网络异常、HTTP 5xx、429 和官方 `36009003` 进入最多两次的重试；其他非零平台 Envelope、非法 JSON 和 DTO 漂移立即失败。
- 429 的数字 `Retry-After` 被限制在 0～5 秒；没有有效提示时使用短时指数退避。
- 平台日志只记录固定事件名、数字错误码和低敏 `provider_request_id`，不记录平台原始消息、请求正文、Token、签名或业务 ID。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 锁文件 | `uv lock --check --offline` | 锁文件一致 | 125 个包解析完成 | 通过 |
| Ruff | `uv run ruff check app tests scripts migrations` | 无静态问题 | All checks passed | 通过 |
| Ruff 格式 | `uv run ruff format --check app tests scripts migrations` | 正式 Python 文件无格式差异 | 215 个文件已格式化 | 通过 |
| mypy | `uv run mypy app scripts` | 严格类型通过 | 160 个源文件无类型错误 | 通过 |
| 缺陷定向测试 | `uv run pytest -q tests/test_tiktok_read.py tests/test_real_runtime_config.py` | 202604、Scope、重试和配置场景通过 | 83 passed | 通过 |
| 默认后端全量 | `uv run pytest -q --basetemp ...` | 历史回归无退化 | 782 passed、10 skipped、2 个既有依赖弃用警告 | 通过 |
| PostgreSQL 迁移 | `alembic upgrade head`、`downgrade 018_ai_observability`、`upgrade head` | 001→019、019→018→019 可执行 | 最终 `019_tiktok_channel_unique (head)` | 通过 |
| PostgreSQL 全量 | 隔离 `postgres-test` + `uv run --frozen pytest -q -rs` | 数据库场景无跳过 | 792 passed、2 个既有依赖弃用警告 | 通过 |
| 前端 | `npm run lint`、`typecheck`、`test`、`build` | 无跨模块回归 | 29 tests passed，14 个静态页面构建成功 | 通过 |
| Compose 基线 | `docker-compose config -q` | 配置可解析 | 通过；Docker 用户配置不可读警告不影响解析 | 通过 |
| 生产 Compose 合并 | 非秘密占位配置 + `docker-compose -f docker-compose.yml -f docker-compose.prod.yml config -q` | 生产叠加文件可解析 | 通过 | 通过 |
| 冒烟脚本入口 | `uv run python -m scripts.verify_tiktok_readonly --help` | 可执行且只接受渠道 UUID | 帮助输出正常 | 通过 |
| 真实店铺只读 | 真实 App/店铺执行冒烟 | 当前契约和权限在真实平台通过 | 本轮未打开开关、未读取凭证、未调用真实平台 | 未执行 |
| 真实 Webhook | Partner Center 真实投递 | 验签、幂等和 Worker 成功 | 本轮真实 Webhook 开关关闭 | 未执行 |

## 8. 实施结果

- 完成项：`DEF-REAL-FS03-001/002` 对应代码、配置、文档和自动化修复；默认与 PostgreSQL 全量回归通过。
- 未完成项：测试工程师独立复测、真实店铺重新授权核对、真实只读冒烟和 Partner Center Webhook 投递。
- 与原方案差异：官方当前文档存在本地旧 OAS 未覆盖的 202604 物流版本，因此以官方当前 docv2 为准升级；额外保留官方明确的瞬时错误 `36009003` 有限重试。
- 当前状态：开发修复已完成；正式报告中的两个缺陷仍为 Open，REAL-FS-03 和生产接入仍未放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-FS03-FIX-001 | 真实店铺现有授权是否包含 `seller.logistics` 尚未核对；缺失时需重新授权 | P1 | 全栈开发工程师Agent、架构师Agent | REAL-FS-03 真实联调 |
| R-FS03-FIX-002 | 当前代码修复尚未由测试工程师独立复测，正式缺陷仍为 Open | P1 | 测试工程师Agent | REAL-FS-03 复测 |
| R-FS03-FIX-003 | 真实 202604 多包裹/重发响应和平台限流尚无真实证据 | P1 | 全栈开发工程师Agent、测试工程师Agent | REAL-FS-03 真实联调 |
| R-FS03-FIX-004 | 真实 Webhook 签名、重复投递和平台重试仍未执行 | P1 | 全栈开发工程师Agent、测试工程师Agent | REAL-FS-03 真实联调 |
| R-FS03-FIX-005 | 本地 Docker 只有独立 `docker-compose`，项目脚本使用 `docker compose` | P3 | 全栈开发工程师Agent | 部署工具链统一任务 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent。
- 后续任务：测试工程师先独立复测两个缺陷和全量回归；通过后由架构师核准，只为单个真实店铺开放读取，依次验证店铺、订单、物流、会话和消息，再开放真实 Webhook。
- 必须注意：真实店铺缺少 `seller.logistics` 时先重新授权；同一订单物流真实查询不得超过每 8 小时一次；所有平台写、公开 AI、营销和自动回复继续关闭。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构边界（未新增 ADR）。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖当前物流 DTO、Scope、错误分类、退避和低敏日志。
- [ ] 测试报告索引将在测试工程师正式复测完成后更新。
