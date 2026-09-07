# 真实环境配置与基础设施实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；关联 REAL-FS-01、P4-11 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、AIAgent开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-25 |
| 完成日期 | 2026-08-25 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`中店铺接入、客服工作台和安全要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md`中健康检查、渠道接入和 SSE 契约。本任务未新增或修改公共 API。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`和`架构师/PLAN-001-REAL-真实平台与AI生产环境接入实施计划-v1.0.md`。
- 任务依据：`全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md`中 `REAL-FS-01`。
- 验收依据：`架构师/验收-001-CROSS-真实环境生产放行检查表-v1.0.md`中配置、密钥、HTTPS、日志、备份和回滚门禁。
- 代码规范：`共享记忆文档/代码编写手册.md`。
- 测试基线：`测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-SSE看板部署与稳定性-综合测试-002.md`以及当前最新 `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-014.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 为真实 TikTok 和 DeepSeek 接入建立默认关闭、配置缺失时安全失败的生产运行基线。
- 补齐 HTTPS 反向代理、固定出口 IP 配置契约、服务端密钥注入、日志脱敏和备份恢复说明。
- 保持现有本地 Mock、后端、前端和 AI 工程测试不退化。

### 3.2 实施范围

- Pydantic Settings 生产配置与交叉校验。
- 生产 Docker Compose 覆盖、Nginx HTTPS/SSE 反向代理和非公开后端端口。
- 结构化日志敏感值脱敏。
- 环境变量模板、部署、备份、恢复和 Redis 灾备边界文档。
- 配置及脱敏回归测试。

### 3.3 非目标

- 不实现 TikTok OAuth、真实只读 API、Webhook 验签或任何真实写操作。
- 不修改 DeepSeek Provider、Prompt、AI 安全语义、SSE 事件契约或模型评测算法。
- 不放行真实平台、公开 AI 回复、AI 营销或自动回复。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及代码时已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

复用现有 FastAPI Settings、DeepSeek Provider、Compose、健康检查、SSE 接口和备份脚本，不建立第二套配置或编排系统。生产 Settings 在进程启动前校验 HTTPS、Cookie、JWT、数据库、MinIO、固定出口 IP、Mock 模式和 DeepSeek 前置条件。真实 TikTok 开关虽已纳入类型化配置，但在 REAL-FS-02/03 完成前一旦开启就拒绝启动。

生产 Compose 将八个高风险开关硬编码为 `false`，防止本地 `.env` 中的开发值被误带入生产。Nginx 是唯一公开入口，后端和前端仅在 Compose 内部网络可访问。SSE 路由禁用代理缓冲和缓存。

### 5.2 依赖关系

