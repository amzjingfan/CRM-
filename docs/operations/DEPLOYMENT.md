# 部署与运行边界

## 环境分层

- 本地/测试：默认 Mock 外部平台，不需要真实密钥。
- Staging：验证真实 OAuth、Webhook、只读、人工消息、DeepSeek、容量、稳定性和恢复。
- Production：只接受固定镜像、迁移、配置、模型资产和发布基线；所有门禁签署后才能放行。

Compose 以 `src/compose/docker-compose.yml` 为基础文件，再叠加同目录的环境覆盖；环境变量只通过部署环境或密钥管理注入。仓库中的 `src/config/.env.example` 只描述变量，不含真实值。

## Split-ingress Rootless staging

管理端所有 HTML 由 Next.js 按请求动态生成并返回 `Cache-Control: private, no-cache, no-store, max-age=0, must-revalidate`，避免切换镜像后浏览器继续使用旧构建页面；`/_next/static/` 下带指纹的 JS/CSS 仍可长期 `immutable` 缓存。staging 切换前后须同时核对 HTML 响应头、页面引用的构建资源和无店铺页面的指引状态，不能只用健康端点判定 UI 已更新。

宝塔 Nginx 的 `http` 级配置启用了共享 `proxy_cache cache_one`，所以仅让 Next 返回 `no-store` 不会使已缓存的旧 HTML 立即消失。正式 staging vhost 在 HTTPS `server` 级显式设置 `proxy_cache off;`，不修改全局缓存或其他站点；验收必须对公网**无查询参数**的 `/login`、`/marketing`、`/knowledge` 执行 GET，确认不再返回旧 `x-nextjs-cache: HIT` 与长期 `s-maxage`，并复核业务机回环响应和静态指纹资源。不得通过加随机 query 代替精确路径验收。

当前 staging 固定使用双服务器入口分离：`staging.overselfx.com:443 → 38.55.145.52 宝塔 Nginx/TLS → 127.0.0.1:18080 → SSH 反向隧道 → 192.168.110.210:127.0.0.1:18081 → crmdeploy Rootless CRM`。Compose 项目名为 `crm-staging`，Docker socket 为 `unix:///run/user/1004/docker.sock`，数据和模型均留在 `/home/crmdeploy`。

旧服务器系统 Docker 的 GitLab 已占用 `10080/10443`，这些容器、端口、卷、网络和 data-root 禁止修改。CRM 只发布单个回环 HTTP 端口 `18081`，不在旧服务器终止 TLS；历史同机 systemd 入口只作为 Git 历史，不是当前操作路径。新服务器只承载宝塔 Nginx、站点证书和回环隧道监听，不运行 CRM 数据或模型服务。

活动运行手册和恢复顺序位于 `src/deploy/staging/rootless/README.md`：先建立公司负载与站点保护基线，上传与 main SHA 绑定的版本化资产，把公网入口置为 HTTP `503`，再切换 `18080 → 18081` 隧道；完成不可变镜像/配置 validate 和 Rootless deploy 后，通过宝塔签发证书，安装正式 HTTPS vhost，执行动态健康、隧道重连和公司负载复核。任何阶段失败都恢复 staging `503`、停止候选并保留数据卷，不切回 GitLab。

该路径已于 2026-09-21 在两台真实服务器上完成部署与验收：DNS、Let's Encrypt SAN/证书链、公网健康、迁移头、Rootless 容器、隧道自恢复和公司负载零变化通过，见 `MVP-STAGING-001` 定稿 IR/TR/RR 与 `release/evidence/staging/`。2026-09-29 已从活动 PostgreSQL/MinIO 建立受限备份，恢复至独立数据库和无公网端口的隔离 MinIO 实例；原业务桶为空，合成对象仅在隔离实例中验证二次备份与字节恢复，见 `MVP-008-RESTORE-001` 记录。2026-09-30 六摘要预取、候选部署、上一版实际切回和候选切返均已现场通过，G0 证据见下节；production 未部署，G1～G6 仍需独立验收。

### Staging 凭据终态

2026-09-21 已在业务服务器完成 `MVP-001` 凭据轮换：`POSTGRES_PASSWORD`、对应 `DATABASE_URL`、`MINIO_SECRET_KEY`、`JWT_SECRET_KEY`、`RETRIEVAL_MODEL_SERVICE_TOKEN` 已更新，并首次生成 `TIKTOK_CREDENTIAL_ENCRYPTION_KEY`。活动环境文件固定为 `/home/crmdeploy/config/crm-staging.env`、`crmdeploy:crmdeploy`、模式 `0600`；密钥值、摘要和可逆材料不进入 Git、日志或响应。

