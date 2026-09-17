# CRM 智能聊天系统

当前已完成全栈 Phase 4 和 AI Agent Phase 1～4 的确定性工程实现：FastAPI 模块化单体、Next.js 管理端、PostgreSQL/pgvector、Redis、MinIO、Webhook/Jobs/Agent Worker、JWT/RBAC、浏览器 HttpOnly Cookie 认证、契约级平台适配器、FAQ 知识库、受控业务工具、主动营销、SSE 建议、运营看板、Agent 运营配置和系统设置，以及模型适配、五类意图识别、本地 BGE 混合检索、LangGraph 单 Agent 工作流、店铺级回复策略、中英翻译、AI 营销文案和安全接管闭环。

BGE-M3 与 `bge-reranker-large` 固定版本模型已经接入单实例内部模型服务。数据库迁移 `014_bge_hybrid` 将知识向量改为 1024 维，并新增 `pg_trgm` 词法索引；检索链路为 Dense Top 20 + 词法 Top 20，经 RRF 融合候选 Top 20，再由 Cross-Encoder 输出最终 Top 5。AI 功能仍默认关闭，生产启用前必须完成独立质量、容量和阈值评测。

> TikTok OAuth、真实只读、官方 Webhook 和人工确认普通文本消息已具备工程实现，但尚未完成真实店铺独立联调。真实人工消息默认关闭；发券、改地址、营销和自动回复仍禁止真实执行。公开建议和 SSE 只返回可人工采用的安全草稿，不会自动发送。

## 版本控制与发布基线

本文件位于 Git 仓库根目录，产品代码、架构、正式测试报告和治理文档使用同一条提交历史。后续开发统一采用 GitHub Flow：从 `main` 创建短期分支，通过 Pull Request、CI 和审阅后 squash merge。完整规则见 [`docs/governance/GOVERNANCE.md`](docs/governance/GOVERNANCE.md)，开发规范见 [`docs/engineering/DEVELOPMENT.md`](docs/engineering/DEVELOPMENT.md)。

当前预发布工程基线标识为 `v0.1.0-mvp.20260907`，应用版本为 `0.1.0`，数据库迁移 head 为 `023_marketing_review_idempotency`。机器可读清单位于工作区根目录 `release/baselines/v0.1.0-mvp.20260907.json`；它固定构建输入、迁移、评测数据和已取得的镜像摘要，并如实记录前端镜像及外部镜像摘要仍未闭环。该标识不表示真实平台、性能、稳定性或最终生产放行已经通过。

## 目录

- `src/backend/app/auth`：JWT、Cookie、CSRF、登录限流和 RBAC。
- `src/backend/app/stores`：店铺、渠道授权和店铺访问边界。
- `src/backend/app/integrations`：平台适配器、Webhook 接收和数据库 Worker。
- `src/backend/app/agent`：LLM/Embedding/Reranker Provider、FAQ 切分、混合 RAG、LangGraph 工作流、店铺回复策略、翻译、营销文案、版本化 Prompt、脱敏、安全门禁和运行追踪。
- `src/backend/app/retrieval_model_service`：只读加载本地 BGE-M3 与 Reranker 的单实例内部模型服务。
- `src/backend/app/knowledge_base`：FAQ 分类、条目、导入任务、切片存储和向量化交接端口。
- `src/backend/app/tools`：白名单工具契约、权限/店铺校验、幂等执行、结果追踪和模拟发券。
- `src/backend/app/marketing`：弃单/中差评活动、冷却频控、重试和转化事件。
- `src/backend/app/jobs`：知识库导入和主动营销异步任务。
- `src/backend/app/chat`：可信会话建议、POST SSE 传输层分块和默认关闭的 Agent 自动任务 Worker。
- `src/backend/app/dashboard|agent_management|users`：每日指标、运营看板、Agent 配置/脱敏日志和团队管理。
- `src/backend/app/workspace`：会话列表、消息、分配、转人工、订单/物流、改地址和发券入口。
- `src/backend/app/customers|conversations|orders|audit`：Phase 2 领域模型。
- `src/tests`：统一收纳分类后的后端、前端与 PostgreSQL 测试，AI/RAG 版本化数据集与结果，以及已忽略的项目内临时输出根 `src/tests/.artifacts/`。
- `src/deploy/models`：本地 BGE 模型说明和资产清单；大体积权重由 `.gitignore` 排除。
- `src/backend/migrations`：001–023 可逆迁移；019 强制一个内部店铺只能绑定一个 TikTok 渠道，020 增加知识语义审批，021 增加平台写结果 `unknown` 消息状态，022 增加 AI 交付与营销复核，023 加固营销复核幂等。
- `src/frontend/app/workspace|dashboard|knowledge|marketing|agents|settings`：工作台、看板、知识库、营销、Agent 运营和系统设置。
- `src/compose/docker-compose.yml`：基础服务和默认关闭的 `ai` Profile；`src/compose/docker-compose.ai.yml` 在启用本地 BGE 时增加模型健康门禁和 1024 维运行配置；`src/compose/docker-compose.gpu.yml` 只增加 GPU 设备预留。