- 前置依赖：迁移 head `018_ai_observability`、现有 Compose/健康检查/SSE/DeepSeek Provider、用户后续提供的 HTTPS 证书、生产密钥和固定出口 IP。
- 后续依赖：REAL-FS-02～06、真实 TikTok 店铺联调、DeepSeek 真实模型评测、性能与五日稳定性验证。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 本地 `.env` 含有开发开关 | 合并生产 Compose 时误开真实能力 | 生产覆盖将高风险开关固定为 `false`，后续只能通过独立评审的放行覆盖开启 |
| 真实 TikTok 实现尚未完成 | 开关误开后运行在 Mock 或半成品路径 | Settings 检测任一真实 TikTok 开关开启时直接拒绝启动 |
| 密钥或客户数据进入日志 | 凭证泄露和隐私风险 | 在 JSON Formatter 前集中脱敏常见凭证、Bearer/JWT、OAuth Code、消息、地址和原始请求体 |
| 反向代理破坏 SSE | 首包延迟或事件堆积 | SSE 路由关闭 buffering/cache，配置长读取超时 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/shared/config/settings.py` | 修改 | 增加真实 TikTok/公网基址/出口 IP 配置与生产安全校验 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/main.py` | 修改 | 移除颠倒的 Mock 生产启动守卫，统一由 Settings 安全校验 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/shared/logging/setup.py` | 修改 | 增加集中式结构化日志脱敏 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/integrations/adapters.py` | 修改 | 仅在 TikTok HMAC 计算点解包 `SecretStr` 密钥 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_runtime_config.py` | 新增 | 覆盖生产配置门禁和日志脱敏 | 全栈开发工程师Agent |
| `CRM智能聊天系统/docker-compose.prod.yml` | 修改 | 增加生产密钥契约、高风险开关关闭、内部端口与 Nginx 入口 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/nginx/nginx.conf` | 新增 | 提供 HTTP 转 HTTPS、TLS、安全头和 SSE 代理 | 全栈开发工程师Agent |
| `CRM智能聊天系统/.env.example` | 修改 | 补齐真实环境配置模板，仅保留空值或安全默认值 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/production/README.md` | 新增 | 记录 HTTPS、出口 IP、密钥、启动、健康、告警和回滚操作 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/postgres/README.md` | 修改 | 补充 Redis 灾备边界 | 全栈开发工程师Agent |
| `CRM智能聊天系统/README.md` | 修改 | 更新生产启动、公开端口和文档入口 | 全栈开发工程师Agent |
| `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` | 修改 | 同步 REAL-FS-01 完成状态和最新测试基线 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无新增或变更公共 API；复用既有 `/v1/health`、`/v1/health/ready` 和 `/v1/chat/query`。健康响应不包含凭证、URL 或店铺数据。
- 数据库：不适用，本任务无迁移和表结构变更，当前 head 仍为 `018_ai_observability`。
- 配置项：新增 `PUBLIC_BASE_URL`、`TIKTOK_APP_SECRET`、`TIKTOK_OAUTH_REDIRECT_URI`、`TIKTOK_CREDENTIAL_ENCRYPTION_KEY`、`TIKTOK_EGRESS_IP`及四个 `REAL_TIKTOK_*` 开关；复用现有 `DEEPSEEK_BASE_URL`、`DEEPSEEK_API_KEY`、`LLM_*`、`AI_TRANSLATION_ENABLED`、`AI_MARKETING_ENABLED`、`AUTO_REPLY_ENABLED` 和 `ALLOW_MOCK_PLATFORM_ADAPTERS`。未保留两套同义开关。
- AI：不适用，未修改 Provider、Prompt、RAG、工具选择、阈值或 AI 评测逻辑。

### 6.3 关键实现说明

- 生产环境禁止 Mock Adapter、不安全 Cookie、默认 JWT/MinIO/数据库凭证、非 HTTPS 公网地址与非 IP 格式出口配置；TikTok Webhook 密钥使用 `SecretStr` 保护。
- 模型实时评测和自动回复必须依赖 `LLM_ENABLED`；高风险 TikTok 写必须依赖普通消息写，普通消息写必须依赖真实只读能力。
- 日志在序列化前脱敏，不记录 Token、Key、原始请求体、完整消息或地址。
- 真实开关未被开启，因此未执行真实店铺、真实模型或对外写操作。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 依赖锁 | `uv lock --check` | 锁文件与项目配置一致 | 通过 | 通过 |
| 后端静态检查 | `uv run ruff check app scripts tests` | 无违规 | 通过 | 通过 |
| 后端格式 | `uv run ruff format --check app scripts tests` | 格式一致 | 181 个文件通过 | 通过 |
| 后端类型 | `uv run mypy app scripts` | 无类型错误 | 150 个源文件通过 | 通过 |
| 后端回归 | `uv run pytest -q --basetemp=.pytest-runtime-fs01-full-final` | 新增及既有测试通过 | 481 通过、8 跳过；2 个既有警告 | 通过 |
| 生产设置导入 | 以非真实占位配置和全部高风险开关关闭导入 `app.main` | 进程可安全启动 | 输出 `crm-chat-system` | 通过 |
| 生产 Compose 合并 | `docker-compose -f docker-compose.yml -f docker-compose.prod.yml config --services` | 配置可解析 | 8 个服务解析成功 | 通过 |
| 生产开关检查 | 检查 Compose 合并结果中的 Mock、TikTok、LLM、翻译、营销和自动回复开关 | 全部关闭 | 全部为 `false` | 通过 |
| 前端质量 | `npm run lint`、`npm run typecheck`、`npm run test`、`npm run build` | 无回归 | lint/typecheck 通过，22 项测试通过，14 个静态页面构建成功 | 通过 |
| Nginx 容器语法 | `nginx:1.27.5-alpine` 一次性容器内为语法检查临时移除证书加载并补充内部主机解析后执行 `nginx -t` | 代理配置语法通过 | `syntax is ok` / `test is successful` | 通过 |
| 真实 TLS 握手与 SSE 穿透 | 使用目标生产主机和真实证书启动 `proxy` | HTTPS/SSE 可访问 | 尚未提供真实证书与目标主机，未执行 | 未执行 |

