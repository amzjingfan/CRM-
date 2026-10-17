# Split-ingress Rootless staging 运行手册

日期：2026-09-21。状态：真实主机切换与动态验收已完成，staging 正常运行，production 未部署。当前架构见 [`docs/architecture/SYSTEM.md`](../../../../docs/architecture/SYSTEM.md)，门禁结论见 [`docs/operations/RELEASE-GATES.md`](../../../../docs/operations/RELEASE-GATES.md)。本文是 staging 唯一活动操作路径；历史同机 systemd 入口只保留在 Git 历史中。

## 1. 目标与禁止事项

```text
staging.overselfx.com:443
  → 38.55.145.52 宝塔 Nginx + 公信 TLS
  → 127.0.0.1:18080
  → crm-tunnel 受限 SSH 反向隧道
  → 192.168.110.210:127.0.0.1:18081
  → crmdeploy Rootless proxy:80
  → CRM 全部服务与 /home/crmdeploy 数据/模型
```

- 新服务器只运行宝塔 Nginx、站点 TLS 和回环 SSH 监听，不运行 CRM、数据库或模型。
- 旧服务器固定使用 `crmdeploy`、UID/GID 1004、`/home/crmdeploy` 和 `unix:///run/user/1004/docker.sock`。
- 系统 Docker 及 GitLab 的 `0.0.0.0:10080/10443` 属于公司负载，禁止停止、重启、改配置、迁移、修复或接管。
- CRM 只发布 `127.0.0.1:18081:80`；禁止 LAN/公网绑定、宿主机 TLS 和第二个 proxy 端口。
- 新服务器反向监听只允许 `127.0.0.1:18080`；禁止交互 shell、PTY、agent/X11 转发、额外 listen 或 `GatewayPorts=yes`。
- 不在服务器 build，不使用浮动标签，不把 `.env`、私钥、Token、证书私钥、模型、备份或业务数据写入 Git/日志。
- 失败只回到 staging `503` 并停止候选容器，保留卷；不得把流量切回 GitLab。

## 2. 当前现场事实

截至 2026-09-21 终态只读复核：

- DNS A 已是 `staging.overselfx.com → 38.55.145.52`。
- 新服务器只由 Nginx 公网监听 80/443，SSHD 只在 `127.0.0.1:18080` 接收反向隧道；Let's Encrypt 证书 SAN 正确，无 `19090` 临时代理监听。
- 新服务器 `crm-tunnel` 为锁定、nologin、无附加组的专用账号，有效 SSHD 策略只允许 remote forwarding 和 `permitlisten="127.0.0.1:18080"`。
- 旧服务器的隧道 argv 固定为 `127.0.0.1:18080:127.0.0.1:18081`；Rootless CRM 共 10 个长运行容器，proxy 只发布 `127.0.0.1:18081:80`。
- 数据库迁移头为 `023_marketing_review_idempotency (head)`；`/healthz`、`/v1/health` 和 `/v1/health/ready` 公网状态均为 200。
- 系统 Docker 的 GitLab 仍监听 `10080/10443`，本次部署不使用系统 Docker socket；临时 registry 出网服务已停用并可恢复隔离。

上述仅是交接摘要；可复核低敏命令、输出和时间窗见 `release/evidence/staging/crm-staging-final-state-20260921.json`。现场状态变化后必须重新读取，不能把本节单独当作当前证据。

## 3. 固定参数和输入

```text
DOCKER_HOST=unix:///run/user/1004/docker.sock
COMPOSE_PROJECT_NAME=crm-staging
CRM_STAGING_ENV_FILE=/home/crmdeploy/config/crm-staging.env
CRM_STAGING_BASE_URL=https://staging.overselfx.com
RETRIEVAL_MODEL_ASSET_DIR=/home/crmdeploy/assets/models
TIKTOK_EGRESS_IP=38.55.145.52
TIKTOK_EGRESS_PROXY_URL=socks5h://tiktok-egress:1080
TIKTOK_EGRESS_SECRET_DIR=/home/crmdeploy/secrets/tiktok-egress
BUSINESS_PROXY=127.0.0.1:18081
PUBLIC_TUNNEL_LISTENER=127.0.0.1:18080
```