轮换验收必须同时证明新 PostgreSQL、MinIO 和检索令牌可用且旧值被拒绝，四个应用容器取得相同的新数据库/MinIO/JWT 配置，真实 TikTok、LLM、AI 和自动回复开关继续失败关闭。PostgreSQL 容器的 localhost 规则允许 trust，因此口令正反例必须从 backend 容器经 `postgres:5432` 验证；backend 被重建后必须重启 proxy 以刷新 Nginx 上游地址，再检查三个公开健康端点。staging 部署门禁和回滚演练已将 proxy 重启及健康等待纳入自动流程。

成功轮换的 root-only 恢复副本位于 `/var/backups/crm-staging/secrets/20260921T080357Z/crm-staging.env.before`。两次失败尝试在变更前/回滚后留下的受限重复副本尚未删除；删除必须另立 `MAINT-CLEANUP-*` 任务和精确批次。

2026-09-23 又仅在 staging 经 SSH 受限通道注入 TikTok App Key、Service ID、App Secret 和 DeepSeek API Key；活动 env 仍为 `crmdeploy:crmdeploy:0600`。仅重建 backend、worker、jobs、agent-worker 并刷新内层 proxy，实际镜像摘要未变，按进程职责验证四项凭据可见性、所有真实能力开关为 false、日志/健康响应未泄漏、三个公网健康端点 200、固定出口仍为 `38.55.145.52`、公司 system Docker 未变。旧 env 的 root-only 恢复副本为 `/var/backups/crm-staging/secrets/external-20260923T025011Z/crm-staging.env.before`；第一次尝试因一次性工具的工作目录权限在容器变更前失败，原配置已恢复并独立复核，修正后复用同一恢复副本完成注入。传输用 `/run` 临时文件已删除，实际密钥值和摘要不进入仓库。**这只证明安全注入和应用生效，不证明 TikTok/DeepSeek 平台已接受凭据**；真实 OAuth、Webhook 投递及 DeepSeek 调用仍按 G1/G2/G4 独立验收，production 未变更或发布。

`TIKTOK_WEBHOOK_SECRET` 只服务于本地 Mock 的 `X-TTS-Signature` 回归，不是需要从 Partner Center 单独获取的真实 Webhook 凭据。真实 Webhook 验签使用已注入的 `TIKTOK_APP_SECRET` 对 `TIKTOK_APP_KEY + 原始请求体` 计算 HMAC-SHA256，并与 `Authorization` 比较；该 Mock 字段在 staging 保持空值。此前把它列为外部凭据准备项的说明由本节纠正，不得生成任意值冒充平台密钥。

G2 的 staging 真实读取与 Webhook 使用部署门禁显式参数 `enable_tiktok_webhook_read=true`。门禁在原四个 Compose 文件之后叠加 `src/compose/docker-compose.rootless-staging-webhook.yml`，只允许 backend 和 worker 的 `REAL_TIKTOK_READ_ENABLED`、`REAL_TIKTOK_WEBHOOK_ENABLED` 为 `true`；其他进程与消息写入、高风险写入、自动回复仍必须为 `false`。仓库外 env 文件继续保留所有能力开关为 `false`，不靠修改凭据文件启用能力。默认 validate/deploy 和 rollback 不叠加该文件；以相同受审镜像摘要再次执行默认 deploy 可恢复关闭状态。每次切换须先记录当前镜像、Compose 合并配置、健康和代理保护基线，再核对门禁低敏证据的模式与叠加文件摘要。此配置契约不代表 G2 已真实投递通过。

G2 只需新后端镜像时，可在当前 `main` 精确 SHA 上使用 `publish-backend-image.yml` 的 `staging-backend` 确认词，仅发布 `crm-backend` 并核对不可变摘要和压缩层大小；沿用已验证的前端和检索摘要，避免重建大体积检索镜像。私有镜像发布仍按独立授权边界执行，发布后还需 staging 预取、受控部署和真实 Webhook 验收。

2026-10-10 G3 中断后安全补丁沿用这一单后端发布路径：源 main `6e975148650bfd8e6cb0b7980b86554345caf5d0`，候选 backend `0a07365e...`，旧版 `b889525f...`。六角色预取和 G2 只读/Webhook 模式预检、部署通过；前端/检索摘要不变，普通消息真实写保持关闭。低敏 artifact ID、文件摘要、固定出口和健康结果见[现场记录](../../release/evidence/staging/crm-staging-g3-backend-rollout-20261010.json)。本轮未执行真实消息发送或实际切回；G3 仍须独立验收。

主机 SSH 不可用时，`inspect-staging-tiktok-webhooks.yml` 可在受审的 `main` 提交和在线 staging Runner 上执行一次只读订阅查询。它先核对运行中 backend 的不可变摘要，再在该容器的新进程中临时启用真实只读能力；要求恰好一个已连接 TikTok 渠道，只调用 `GET /event/202309/webhooks`。机器证据只记录订阅数、主题及与预期回调地址的匹配数，不输出 URL、请求 ID、店铺标识或凭据；工作流不创建、修改、删除订阅，也不切换常驻服务环境。

