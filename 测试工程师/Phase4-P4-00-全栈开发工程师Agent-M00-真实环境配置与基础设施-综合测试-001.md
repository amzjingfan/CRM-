# Phase 4 REAL-FS-01 真实环境配置与基础设施综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-FS-01` |
| 模块编号 | M00（真实环境基础设施跨模块基线） |
| 模块名称 | 真实环境配置与基础设施 |
| 被测主责 Agent | 全栈开发工程师Agent |
| 被测协作 Agent | 架构师Agent、AIAgent开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 被测计划 | `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 `REAL-FS-01` |
| 被测实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-真实环境配置与基础设施-001.md` |
| 测试类型 | 综合测试、回归测试、配置测试、安全测试、数据库测试、部署测试、恢复演练检查 |
| 执行日期 | 2026-08-25 |
| 测试结论 | **不通过；不得据此进入真实 OAuth、真实平台写操作或 DeepSeek 生产联调** |

最终结论：工程质量、481 项默认后端回归、489 项隔离 PostgreSQL 全量回归、001→018 迁移及 018→017→018 回滚恢复、22 项前端测试、14 个页面生产构建、依赖审计、Compose 高风险开关关闭、内部端口隔离、健康检查和恢复脚本安全门禁均通过。但独立安全审查发现 2 个 P1、1 个 P2 和 1 个 P3 缺陷：应用与 Nginx 日志仍可泄漏 OAuth 参数和若干真实密钥/消息字段；生产 Compose 未建立 TikTok/DeepSeek 密钥的主机或 CI 注入契约并继续继承开发 `.env`；生产 CORS 校验接受带凭据、路径和查询串的伪来源；实施记录存在失效文档路径。`REAL-FS-01` 当前不满足“日志无凭证”和“服务端密钥注入”验收要求。

## 2. 测试依据、范围与边界

### 2.1 测试依据

- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- `共享记忆文档/智能客服平台 — 管理端接口文档.md`。
- `共享记忆文档/开发任务拆解（按人天分配）.md`。
- `共享记忆文档/MVP范围与验收标准.md`。
- `共享记忆文档/代码编写手册.md`。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- `架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`。
- `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.0.md`。
- `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md`。
- 项目全部适用的 `AGENTS.md` 和 `测试工程师/测试报告命名规范.md`。

### 2.2 本轮覆盖

- 真实 TikTok、Webhook、消息写操作和 DeepSeek 能力开关的默认关闭与生产失败关闭。
- 生产配置类型校验、必填项、HTTPS、固定出口 IP、Cookie、Mock 禁用和弱密钥拒绝。
- 生产 Compose 服务、端口、密钥注入契约、持久化、健康检查和反向代理。
- Nginx HTTPS/SSE 配置语法、安全头、访问日志和 OAuth 回调参数泄漏。
- 应用结构化日志的字段脱敏与配置对象泄漏风险。
- 后端、前端、数据库迁移、依赖安全和现有 AI Agent 测试回归。
- PostgreSQL、MinIO 备份恢复脚本语法、`WhatIf` 和目标确认门禁。
- `/v1/health` 与 `/v1/health/ready` 的低敏感响应。

### 2.3 未执行和结论边界

- 未提供正式域名证书和目标生产主机，未执行真实 TLS 握手、证书链、HSTS 浏览器行为和公网 SSE 穿透。
- 未在目标云环境核验固定出口 IP，也未实际修改 TikTok IP 白名单。
- 未取得真实 TikTok/DeepSeek 凭证；所有安全专项只使用无价值哨兵数据，报告不记录任何真实密钥。
- 未执行真实 PostgreSQL/MinIO 全量备份恢复，只验证脚本解析、预演和错误目标拒绝；正式恢复仍需在隔离生产等价环境演练。
- `REAL-FS-02` 及以后范围的 OAuth、真实 TikTok API、Webhook、平台写操作、DeepSeek Provider 和真实 SSE 不在本报告功能验收范围内。