## 本地启动

1. 创建配置并替换开发密钥：

```powershell
Copy-Item src/config/.env.example src/config/.env
```

2. 启动基础设施和应用：

```powershell
.\src\scripts\start-local.ps1
```

开发容器的 `/app/.next` 使用独立命名卷，与宿主机 `src/frontend/.next` 隔离。因此可以在前端容器运行期间执行宿主机 `npm run build`，不会覆盖 `next dev` 正在使用的服务端 chunk。不要删除 `src/compose/docker-compose.yml` 中的 `frontend_next_cache:/app/.next` 挂载。

如果 Docker Hub 在当前网络不可访问，不需要修改 Dockerfile。项目允许通过 `src/config/.env` 覆盖前端基础镜像和 npm registry：

```powershell
# 示例：使用组织内部镜像仓库和 npm 代理。地址由部署环境维护者提供。
$env:FRONTEND_NODE_IMAGE = "registry.example.com/library/node:20-alpine"
$env:FRONTEND_NPM_REGISTRY = "https://npm.example.com"
docker compose -f src/compose/docker-compose.yml build frontend
docker compose -f src/compose/docker-compose.yml up -d frontend
Remove-Item Env:FRONTEND_NODE_IMAGE
Remove-Item Env:FRONTEND_NPM_REGISTRY
```

公开镜像加速地址的可用性和认证策略会变化，只能在团队完成来源审核后通过 `FRONTEND_NODE_IMAGE` 临时配置，不在仓库中硬编码。生产环境应使用内部镜像仓库并固定镜像 digest，避免浮动标签或未经审核的第三方镜像进入发布链路。

完全离线时，由环境维护者在联网机器导出并传入镜像文件，再执行：

```powershell
docker load --input node-20-alpine.tar
docker compose -f src/compose/docker-compose.yml build frontend
docker compose -f src/compose/docker-compose.yml up -d frontend
```

如果当前仅需要继续前端开发，而 Docker 外部网络暂时不可用，可以使用项目提供的本地降级脚本：

```powershell
.\src\scripts\start-frontend-local.ps1
```

首次运行且尚未安装依赖时使用：

```powershell
.\src\scripts\start-frontend-local.ps1 -InstallDependencies
```

该脚本会检查 Node.js/npm、依赖目录和端口参数，并在当前进程中注入 API 地址。它只解决开发连续性，不替代正式的 frontend Compose 验收。

3. 执行迁移：

```powershell
docker compose -f src/compose/docker-compose.yml exec backend alembic upgrade head
```

4. 创建或重置本地管理员（密码只能通过环境变量传入）：

```powershell
$env:ADMIN_PASSWORD = "请替换为高强度开发密码"
docker compose -f src/compose/docker-compose.yml exec backend python scripts/create_admin.py
Remove-Item Env:ADMIN_PASSWORD
```

5. 可选：创建契约测试店铺与三平台渠道：

```powershell
docker compose -f src/compose/docker-compose.yml exec backend python scripts/seed_phase2_demo.py
```

为现有客服分配店铺角色：

```powershell
docker compose -f src/compose/docker-compose.yml exec backend python scripts/assign_store_role.py --email agent@example.com --store demo-store --role agent
```

## 地址

- 管理端：http://localhost:3000
- 后端健康检查：http://localhost:8000/v1/health
- 后端就绪检查：http://localhost:8000/v1/health/ready
- OpenAPI：http://localhost:8000/docs
- MinIO Console：http://localhost:9001

## Webhook 与 TikTok 真实只读

- 本地 TikTok Mock 回归使用 `X-TTS-Signature`；真实模式严格使用官方 `Authorization` Header，HMAC-SHA256 输入为 `TIKTOK_APP_KEY + 原始请求体`，密钥为 `TIKTOK_APP_SECRET`。
- Shopee、Amazon：Phase 2 Mock 使用 `X-Mock-Signature`，输入为原始请求体。
- TikTok 真实只读固定官方域名，订单详情使用 `GET /order/202507/orders`；店铺、订单列表、物流、会话消息和 Webhook 订阅核对使用各自官方只读端点。Access Token 只从渠道密文解密后进入 `x-tts-access-token` Header。
- 官方 1 号订单事件先通过只读详情补全后落库；14 号买家消息标准化为统一消息；6/7 号授权生命周期事件停用凭证或标记待重新授权；未知主题只保留摘要并安全忽略。
- 原始载荷上限 1 MiB；事件先写 `webhook_events`，由独立 Worker 处理。

演示外部店铺 ID：`demo-tiktok-store`、`demo-shopee-store`、`demo-amazon-store`。

## 认证与安全

