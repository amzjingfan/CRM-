# 生产配置与基础设施运行说明

本目录说明 REAL-FS-01～04 的安全运行面。OAuth、真实只读、Webhook 和人工确认普通消息已具备工程实现，但尚未完成真实店铺正式验收，因此所有 `REAL_TIKTOK_*` 开关默认保持 `false`；高风险写入和自动回复必须固定关闭。

2026-09-09：当前 staging 采用 `/home/crmdeploy` 下 Rootless Docker，独立域名为 `staging.hophorsefit.com`。唯一操作手册见 [`../staging/rootless/README.md`](../staging/rootless/README.md)，架构边界见 ADR-007。本文的 production 地址和 Compose 示例保留作为生产契约；production 最终运行方式尚未决定，不能直接套用到公司系统 Docker。系统 Docker 与现有公司容器禁止停止、重启、迁移、修复或接管。

## 1. 外部基础设施前置条件

- 域名 `www.hophorsefit.com` 的 A/AAAA 记录指向部署入口。
- 云主机、安全组或负载均衡器只对公网开放 80/443；PostgreSQL、Redis、MinIO、backend 和 frontend 不直接暴露。
- 为服务器或 NAT 网关分配固定公网出口 IP，将其作为 `TIKTOK_EGRESS_IP`，后续加入 TikTok IP 白名单。
- TLS 证书目录位于仓库外，包含 `fullchain.pem`、`privkey.pem`，仅部署账户可读。
- BGE 模型目录位于仓库外，例如 `/srv/crm/models`；只读挂载给模型服务，不随 Git checkout 或应用镜像更新。
- 真实密钥由主机环境、CI/CD Secret 或云密钥管理系统注入，不写入仓库和命令历史。
- 生产 Compose 会重置基础服务的开发 `.env` 注入；TikTok/DeepSeek 凭据只通过
  显式环境映射进入服务。Compose 插值必须使用仓库外生产文件或 CI 环境，不能依赖仓库 `.env`。

生产容器按职责使用以下最小密钥矩阵：

| 服务 | 公共运行配置 | TikTok 平台域 | DeepSeek 模型域 | 检索服务 Token |
| --- | --- | --- | --- | --- |
| `backend` | 是 | 是 | 是 | AI Profile 下是 |
| `worker` | 是 | 是 | 否 | 否 |
| `jobs` | 是 | 是 | 是 | AI Profile 下是 |
| `agent-worker` | 是 | 否 | 是 | 是 |
| `retrieval-model-service` | 否 | 否 | 否 | 是 |

`retrieval-model-service` 不接收数据库、Redis、MinIO、JWT、TikTok 或 DeepSeek 凭据；
它只运行本地 BGE 模型并接收自身服务 Token。新增服务或调整职责时必须同步修改此矩阵和
`backend/tests/test_real_runtime_config.py`，不能把平台与模型凭据重新放回公共锚点。

应用会校验 `TIKTOK_EGRESS_IP` 的格式，但无法证明云网络实际使用该地址。正式联调前由运维在目标主机查询公网出口地址，并与云控制台、TikTok 白名单三方核对。

## 2. 最小生产配置

必须安全注入：

```text
DATABASE_URL
REDIS_URL
MINIO_ENDPOINT
MINIO_ACCESS_KEY
MINIO_SECRET_KEY
JWT_SECRET_KEY
CORS_ORIGINS=https://www.hophorsefit.com
PUBLIC_BASE_URL=https://www.hophorsefit.com
PUBLIC_API_BASE_URL=https://www.hophorsefit.com/v1
TIKTOK_EGRESS_IP
TIKTOK_APP_KEY
TIKTOK_SERVICE_ID
TIKTOK_APP_SECRET
TIKTOK_OAUTH_REDIRECT_URI
TIKTOK_OAUTH_MARKET=ROW
TIKTOK_OAUTH_STATE_TTL_SECONDS=600
TIKTOK_TOKEN_REFRESH_POLL_SECONDS=300
TIKTOK_TOKEN_REFRESH_LEAD_SECONDS=86400
TIKTOK_TOKEN_REFRESH_BATCH_SIZE=20
TIKTOK_REQUIRED_SCOPES=seller.authorization.info,seller.order.info,seller.customer_service,seller.logistics
TIKTOK_WEBHOOK_SECRET
TIKTOK_CREDENTIAL_ENCRYPTION_KEY
DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL
LLM_PRIMARY_PROVIDER
LLM_PRIMARY_MODEL
LLM_TIMEOUT_SECONDS
LLM_MAX_ATTEMPTS
CHAT_STREAM_TIMEOUT_SECONDS
CHAT_SSE_HEARTBEAT_SECONDS
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
TLS_CERT_DIR
RETRIEVAL_MODEL_ASSET_DIR
BACKEND_IMAGE
FRONTEND_IMAGE
RETRIEVAL_MODEL_SERVICE_IMAGE
POSTGRES_IMAGE
REDIS_IMAGE
MINIO_IMAGE
NGINX_IMAGE
```