2026-10-09 首次只读查询确认当时订阅为 0，见[写入前证据](../../release/evidence/staging/crm-staging-g2-subscription-read-20261009.json)。一次性 `subscribe-staging-tiktok-new-message.yml` 仅能从 main 对已核对的 staging backend 执行最多一次 `PUT /event/202309/webhooks`：唯一主题 `NEW_MESSAGE`，唯一地址 `https://staging.overselfx.com/v1/webhooks/tiktok`。调用前重新 GET；若已是精确目标则不写，若有任何其他订阅则失败关闭。PUT 后 GET 对账；连接失败或结果不确定时不自动重试，需另行只读核对。脚本不接受动态主题/地址，输出仅包含状态、数量和 HTTP 状态码。所用 `202309` 路径及正文来自本地 TikTok 官方 OAS。

用户已精确授权一次外部订阅写入；main `253a6cf0f563aae85b15ea7447a3589f203484b1` 上 workflow `37881350331` 执行一次 PUT 并写后 GET 确认，随后独立只读 workflow `37881477237` 确认 `NEW_MESSAGE` 订阅数 1、预期地址匹配数 1、其他地址数 0，见[低敏证据](../../release/evidence/staging/crm-staging-g2-subscription-confirmed-20261009.json)。已用尽这次写入授权；不要再次触发写入工作流。订阅成功不证明官方事件已投递，也未发布新镜像或改动 production。

`inspect-staging-tiktok-webhook-events.yml` 仅用于 G2 staging 现场前后计数对账。从 main 精确提交读取并验证脚本 Git blob，核对正在运行的 backend 不可变摘要；脚本要求 staging Webhook 模式开启、恰好一个已连接 TikTok 渠道，第一条数据库语句设置只读事务。它只读取 2026-10-09 03:54:01Z 订阅确认后的 `NEW_MESSAGE` 事件状态/签名/重试聚合、同店铺 TikTok 入站消息累计数和该时间后的未绑定事件数。输出固定计数字段，不包含消息正文、事件 ID、店铺 ID、签名或平台响应；执行前后使用两个 artifact 比较差值。此工具不调用外部平台、不修改数据库，也不等于真实投递通过。

### TikTok 固定出口契约

staging 的 TikTok 出站与 split-ingress 入口分离：应用只经 `socks5h://tiktok-egress:1080` 访问独立 helper，helper 再以 `crm-egress@38.55.145.52` 建立 SSH 动态转发。公网账号只允许 local/dynamic forwarding 到 `auth.tiktok-shops.com:443`、`open-api.tiktokglobalshop.com:443` 和门禁专用 `checkip.amazonaws.com:443`；不得复用 `crm-tunnel`、开放代理端口或放宽为任意目标。

staging 固定按以下顺序叠加 Compose：

```text
src/compose/docker-compose.yml
src/compose/docker-compose.prod.yml
src/compose/docker-compose.tiktok-egress.yml
src/compose/docker-compose.rootless-staging.yml
```

仓库外环境文件声明 `TIKTOK_EGRESS_IP=38.55.145.52` 与 `TIKTOK_EGRESS_SECRET_DIR=/home/crmdeploy/secrets/tiktok-egress`；overlay 固定向应用注入 `TIKTOK_EGRESS_PROXY_URL=socks5h://tiktok-egress:1080`。密钥目录所有者为 UID/GID 1004、模式 `0700`，其中 `id_ed25519` 和 `known_hosts` 为 `0600`，只读挂载到 helper 的 `/run/secrets/tiktok-egress`。helper 显式 `user: "0:0"`，在 Rootless 映射下只是宿主机 `crmdeploy`，不会取得宿主机 root；应用容器仍为非 root。私钥不得进入应用容器、镜像、Git、环境文件或证据。

门禁先以候选 backend RepoDigest 启动并等待 helper，再从同一候选 backend 镜像执行：

```text
python scripts/verify_tiktok_egress.py
```

验证器经应用实际使用的 SOCKS5H 路径访问固定检查地址，只有 `configured_ip` 与 `observed_ip` 都精确为 `38.55.145.52` 才通过；代理失败、格式错误或 IP 不一致均失败关闭，不尝试直连。staging 回滚只把应用切换到已验证的上一 RepoDigest，helper 继续使用包含当前隧道资产的候选 backend 镜像，全部真实 TikTok/LLM/自动回复开关保持 false。

2026-09-23 已在真实 staging 用合并 `main` 的部署门禁完成固定出口验收：workflow `35806983990` 精确观测 `38.55.145.52`、迁移头和三个公网 200；仅停止 helper 的故障演练得到验证器非零，恢复后同一出口再次通过。两个 TikTok 官方端点经应用 SOCKS5H 路径完成无凭据 TLS 请求；公司 system Docker、入口策略、非 staging 站点和保护监听复核未发生业务漂移。最终低敏证据为 `release/evidence/staging/crm-staging-tiktok-egress-20260923.json`，R02 IR/TR/RR 解释初次 502、proxy 刷新修复和镜像例外。