## 3. 测试环境与代码状态

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell 7.6.4，Asia/Shanghai |
| Python | 3.11.15，uv 0.12.3，锁文件解析 125 个包 |
| 前端 | Node.js 24.19.0、npm 11.17.0；生产 Compose 默认 Node 20.19.4 镜像 |
| Docker | Docker Engine 29.7.2、Docker Compose 5.3.1 |
| 数据库 | PostgreSQL 16 + pgvector；迁移 head 为 `018_ai_observability` |
| 运行态 | 当前开发环境 `/v1/health`、`/v1/health/ready` 可用 |
| 代码状态 | 当前目录不是 Git 仓库；按 2026-08-25 工作区执行，只新增本报告并更新测试索引，未修改产品代码 |

## 4. 测试汇总

| 分类 | 通过 | 失败 | 未执行 | 结论 |
| --- | ---: | ---: | ---: | --- |
| 工程质量与自动化 | 9 | 0 | 0 | 通过 |
| 数据库与迁移 | 5 | 0 | 0 | 通过 |
| 生产配置与安全 | 11 | 3 | 0 | 不通过 |
| Compose、代理与运行态 | 9 | 2 | 2 | 不通过 |
| 备份恢复 | 4 | 0 | 2 | 当前静态门禁通过 |
| 文档一致性 | 2 | 1 | 0 | 存在 P3 |

缺陷统计：P0 0 个、P1 2 个、P2 1 个、P3 1 个；另有 1 项跨 Agent 文档状态观察。

## 5. 测试场景与结果

### 5.1 工程质量和自动化回归

| 测试项 | 命令/方法 | 实际结果 | 状态 |
| --- | --- | --- | --- |
| 锁文件一致性 | `uv lock --check` | 解析 125 个包 | 通过 |
| Ruff | `ruff check app scripts tests` | All checks passed | 通过 |
| Ruff 格式 | `ruff format --check app scripts tests` | 181 个文件已格式化 | 通过 |
| mypy | `mypy app scripts` | 150 个源文件无问题 | 通过 |
| 后端默认回归 | `pytest -q -rs`，使用项目内独立 basetemp | 481 passed、8 skipped、2 个既有警告 | 通过 |
| 隔离数据库全量回归 | `scripts/run-postgres-integration-tests.ps1` | 489 passed、0 skipped、2 个既有警告 | 通过 |
| 前端 lint/typecheck | `npm run lint`、`npm run typecheck` | 无错误 | 通过 |
| 前端自动化 | `npm run test` | 22 passed | 通过 |
| 前端生产构建 | `npm run build` | Next.js 15.5.23 构建成功，14 个静态页面 | 通过 |
| 依赖审计 | `uv audit --locked` | 124 个已审计包无已知漏洞或不良状态 | 通过 |

保留两项既有非阻断警告：Starlette TestClient/httpx 兼容性弃用提示、passlib 读取 argon2 版本的弃用提示。8 项默认跳过的数据库用例已在隔离 PostgreSQL 全量回归中执行。

### 5.2 数据库与迁移

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 空库完整升级 | tmpfs 隔离数据库完成 001→018 | 通过 |
| 当前 head | `018_ai_observability (head)` | 通过 |
| 最新版本回滚 | 018→017 | 通过 |
| 回滚后恢复 | 017→018 | 通过 |
| 测试隔离与清理 | 精确删除隔离 PostgreSQL 容器，未触碰开发数据库卷 | 通过 |

### 5.3 生产配置与失败关闭

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 生产禁用 Mock | `ALLOW_MOCK_PLATFORM_ADAPTERS=true` 被设置校验拒绝 | 通过 |
| 生产 Cookie 安全 | 非 Secure Cookie 被拒绝 | 通过 |
| 弱 JWT/MinIO/数据库凭据 | 默认值、弱值和开发凭据被拒绝 | 通过 |
| 公网基址 | 非 HTTPS 或无主机名被拒绝 | 通过 |
| 固定出口 IP | 缺失、非公网或非法格式被拒绝 | 通过 |
| 高风险功能开关 | TikTok 四开关、LLM、在线评测、翻译、营销和自动回复在生产 Compose 中均为 `false` | 通过 |
| 必填生产变量 | 将 Compose 必填变量置空后，配置解析以非零状态安全失败 | 通过 |
| 应用日志常见字段 | 既有 `authorization`、`token`、`content` 等模式被脱敏 | 通过 |
| 应用日志真实业务字段 | `app_secret`、`client_secret`、`tiktok_app_secret`、`message` 未被脱敏 | **失败，DEF-REAL-FS01-001** |
| 配置对象异常输出 | Settings 的 `repr` 及经 `redact_log_text` 处理后仍可见 JWT、数据库密码和 MinIO 密钥哨兵 | **失败，DEF-REAL-FS01-001** |
| CORS 来源语法 | 带用户名密码、路径和查询串的 HTTPS 字符串被接受 | **失败，DEF-REAL-FS01-003** |