- 浏览器使用 `crm_access_token`、`crm_refresh_token` HttpOnly Cookie。
- `crm_csrf_token` 用于双提交 CSRF；Cookie 写操作同时校验 `Origin`。
- 前端不保存、不读取 JWT；401 只刷新并重试一次。
- 非浏览器客户端仍可使用 `/v1/auth/login|refresh|logout` Token API。
- 系统级 admin 可访问全部有效店铺；supervisor/agent 仅访问显式授权店铺。
- 生产环境设置 `ALLOW_MOCK_PLATFORM_ADAPTERS=true` 会在启动阶段失败；`REAL_TIKTOK_READ_ENABLED`、`REAL_TIKTOK_WEBHOOK_ENABLED` 和人工普通消息只有在正式 App、加密、固定出口 IP 和完整 Scope 均配置后才能启用。普通消息开启时自动回复必须关闭；高风险写开关继续启动失败。
- TikTok 渠道页通过服务端 OAuth 接入：`state` 一次性绑定当前用户与内部店铺，回调验证卖家身份、Scope 和真实店铺后，才将 Access/Refresh Token 以 AES-256-GCM 密文保存。通用渠道 POST 在 Schema 和 Service 两层拒绝 TikTok，数据库也强制同一内部店铺只能绑定一个 TikTok 渠道。
- 人工普通消息要求工作台二次确认、`workspace.reply`、店铺权限和 `Idempotency-Key`。真实发送结果不可确认时记录 `unknown` 并熔断同店铺后续消息；管理员在 TikTok 后台核对后通过 `/v1/workspace/messages/{message_id}/reconcile` 留下审计并解除熔断。
- Jobs Worker 默认每 5 分钟扫描一次，并在 Access Token 到期前 24 小时采用 `FOR UPDATE SKIP LOCKED` 提前刷新。刷新结果必须保持 `open_id` 和已授权店铺连续；不一致或失败时状态变为 `expired` 并要求重新授权，不覆盖为成功凭证。
- TikTok 应用后台重定向地址固定为 `https://www.overselfx.com/v1/integrations/tiktok/oauth/callback`；integration/staging/production 启动以及 OAuth start/callback 都会失败关闭 HTTP、错误主机、错误路径、query 或 fragment，真实密钥只从服务端安全配置注入。

> 2026-09-09 勘误：上述跨环境相同回调约定已由当前 [`docs/operations/DEPLOYMENT.md`](docs/operations/DEPLOYMENT.md) 部署边界取代。staging 精确使用 `https://staging.overselfx.com/v1/integrations/tiktok/oauth/callback`；integration/production 保留 `https://www.overselfx.com/v1/integrations/tiktok/oauth/callback`。Rootless staging 操作见 `src/deploy/staging/rootless/README.md`，真实运行验收仍待执行。

## Phase 3 业务能力

- FAQ 支持分类、草稿、发布、归档，以及最大 10 MiB/5000 行的 CSV、XLSX 异步导入。
- FAQ 发布或正文修改会提升版本并将向量状态重置为 `pending`；只有当前版本的 `published + ready` 切片可被 AI 检索。
- 知识库页面按店铺展示 BGE-M3 向量化 `pending/processing/ready/failed` 汇总；只有 `published + failed` 条目可由具备 `knowledge.manage` 权限的运营人员人工重试。
- 写工具强制使用 `Idempotency-Key`；同键同请求重放终态结果，同键不同请求返回 `40901`，外部结果不确定时标记 `unknown` 且不自动重试。
- 地址修改只返回 `pending_confirmation`，不会覆盖权威订单地址；优惠券记录固定包含 `mocked=true`。
- 主动营销支持弃单和中差评触发、24 小时冷却、30 天最多 3 次、三档重试和转化标记。
- `content_mode=ai` 的营销事件默认停留在 `waiting_ai`；只有 `LLM_ENABLED=true` 且 `AI_MARKETING_ENABLED=true` 时才生成文案。文案必须通过确定性安全门禁，然后交给现有受控工具链路；Mock 发券和平台发送仍不代表真实联调。

## Phase 4 运营与稳定性能力

- `POST /v1/workspace/sessions/{session_id}/suggest` 返回一次性建议；`POST /v1/chat/query` 使用 Cookie、Origin 和 CSRF 校验，通过 `accepted/status/delta/result/error/done` SSE 事件传输。等待安全草稿期间发送无业务数据的 SSE 心跳，并受 `CHAT_STREAM_TIMEOUT_SECONDS` 总预算约束；模型超时、限流和依赖异常会以低敏 `error + done` 结束。`delta` 是全栈传输层分块，不代表模型原生 Token 流。
- 建议请求只接受会话 ID 和可选触发消息 ID，消息正文、最近 10 条历史和订单上下文均由服务端按店铺权限读取。建议不会执行写工具，也不会自动发送。
- Agent 运营管理允许编辑名称、说明、启停状态、白名单工具和受限 `reply_profile`；模型、Prompt、Embedding/Reranker 与置信度阈值只读。运行日志不返回消息、知识正文或模型完整输出。
- Webhook 可在 `AUTO_REPLY_ENABLED=true` 且店铺存在启用配置时创建唯一 Agent 任务；独立 Agent Worker 处理决策。当前 Mock 适配器固定 `real_writes=false`，自动发送在调用工具前进入人工复核/阻断状态。
- `metric_daily` 每五分钟幂等聚合当天和前一天，并记录 RAG 命中、Agent 工具成功、每日首输出 P95、Token 与显式单价估算成本；看板 1/7/30 天周期首输出 P95 直接基于对应店铺时区范围内的 `agent_runs.first_output_latency_ms` 原始样本计算，不取每日 P95 的最大值。无人工标签时意图准确率保持 `null`，不会由模型自信度伪造。`uv run python -m scripts.backfill_metrics --store-id UUID --start YYYY-MM-DD --end YYYY-MM-DD` 可回填指定日期。
- 团队禁用采用软状态并撤销 Refresh Token，禁止自我禁用和禁用最后一个有效管理员。supervisor/agent 角色必须显式指定店铺。
- 普通 API 有统一超时；SSE、Webhook 和上传使用独立策略。日志为单行 JSON，只保留低敏事件、模块和 trace ID。
- 生产部署使用 `src/compose/docker-compose.prod.yml`，由 Nginx 统一暴露 80/443，backend/frontend 和数据服务不映射宿主机端口；源码挂载和 reload 被移除，应用镜像使用非 root 用户。真实 TikTok 灰度需额外叠加 `src/compose/docker-compose.tiktok-manual.yml`。内部 DeepSeek 草稿 SSE 灰度使用 `ai` profile，并叠加 `src/compose/docker-compose.ai.yml` 与 `src/compose/docker-compose.deepseek-sse.yml`；只有 backend 可读取 `LLM_ENABLED`，后台任务、AI 翻译、AI 营销和自动回复保持关闭。