服务器模型目录必须具有以下固定结构：

```text
/srv/crm/models/
├─ bge-m3/
│  ├─ config.json
│  ├─ pytorch_model.bin
│  └─ tokenizer.json
└─ bge-reranker-large/
   ├─ config.json
   ├─ model.safetensors
   └─ tokenizer.json
```

权重通过受控文件传输或服务器资产管理流程放入该目录，不通过 Git、GHCR 应用镜像或
GitHub Secret 传输。仓库外环境文件设置 `RETRIEVAL_MODEL_ASSET_DIR=/srv/crm/models`；
staging 门禁会拒绝相对路径、Git checkout 内路径、路径链或六个文件中的符号链接/reparse point，
以及缺少任一必需模型运行文件的目录。生产 Compose
只读挂载该目录到 `/models`，并固定启用 `RETRIEVAL_MODEL_VERIFY_HASHES=true`；模型服务
启动时会按代码内固定 SHA-256 复核约 4.5 GB 权重，因此首次启动时间会相应增加。
门禁通过 `git rev-parse --show-toplevel` 识别整个 checkout 边界，嵌套产品目录不能把同一
工作树中的兄弟目录误判为仓库外资产；服务器模型目录及其必需文件必须是普通目录/文件，
不能通过符号链接或 Windows Junction 指回 checkout。

生产基础 Compose 的所有能力开关保持：

```text
ALLOW_MOCK_PLATFORM_ADAPTERS=false
REAL_TIKTOK_READ_ENABLED=false
REAL_TIKTOK_WEBHOOK_ENABLED=false
REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false
REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false
LLM_ENABLED=false
LLM_LIVE_EVAL=false
AI_TRANSLATION_ENABLED=false
AI_MARKETING_ENABLED=false
AUTO_REPLY_ENABLED=false
```

### 不可变镜像供应链

生产 Compose 不再在目标主机临时构建 backend、worker、jobs、agent-worker、frontend 或
retrieval-model-service，而是要求 `BACKEND_IMAGE`、`FRONTEND_IMAGE`、
`RETRIEVAL_MODEL_SERVICE_IMAGE` 使用完整的
`repository@sha256:<64 hex>`。PostgreSQL、Redis、MinIO 和 Nginx 的默认引用也已固定
Docker Hub 多架构清单摘要；仓库外环境文件如覆盖这些变量，同样必须使用完整摘要。

应用镜像由 `.github/workflows/publish-images.yml` 发布到：

```text
ghcr.io/cp11-gh/crm-backend
ghcr.io/cp11-gh/crm-frontend
ghcr.io/cp11-gh/crm-retrieval-model-service
```

三个发布 job 均绑定 main-only 的 GitHub `image-publishing` Environment，同时检查
`github.ref` 和当前远端 `main` SHA。工作流要求输入完整 Git commit SHA，不会推送 `latest`，
而是生成与提交绑定的候选标签、真实 RepoDigest 和 30 天低敏 JSON 证据制品。最终
`main@f7c0f9f9dd9a8c7b36a07145c053db7df23a15b8` 的三类应用镜像已由 run
`34178017173` 发布，完整摘要记录在 `release/images/mvp-production-gates.json`。正式部署前
历史版本的部署需把对应摘要同步到仓库外配置并由操作人复核；本次 Rootless staging 候选要求见下段。仓库示例值不是目标机配置证据。

上述 `f7c0f9f9` 是历史发布基线。本次 Rootless staging 改动必须在合并 main 后重新发布三个应用镜像，并将完整 main SHA 与三条 `repository@sha256:<64-hex>` 关联到机器可读发布证据；历史清单不能证明包含新代码。历史镜像的 staging OAuth 仍校验 www 地址，上一版回滚必须先确认兼容性。当前没有新候选发布或真实回滚成功证据。

前端镜像把 `NEXT_PUBLIC_API_BASE_URL` 固定为同源 `/v1`，因此同一不可变镜像可通过反向代理
部署到 staging 和生产域名，不需要为不同域名重新构建。

`Staging production gates` 使用工作流自带的 `GITHUB_TOKEN` 登录 GHCR，权限固定为
`contents: read` 和 `packages: read`。如 GHCR 包保持私有，必须确保三个容器包允许
`CP11-gh/CRM` 仓库的 Actions 读取；不在服务器环境文件中保存 GitHub 个人访问令牌。