TikTok 出站密钥与入口隧道密钥完全分离。`/home/crmdeploy/secrets/tiktok-egress` 必须归 UID/GID 1004、模式 `0700`，其中 `id_ed25519` 和 `known_hosts` 为 `0600`；目录位于 Git checkout 外，只以只读方式挂载到 `tiktok-egress` helper。helper 在 Rootless Docker 内显式使用容器 `0:0`，只映射为宿主机 `crmdeploy` 以读取该私钥，不取得宿主机 root；应用服务继续使用镜像默认非 root 用户。私钥不得出现在环境文件、应用容器、日志或证据中。

环境文件必须把以下能力明确设为 `false`：

```text
ALLOW_MOCK_PLATFORM_ADAPTERS
REAL_TIKTOK_READ_ENABLED
REAL_TIKTOK_WEBHOOK_ENABLED
REAL_TIKTOK_MESSAGE_WRITE_ENABLED
REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED
LLM_ENABLED
LLM_LIVE_EVAL
AI_TRANSLATION_ENABLED
AI_MARKETING_ENABLED
AUTO_REPLY_ENABLED
```

G2 Webhook 实测只通过 `Staging production gates` 工作流的 `enable_tiktok_webhook_read=true` 显式模式开启。该模式仅适用于 `validate`、`deploy`，在固定四层 Compose 之后叠加 `docker-compose.rootless-staging-webhook.yml`，并逐服务确认 backend/worker 的真实只读与 Webhook 为 true，其他能力和进程保持 false。仓库外 env 文件仍全部为 false；默认模式与 rollback 继续失败关闭。恢复时以相同受审镜像摘要执行默认 `validate`、`deploy`，核对模式证据、容器环境、健康和公网入口；不得把本模式延伸到 production。

G5 压测窗口由同一工作流显式选择 `enable_g5_sse_load_test=true`，仅限 staging `validate`/`deploy`，与 G2 模式互斥。门禁在固定四层后追加 `docker-compose.rootless-staging-g5-sse.yml`，只让 backend 启用模型建议及 SSE 压测，单 IP 限流固定 60；运行容器与健康必须复核。恢复仍从同一镜像摘要运行不带额外模式的默认 `validate`/`deploy`，检查 backend 模型、压测均关闭且限流 10。本变更只准备并验证入口；现场切换和 DeepSeek 调用须另定精确窗口与费用范围。

### G5 手动 staging 路径（不运行 GitHub Actions）

`src/scripts/Invoke-StagingManualG5.ps1` 复用上述 Rootless 门禁，在 `crmdeploy` 的持久源码目录手动执行。新部署要求干净 Git clone 对应经 GitHub 验证的当前 `main` 完整 SHA；默认恢复和上一版回滚允许使用原先审核过的历史提交，但必须核对候选 backend 的 OCI revision 与该源码 SHA 一致。全部镜像均须使用指定 GHCR 仓库的不可变摘要。运行人须先用 GitHub 凭据建立私有仓库只读和 `read:packages` 访问；凭据可来自进程环境中的 `GH_TOKEN` 或已登录的 `gh`。脚本把短期 GHCR 登录限制在 `/run/user/1004` 下的私有目录，并在退出时注销。不要把 Token 放进命令参数、证据或仓库。发布新候选镜像另需 `write:packages` 和精确资源授权，部署只读凭据不具备该权限。