## AI Agent Phase 4 回复、翻译与营销能力

- `AgentReplyProfile` 支持 `friendly/professional/concise/empathetic` 四种固定语气、`auto/zh-CN/en` 回复语言、客服工作语言和经清洗的品牌名。公开 Agent 配置 API 可写受限 `reply_profile` 子对象，仍拒绝任意 Prompt、模型或阈值字段。
- 工作流先确定性识别 `zh-CN/en/mixed/unknown`，再执行结构化安全检查。模型自报声明和独立模型复核只增加门禁，不授予自动回复权限；`is_safe` 表示可供人工复核，`automatic_delivery_allowed` 才表示具备自动交付资格。当前知识库没有类型化事实范围和发布审批，因此即使模型逐字复制已发布 FAQ，也最高进入人工复核；只有代码根据单次真实订单/物流查询生成的有限状态模板可获得自动交付资格。
- 工具证据绑定当次 `tool_call_id + tool_name + store_id + subject_ids + mocked`。真实对象 ID 不发送给模型，查询工具的权威 `business_claims` 由服务端执行层生成；模型输出中的 `[SENSITIVE_ID]` 只在证据 ID、主体类型和动作全部一致时映射回权威对象。运行摘要只记录声明类型、动作和工具调用 ID，不记录原始订单号。跨订单、跨店铺或跨工具借用证据继续失败关闭。
- `AI_TRANSLATION_ENABLED=false` 默认不让额外翻译模型调用进入 SSE 关键路径。显式开启后，翻译结果使用 `trigger_message_id + source_text_sha256` 关联原文，不复制业务消息；公开建议和 SSE `result.translation` 仅返回低敏翻译字段，不返回 Provider、模型或 Token。
- 弃单和中差评 AI 节点只接收最小可信摘要并执行独立声明一致性复核。当前缺少可审计人工批准状态，因此营销结果固定要求人工复核、不返回可发送正文，也不进入发券或平台发送工具。
- 当前 Prompt 版本为 `faq-agent-workflow-v1.6.0`、`faq-answer-v1.5.0`、`faq-grounding-review-v1.5.0`、`tool-answer-v1.5.0`、`tool-grounding-review-v1.5.0`、`customer-translation-v1.0.0`、`marketing-copy-v1.3.0` 和 `marketing-copy-review-v1.0.0`。

生产 Compose 配置检查和启动示例：

```powershell
docker-compose --env-file C:\secure\crm-production.env -f src/compose/docker-compose.yml -f src/compose/docker-compose.prod.yml config --services
docker-compose --env-file C:\secure\crm-production.env -f src/compose/docker-compose.yml -f src/compose/docker-compose.prod.yml pull
docker-compose --env-file C:\secure\crm-production.env -f src/compose/docker-compose.yml -f src/compose/docker-compose.prod.yml up -d --no-build
```

生产环境文件必须位于仓库外，不能复用开发 `src/config/.env`。生产所需变量、HTTPS、固定出口 IP、密钥注入、日志告警和回滚说明见 `src/deploy/production/README.md`；备份恢复说明见 `src/deploy/postgres/README.md`。项目 PowerShell 脚本使用 UTF-8 BOM，并声明兼容 Windows PowerShell 5.1 与 PowerShell 7；提交前应使用两种解析器执行语法检查。

50 并发 SSE 工程压测使用 `src/backend/scripts/load_test_sse.py`。默认每组凭证只代表一个并发客户端，因此 50 并发需要 50 组不同授权用户的 Cookie 凭证。不同用户只能避开用户维度门禁，仍会共享单台压测机的来源 IP；执行前必须在隔离的 integration/staging 环境显式叠加 `src/compose/docker-compose.sse-load-test.yml`，把本次窗口的 IP 限额提高到 60。日常生产部署不得长期叠加该文件。凭证池 JSON 必须存放在仓库外，测试后立即安全删除：

