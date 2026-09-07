# TikTok 只读 API 与 Webhook 实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-03 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、测试工程师Agent |
| 实施状态 | 部分完成（工程实现和本地回归完成；真实店铺冒烟、Partner Center 投递和独立测试待执行） |
| 开始日期 | 2026-08-31 |
| 完成日期 | 未完成 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中平台统一接入、订单、会话和消息范围。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 中平台 Webhook、店铺隔离及 11.15 增量。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`。
- 任务依据：`全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-03。
- 验收依据：真实只读 API、官方 Webhook 验签、幂等、Worker、稳定错误、消息与订单幂等，以及所有平台写入保持关闭。
- 代码规范：`共享记忆文档/代码编写手册.md`。
- 官方依据：TikTok Shop Partner Center 当前请求签名、Webhook、订单详情 202507、客服会话消息和通用错误文档。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 在现有 OAuth 密文和 `PlatformAdapter` 基础上完成真实 TikTok 只读客户端。
- 复用 `/v1/webhooks/tiktok`、`webhook_events` 和 Worker 完成官方通知接收与业务标准化。
- 在无真实凭证的开发环境完成确定性契约、安全、错误和回归验证。

### 3.2 实施范围

- 有效店铺、订单列表、订单详情、物流、客服会话、会话消息、Webhook 订阅读取。
- 官方 API 请求签名、Access Token 解密、Scope 前置校验、错误映射和只读重试。
- 官方 Webhook 原始正文验签、通知幂等、店铺映射、订单补全、消息标准化和授权生命周期。
- 配置门禁、冒烟脚本、README、接口增量、测试和任务状态同步。

### 3.3 非目标

- 真实消息发送、发券、地址修改、营销、自动回复或任何平台写操作。
- 浏览器直接读取 TikTok 远程数据或向前端返回 Token、Secret、shop_cipher。
- 修改 AI Agent、Prompt、RAG、模型 Provider 或 AI 评测。
- 本轮不新增数据表、字段、索引或 Alembic 迁移。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册、全部适用 `AGENTS.md` 和 TikTok OpenAPI Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认迁移 head 为 `019_tiktok_channel_unique`，不重写历史迁移。
- [x] 已确认真实凭证未进入代码、日志、测试或文档。

## 5. 实施方案

### 5.1 方案说明

```text
Webhook 原始正文
→ Authorization/App Secret 常量时间验签
→ tts_notification_id 幂等落库
→ Worker SKIP LOCKED 认领
→ 1 号订单事件调用 202507 详情补全 / 14 号消息直接标准化
→ 6/7 号授权生命周期处理 / 未知主题安全忽略
→ 既有订单、客户、会话、消息和审计表
```

只读客户端固定 `https://open-api.tiktokglobalshop.com`，不接受调用方 URL。请求实时生成 10 位 UTC 时间戳和 HMAC-SHA256，正文使用发送时的紧凑 JSON 原始字节；Token 从 AES-GCM 密文按租户、店铺和凭证类型上下文解密，只进入 Header。

### 5.2 依赖关系