真实 50 客户端窗口另用 `src/backend/scripts/sample_sse_staging_resources.py` 从 `crmdeploy` 主机账户只读采样：`DOCKER_HOST` 固定为 Rootless socket，传入实际运行的 backend 不可变摘要、1～300 秒采样时长和 1～10 秒间隔，结果独占写入已创建且属 `crmdeploy`、权限 `0700` 的 `/home/crmdeploy/.cache/crm-g5-manual/<本次批次>/resources.json`。在负载开始前启动，负载结束后向采样进程发送 `SIGTERM` 并等待其写完报告，然后立即执行恢复门禁。报告只保留三个固定容器的 CPU、内存、进程峰值，以及 backend:8000 的已建立连接、TCP 待接收连接队列和收发队列字节峰值；当前 `/chat/query` 是同步工作流，没有独立业务队列，报告明确标记 `application_queue=not_applicable_sync_workflow`。任何容器缺失、镜像不符、监听缺失、解析失败或零样本都失败关闭。采样器不发模型请求，也不记录凭证、连接地址、原始日志或响应正文；它的 `passed` 只证明采样完成，不代表 50 客户端容量门禁通过。

只在确认可经受控 SSH 进入主机、从可访问的源码目录切换到 `crmdeploy` UID 1004、Rootless socket 为 `unix:///run/user/1004/docker.sock` 后继续。只读与内容操作可沿用受审归档传输方式：按操作核对源码提交（新部署为当时远端 main，恢复可为原已审核提交），用 `git archive --format=tar` 生成包并记 SHA-256；把归档和 SHA-256 作为同一恢复点转入 staging，独立解包到此前不存在的 `/home/crmdeploy/src/crm-reviewed-source-<唯一小写标识>/`。运行时另传 `-ArchivePath /home/crmdeploy/src/<包名>.tar -ArchiveSha256 <本机核对值>`；入口会再次核对归档哈希、全部解包文件内容、路径安全与 GitHub 仓库提交；仅新部署要求该 SHA 仍为当前 main，归档内 UID/GID 不参与比较。也可用 GitHub 凭据直接 clone 对应的已审核提交到同一格式的持久目录，此时不传归档参数，入口要求干净 checkout 和准确的 Git HEAD。R23 现场确认下层生产门禁仍要求 Git checkout：`DeployG5`、`RestoreDefault`、`RestoreReadAndTranslation` 和 `RollbackPrevious` 必须从干净的持久 Git clone 执行且不传归档参数；归档解包目录仅用于 `CheckOnly` 和三种内容模式。两种方式都不得复用 Runner 临时目录或覆盖现有源码。核对镜像发布证据的 backend 摘要和 `org.opencontainers.image.revision`；前端、检索和上一版三摘要由当前运行证据与 Rootless inspect 读取，不猜测或使用浮动 tag。先执行 `CheckOnly`；它不创建凭据、证据或改动服务。每个写入模式使用唯一 `/home/crmdeploy/.cache/crm-g5-manual/<唯一小写标识>/` 证据目录，传入全部六个摘要及相同 SHA：

```text
pwsh src/scripts/Invoke-StagingManualG5.ps1 -Mode CheckOnly|DeployG5|RestoreDefault|RestoreReadAndTranslation|RollbackPrevious \
  -SourceSha <完整 main SHA> -CandidateBackendImage <backend@sha256:...> \
  -FrontendImage <frontend@sha256:...> -RetrievalModelImage <retrieval@sha256:...> \
  -PreviousBackendImage <上一 backend@sha256:...> \
  -PreviousFrontendImage <上一 frontend@sha256:...> \
  -PreviousRetrievalModelImage <上一 retrieval@sha256:...> \
  -ConfirmTarget staging -EvidenceDirectory <唯一私有证据目录> \
  [-ArchivePath <已核对 tar 路径> -ArchiveSha256 <本机核对的 64 位 SHA-256>]
```