2026-10-08 staging 运行检查发现现有 `tiktok-egress` 容器已退出；Docker 保存的最后启动错误是 systemd 创建该容器 cgroup scope 超时，同一时段同机多个容器的健康检查也出现启动超时，未见该容器 OOM。仅启动原容器后其健康检查恢复，并从 backend 执行 `python scripts/verify_tiktok_egress.py` 再次实测固定出口 `38.55.145.52`；其他 CRM 容器未重启，公网 ready 为 200。低敏事实见 [`crm-staging-tiktok-egress-recovery-20261008.json`](../../release/evidence/staging/crm-staging-tiktok-egress-recovery-20261008.json)。此恢复不证明 systemd 超时不会再发；每次真实 TikTok 门禁前先核对 helper `running/healthy` 并运行同一出口验证器，G6 还需覆盖 helper 退出告警及连续运行。

本次用户仅限 staging 授权继续使用已验证的 backend/frontend 不可变摘要（与候选 `746c10c` 的构建输入零差异）和旧检索镜像摘要（检索服务源码与 Dockerfile 不变，但依赖锁文件**不同**）。新摘要 GHCR 下载失败/停滞不能写成已部署；下次镜像升级和 production 必须重新通过独立摘要与供应链门禁，不能沿用此例外。production 仍仅有可复用配置契约，未选择出口服务器、创建账号/密钥或实施部署。

2026-09-23 UI 修复合并后，`main` 的 `58263b1` 已单独发布到 staging：新 frontend `e5d6bbfc...`、backend/helper `a3bb63c4...` 正在运行且健康，门禁 `35849490309`、固定出口、迁移头和三个公网健康端点均通过。全量同源尝试 `35845426383` 在新检索镜像下载阶段取消，取消前没有容器切换；用户为**这一次 staging UI 部署**另行批准保留当前健康的旧检索摘要 `bc99dfa3...`。检索服务源码/Dockerfile 相同，但依赖锁不同；这是明确的运行版本偏差，不是新检索镜像已部署或 production 供应链通过。恢复点、前后保护基线和未测项见 `release/evidence/staging/crm-staging-ui-rollout-20260923.json` 与 `MVP-UI-DEPLOY-001` R01。前一段固定出口任务的历史豁免仍只属于那次验收，本次授权不能延伸到下一次镜像升级。

## TikTok 与 DeepSeek

- TikTok OAuth 回调在 staging 使用 `staging.overselfx.com`、在 production 使用 `www.overselfx.com` 的 HTTPS 固定地址，state 默认 600 秒、哈希存储并原子消费。
- Webhook 真实模式使用官方签名和原始请求体；开发签名只能在真实开关关闭时使用。
- Token 加密保存，刷新失败将渠道置为 `expired`；日志和响应不输出 Token 或凭证引用。
- DeepSeek Key 只从环境读取，Provider 使用固定正向输入协议、DLP 和结构化输出。
- G4 一次性入口为 `evaluate-staging-deepseek.yml`：从 `main` 手动派发，必须填写精确的 `expected_source_sha` 与当前运行 `crm-backend` 的 `repository@sha256`。Runner 按该提交从 GitHub API 读取所需六个文件并校验 Git blob SHA，避免全仓 Git fetch 卡住。先运行 `prepare`，它校验独立冻结集、36 条样本、34 条真实模型样本、2 条故障注入、staging 配置及代码哈希，只上传低敏准备证据，Provider 调用数为 0。`live` 另需针对 34 条合成数据外发及可能费用的单独批准，并填入工作流要求的确认短语；它只在现有 backend 容器的一次性子进程中启用评测与保守估价，不修改服务配置、TikTok 写开关或 production。质量未达门禁时上传低敏报告后作业失败；报告中的成本是估算，不是账单。历史 32/36 不能代替新现场结果。
- SSE `delta` 是经安全校验后的草稿分块，不把模型原生流直接暴露给客户端。

## 模型资产

模型固定 Revision、权重清单、SHA-256、质量和容量证据的机器权威入口是 `src/deploy/models/model-manifest.json`。实际权重不进入 Git。部署前校验文件名、大小和哈希；不允许漂移到浮动分支或静默降级模型。

BGE 运行基线为 1024 维、Dense Top-20、Rerank Top-5、阈值 0.52。质量可使用 `src/backend/scripts/evaluate_rag.py` 复验，运行时与混合检索可使用同目录的 `verify_retrieval_model_runtime.py` 和 `verify_bge_hybrid_runtime.py`；发布证据保存在 `release/evidence/retrieval/`。

## 默认关闭项

至少保持 `AUTO_REPLY_ENABLED=false`、`REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false`。Shopee/Amazon 真实接入、自动营销、公开自动回复和高风险工具在 v0.1 不启用。真实开关只能在对应 Scope、审计、幂等、容量、稳定性和回滚门禁通过后改变。