- 前置依赖：REAL-FS-01 配置基础设施、REAL-FS-02 OAuth 和迁移 `019`、真实 App Scope、固定出口 IP、HTTPS 域名。
- 后续依赖：测试工程师 REAL-FS-03 独立测试、真实店铺冒烟、REAL-FS-04 人工确认普通消息。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 平台字段或版本变化 | 订单/消息无法标准化 | Pydantic 显式消费字段、未知字段兼容、必需字段漂移失败关闭 |
| 重复通知或伪造相同通知 ID | 重复业务数据或验签绕过 | 每次请求先验签，通知 ID 仅作为验签后的幂等键 |
| Token、Scope 或固定 IP 无效 | 真实 API 不可用 | 启动门禁、渠道 Scope 校验、官方错误码映射、重新授权状态 |
| 未知 Webhook 数值主题 | 错误写入业务表 | 仅处理官方主题页确认的 1/6/7/14，其余标记 ignored |
| 误开平台写能力 | 产生真实副作用 | REAL-FS-04 前两个写开关继续启动失败，真实适配器 `real_writes=false` |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/integrations/tiktok_read.py` | 新增 | 官方只读 API 客户端、响应 DTO、错误映射和金额校验 | 全栈开发工程师Agent |
| `backend/app/integrations/adapters.py` | 修改 | 官方 Webhook 验签、1/6/7/14 主题解析、订单和消息标准化 | 全栈开发工程师Agent |
| `backend/app/integrations/oauth_service.py` | 修改 | 增加上下文绑定的服务端 Access Token 解密入口 | 全栈开发工程师Agent |
| `backend/app/integrations/service.py` | 修改 | 官方通知幂等/店铺/主题字段、生命周期、未知主题和失败码 | 全栈开发工程师Agent |
| `backend/app/integrations/router.py` | 修改 | 加固 Content-Length 格式、负数和 1 MiB 上限校验 | 全栈开发工程师Agent |
| `backend/app/integrations/schemas.py` | 修改 | 增加 TikTok 授权生命周期内部类型 | 全栈开发工程师Agent |
| `backend/app/shared/config/settings.py` | 修改 | 放行只读/Webhook，保持写能力失败关闭，校验最小 Scope | 全栈开发工程师Agent |
| `backend/scripts/verify_tiktok_readonly.py` | 新增 | 低敏真实只读冒烟入口 | 全栈开发工程师Agent |
| `backend/tests/test_tiktok_read.py` | 新增 | API、签名、错误、事件、幂等与授权撤销专项测试 | 全栈开发工程师Agent |
| `backend/tests/test_real_runtime_config.py` | 修改 | 更新 REAL-FS-03/04 配置门禁测试 | 全栈开发工程师Agent |
| `.env.example`、`README.md` | 修改 | 配置、官方/Mock 边界、冒烟步骤和当前状态 | 全栈开发工程师Agent |
| `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` | 修改 | 同步 REAL-FS-02/03 当前状态 | 全栈开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 增加 11.15 内部只读与 Webhook 契约 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：复用 `POST /v1/webhooks/tiktok`；不新增浏览器公共读取接口。
- 数据库：无迁移；复用 `channel_accounts`、`webhook_events`、`audit_logs`、订单、客户、会话和消息表。
- 配置项：`REAL_TIKTOK_READ_ENABLED`、`REAL_TIKTOK_WEBHOOK_ENABLED` 可在前置配置完整时启用；默认仍为 false。真实 Webhook 使用 `TIKTOK_APP_SECRET`，`TIKTOK_WEBHOOK_SECRET` 仅保留给本地 Mock 回归。
- AI：不适用；未修改 AI 代码或契约。

### 6.3 关键实现说明

- 订单详情使用官方当前 202507 版本；订单列表、物流、会话、消息和订阅使用当前适用 202309 版本。
- API 客户端只支持 GET 和 TikTok 定义为查询的 POST 搜索，不提供 PUT、DELETE 或发送方法。
- 只读 HTTP 429、网络和 5xx 最多尝试两次；Token/权限错误不重试。平台错误只对外返回稳定错误，不返回原始消息。
- 日志中的平台 request ID 进入既有不可逆摘要字段；不保存 URL 查询、Token、签名、订单号或消息。
- 官方消息 ID、订单 ID、会话 ID 和 shop ID 必须为十进制数字，防止路径构造和契约漂移。
- 卖家撤销授权会清除 Refresh Token、shop_cipher 和 Open ID 哈希，并把 Access Token 变为不可用撤销引用；事件重复处理保持幂等。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 锁文件 | `uv lock --check` | 锁文件一致 | 125 个包解析完成 | 通过 |
| Ruff | `uv run ruff check .` | 无静态问题 | All checks passed | 通过 |
| 格式 | `uv run ruff format --check app scripts tests ../tests/integration` | 无格式差异 | 200 files already formatted | 通过 |
| mypy | `uv run mypy app scripts` | 严格类型通过 | 160 个源文件无问题 | 通过 |
| REAL-FS-03 专项 | `uv run pytest -q tests/test_tiktok_read.py ...` | 签名、读取、错误和事件通过 | 77 passed | 通过 |
| 后端全量 | `uv run pytest -q --basetemp=...` | 历史回归不退化 | 772 passed、10 skipped、2 个既有依赖弃用警告 | 通过 |
| 前端 | `npm run lint && npm run typecheck && npm run test && npm run build` | 全部通过 | 29 tests passed，14 个路由构建完成 | 通过 |
| Compose 静态 | `docker-compose config --services` | 配置可解析 | 7 个服务解析成功 | 通过 |
| 运行服务 | `docker-compose ps` | 基础服务健康 | backend/frontend/PostgreSQL/Redis/MinIO 健康，Worker/Jobs 运行 | 通过 |
| 数据库版本 | `docker-compose exec -T backend alembic current` | 当前为 019 | `019_tiktok_channel_unique (head)` | 通过 |
| 健康检查 | `/v1/health`、`/v1/health/ready` | ok/ready | `code=0`，状态 ok/ready | 通过 |
| 冒烟脚本入口 | `python -m scripts.verify_tiktok_readonly --help` | 可执行且只接受渠道 UUID | 帮助输出正常 | 通过 |
| 真实店铺只读 | 使用真实渠道执行冒烟脚本 | 店铺/订单/物流/消息/订阅读取成功 | 未注入真实凭证，未执行 | 未执行 |
| Partner Center 投递 | 官方 ORDER_STATUS_CHANGE/NEW_MESSAGE/授权事件 | 验签、幂等和 Worker 成功 | 未配置本轮真实投递 | 未执行 |
| 依赖审计 | `uv audit --locked` | OSV 查询完成 | 沙箱及提权后仍无法稳定访问 OSV，已中止 | 未执行 |

## 8. 实施结果

- 完成项：真实只读客户端、官方 Webhook 验签与标准化、授权生命周期、配置门禁、冒烟脚本、测试和文档同步。
- 未完成项：真实店铺只读冒烟、Partner Center 真实通知、平台重试实投、测试工程师正式报告。
- 与原方案差异：未新增公共管理端读取接口；采用内部客户端和只读脚本，避免前端绕过本地店铺隔离与数据模型。未新增迁移。
- 当前状态：工程实现完成但外部真实环境验收未完成，因此记录为部分完成、生产未放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-FS03-001 | 真实 App Scope、店铺地区和平台响应尚未冒烟 | P1 | 全栈开发工程师Agent、测试工程师Agent | REAL-FS-03 真实联调 |
| R-FS03-002 | Partner Center 四类 Webhook 尚未真实投递，3 秒 SLA 和官方重试未实测 | P1 | 全栈开发工程师Agent、测试工程师Agent | REAL-FS-03 真实联调 |
| R-FS03-003 | 本轮 OSV 网络不可达，无法刷新依赖审计证据 | P2 | 全栈开发工程师Agent | 网络恢复后重跑 |
| R-FS03-004 | 架构 v1.4 仍记录迁移 018，实际当前 head 已是 019 | P3 | 架构师Agent | 下次架构版本同步 |
| R-FS03-005 | 真实平台写操作仍未实现且必须保持关闭 | P1 | 全栈开发工程师Agent | REAL-FS-04 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent。
- 后续任务：测试工程师先执行确定性独立测试；具备真实凭证后在 integration 单店铺执行只读冒烟和 Partner Center 投递，再决定是否进入 REAL-FS-04。
- 必须注意：先在 Partner Center 核对授权店铺、订单、客服消息以及物流所需 Scope；配置四类 Webhook 到固定 HTTPS 地址。不得把 Token、App Secret、shop_cipher、订单号或消息写入命令、截图或报告。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构边界和实际迁移差异。
- [x] 已同步任务状态。
- [x] 已列明测试工程师需要覆盖的范围。
- [x] 测试报告索引将在正式测试完成后更新。