PowerShell 多行续接应使用反引号；上面是参数示意，不是可直接粘贴的命令。`DeployG5` 在 `try/finally` 中设置并恢复受审的 Rootless 拉取模式，依次预取候选与回滚六摘要、检查 backend revision、运行 G5 `ValidateOnly`、执行 `Deploy`，保留预取/验证/部署 JSON。任一步失败都停止，不自动重试外部写入。G5 完成后使用新证据目录恢复原运行模式：若压测前仅运行默认全关闭模式，执行 `RestoreDefault`；若压测前同时运行 TikTok Webhook 只读与工作台翻译，执行 `RestoreReadAndTranslation`。两者都使用同一候选摘要，关闭 backend 通用模型和 SSE、恢复限流 10；后者还要求运行态的 TikTok 只读与工作台翻译均为 true。不能以 `RestoreDefault` 关闭已有能力后声称恢复成功。若候选已完整运行且需要切回上一版，再用新目录执行 `RollbackPrevious`，它复用原回滚演练脚本，保持候选 egress helper 并切回上一版应用镜像。若部署中途失败、候选尚未完整运行，先人工核对实际容器状态和证据；回滚脚本要求候选运行态，不可盲目调用。恢复必须经过各自原门禁的 validate、健康与固定出口验证，随后只读核对运行摘要和公网健康。原始 G5 凭证池与合成数据仍保留在仓库外；单会话安全 `delta`、50 并发、队列/资源采样及 DeepSeek 调用各自需要现场证据，不能以脚本或部署成功代替 G5 通过。

合成内容使用同一手动入口的 `ContentCheck`、`ContentPrepare`、`RenewCredentials` 模式。三者要求 GitHub 可验证的受审源码完整 SHA 与运行中 backend 镜像 OCI revision 相同；证据合并使 main 前进后仍可使用原受审 SHA，六个镜像参数、GitHub 凭据、持久审核源码与归档核对方式和上例相同；`-EvidenceDirectory` 每次使用新的私有目录。`ContentPrepare` 另传 `-ConfirmContent prepare-50-isolated-g5-messages`；`RenewCredentials` 另传 `-ConfirmContent renew-50-existing-g5-tokens`；只读 `ContentCheck` 不传确认值。容器固定 `--workdir /opt/crm-g5-source`，只读挂载审核源码；脚本核对运行镜像、数据库目标、原 R05 两份仓库外凭证、签名配置和知识服务契约。先执行 `ContentCheck`，仅在 `fixture_state=original` 且现场写入获得精确授权后执行一次 `ContentPrepare`；结果不确定时停止并只读对账，不能盲重试。再执行 `ContentCheck` 等待 `knowledge_ready=true`，然后在单独获准的凭证写入范围内执行一次 `RenewCredentials`。新凭证仅保存在仓库外，原文件保留；续期后 `ContentCheck` 可只读验签第三份文件并核对原 50 个用户/会话映射，续期结果不确定时用它对账，始终禁止重跑 `RenewCredentials`。低敏报告只记录 `credentials_state` 枚举并写入本次私有证据目录的 `content.json`。源码实现不代表现场已写入或 G5 通过。

若 G2 仅改变后端，先在当前 main 精确 SHA 上使用 `Publish backend image for staging` 工作流发布单个 backend 私有镜像并核对摘要和层大小，再沿用已验证的 frontend、retrieval-model-service 摘要进行预取及门禁。镜像发布需独立授权；不得为方便而重建大体积检索镜像。

`Inspect staging TikTok Webhook subscriptions` 只读取运行中 backend 的官方订阅摘要，要求输入实际运行的 backend 不可变摘要。结果仅含主题、订阅数和地址匹配数；它不替代官方事件投递验收，也不修改常驻开关或平台订阅。

TLS 只由新服务器宝塔管理，旧服务器 staging 环境文件不需要 `TLS_CERT_DIR`。常规部署中 backend、frontend 和 retrieval-model-service 必须使用目标远端 main SHA 发布的 `repository@sha256:` 完整摘要；`release/images/mvp-production-gates.json` 中的历史 `f7c0f9f9` 候选不得复用。本轮根据用户明确的 staging 门禁豁免，部署了 source `5099fc08d1ab0efbc30d679649bee32a7395ec36` 发布的三个不可变摘要；已用 `git diff --quiet 5099fc08...98460796 -- src/backend src/frontend src/docker/Dockerfile.backend src/docker/Dockerfile.frontend.prod src/docker/Dockerfile.model-service` 确认它们的全部构建输入与最终运行 subject 一致。该豁免不自动适用于后续或 production 部署。

## 4. 活动部署顺序

以下十一步必须按顺序执行。任一步失败都停在最近恢复点，不串行尝试多个补救。