## 消息不确定性

真实普通文本消息只调用平台一次。本地超时或响应不完整时记录 `unknown`，通过 `POST /workspace/messages/{message_id}/reconcile` 核对平台结果；部署或运维脚本不得通过自动重发解决不确定性。

## 迁移、备份与回滚

1. 在维护窗口验证镜像、配置、模型哈希和数据库迁移；当前代码迁移头为 `024_tiktok_oauth_jobs`，2026-09-28 业务机 staging 运行库只读查询亦为 `024_tiktok_oauth_jobs`。此事实不代替镜像兼容回滚或 production 迁移验收。
2. 部署前完成数据库和对象存储备份，并验证可读取性。
3. 先迁移再启动应用；健康检查、Webhook、SSE 和关键人工流程通过后再切入口。
4. 回滚使用已验证的上一镜像和兼容迁移路径；禁止 `git reset --hard` 或手工改生产表。
5. 真实恢复和回滚演练证据缺失时，发布门禁保持阻塞。

staging 镜像回滚准备阶段使用 `staging-gates.yml` 的 `prefetch` 操作：自托管 Runner 凭当次 `GITHUB_TOKEN` 的 `contents: read` 与 `packages: read` 权限，将候选与上一版的后端、前端、检索服务六个不可变摘要拉到 `crmdeploy` Rootless Docker 并核对本地 RepoDigest。`prefetch` 仅从 `main` 调度，先从 GitHub API 以精确调度 `GITHUB_SHA` 读取预取、临时下载配置及 OCI 续传三个脚本，核对提交 SHA 和返回内容的 Git blob SHA-1，成功后才允许 GHCR 登录与 Docker 操作；API 获取或核对失败时关闭。`validate/deploy/rollback` 由 GitHub 托管 Runner 检出并核对精确调度提交，以 `git archive` 打包受审文件并计算 SHA-256；自托管 Runner 从同一次工作流下载包，先核对托管作业输出的 SHA-256，再解包到独立临时目录，初始化只用于确定安全边界的本地 Git 仓库，之后才允许 GHCR/Docker。包缺失、摘要不一致或步骤失败时均不触碰 Docker；本地临时仓库的 HEAD 不冒充上游提交。修复合并后必须从 `main` 新建 `workflow_dispatch`，不得用旧 run 的 Re-run 验证，因为旧 run 仍绑定原调度提交。预取不读取 staging 环境文件、不重建容器、不改活动数据，也不代表回滚通过。失败或作业超时后用相同六摘要重新运行时，脚本逐项报告当前镜像，并跳过本地 RepoDigest 已精确匹配的镜像；单个缺失摘要最多进行三次拉取，每次失败后仅重试同一不可变摘要并重新核对本地 RepoDigest，持续失败不得生成通过证据。预取专用作业时限为 240 分钟，其他操作保持 120 分钟；只有六项全部核对后才写入通过证据。只有独立恢复库上的旧版兼容性检查、镜像预取、受限备份和切返路径都确认后，才可在维护窗口执行实际切回/切返。`rollback -Execute` 在容器变更前还须核对正在运行的后端、前端和检索服务均为输入的候选摘要；如果 staging 仍保留旧检索镜像，先完成候选三镜像部署及验收。现有 `rollback` 操作本身**不会自动切返**，必须单独验证恢复候选运行态。production 不使用本操作。

针对 GHCR 大层传输重置，staging 预取临时将 /home/crmdeploy/.config/docker/daemon.json 的 max-concurrent-downloads 设为 1；修改前逐字节备份，使用 crmdeploy 的 Rootless Docker HUP 热重载，并核对 daemon PID/ID 不变。成功或失败后恢复原始配置并再次核对；工作流另设 always() 恢复步骤。若整项作业被强制结束，遗留备份必须先核对和恢复，才可再次预取。此调整不发布新镜像、不改变六摘要或运行服务，也不适用于 production。

2026-09-29 预取 `36535392094` 在检出调度 SHA `6d2188a` 时，Runner 的 Git HTTPS 三次返回 `upload-pack: not our ref`，因此未执行 Docker。PR #73 合并后的只读诊断 `36538863633` 以 `8183ba8` 触发：GitHub API 的 `main` 为相同 SHA，Runner 没有 HTTPS 代理、Git 全局代理或 URL 重写；Git HTTPS `ls-remote` 返回 `128/transport`，精确 SHA fetch 返回 `128/other`。诊断没有运行 Docker。PR #74 的预取专用 API 脚本路径已合入 main `06b65a6`，预取 `36542000513` 完成源码、目标和 GHCR 登录，前两摘要在本地已核对；第 3 项候选检索镜像拉取约 62 分钟后 GHCR TCP 重置，作业失败且无六项通过证据。PR #75 源码包路径已合入 main `b766645`，只读 `validate` 的首次 `36546406332` 因输入摘要不等于 staging 环境中的 `RETRIEVAL_MODEL_SERVICE_IMAGE` 失败；按上次成功现场门禁的精确 `bc99dfa3...` 摘要重跑 `36549567208` 后，受审源码包 SHA-256、当前混合镜像 Compose 和外部模型资产预检通过，未执行迁移、部署或回滚。该路径不修复主机 Git HTTPS 本身。