完成 OAuth、真实只读和 Webhook 门禁后，人工消息灰度只能显式叠加
`docker-compose.tiktok-manual.yml`。该叠加文件只允许 backend 读取
`REAL_TIKTOK_MESSAGE_WRITE_ENABLED`，Worker、自动回复和高风险写入仍固定关闭：

```powershell
docker compose --env-file C:\secure\crm-production.env -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.tiktok-manual.yml config --services
```

首次灰度固定为单店铺、单渠道、单操作人。开启顺序为只读、Webhook、人工普通消息；
每一步均需测试工程师证据和架构师放行。不得仅因配置可以启动就宣称生产接入完成。

### DeepSeek 内部草稿 SSE 灰度

REAL-FS-05 只开放认证员工按需生成内部草稿。生产环境文件至少设置：

```text
LLM_ENABLED=true
LLM_PRIMARY_PROVIDER=deepseek
LLM_PRIMARY_MODEL={架构师和AI工程师确认的模型}
DEEPSEEK_API_KEY={密钥系统注入}
DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_TIMEOUT_SECONDS=30
LLM_MAX_ATTEMPTS=2
CHAT_STREAM_TIMEOUT_SECONDS=180
CHAT_SSE_HEARTBEAT_SECONDS=15
AI_TRANSLATION_ENABLED=false
AI_MARKETING_ENABLED=false
AUTO_REPLY_ENABLED=false
```

必须使用 `ai` profile 和两个受控叠加文件；配置检查只输出服务名：

```powershell
docker compose --profile ai --env-file C:\secure\crm-production.env -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.ai.yml -f docker-compose.deepseek-sse.yml config --services
docker compose --profile ai --env-file C:\secure\crm-production.env -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.ai.yml -f docker-compose.deepseek-sse.yml pull backend retrieval-model-service
docker compose --profile ai --env-file C:\secure\crm-production.env -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.ai.yml -f docker-compose.deepseek-sse.yml up -d --no-build --wait --wait-timeout 600 backend retrieval-model-service
```

`docker-compose.deepseek-sse.yml` 只允许 backend 读取 `LLM_ENABLED`；jobs 和 agent-worker
仍固定关闭 LLM、翻译、营销和自动回复。`POST /v1/chat/query` 等待安全草稿期间每隔
`CHAT_SSE_HEARTBEAT_SECONDS` 发送 SSE 注释心跳，总时长超过
`CHAT_STREAM_TIMEOUT_SECONDS` 会取消工作流并返回低敏 `error + done(timeout)`。
浏览器取消或断线也会取消仍在运行的工作流，避免继续消耗模型配额。

认证、权限和请求频率限制发生在流建立前，继续返回统一 HTTP JSON 401/403/429；流已经
接受后发生的模型限流、超时和依赖错误使用既有 SSE `error + done` 终态。服务端只传输
安全检查完成后的草稿分块，不直出模型原生 Token，也不自动发送 TikTok 消息。

TikTok 应用后台的重定向地址必须与 `TIKTOK_OAUTH_REDIRECT_URI` 完全一致：

```text
https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback
```

生产 Compose 要求显式提供该变量；应用在 integration 和 production
启动时会校验其为上述固定值。staging 则精确要求
`https://staging.hophorsefit.com/v1/integrations/tiktok/oauth/callback`。
OAuth start/callback 还会再次校验。HTTP、其他主机、
其他路径、query 和 fragment 均会在跳转 TikTok 前失败关闭。该变量是应用对
Partner Center 外部配置的部署断言，不作为 TikTok 授权 URL 参数发送；发布人员仍须
在 Partner Center 的应用配置页逐字核对实际 Redirect URL，并保留发布截图或审批证据。

`TIKTOK_CREDENTIAL_ENCRYPTION_KEY` 至少 32 个随机字符，必须与数据库备份采用不同密钥并单独备份。
授权 `state` 只在 Redis 保存哈希键，默认 10 分钟且原子消费；Access Token 和 Refresh Token
使用 AES-256-GCM 按内部店铺、外部店铺和凭证类型绑定后保存。授权开始前不需要打开任何
`REAL_TIKTOK_*` 能力开关；这些开关属于后续真实 Adapter 放行门禁。