### 4.1 建立保护基线

1. 在旧服务器记录系统 Docker 容器 ID、名称、镜像 ID、StartedAt、Running 和端口，按名称排序后保存到 `0600` 证据文件并计算 SHA-256。
2. 记录 Rootless `docker info` 的 socket、security options、data-root、磁盘和当前容器/卷摘要。
3. 在新服务器记录 Nginx 版本、监听、全部 vhost 文件名/摘要和 staging vhost 元数据；只备份 staging vhost，不复制证书私钥。
4. 基线中发现 `18081` 被占用、GitLab 不健康、公司容器变化、其他 vhost 异常或磁盘不足时立即停止。

### 4.2 上传与 main SHA 绑定的资产

只从已经合并的远端 main 导出跟踪文件，计算包摘要，在旧服务器创建此前不存在的 `/home/crmdeploy/src/split-ingress-$MAIN_SHA/`。目录归 `crmdeploy:crmdeploy`，权限 `0750`；不得覆盖已有 SHA 目录。部署必须从该目录运行，不从 Runner 的临时 checkout 复制秘密。

### 4.3 把公网入口置于 HTTP 503

把 `/www/server/panel/vhost/nginx/staging.overselfx.com.conf` 精确备份到本轮受限目录，安装 `public-nginx/staging.overselfx.com-http.conf`。每次变更必须先执行：

```bash
/www/server/nginx/sbin/nginx -t
/www/server/nginx/sbin/nginx -s reload
```

`nginx -t` 非零时不 reload。此阶段除 `/.well-known/acme-challenge/` 外都必须返回 `503`，包括 `/healthz`；不得继续代理当前错误的 GitLab 隧道。

### 4.4 校验账号并切换隧道

公网账号已存在时只读确认 nologin、无 sudo/附加组、`authorized_keys` 单行限制和回环 `permitlisten`。只有账号需要新建或已知配置与已审查资产完全相同时，才以 root 使用 `install-public-tunnel-account.sh`；脚本遇到未知授权行会失败，不覆盖。

旧服务器以 `crmdeploy` 从版本化目录运行：

```bash
./install-reverse-tunnel.sh
```

安装器核验 UID、home、`0700` secret 目录、`0600` 私钥/known_hosts、固定 Ed25519 主机指纹和 systemd unit，然后显式 restart 并从运行中 SSH 进程参数验证已切换为 `18080 → 18081`；仅 `enable --now` 不能用于替换既有错误隧道。CRM 尚未启动时新服务器连接 `18080` 失败是预期，公网继续保持 `503`。

### 4.5 验证镜像、配置和模型

GitHub `staging` Environment 只保存环境文件路径和公开 Base URL，不保存环境正文：

```text
Secret: CRM_STAGING_ENV_FILE=/home/crmdeploy/config/crm-staging.env
Variable: CRM_STAGING_BASE_URL=https://staging.overselfx.com
```

从镜像发布 artifact 程序化读取三条 RepoDigest，核对 `source_sha`、manifest digest 和 OCI `org.opencontainers.image.revision`。使用 `Staging production gates` 的 `validate` 操作；非零退出、证据缺失或任何 digest 漂移都停止。门禁固定按 `docker-compose.yml → docker-compose.prod.yml → docker-compose.tiktok-egress.yml → docker-compose.rootless-staging.yml` 顺序解析，拒绝缺少 overlay、helper 发布端口、错误网络、可写根文件系统、额外能力、非只读密钥挂载或应用容器取得密钥。

`Staging production gates` 的 `validate` 可在 Runner 临时目录解包受审源码；`deploy` 与 `rollback` 必须在 `/home/crmdeploy/src/crm-reviewed-source-<run-id>-<attempt>/` 解包同一已校验 SHA-256 的源码包。Rootless Compose 的 proxy 相对配置路径由该持久目录解析，不能指向 Runner 临时目录。每次运行使用唯一目录，目标已存在即失败；运行中的 proxy 仍引用该目录时不得清理。部署后用 Rootless `docker inspect` 核对 `/etc/nginx/nginx.conf` 的只读 bind 来源和源文件摘要，再做一次代理重启与公网健康复测。