PR #76 的有界重试已合入 main `d63fc0267debbb896010d17a483ac6c0607d9183`；新预取 `36551693111` 的第 1、2 项精确命中本地摘要，第 3 项候选检索镜像连续三次拉取分别运行约 103、44、27 分钟，均以连接到 `185.199.*.154:443` 时 `read: connection reset by peer` 结束。脚本拒绝生成六项证据，未变更服务。当前增加只读 GHCR manifest 检查：GitHub 托管 Runner 只读取候选及上一版检索镜像的 linux/amd64 压缩层大小，不下载层、不写 staging，用于决定后续是否缩小镜像或改变传输路径。只读清单运行 `36653973420`（main `ec410b5`）通过：候选及上一版 linux/amd64 镜像均为 10 层，压缩总量分别为 2,881,272,740 与 2,881,270,875 字节；各自最大的单层分别为 2,810,381,159 与 2,810,381,463 字节，均占约 97.54%，但这两个大层摘要不同。两镜像只有 5 个共享层，合计 70,464,540 字节。现有 `docker pull` 日志只打印最终 TCP 重置，未显示失败时所在层，因此不能断言每次均断在大层；但单层体积使网络重置的重试代价很高。下一步先评审在不改变锁定依赖和运行行为的前提下分层重建候选与上一版镜像，验证构建及镜像层大小；发布新的私有 GHCR 版本可能增加计费存储，须另按资源授权边界执行。该检查不能替代本机六摘要核对；只有实际六摘要核对和后续演练才能关闭 G0。

检索镜像的构建定义现将锁定的 Torch/CUDA wheel 分六组安装，并在末尾执行原有的完整 `uv sync --frozen --no-dev --extra retrieval-model`；不改 `uv.lock`、运行命令、模型资产或服务配置。2026-09-30 本机直接构建该 Dockerfile 时，首次 Torch 下载被 PyPI TLS EOF 打断，未生成正式构建结果。随后在已忽略的测试材料中使用既有镜像的 uv 缓存做等价依赖命令的隔离探针：六组和最终完整同步均按当前锁文件成功，`torch 2.13.0+cu130`、`transformers 5.10.4`、`fastapi 0.141.1` 在无网络容器中可导入。Docker 历史显示六个提前安装层约 480 MB–1.13 GB（未压缩），最后完整同步层约 1.25 GB（未压缩）。探针使用临时缓存挂载及补齐一个缺失小包，不能把未压缩本机层大小等同于待发布 GHCR 的压缩层，也不能证明正式 Dockerfile 构建、完整检索服务运行或目标 Runner 下载成功。现有 `publish-images.yml` 只接受当前 `main` SHA；上一版源码和锁文件若要生成新分层摘要，须另建立来源可核对的受审构建路径，不能把当前锁文件冒充旧版。正式构建、运行时检查、两版新摘要发布及 staging 六项预取仍须分别留存证据。

上一版专用的 `publish-previous-retrieval-image.yml` 为这条受审路径：源码和锁文件固定在 `118ba775e291b88998bd033b7bca3410e29f8b88`，分层 Dockerfile 固定在 `fb6b2f9d18403ea77d80f039b6b68aba437e2ccb`。它只允许当前 `main` 的手动 `workflow_dispatch`，输入必须为 `staging-rollback`，并使用既有 `image-publishing` 环境；验证三个 checkout SHA 后才登录 GHCR、构建并发布单个上一版检索镜像。唯一运行标签含 run ID/attempt，结果记录不可变 RepoDigest、锁文件与 Dockerfile 的 SHA-256 与实际压缩层大小；若发布后清单读取失败，仍上传标为 `UNVERIFIED` 的摘要证据，不能将镜像视为通过。该工作流的合入不会自行触发发布；首次运行仍受私有镜像资源授权约束。新旧分层镜像生成后，必须以摘要分别完成清单检查、六项预取和回滚前置核对。