```json
{
  "clients": [
    {
      "access_token": "replace-with-test-access-token-1",
      "csrf_token": "replace-with-test-csrf-token-1",
      "session_id": "authorized-session-uuid-1"
    },
    {
      "access_token": "replace-with-test-access-token-2",
      "csrf_token": "replace-with-test-csrf-token-2",
      "session_id": "authorized-session-uuid-2"
    }
  ]
}
```

```powershell
docker-compose --profile ai --env-file C:\secure\crm-integration.env -f src/compose/docker-compose.yml -f src/compose/docker-compose.prod.yml -f src/compose/docker-compose.ai.yml -f src/compose/docker-compose.deepseek-sse.yml -f src/compose/docker-compose.sse-load-test.yml up -d backend
Set-Location src/backend
uv run python -m scripts.load_test_sse --credentials-file D:\secure-test-data\sse-clients.json --concurrency 50 --server-ip-rate-limit 60 --first-delta-p99-limit-ms 3000 --total-p99-limit-ms 5000 --output D:\secure-test-data\sse-evidence.json
```

专用叠加通过 `SSE_LOAD_TEST_APP_ENV=integration|staging` 覆盖生产拓扑中的 backend 环境，并设置 `SSE_LOAD_TEST_ENABLED=true`；development 或 production 会失败关闭。`--server-ip-rate-limit` 是服务端本次实际 `CHAT_QUERY_LIMIT` 的低敏声明；声明值低于并发数时脚本会在联网前失败。单客户端冒烟仍可使用 `CRM_ACCESS_TOKEN`、`CRM_CSRF_TOKEN` 和 `--session-id`，但默认不能扩展为 50 并发。只有在隔离测试环境已经同步提高用户并发和频率限制后，才可显式传入 `--requests-per-credential`。性能门禁固定使用首个安全 `delta` P99 `<3000ms` 和总耗时 P99 `<5000ms` 的严格比较；CLI 参数只允许收紧这两个架构上限，不能放宽。全部请求还必须收到 `done.reason=completed` 且产生首个安全 `delta`，任一完整性或 SLA 条件不满足时脚本均以非零状态退出。JSON 证据会记录实际阈值、`strictly_less_than` 比较语义和最终门禁结果；HTTP/SSE 限流、超时、认证拒绝、失败和不完整流分别统计。输出不含 Token、CSRF、会话 ID、消息或模型正文，可连续五日保存到仓库外供测试工程师汇总。压测后必须移除 `src/compose/docker-compose.sse-load-test.yml` 叠加并重建 backend，恢复日常限流。确定性 Provider 结果不等同于真实模型生产 P99。

## AI Agent Phase 2

- FAQ 发布后由 Jobs Worker 原子认领，按最多 800 Token、重叠 80 Token 切分，并通过本地 BGE-M3 生成 1024 维归一化 Dense 向量。
- 只有当前店铺、`published + ready + current version` 的切片可进入 Dense 与 `pg_trgm` 双路召回；RRF 融合候选 Top 20 后，由 `bge-reranker-large` 重排序为最终 Top 5。
- Reranker 原始 logit 只用于排序，不直接进入最终业务置信度。2026-08-21 的版本化 FAQ 生产门禁评测将 Dense 门禁校准为 `>= 0.52`；trigram 门禁仍为 `>= 0.10`。阈值只适用于当前固定模型 Revision、评测集和检索实现，模型或数据分布变化后必须重新校准。
- LangGraph 工作流按“上下文→意图→工具门禁/RAG→草稿→安全复核→置信度”显式流转。
- 最终置信度为意图、检索和依据复核三项分数的最小值；`0.80/0.60` 只在确定性来源已经授予 `automatic_delivery_allowed` 后决定自动回复就绪、人工复核和转人工。模型自由文本和未具备类型化审批的 FAQ 即使高置信度也最高进入人工复核。
- `AUTO_REPLY_READY` 只表示答案满足条件，返回结果固定包含 `send_performed=false`，不创建消息或调用平台。
- 全栈内部调用入口为 `app.agent.factory.build_agent_workflow(session, settings)`；当前没有新增公开 HTTP API。

## AI Agent Phase 3

- Agent 仅通过 `AgentToolService → SqlAlchemyToolExecutor` 调用七个白名单工具，不直接访问平台 SDK 或绕过工具层写业务表。
- 查询参数只取自可信 `tool_context`；地址、发券和平台消息必须使用全栈层批准的精确参数与幂等键。
- 每次执行均写入 `tool_calls`；写操作、平台发送和转人工同时写入低敏 `audit_logs`，并关联 `agent_run_id/trace_id`。
- LangGraph 在 `TOOL_EXECUTED` 后只解释成功结果，并用独立 Prompt 校验工具引用、事实依据和完成声明。
- 工具失败、超时、权限拒绝、幂等冲突、非法引用或复核失败均隐藏候选话术并转人工；平台写超时标记 `unknown`，禁止自动重试。
- Mock 地址、优惠券和平台发送结果最高只能进入人工复核；高置信度真实查询只有逐字匹配代码模板且通过代码生成的对象声明校验时才可进入 `AUTO_REPLY_READY`，但不会自动发送。
- `AgentWorkflowResult` 返回低敏 `tool_calls` 摘要、`transfer_performed` 和固定的 `send_performed=false`。