Jobs Worker 按 `TIKTOK_TOKEN_REFRESH_POLL_SECONDS` 扫描即将过期的 TikTok 渠道，默认提前
24 小时刷新且单轮最多处理 20 条。认领使用 PostgreSQL `FOR UPDATE SKIP LOCKED`；刷新后
必须重新校验卖家类型、Scope、`open_id` 和唯一授权店铺。任何主体或店铺变化都会把渠道
标记为 `expired` 并要求重新授权，不得继续使用新 Token。

将生产变量保存在仓库外、仅部署账户可读的环境文件中。显式 `--env-file`
会替代默认 `.env` 的 Compose 插值来源；配置检查只输出服务名，避免展开敏感值：

```powershell
docker compose --env-file C:\secure\crm-production.env -f docker-compose.yml -f docker-compose.prod.yml config --services
```

CI/CD 场景可直接注入同名环境变量，且环境变量优先于 `--env-file`。禁止执行会打印
完整合并配置的 `config` 命令，也禁止把生产环境文件放入仓库。

## 3. HTTPS 和健康检查

生产叠加文件新增 Nginx HTTPS 入口：

```text
https://www.hophorsefit.com/       → frontend:3000
https://www.hophorsefit.com/v1/*   → backend:8000
```

HTTP 自动跳转 HTTPS。SSE 路径关闭代理缓冲，其他应用容器不映射宿主机端口。启动后验证：

```powershell
curl.exe --fail https://www.hophorsefit.com/healthz
curl.exe --fail https://www.hophorsefit.com/v1/health
curl.exe --fail https://www.hophorsefit.com/v1/health/ready
```

`/v1/health/ready` 只返回组件级 `ok/disabled/error`，不返回连接 URL、模型路径、Token、密钥或底层异常正文。`llm_provider=ok` 只表示服务端配置契约完整，不代表 DeepSeek 公网实时可用；真实可用性必须通过受控草稿请求和监控确认。

## 4. 日志和告警

应用日志保持单行 JSON。统一日志出口会对 Bearer、JWT、API Key、任意
`*_secret`、Token、OAuth Code/State、连接串密码、客户消息和地址字段进行纵深脱敏；
同一敏感字段同时覆盖 JSON、`key=value` 和 HTTP Header/诊断文本常见的 `key: value` 格式；
Nginx 访问日志只记录不含查询串的规范化 URI。业务代码仍禁止主动记录完整请求体。
OAuth callback 的 Nginx 错误日志也被关闭，避免上游失败时原生 request line
带出 code/state；该路由通过应用侧已脱敏 trace 日志、健康检查和平台请求 ID 排障。

生产日志平台至少对以下事件告警：

- `not_ready` 持续 2 分钟；
- `http_client_request`、`http_client_transport`、`http_server_access`、`http_server_runtime`、`database_engine_event` 和 `database_migration_event` 异常增长；这些事件只由受控 logger 命名空间映射，不包含原始 URL、SQL 或消息正文；
- `retrieval_model_service_load_failed`、`retrieval_embedding_failed`、`retrieval_rerank_failed` 或 `agent_task_failed` 出现；这些第一方关键失败使用显式固定事件，不依赖自由文本推断；
- 认证失败、Webhook 验签失败或第三方错误突增；
- 日志出现脱敏标记异常增长；
- Worker 连续重启；
- PostgreSQL、Redis、MinIO 不可用；
- 任意真实写操作进入 `unknown`。
- `chat_stream_timeout`、`chat_stream_agent_failed` 或 SSE 失败率持续升高。

50 个授权客户端压测必须使用仓库外凭证池，并把低敏结果写到仓库外证据目录。50 个不同用户仍共享压测机来源 IP，因此只能在隔离的 integration/staging 测试窗口叠加专用限流文件；日常生产不得长期使用该叠加：

```powershell
docker compose --profile ai --env-file C:\secure\crm-integration.env -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.ai.yml -f docker-compose.deepseek-sse.yml -f docker-compose.sse-load-test.yml up -d --wait --wait-timeout 600 backend
Set-Location backend
uv run python -m scripts.load_test_sse --credentials-file D:\secure-test-data\sse-clients.json --concurrency 50 --server-ip-rate-limit 60 --first-delta-p99-limit-ms 3000 --total-p99-limit-ms 5000 --output D:\secure-test-data\sse-evidence.json
```