用户于 2026-09-30 单独授权本次仅为 staging G0 发布四个私有镜像。候选三镜像运行 `36660691623` 与上一版检索运行 `36661103062` 均成功，主线源码固定 `33d80bd4acc1dfb9c93ec687086ee466d99682c6`；上一版另核对旧源码 `118ba775` 与分层 Dockerfile `fb6b2f9`。只读清单运行 `36661448273` 对两条新检索摘要均通过：各 16 层、压缩总量约 2.879 GB，最大压缩层分别为 523,019,509 与 523,019,642 字节；旧镜像约 2.81 GB 单层已消除。低敏来源、摘要与 SHA-256 见 [分层镜像发布证据](../../release/evidence/staging/crm-staging-mvp008-layered-images-20260930.json)。六摘要预取 `36661590529` 于第 3/6 项候选检索镜像失败：三次尝试分别为连接重置、371,825,409 字节层只收到 41,943,040 字节时 EOF、连接重置；前两项已拉取，本次未生成六项通过证据且未变更活动服务。Docker 默认每次并发下载三个层，官方建议低带宽连接降低 `max-concurrent-downloads`；PR #81 已将临时单层下载并发和逐字节配置恢复纳入 staging 工作流，实际效果须由 Runner 成功领取后核对。PR #81 的可恢复 Rootless Docker 单层下载并发设置已由前后端 CI 通过并合入 main `2dc12ae`；新调度 `36677814365`、`36678234455` 均在任何步骤开始前因 self-hosted Runner 未领取作业而被 GitHub 取消，首次两个新调度尚未执行低并发，六摘要仍未通过。Runner API 显示在线，排队时短暂显示 busy，结束后恢复 idle；用户提供主机密钥后只读诊断确认：Runner `2.336.0` 自动升级 `2.337.0` 的官方包三次下载超时，作业领取因此中断。官方 226,430,031 字节归档经 SHA-256 核对并经内网传输后，已备份旧安装并升级 Runner；GitHub API 显示原 ID `22` 在线、版本 `2.337.0`，注册文件哈希不变。11 个 staging 容器 ID 均未改变，三个公网健康端点均为 200。低敏证据见 `../../release/evidence/staging/crm-staging-runner-recovery-20260930.json`。Runner 2.337.0 已成功领取预取 `36684323365`，但候选检索镜像第 3/6 项在 `07:52:28`、`08:02:52`、`08:14:41` UTC 三次遇到 GHCR 数据节点 TCP 重置。临时 `max-concurrent-downloads=1` 已实际执行，原 Docker 配置随后逐字节恢复，Docker 身份和 11 个 staging 容器未改变，三个公网健康端点均为 200；仍无六摘要通过证据。同一 523,019,509 字节层的 1 MiB HTTP Range 请求在 staging 用时 74.2 秒，本机用时 5.0 秒，均返回 `206` 和预期 Content-Range。下一步需要可校验、可断点续传的传输与准确摘要导入，再做 staging 候选部署及回滚演练。 发布/清单本身不代表 staging 已部署或 G0 已关闭。

`prefetch` 对尚未在本机缓存的两条检索镜像改用 `src/scripts/prefetch_ghcr_oci.py`：工作流从调度 `main` 的精确 SHA 读取该脚本并核对 Git blob 摘要，复用当次仅有 `packages: read` 的 GHCR 登录。脚本只接受已审核的检索仓库和小写 `sha256` 摘要；固定以 `crmdeploy` UID 1004、Rootless Docker/containerd socket 运行。它选择 OCI index 的唯一 linux/amd64 manifest，按 1 MiB HTTP Range 最多 8 路获取压缩 blob，原子保存已完成分段；重跑可继续使用已落盘分段。每个 manifest、config 和层都按原始 SHA-256、描述符长度核对，最后以 OCI 原始 index 摘要导入 Rootless containerd，并要求 Docker `RepoDigests` 精确包含输入摘要。临时分段和内容保存在 `crmdeploy` 私有的 `/home/crmdeploy/.cache/crm-ghcr-prefetch/`；其中不保存凭据，失败时保留以便续跑。导入不会切换容器；只有六项都按 Docker 本地摘要复核后才能产生预取通过证据。已缓存的后端和前端仍由原流程核对，未缓存时沿用有界 `docker pull`。已在 staging 用现有前端 `8a0b99af...` 的 OCI 导出材料试跑 Python 打包与 Rootless `ctr import`，Docker 仍返回原始 RepoDigest；11 个活动容器 ID 未变，三个公网健康端点均为 200。这条路径尚需两条检索镜像与六项实际通过证据，不能视作 G0 完成。

### 2026-09-30 G0 现场闭环

PR #83 合入 main `3b091055908a4fd374dc95518dfd31d8d8960a47` 后，预取工作流 `36699523917` 在 staging Rootless Docker 核对了候选和上一版后端、前端、检索共六个不可变 RepoDigest。检索 OCI 层按 1 MiB 范围下载、校验 SHA-256 并支持断点续传；对于主机到 GHCR 数据节点反复重置的两个检索镜像，已通过本机校验后经内网传输到 staging 缓存，再由受审预取路径导入并核对摘要。此过程没有修改活动服务。原 Docker daemon 配置逐字节恢复，daemon ID 保持不变。