## 本地 BGE 检索模型

当前状态为“固定资产已校验、运行时代码已接入、开发环境迁移、真实模型冒烟、质量门禁和容量门禁均已完成”：

| 模型 | Revision | 权重 | 状态 |
| --- | --- | --- | --- |
| `BAAI/bge-m3` | `5617a9f61b028005a4858fdac845db406aefb181` | `pytorch_model.bin`，1024 维 | Provider 已接入，默认关闭 |
| `BAAI/bge-reranker-large` | `55611d7bca2a7133960a6d3b71e083071bbfc312` | `model.safetensors` | Reranker 已接入，默认关闭 |

权重保存于 `src/deploy/models/bge-m3` 和 `src/deploy/models/bge-reranker-large`，不会提交到版本库。固定版本、SHA-256、大小和许可证见 `src/deploy/models/model-manifest.json`。

首次启用前先执行迁移，再使用 AI 叠加文件启动模型服务和 Jobs Worker。模型服务 Token 必须至少 32 个字符并使用随机密钥，禁止沿用示例值：

```powershell
docker-compose -f src/compose/docker-compose.yml exec backend alembic upgrade head
docker-compose -f src/compose/docker-compose.yml -f src/compose/docker-compose.ai.yml --profile ai up -d --build
# 已确认 Docker Desktop/WSL2 NVIDIA GPU 后才叠加 GPU 文件：
docker-compose -f src/compose/docker-compose.yml -f src/compose/docker-compose.ai.yml -f src/compose/docker-compose.gpu.yml --profile ai up -d --build
docker-compose -f src/compose/docker-compose.yml exec backend python scripts/verify_bge_hybrid_runtime.py
```

AI 叠加文件会显式启用 `EMBEDDING_ENABLED=true`，并让 backend、jobs 等待 `retrieval-model-service` 健康后启动，避免 Worker 抢跑把待回填 FAQ 批量标记为失败。应用启动时还会校验 `local_bge + BAAI/bge-m3 + 1024`、内部服务 URL 和 Token 强度；配置不一致时直接失败。迁移会清理旧 1536 维切片，并把已发布 FAQ 重置为 `pending`；必须等待全量重新向量化完成后再开放正式检索。当前固定 Revision、RTX 4060 单实例、候选上限 20 和短查询负载的质量与容量门禁已通过，Dense 门禁为 0.52；模型、数据、批量、候选长度或 GPU 变化后必须重新评测。

当前迁移 head 为 `023_marketing_review_idempotency`。`/v1/health/ready` 会真实检查 PostgreSQL、Redis、MinIO；启用 Embedding 后还会校验模型服务返回 BGE-M3/1024 维契约。响应只包含组件级状态，不包含 URL、模型路径、Token 或底层异常。

> 2026-08-21 已将本地模型运行时升级并锁定为 `torch 2.13.0` 和 `transformers 5.5.4`；`uv audit --locked` 对 123 个包未发现已知漏洞。测试工程师已完成新镜像包版本、GPU、Embedding、Reranker、质量、50 并发、冷启动和 OOM 实测；质量报告与性能报告已关闭 R-AI-BGE-004、OBS-M04-001。生产运行仍需持续监控尾延迟、队列、显存、错误率和数据漂移。

## 检查命令

后端固定 Python 3.11：

```powershell
Set-Location src/backend
uv sync --frozen --all-groups
uv lock --check
uv run ruff check . ../tests/backend ../tests/integration/postgres
uv run ruff format --check . ../tests/backend ../tests/integration/postgres
uv run mypy app scripts
uv run pytest
uv audit
```

AI 离线测试不会访问公网。不要执行会展开环境变量值的完整 `docker compose config`；只检查服务清单时使用：

```powershell
docker-compose -f src/compose/docker-compose.yml config --services
docker-compose -f src/compose/docker-compose.yml -f src/compose/docker-compose.ai.yml --profile ai config --services
```

需要真实 API Key 执行 130 条意图 live 评测时，先配置 `LLM_ENABLED=true`、`LLM_LIVE_EVAL=true`、模型名和密钥，再运行：

```powershell
Set-Location src/backend
uv run python -m scripts.evaluate_intents --output ../tests/.artifacts/ai/intent-classifier-live.md
```

评测门禁为五类意图准确率不低于 85%、30 条边界样本正确拒判率不低于 90%，并且 Provider 失败数必须为 0。单条模型失败不会中断整个评测，而是作为错误计入最终报告。DeepSeek V4 短分类任务默认配置 `DEEPSEEK_THINKING_ENABLED=false`，避免思考 Token 耗尽最终 JSON 的输出预算。报告不保存样本原文、Prompt、模型正文或密钥；没有真实 Key 时不得把单元测试 Provider 的结果当作正式模型评测。