### 5.4 Compose、Nginx 与运行态

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 生产 Compose 合并 | 使用安全哨兵配置解析为 8 个服务 | 通过 |
| 对外端口 | 仅 proxy 发布 80/443；backend、frontend、PostgreSQL、Redis、MinIO 无宿主机端口 | 通过 |
| 持久化与健康检查 | PostgreSQL、Redis、MinIO 的卷与健康检查保留 | 通过 |
| Nginx 语法 | `nginx:1.27.5-alpine` 一次性容器执行 `nginx -t` | `syntax is ok`、`test is successful` | 通过 |
| SSE 代理 | `/v1/chat/query` 关闭 buffering/cache，读取超时 120 秒 | 通过（静态与语法） |
| HTTP 跳转 | 80 端口统一 301 到 HTTPS | 通过（静态与语法） |
| Nginx OAuth 日志 | 请求 OAuth callback 后，容器访问日志包含完整 `code` 和 `state` 哨兵 | **失败，DEF-REAL-FS01-001** |
| TikTok 密钥注入 | 主机环境设置 4 个 TikTok 契约变量后，合并配置中命中 0/4 | **失败，DEF-REAL-FS01-002** |
| DeepSeek 密钥注入 | 主机环境设置 DeepSeek Key 哨兵后，合并配置未采用该值 | **失败，DEF-REAL-FS01-002** |
| `/v1/health` | HTTP 200，响应只包含状态和版本 | 通过 |
| `/v1/health/ready` | HTTP 200，`status=ready`，依赖状态为低敏感枚举 | 通过 |
| 真实 TLS 握手 | 缺少目标证书和主机 | 未执行 |
| 公网出口 IP | 缺少目标部署和 TikTok 白名单变更授权 | 未执行 |

生产叠加文件没有显式传入 TikTok/DeepSeek 凭据，也没有重置基础 Compose 的 `env_file: .env`。独立测试中，容器环境里出现的部分 DeepSeek 配置来自仓库开发 `.env`，而不是本轮设置的主机/CI 哨兵变量。这既不能证明生产密钥注入有效，也造成开发环境文件进入生产合并配置的风险。

### 5.5 备份与恢复

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| PowerShell AST 解析 | PostgreSQL、MinIO 的备份/恢复 4 个脚本均为 0 语法错误 | 通过 |
| PostgreSQL 恢复预演 | `restore-postgres.ps1 -WhatIf` | 通过 |
| MinIO 恢复预演 | `restore-minio.ps1 -WhatIf` | 通过 |
| 错误目标确认 | PostgreSQL 恢复使用错误 `ConfirmTarget` 被拒绝 | 通过 |
| PostgreSQL 真实恢复 | 未提供生产等价隔离备份 | 未执行 |
| MinIO 真实恢复 | 未提供生产等价隔离备份 | 未执行 |

### 5.6 敏感信息与清理

- 对产品源码、配置模板和文档执行常见私钥、DeepSeek Key、AWS/Google 凭据模式扫描，256 个文件中未发现命中；该结果不替代日志动态脱敏缺陷。
- 所有独立安全测试只使用无价值哨兵值，命令输出和本报告不记录仓库 `.env` 内容、真实 Token、密码、客户地址或完整消息。
- 一次性 Nginx、隔离 PostgreSQL 容器均已精确删除。
- `.pytest-real-fs01-default` 及 4 个本轮 `.uv-cache-real-fs01*` 目录均已精确删除。
- 测试工程师未修改产品代码、数据库迁移和现有业务数据。

## 6. 缺陷详情

### DEF-REAL-FS01-001：应用与 Nginx 日志可泄漏 OAuth 参数、真实密钥和消息字段

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 安全、日志脱敏、OAuth |
| 影响范围 | 应用日志、Nginx 访问日志、异常日志、TikTok OAuth 回调 |
| 是否阻断 | 是；阻断 REAL-FS-01 和真实 OAuth 联调 |
| 建议负责 Agent | 全栈开发工程师Agent |