## 8. 实施结果

- 完成项：REAL-FS-01 范围内的配置、生产安全失败、HTTPS 代理、出口 IP 契约、密钥注入、日志脱敏、备份恢复说明和自动化回归。
- 未完成项：真实证书、DNS、固定公网出口和目标主机启动验收依赖用户/生产环境，将在 REAL-FS-02 前的环境门禁和 REAL-FS-06 部署演练中完成。
- 与原方案差异：复用项目已有 `DEEPSEEK_BASE_URL`、`LLM_*` 和 AI 功能开关，未新建同义变量；生产 Compose 中的高风险开关不从开发 `.env` 继承。
- 当前状态：REAL-FS-01 工程实施已完成；整体真实生产接入仍未放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-FS01-001 | 真实 TLS 证书、DNS 和固定出口 IP 尚未在目标主机验证 | P1 | 全栈开发工程师Agent、架构师Agent | REAL-FS-02 前置门禁、REAL-FS-06 |
| R-FS01-002 | Nginx 语法已通过，但真实 TLS 握手和 SSE 穿透尚未在目标 Docker 主机执行 | P1 | 全栈开发工程师Agent、测试工程师Agent | REAL-FS-02 前置门禁 |
| R-FS01-003 | 真实 TikTok 开关会在 REAL-FS-02/03 完成前拒绝启动 | P0 | 全栈开发工程师Agent | REAL-FS-02、REAL-FS-03 |
| R-FS01-004 | DeepSeek 真实模型、50 并发和五日稳定性未验证 | P0 | AIAgent开发工程师Agent、全栈开发工程师Agent、测试工程师Agent | REAL-AI-03/05、REAL-FS-05 |

## 10. 交接事项

- 交接给：架构师Agent、AIAgent开发工程师Agent、测试工程师Agent。
- 后续任务：REAL-FS-02 TikTok OAuth、REAL-FS-03 TikTok 只读与 Webhook、REAL-FS-05 DeepSeek/SSE 运行面、REAL-FS-06 生产部署和回滚。
- 必须注意：不得直接改动生产 Compose 中的高风险关闭值；开启时必须创建独立的放行覆盖、关联测试证据并由架构师签署。当前 M04 014 已关闭确定性工程范围缺陷，但不代表真实 DeepSeek、公开 AI 回复或真实平台已放行。

## 11. 文档同步

- [x] 已同步接口变化（本任务无公共 API 变化）。
- [x] 已同步架构决策（按 ADR-004 落地，无新架构决策）。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围（见第 7 节和遗留风险）。
- [x] 测试报告索引将在测试工程师完成 REAL-FS-01 独立测试后更新。

## 12. 测试后修正追踪

- 2026-08-25，测试工程师在 `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-真实环境配置与基础设施-综合测试-001.md` 中判定 REAL-FS-01 不通过，并登记 `DEF-REAL-FS01-001～004`。
- 全栈开发工程师已完成修复和开发自测，证据见 `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-真实环境基础设施测试缺陷修复-004.md`。
- 本历史记录保留首次实施证据；正式缺陷状态和 REAL-FS-01 验收结论仍由测试工程师独立复测后更新。