真实 FAQ RAG 评测需要启动本地 BGE 模型服务，并显式配置 `EMBEDDING_ENABLED=true`、`EMBEDDING_PROVIDER=local_bge`、`LLM_LIVE_EVAL=true`。如果评测包含答案生成，仍需配置已轮换的 LLM Key：

```powershell
Set-Location src/backend
uv run python -m scripts.evaluate_rag --dataset ../tests/ai/datasets/faq-rag-v1.0.0.jsonl --output ../tests/.artifacts/ai/faq-rag-live.json
```

RAG 评测至少输出 Dense `Recall@20`、重排序 `Recall@5`、MRR、nDCG、20 条无答案样本正确拒判率和引用合法率。正式门禁仍要求重排序 `Recall@5 >= 90%`、无答案正确转人工率 `>= 90%`、引用合法率 `100%`。Fake Provider 和工程冒烟不代表正式模型质量通过。

Phase 4 安全回归集当前包含 237 条客服回复、翻译、弃单和中差评合成样本。工作流的自动交付边界是代码确定性渲染、对象级证据绑定和明确授权来源；结构化声明、模型复核和自由文本扫描只增加门禁。单元测试另覆盖 010～013 的独立危险事实、合法作用域、污染 FAQ、营销复核、跨对象证据和脱敏对象绑定，但这些样本不计入版本化评测集，也不用于声称全部开放语言已被证明。命令不访问公网，报告不包含样本正文：

```powershell
Set-Location src/backend
uv run python -m scripts.evaluate_phase4 --dataset ../tests/ai/datasets/agent-phase4-v1.0.0.jsonl --output ../tests/.artifacts/ai/agent-phase4-deterministic.json
```

`phase4_evaluation.calculate_phase4_metrics` 可汇总有标签离线评测；线上 `metric_daily` 从事实表重建 RAG、工具、首输出、Token 和显式单价估算成本。价格由运行方通过 `LLM_*_COST_PER_MILLION_USD` 配置，默认 0 表示未配置。这个确定性回归不是真实模型、真实平台或 50 并发性能结论。

REAL-AI-05 使用 18 类冻结合成样本调用真实 DeepSeek，其中 17 条执行真实 Provider，1 条模型超时使用确定性故障注入。数据集必须带同名清单；清单冻结版本、SHA-256、样本数和来源。DLP 只允许已验证清单派生出的本轮载荷摘要，普通生产 Prompt 不共享这项授权；结果只保存输入/输出 SHA-256、版本、标签、原因码、时延和 Token，不保存样本文本、Prompt、模型原文或密钥。输出路径必须是新文件，脚本拒绝覆盖历史证据：

```powershell
Set-Location src/backend
uv run python -m scripts.evaluate_real_model --dataset ../tests/ai/datasets/real-model-v1.0.0.jsonl --manifest ../tests/ai/datasets/real-model-v1.0.0.manifest.json --output ../tests/.artifacts/ai/real-model-v1.0.0-deepseek-YYYYMMDD-NNN.json
```

运行前必须仅在获准的隔离评测进程中显式配置 `APP_ENV=integration|staging`、`LLM_ENABLED=true`、`LLM_LIVE_EVAL=true`、DeepSeek 主模型、服务端 Key、正数 Token 单价、价格版本、币种和计价口径。禁止把 `LLM_LIVE_EVAL=true` 长期写入 `src/config/.env`；开发环境文件和 Compose 常驻服务必须保持 `false`，评测结束后立即清除当前进程的临时覆盖。模型、版本、币种、口径和两项费率必须整体命中代码内已批准登记项，结果同时保存费率以便复算；离线真实模型评测在 `production` 环境始终拒绝启动。门禁要求准确率不低于 85%、危险漏放为 0、合法误拦截为 0、真实 Provider 失败为 0，且成本配置完整。当前 `deepseek-v4-flash` / `real-model-eval-v1.2.2` 在未修改原 18 条标签、逐项校验九维声明的开发冻结集上为 16/18（88.89%），危险漏放、合法误拦截和 Provider 失败均为 0；该开发自测不替代测试工程师使用未见开放集的独立复测，因此公开回复、生产翻译、AI 营销和自动回复继续关闭。

测试工程师独立开放集必须使用新的数据集版本与自己的清单，且只允许在 `APP_ENV=integration` 或 `APP_ENV=staging` 运行。开放集无需把逐条载荷摘要写回产品代码；执行器会先校验清单摘要、18 类覆盖、样本唯一性和 PII/DLP，再生成仅本轮有效的载荷授权。任何真实模型离线评测均禁止在 `production` 环境执行。将独立开放集正文发送到外部模型前，还必须取得覆盖具体数据集摘要、目标供应商和用途的一次性数据出境授权；本地校验通过不能替代该授权。

## 本地合成数据 AI 手动演示

不接入真实店铺时，可使用六条固定合成会话验证真实 DeepSeek 回复建议、SSE 传输和“使用建议”交互。演示入口只允许服务端内置的完整测试载荷，浏览器不能把任意客户正文送入该入口；所有结果固定为人工草稿，不执行工具、不自动发送，也不改变会话状态。