复现步骤：

1. 使用无价值哨兵字符串调用 `redact_log_text`，字段分别命名为 `app_secret`、`client_secret`、`tiktok_app_secret` 和 `message`。
2. 构造满足生产校验的 Settings，再检查其 `repr` 及 `redact_log_text(settings_repr)`。
3. 使用项目 `deploy/nginx/nginx.conf` 启动一次性 Nginx，访问 `/v1/integrations/tiktok/oauth/callback?code=<sentinel>&state=<sentinel>`。
4. 检查应用脱敏结果和 Nginx 容器日志。

实际结果：

- 4 个真实业务字段均未被应用脱敏函数覆盖。
- Settings 异常表示中可见 JWT、数据库密码和 MinIO 密钥哨兵；现有文本脱敏仍未移除。
- Nginx 默认访问日志记录 `$request`，OAuth `code` 和 `state` 哨兵均可检索到；项目只对 `/healthz` 关闭访问日志。

预期结果：OAuth code/state、任意 `*_secret`、数据库 DSN 密码、客户消息和密钥字段不得进入应用或代理日志；即使配置对象被意外记录，仍应输出掩码。

建议修复：

- 将核心密钥和完整数据库 URL 使用 `SecretStr` 或自定义安全表示；禁止记录完整 Settings。
- 扩展结构化日志按键脱敏，覆盖 `*_secret`、`*_secret_key`、`message`、OAuth code/state 和 DSN 密码，并增加本报告哨兵用例。
- 为 Nginx 定义不含查询串的 JSON 访问日志格式，或对 OAuth callback 禁用访问日志；HTTP 跳转同样不得记录敏感 query。
- 修复后同时验证正常访问、错误页、上游超时和 4xx/5xx 日志路径。

### DEF-REAL-FS01-002：生产 Compose 未建立 TikTok/DeepSeek 服务端密钥注入契约

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 生产配置、密钥管理、环境隔离 |
| 影响范围 | backend、worker、jobs、agent-worker；REAL-FS-02、REAL-FS-05 |
| 是否阻断 | 是；阻断真实 TikTok OAuth 和 DeepSeek 生产联调 |
| 建议负责 Agent | 全栈开发工程师Agent；架构师Agent评审 |

复现步骤：

1. 在当前进程设置 4 个 TikTok 密钥契约变量和 1 个 DeepSeek Key 哨兵，不写入 `.env`。
2. 使用 `docker-compose -f docker-compose.yml -f docker-compose.prod.yml config --format json` 合并生产配置。
3. 仅比较容器环境中的值是否等于本轮哨兵，不输出任何值。

实际结果：

- TikTok 4 个主机/CI 哨兵命中 0/4。
- DeepSeek Key 主机/CI 哨兵未命中。
- `docker-compose.prod.yml` 只映射数据库、Redis、MinIO、JWT、CORS、公网基址和出口 IP；基础 Compose 的 `env_file: .env` 仍被继承。
- 合并结果中的部分 DeepSeek 键来自开发 `.env`，说明生产运行面依赖仓库本地文件而非明确的生产密钥来源。

预期结果：生产 Compose 应显式接受并向需要的服务传递 TikTok/DeepSeek 凭据，或使用 Docker/云密钥挂载；不得隐式继承开发 `.env`。高风险功能开关在凭据存在时仍应默认关闭。

建议修复：

- 在生产叠加文件中重置基础 `env_file`，或改用仓库外专用生产环境文件/密钥服务。
- 对需要凭据的服务显式映射 `${TIKTOK_...:?}`、`${DEEPSEEK_...:?}`，或挂载只读 secret 文件；不要在 Compose 配置输出中暴露值。
- 区分“凭据可用”和“能力放行”，继续保持 TikTok 写操作、公开 AI 和自动回复开关为 `false`。
- 增加主机环境、CI、缺失密钥、轮换和撤销的自动化配置契约测试。

