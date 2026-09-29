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

该路径已于 2026-09-21 在两台真实服务器上完成部署与验收：DNS、Let's Encrypt SAN/证书链、公网健康、迁移头、Rootless 容器、隧道自恢复和公司负载零变化通过，见 `MVP-STAGING-001` 定稿 IR/TR/RR 与 `release/evidence/staging/`。2026-09-29 已从活动 PostgreSQL/MinIO 建立受限备份，恢复至独立数据库和无公网端口的隔离 MinIO 实例；原业务桶为空，合成对象仅在隔离实例中验证二次备份与字节恢复，见 `MVP-008-RESTORE-001` 记录。兼容上一版镜像的实际回滚仍缺，G0 与 production 不放行。

### Staging 凭据终态

2026-09-21 已在业务服务器完成 `MVP-001` 凭据轮换：`POSTGRES_PASSWORD`、对应 `DATABASE_URL`、`MINIO_SECRET_KEY`、`JWT_SECRET_KEY`、`RETRIEVAL_MODEL_SERVICE_TOKEN` 已更新，并首次生成 `TIKTOK_CREDENTIAL_ENCRYPTION_KEY`。活动环境文件固定为 `/home/crmdeploy/config/crm-staging.env`、`crmdeploy:crmdeploy`、模式 `0600`；密钥值、摘要和可逆材料不进入 Git、日志或响应。

轮换验收必须同时证明新 PostgreSQL、MinIO 和检索令牌可用且旧值被拒绝，四个应用容器取得相同的新数据库/MinIO/JWT 配置，真实 TikTok、LLM、AI 和自动回复开关继续失败关闭。PostgreSQL 容器的 localhost 规则允许 trust，因此口令正反例必须从 backend 容器经 `postgres:5432` 验证；backend 被重建后必须重启 proxy 以刷新 Nginx 上游地址，再检查三个公开健康端点。staging 部署门禁和回滚演练已将 proxy 重启及健康等待纳入自动流程。

成功轮换的 root-only 恢复副本位于 `/var/backups/crm-staging/secrets/20260921T080357Z/crm-staging.env.before`。两次失败尝试在变更前/回滚后留下的受限重复副本尚未删除；删除必须另立 `MAINT-CLEANUP-*` 任务和精确批次。

2026-09-23 又仅在 staging 经 SSH 受限通道注入 TikTok App Key、Service ID、App Secret 和 DeepSeek API Key；活动 env 仍为 `crmdeploy:crmdeploy:0600`。仅重建 backend、worker、jobs、agent-worker 并刷新内层 proxy，实际镜像摘要未变，按进程职责验证四项凭据可见性、所有真实能力开关为 false、日志/健康响应未泄漏、三个公网健康端点 200、固定出口仍为 `38.55.145.52`、公司 system Docker 未变。旧 env 的 root-only 恢复副本为 `/var/backups/crm-staging/secrets/external-20260923T025011Z/crm-staging.env.before`；第一次尝试因一次性工具的工作目录权限在容器变更前失败，原配置已恢复并独立复核，修正后复用同一恢复副本完成注入。传输用 `/run` 临时文件已删除，实际密钥值和摘要不进入仓库。**这只证明安全注入和应用生效，不证明 TikTok/DeepSeek 平台已接受凭据**；真实 OAuth、Webhook 投递及 DeepSeek 调用仍按 G1/G2/G4 独立验收，production 未变更或发布。

`TIKTOK_WEBHOOK_SECRET` 只服务于本地 Mock 的 `X-TTS-Signature` 回归，不是需要从 Partner Center 单独获取的真实 Webhook 凭据。真实 Webhook 验签使用已注入的 `TIKTOK_APP_SECRET` 对 `TIKTOK_APP_KEY + 原始请求体` 计算 HMAC-SHA256，并与 `Authorization` 比较；该 Mock 字段在 staging 保持空值。此前把它列为外部凭据准备项的说明由本节纠正，不得生成任意值冒充平台密钥。

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

本次用户仅限 staging 授权继续使用已验证的 backend/frontend 不可变摘要（与候选 `746c10c` 的构建输入零差异）和旧检索镜像摘要（检索服务源码与 Dockerfile 不变，但依赖锁文件**不同**）。新摘要 GHCR 下载失败/停滞不能写成已部署；下次镜像升级和 production 必须重新通过独立摘要与供应链门禁，不能沿用此例外。production 仍仅有可复用配置契约，未选择出口服务器、创建账号/密钥或实施部署。

2026-09-23 UI 修复合并后，`main` 的 `58263b1` 已单独发布到 staging：新 frontend `e5d6bbfc...`、backend/helper `a3bb63c4...` 正在运行且健康，门禁 `35849490309`、固定出口、迁移头和三个公网健康端点均通过。全量同源尝试 `35845426383` 在新检索镜像下载阶段取消，取消前没有容器切换；用户为**这一次 staging UI 部署**另行批准保留当前健康的旧检索摘要 `bc99dfa3...`。检索服务源码/Dockerfile 相同，但依赖锁不同；这是明确的运行版本偏差，不是新检索镜像已部署或 production 供应链通过。恢复点、前后保护基线和未测项见 `release/evidence/staging/crm-staging-ui-rollout-20260923.json` 与 `MVP-UI-DEPLOY-001` R01。前一段固定出口任务的历史豁免仍只属于那次验收，本次授权不能延伸到下一次镜像升级。

## TikTok 与 DeepSeek

- TikTok OAuth 回调在 staging 使用 `staging.overselfx.com`、在 production 使用 `www.overselfx.com` 的 HTTPS 固定地址，state 默认 600 秒、哈希存储并原子消费。
- Webhook 真实模式使用官方签名和原始请求体；开发签名只能在真实开关关闭时使用。
- Token 加密保存，刷新失败将渠道置为 `expired`；日志和响应不输出 Token 或凭证引用。
- DeepSeek Key 只从环境读取，Provider 使用固定正向输入协议、DLP 和结构化输出。
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

staging 镜像回滚准备阶段使用 `staging-gates.yml` 的 `prefetch` 操作：自托管 Runner 仅凭当次 `GITHUB_TOKEN` 的 `packages: read` 权限，将候选与上一版的后端、前端、检索服务六个不可变摘要拉到 `crmdeploy` Rootless Docker 并核对本地 RepoDigest。该操作不读取 staging 环境文件、不重建容器、不改活动数据，也不代表回滚通过。只有独立恢复库上的旧版兼容性检查、镜像预取、受限备份和切返路径都确认后，才可在维护窗口执行实际切回/切返；现有 `rollback` 操作本身**不会自动切返**，必须单独验证恢复候选运行态。production 不使用本操作。

## 发布入口

当前发布状态见 `docs/operations/RELEASE-GATES.md`，最新测试摘要见 `docs/quality/TEST-STATUS.md`，固定资产与评测集见 `release/baselines/` 和 `release/evidence/`。部署说明不替代真实签署。