专用叠加通过 `SSE_LOAD_TEST_APP_ENV=integration|staging` 覆盖生产拓扑中的 backend 环境，把单 IP 窗口限额设为 60，并设置 `SSE_LOAD_TEST_ENABLED=true`；development 或 production 会失败关闭。脚本通过 `--server-ip-rate-limit 60` 声明并预检同一值。全部 50 个请求必须收到 `done.reason=completed` 且产生首个安全 `delta`；首个安全 `delta` P99 必须严格 `<3000ms`，总耗时 P99 必须严格 `<5000ms`，等于阈值也失败。两个 CLI 阈值只能收紧、不能超过架构上限，JSON 证据同步记录阈值、毫秒单位、严格比较语义和最终门禁结果。任一完整性或 SLA 条件不满足时脚本以非零状态退出；SSE 内部限流、超时、认证拒绝、失败和不完整流均独立计数。压测后移除 `docker-compose.sse-load-test.yml` 并重建 backend，恢复默认限流。五日稳定性由测试工程师连续五日执行同一受控场景并汇总可用性、首个安全 `delta` P50/P99、总耗时 P50/P99 和失败原因；工程脚本本身不构成真实模型质量或生产放行。

本项目不绑定具体云告警供应商；在选定部署平台后，将上述 JSON 事件接入该平台原生告警即可。

## 5. 备份、恢复和回滚

- PostgreSQL 和 MinIO 使用 `scripts/backup-*`、`scripts/restore-*`，详细步骤见 `deploy/postgres/README.md`。
- Redis 当前只保存可重建缓存、限流状态和短期任务协调数据，不作为长期业务事实备份；灾难恢复时使用空 Redis，并通过数据库状态恢复 Worker。
- 回滚优先关闭最小功能开关并重启对应服务，不删除数据库业务记录。
- DeepSeek 草稿异常时先将 `LLM_ENABLED=false`，移除 `docker-compose.deepseek-sse.yml` 叠加并重建 backend；本操作不修改 Agent 运行历史，也不打开 Mock、翻译、营销或自动回复。
- 基础生产 Compose 的四个真实 TikTok 开关都为 false。人工发送异常时优先把 `REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false` 并重启 backend；`unknown` 消息不得重试，必须在 TikTok 后台人工对账。高风险写入和自动回复即使出现在外部环境文件中也会被叠加文件及应用启动门禁拒绝。
- 恢复后依次验证迁移 head、`/v1/health/ready`、店铺隔离、审计链路和任务积压。

### staging 门禁和镜像回滚脚本

GitHub 仓库已经建立 `staging` Environment，并把可部署来源限制为 `main`。实际运行前，
运维仍需连接带 `self-hosted, linux, x64, crm-staging` 标签的专用 runner，并在 Environment 中设置：

```text
Secret: CRM_STAGING_ENV_FILE   # runner 上仓库外环境文件的绝对路径
Variable: CRM_STAGING_BASE_URL # staging 的 HTTPS 基础地址
```

不得把环境文件正文保存成 GitHub Secret、提交到仓库或贴入工作流输入。配置完成后，通过
`Staging production gates` 手工工作流依次执行 `validate`、`deploy`；回滚必须另行提供
候选和上一版本的六个完整应用镜像摘要（backend、frontend、retrieval model 各一组）。
工作流和脚本都拒绝 `production`。

Rootless staging 的固定参数为：

```text
DOCKER_HOST=unix:///run/user/1004/docker.sock
COMPOSE_PROJECT_NAME=crm-staging
CRM_STAGING_ENV_FILE=/home/crmdeploy/config/crm-staging.env
CRM_STAGING_BASE_URL=https://staging.hophorsefit.com
```

两个门禁脚本必须传入 `-DockerHost unix:///run/user/1004/docker.sock`，内部清除继承的
`DOCKER_CONTEXT` 并固定叠加 `docker-compose.rootless-staging.yml`，高端口只绑定回环。
直接预检、部署、入口撤除和回滚命令统一见 Rootless staging 运行手册；不要沿用旧 Windows
主机路径或 `staging.example.com` 示例。全部真实能力强制关闭的基础脚本不能用来直接开启 G1～G6。

真实回滚由 `Invoke-StagingRollbackDrill.ps1 -Execute` 完成，固定顺序是：先强制关闭全部真实
能力，再切换上一版本 RepoDigest，最后复核三个健康端点。`-ValidateOnly` 只验证计划和输入，
不能作为真实部署或回滚通过证据。目标机必须安装 Docker CLI 和 Compose 插件（本次目标 5.3.1，待实测）；两个实时
脚本的每次 `docker compose up` 都使用 `--wait --wait-timeout 600`，只有包括
`retrieval-model-service` 在内的容器达到 running/healthy 后才继续外部健康检查并写入
`passed` 证据。

`基础运行面就绪`、`失败关闭部署通过`、`G1～G6 真实门禁通过` 与 `production 放行`
是独立结论，任何前项不推导后项。当前 DNS、TLS、模型、runner、公开健康、备份恢复与回滚
仍待真实验证；生产签署继续阻塞。