### DEF-REAL-FS01-003：生产 CORS 校验接受带凭据和请求路径的伪来源

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 类型 | 配置校验、安全加固 |
| 影响范围 | 浏览器跨域配置、生产启动门禁 |
| 是否阻断 | 阻断当前 REAL-FS-01 验收；不构成已发生的数据泄漏证据 |
| 建议负责 Agent | 全栈开发工程师Agent |

复现步骤：

1. 构造其余字段均合法的生产 Settings。
2. 将 `CORS_ORIGINS` 设置为带用户名、密码、路径和查询串的 HTTPS URL 哨兵。
3. 实例化配置。

实际结果：配置被接受。当前校验只检查来源不是 `*` 且以 `https://` 开头。

预期结果：每个来源只能包含 HTTPS scheme、明确 hostname 和可选 port；不得包含用户名、密码、路径、查询串、fragment 或通配符。

建议修复：使用 URL 解析器逐项校验来源结构，并增加 IPv6、端口、多来源、尾斜杠、凭据、路径、query 和 fragment 的正反用例。

### DEF-REAL-FS01-004：REAL-FS-01 实施记录引用了不存在的共享文档路径

| 项目 | 内容 |
| --- | --- |
| 优先级 | P3 |
| 类型 | 文档一致性、可追踪性 |
| 影响范围 | 实施记录、后续 Agent 交接 |
| 是否阻断 | 否 |
| 建议负责 Agent | 全栈开发工程师Agent |

实际结果：实施记录引用 `共享记忆文档/CRM智能聊天系统产品需求文档（PRD）-v2.0.md` 和 `共享记忆文档/CRM智能聊天系统管理端接口文档-v1.0.md`，但实际权威文件名分别为 `智能客服平台 — 产品需求文档（PRD）V2.0.md` 和 `智能客服平台 — 管理端接口文档.md`。

预期结果：交付记录中的依据路径应可定位到当前权威文档。

建议修复：只修正当前实施记录中的链接文字，不覆盖或删除历史测试证据。

## 7. 文档状态观察

### OBS-REAL-FS01-001：部分架构文档仍将 DEF-P4-AI-008/009 标记为未关闭

`ARCH-001-SYS-v1.4`、`ADR-004` 和生产放行检查表仍使用修复前状态；当前权威结论是 `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-014.md` 已确认 `DEF-P4-AI-001～012` 全部 Closed。建议架构师同步为“历史风险已关闭，真实模型与生产门禁仍待完成”。该观察不改变本报告对 REAL-FS-01 的失败结论。

## 8. 验收与回归建议

- `REAL-FS-01` 判定为不通过；修复 `DEF-REAL-FS01-001～003` 后必须由测试工程师独立复测。
- 在 P1 关闭前，不配置真实 TikTok OAuth 回调、不注入真实 TikTok/DeepSeek 密钥、不执行真实平台或模型联调。
- P1/P2 关闭后，至少重跑：日志哨兵矩阵、Nginx OAuth 访问日志、生产 Compose 主机/CI 注入、开发 `.env` 隔离、CORS URL 语法、后端 489 项隔离数据库回归、前端构建、Compose 合并和健康检查。
- 真实 TLS、固定出口 IP、真实备份恢复仍需在生产等价隔离环境生成专项证据；本报告不能替代后续 REAL-FS-02～05 和最终生产放行报告。
- 当前高风险开关保持全部关闭是正确状态，修复密钥注入时不得顺带打开任何能力开关。

## 9. 执行命令与证据摘要

主要执行命令：

```text
uv lock --check
ruff check app scripts tests
ruff format --check app scripts tests
mypy app scripts
pytest -q -rs --basetemp=<project-local-temp>
scripts/run-postgres-integration-tests.ps1
alembic upgrade head / downgrade 017 / upgrade head
uv audit --locked
npm run lint
npm run typecheck
npm run test
npm run build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml config
nginx -t（一次性 nginx:1.27.5-alpine 容器）
restore-postgres.ps1 -WhatIf
restore-minio.ps1 -WhatIf
```

证据摘要：

- 后端默认回归 481 passed、8 skipped；隔离 PostgreSQL 489 passed、0 skipped。
- 迁移 001→018、018→017→018，最终恢复 `018_ai_observability (head)`。
- 前端 22 passed、14 个静态页面构建成功。
- 依赖审计未发现已知漏洞。
- 本轮所有临时容器和测试缓存已清理；未修改产品代码。