### 4.6 部署 Rootless CRM

用与 validate 完全相同的三条 RepoDigest 触发 `deploy`。门禁固定使用 `crm-staging`、Rootless socket、上述四个 Compose 文件、`ai` profile、`--no-build --wait --wait-timeout 600`，并强制所有真实能力关闭。helper 使用候选 `BACKEND_IMAGE`，不使用浮动镜像或目标机 build。执行顺序固定为：

1. 启动并等待 PostgreSQL/Redis/MinIO 健康；
2. 启动并等待 `tiktok-egress` helper 健康；
3. 从同一候选 backend 镜像运行 `python scripts/verify_tiktok_egress.py`，要求 `configured_ip` 与 `observed_ip` 都为 `38.55.145.52`；
4. 用候选 backend RepoDigest 执行一次性 `alembic upgrade head`，再以 `alembic current --check-heads` 失败关闭；
5. 最后才启动 backend/worker/jobs/agent-worker/frontend/proxy/retrieval-model-service。

出口验证失败、代理不可达或观察值不一致时不得继续，也不得改用主机直连。通过证据只记录状态和两个 IP，不记录代理 URL、密钥路径内容、公钥、指纹或凭据。

首次部署没有兼容的上一 CRM 实例。部署前只记录“无既有 Rootless CRM 容器/卷”的事实，不创建伪备份。任何容器不健康时停止候选并保留卷，公网继续 `503`。

### 4.7 在切公网前验证内链路

- 旧服务器只有 `127.0.0.1:18081` 提供 proxy，所有 Compose 容器 running/healthy；deploy 证据中 `database_migration=heads_applied`，现场 `alembic current` 显示 `023_marketing_review_idempotency (head)`。
- 新服务器通过带固定 Host 的 `http://127.0.0.1:18080/healthz` 验证 SSH→CRM 链路。
- 响应出现 `X-Gitlab-*`、`/users/sign_in`、其他站点内容或 LAN/公网 18080/18081 监听时立即失败。

### 4.8 通过宝塔签发证书

验证本机、`1.1.1.1` 和 `8.8.8.8` 的 A 记录均为 `38.55.145.52`。用随机低敏文件确认 ACME webroot 可达并立即删除，再通过宝塔站点 SSL 流程为唯一域名 `staging.overselfx.com` 申请 Let's Encrypt RSA2048。不得安装新的 ACME 客户端、读取宝塔数据库凭据或复用其他站点证书。

只读取公开证书信息，核验 SAN、链、有效期和证书/私钥公钥匹配；不得输出私钥正文。

### 4.9 安装正式 HTTPS vhost

安装 `public-nginx/staging.overselfx.com.conf`，先 `nginx -t` 再 reload。正式入口要求：

- HTTP 除 ACME 外 301 到 `https://staging.overselfx.com`；
- 443 只代理 `http://127.0.0.1:18080`；
- Host、客户端地址和 `X-Forwarded-Proto=https` 由公网层覆盖；
- SSE 两层关闭 buffering；
- access log 只记录 `$uri`，OAuth callback/Webhook 的原生错误日志关闭。

### 4.10 动态验证和恢复检查

分别运行：

```bash
# 新服务器
./verify-split-ingress.sh public

# 旧服务器
./verify-split-ingress.sh business
```

同时从外部验证首页精确返回 `307` 且只有一个 `Location: /dashboard`，`/healthz`、`/v1/health` 和 `/v1/health/ready` 均返回 200；重复或其他首页跳转目标必须失败关闭。随后只重启一次旧服务器用户级 `crm-staging-tunnel.service`，记录断开期间 `502/503`、重新监听和健康恢复时间；不得重启 sshd、Nginx、系统 Docker 或公司容器。