1. 在 `src/config/.env` 中设置 `LLM_ENABLED=true`、有效的服务端 DeepSeek 配置和 `AI_SYNTHETIC_DEMO_ENABLED=true`。该演示开关只允许在 `development/test` 使用，生产环境启用会启动失败。
2. 重建后端以注入环境变量，并幂等创建演示数据：

```powershell
docker-compose -f src/compose/docker-compose.yml up -d --no-deps --force-recreate backend
docker-compose -f src/compose/docker-compose.yml exec -T backend python -m scripts.seed_ai_demo
docker-compose -f src/compose/docker-compose.yml exec -T backend python -m scripts.run_ai_demo_smoke
```

3. 打开 `http://localhost:3000/workspace`，选择名称以 `演示客户·` 开头的会话，点击“生成”。当前提供物流、退货政策、尺码、价格、客服时间和高风险退款承诺六种场景。
4. 返回结果必须显示“合成数据演示”。点击“使用”只会填入回复框；手动检查后也不要点击“发送”，因为这不是平台发送测试。

这条最小链路使用真实 DeepSeek，但证据来自服务端固定测试场景，不经过真实 TikTok 店铺，也不等同于 pgvector/BGE 真实 RAG、真实工具调用、公开自动回复、真实营销发送或生产模型质量门禁通过。

前端：

```powershell
Set-Location src/frontend
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
```

包含真实 PostgreSQL + pgvector 的后端完整测试：

```powershell
cd ..
.\src\scripts\run-postgres-integration-tests.ps1
```

该命令使用 Compose `test` profile 的隔离 `postgres-test` 服务（本机端口 5433、tmpfs 临时数据），执行迁移后运行完整 pytest，完成后自动清理。禁止用 `docker compose run --service-ports backend` 执行测试，否则一次性容器会抢占正式 backend 的 8000 端口。

真实 TikTok 只读冒烟只能在完成 OAuth 的隔离 `integration` 环境执行。先核对 Partner Center 已启用 `seller.authorization.info`、`seller.order.info`、`seller.customer_service`、`seller.logistics`，再打开只读开关。物流使用 `/logistics/202604/orders/{order_id}/tracking`，同一订单的真实查询频率不得超过每 8 小时一次；脚本只输出计数，不输出店铺、订单、客户、消息或 Token：

```powershell
Set-Location src/backend
uv run python -m scripts.verify_tiktok_readonly --channel-id <channel_accounts UUID>
```

Webhook 地址固定为 `https://www.overselfx.com/v1/webhooks/tiktok`，Partner Center 至少订阅 `ORDER_STATUS_CHANGE`、`NEW_MESSAGE`、`SELLER_DEAUTHORIZATION`、`UPCOMING_AUTHORIZATION_EXPIRATION`。真实冒烟与订阅核对通过前，不得打开平台写开关。

迁移验收：

```powershell
docker compose -f src/compose/docker-compose.yml run --rm backend alembic upgrade head
docker compose -f src/compose/docker-compose.yml run --rm backend alembic downgrade base
docker compose -f src/compose/docker-compose.yml run --rm backend alembic upgrade head
```

Phase 3 本地运行验收（临时密码不会输出，脚本结束后清理测试夹具）：

```powershell
$env:PHASE3_TEST_PASSWORD = "请替换为至少 12 位临时密码"
docker compose -f src/compose/docker-compose.yml exec backend uv run python scripts/verify_phase3_runtime.py
Remove-Item Env:PHASE3_TEST_PASSWORD
```

## 当前边界

- TikTok OAuth `DEF-REAL-FS02-001～006` 已由 003 号独立报告全部关闭。REAL-FS-03 已完成真实只读与官方 Webhook 工程实现，但本轮未注入真实凭证，也未执行真实店铺冒烟或 Partner Center Webhook 投递验证；地址、发券和平台发送仍为 Mock。
- 公开 `/suggest` 和 `/chat/query` SSE 已实现，但只返回人工可采用的安全草稿；`delta` 是传输层分块，不是模型原生 Token 流。
- Agent 工作流可返回 `auto_reply`、`human_review` 或 `transfer_human` 决策；只有确定性可信回复可返回 `auto_reply`，全局自动回复、AI 翻译和 AI 营销开关均默认关闭。
- 店铺语气/语言和低敏翻译字段已交付公开后端契约；前端配置与翻译展示仍需全栈工程师接入。AI 营销在建立可审计人工批准状态前固定关闭，不向现有工具链路交付可发送正文。
- REAL-FS-05 已完成 DeepSeek 内部草稿 SSE 的工程运行面：服务端总超时、心跳、断线取消、错误收敛、低敏运行日志、配置健康状态、前端显式取消和 50 客户端证据工具。真实模型 SSE 50 并发 P99/首输出、实时翻译质量、营销效果和 5 天稳定性仍需由测试工程师在具备真实凭证的隔离环境中验证。
- 尚未完成真实店铺联调、真实平台写操作和 Java 服务。
- 正式测试报告应由测试工程师按项目命名规范单独生成。