受控切换 staging 环境文件中的检索镜像摘要前保存 `0600` 恢复副本；工作流 `36700668599` 的 `validate` 通过。候选部署 `36701049769`、上一版三镜像实际切回 `36701815122`、候选切返 `36702556391` 均通过，并各自产生工作流证据。切回时先关闭真实能力，再部署上一版三摘要并验证三个健康接口；切返后独立现场检查候选三摘要、11 个活动容器、`024_tiktok_oauth_jobs` 迁移头、三个公网 HTTPS 健康接口 200 和固定出口 `38.55.145.52`。当前 staging 运行候选三摘要。低敏汇总及原始工作流 artifact SHA-256 见 [G0 现场证据](../../release/evidence/staging/crm-staging-mvp008-g0-20260930.json)。此次仅关闭 staging G0 的恢复与镜像回滚条件，不代表 G1～G6 或生产发布通过。

### staging 前端单镜像更新路径

渠道页 OAuth 状态修复已合入 main，staging 仍运行旧前端摘要。`publish-frontend-image.yml` 提供仅前端的手动发布入口：必须从当前 main 调度、输入完整且等于当前 main 的 `source_sha`、填写 `staging-frontend`，经既有 `image-publishing` 环境发布一个 GHCR 私有前端镜像。工作流生成带 run ID 的唯一标签，记录不可变 RepoDigest 和 linux/amd64 压缩层大小；清单未核对通过时证据为 `UNVERIFIED`，不得部署。原三镜像发布工作流保持独立。

此更新只复用现场与 G0 证据一致的后端 `fb1bffec...` 和检索 `feeee5a3...` 摘要。取得前端新摘要后，以 `staging-gates.yml` 的 `prefetch` 核对候选三项和部署前运行的三项；后端、检索两组候选与上一版摘要允许相同，但至少前端一组必须不同。六个服务角色仍逐项核对不可变 RepoDigest，不能把相同摘要重复计作六个不同镜像。然后执行 `validate` 和 `deploy`；回滚目标为部署前实际运行的三摘要。部署前复核 staging 环境文件的检索摘要、Rootless 容器、持久代理配置与三个公网健康接口；部署后核对运行镜像摘要、迁移头、健康和渠道页旧连接提示。发布或健康通过均不等于真实 OAuth callback 重放通过，G1 与 production 继续按独立门禁判断。

2026-10-08 已从 `main=f268408f3d9e396444e95cf2106141f0aae98188` 仅发布一个前端私有镜像：运行 `37742119116` 的清单与压缩层校验通过，摘要为 `c56443c8...`。staging 预取 `37742409755` 逐项核对六个角色、四个不同摘要且未变更服务；只读预检 `37743493147` 通过；部署 `37743848722` 通过。独立核对 11 个 Rootless 容器、前端新摘要、后端与检索原摘要、数据库头 `024_tiktok_oauth_jobs`、持久 proxy 配置来源、三个公网健康 200 与固定出口 `38.55.145.52`。其后从本机重新请求五个公网路径均返回 200，前端容器仍健康。低敏机器证据见 [前端单镜像更新](../../release/evidence/staging/crm-staging-frontend-only-rollout-20261008.json)。Codex 内置浏览器读取超时，用户表示该浏览器无法刷新并撤回此前“有成功提示”的回答；带身份渠道页提示仍未验证，此部署不签署 G1。

### 2026-10-08 staging 代理配置挂载恢复

按用户要求重启 staging 现有 CRM 容器时，Rootless proxy 因 `/etc/nginx/nginx.conf` 的宿主机 bind 来源位于已清理的 Runner 临时源码目录而无法重新启动，公网 ready 短暂返回 502。已从持久、已审核源码复制 SHA-256 相同的 `nginx-tunnel.conf` 到原挂载位置，proxy 恢复健康，公网 `/login`、`/healthz` 和 ready 返回 200，固定出口仍实测为 `38.55.145.52`；系统 Docker 的其他业务容器 ID 未变。这个现场恢复只恢复当前容器，下一次 Runner 清理仍可能删除临时来源。

`MVP-STAGING-PROXY-PERSIST-001` 已由 PR #89 合入 `main=dcddb26cbb6ecc92db30a11a2f504d034e6ec048`。正式 `validate` 运行 `37716193186`、`deploy` 运行 `37716402745` 通过；后者将已校验源码包放入 `/home/crmdeploy/src/crm-reviewed-source-37716402745-1/`，proxy 的相对只读 bind 来自该持久路径。作业结束后再次显式重启 proxy 成功并健康，公网首页 307、登录与三个健康接口 200，配置文件 SHA-256 与仓库一致，其他公司容器 ID 不变。低敏证据见 [代理持久挂载复测](../../release/evidence/staging/crm-staging-proxy-persistent-source-20261008.json)。运行中的源码目录不得作为普通 Runner 临时材料清理；此结论不替代 G6 连续五日稳定性。

## 发布入口

当前发布状态见 `docs/operations/RELEASE-GATES.md`，最新测试摘要见 `docs/quality/TEST-STATUS.md`，固定资产与评测集见 `release/baselines/` 和 `release/evidence/`。部署说明不替代真实签署。