前端镜像或入口缓存配置变化时，还必须从**公网无查询参数**对 `/login`、`/marketing`、`/knowledge`、`/settings/stores` 分别执行 GET（例如 `curl -sS -D - -o /dev/null https://staging.overselfx.com/marketing`）：四个路径均为 200，`Cache-Control` 含 `no-store`，不出现旧 `x-nextjs-cache: HIT` 或长期 `s-maxage`。再从页面引用的 `/_next/static/` 指纹 JS 取样确认 200 和 `immutable`。随机 query 命中新的缓存键不能替代精确路径检查；任一项失败都不得把 UI 部署标为完成，须按入口与回环分层定位并保留恢复点。

### 4.11 复核公司负载和其他站点

重新生成旧服务器系统 Docker 的六字段规范化摘要，与 4.1 基线逐字比较。复核新服务器其他 vhost 文件摘要和选定站点 HTTP 状态。任一非 staging 漂移都恢复 staging HTTP `503`、停止后续步骤并交由运维判断，不自动“修复”公司负载。

## 5. 失败关闭与恢复

- Nginx 变更失败：保留或恢复已验证的 HTTP `503` vhost，`nginx -t` 成功后才 reload。
- 隧道失败：保持公网 `503`；检查用户级 unit、回环监听和固定主机指纹，不放宽 SSH 权限。
- 镜像/配置失败：不启动 Compose，不使用历史或浮动标签替代。
- TikTok helper/出口失败：保持全部真实 TikTok 开关为 false，停止候选应用；禁止从 SOCKS5H 回退为业务服务器直连。应用镜像回滚时继续使用包含当前 helper 资产的候选 backend 镜像，只把 backend/worker/jobs 等应用切换到已验证的上一 RepoDigest。
- 首次部署不健康：停止候选应用，保留 PostgreSQL/MinIO/Rootless 卷，不删除数据。
- 公开响应为 GitLab：立即恢复 `503`，核对隧道必须是 `18080 → 18081`；不得调整 GitLab `10080/10443`。
- 无兼容上一版镜像时不得调用“回滚成功”；真正的数据库/对象恢复和兼容版本回滚仍是独立 G0 阻断项。

## 6. 证据与放行边界

原始主机快照保存在本轮受限服务器目录，仓库只记录低敏摘要、SHA、workflow run、健康状态、恢复时间和前后基线比较。禁止记录 `.env` 值、私钥、Token、Cookie、证书私钥、模型、备份或客户数据。

完成 split-ingress 部分只证明 `MVP-STAGING-001` 的失败关闭 staging 基础设施。固定出口还必须使用合并 main 的不可变镜像完成真实 IP、断隧道无直连回退、入口和公司负载复核；当前实现分支上的 live-staging 状态为 `NOT_EXECUTED — requires merged main image`。TikTok OAuth/读取、Webhook、人工消息、DeepSeek/RAG、50 客户端 SSE、五日稳定性、数据库/对象恢复、兼容回滚和 production 放行仍按 G0～G8 独立取得证据；所有真实能力保持关闭。

#### G5 单条合成 FAQ 的一次性本地向量化

`VectorizeG5` 只用于 R24 已准备的隔离店铺唯一内部审阅 FAQ。它要求受审脚本取自**运行时远端当前 main** 的干净持久 Git clone，`-SourceSha` 为该 main 完整 SHA；`-RuntimeBackendSourceSha` 为现场运行后端镜像的 OCI revision（允许该镜像较旧）。其余六摘要按运行现场提供，`-ConfirmContent vectorize-one-isolated-g5-faq`，证据使用全新私有目录。脚本把当前 main 的完整受审 backend 源码只读挂入当前后端镜像，满足原有容器挂载安全门禁，一次性容器临时开启 `EMBEDDING_ENABLED=true`，强制关闭通用 LLM 与 TikTok 写入，且仅允许 `http://retrieval-model-service:8010` 的本地 BGE-M3；常驻服务配置不变。认领 SQL 限定原店铺、原文档、版本 1、内部审批与 pending，且只认领 1 条。若结果不确定，停止并使用旧运行镜像及其受审源码运行 `ContentCheck` 只读对账；绝不盲目重试向量写入。此操作不续期凭证、不运行 SSE 或 DeepSeek，也不表示 G5 通过。
