# 部署与运行边界

## 环境分层

- 本地/测试：默认 Mock 外部平台，不需要真实密钥。
- Staging：验证真实 OAuth、Webhook、只读、人工消息、DeepSeek、容量、稳定性和恢复。
- Production：只接受固定镜像、迁移、配置、模型资产和发布基线；所有门禁签署后才能放行。

Compose 以 `src/compose/docker-compose.yml` 为基础文件，再叠加同目录的环境覆盖；环境变量只通过部署环境或密钥管理注入。仓库中的 `src/config/.env.example` 只描述变量，不含真实值。

## Split-ingress Rootless staging

当前 staging 固定使用双服务器入口分离：`staging.overselfx.com:443 → 38.55.145.52 宝塔 Nginx/TLS → 127.0.0.1:18080 → SSH 反向隧道 → 192.168.110.210:127.0.0.1:18081 → crmdeploy Rootless CRM`。Compose 项目名为 `crm-staging`，Docker socket 为 `unix:///run/user/1004/docker.sock`，数据和模型均留在 `/home/crmdeploy`。

旧服务器系统 Docker 的 GitLab 已占用 `10080/10443`，这些容器、端口、卷、网络和 data-root 禁止修改。CRM 只发布单个回环 HTTP 端口 `18081`，不在旧服务器终止 TLS；历史同机 systemd 入口只作为 Git 历史，不是当前操作路径。新服务器只承载宝塔 Nginx、站点证书和回环隧道监听，不运行 CRM 数据或模型服务。

活动运行手册和恢复顺序位于 `src/deploy/staging/rootless/README.md`：先建立公司负载与站点保护基线，上传与 main SHA 绑定的版本化资产，把公网入口置为 HTTP `503`，再切换 `18080 → 18081` 隧道；完成不可变镜像/配置 validate 和 Rootless deploy 后，通过宝塔签发证书，安装正式 HTTPS vhost，执行动态健康、隧道重连和公司负载复核。任何阶段失败都恢复 staging `503`、停止候选并保留数据卷，不切回 GitLab。

该路径已于 2026-09-21 在两台真实服务器上完成部署与验收：DNS、Let's Encrypt SAN/证书链、公网健康、迁移头、Rootless 容器、隧道自恢复和公司负载零变化通过，见 `MVP-STAGING-001` 定稿 IR/TR/RR 与 `release/evidence/staging/`。数据库/对象存储恢复和兼容版本回滚仍是后续 G0 门禁；staging 通过不等于 production 放行。

### Staging 凭据终态

2026-09-21 已在业务服务器完成 `MVP-001` 凭据轮换：`POSTGRES_PASSWORD`、对应 `DATABASE_URL`、`MINIO_SECRET_KEY`、`JWT_SECRET_KEY`、`RETRIEVAL_MODEL_SERVICE_TOKEN` 已更新，并首次生成 `TIKTOK_CREDENTIAL_ENCRYPTION_KEY`。活动环境文件固定为 `/home/crmdeploy/config/crm-staging.env`、`crmdeploy:crmdeploy`、模式 `0600`；密钥值、摘要和可逆材料不进入 Git、日志或响应。

轮换验收必须同时证明新 PostgreSQL、MinIO 和检索令牌可用且旧值被拒绝，四个应用容器取得相同的新数据库/MinIO/JWT 配置，真实 TikTok、LLM、AI 和自动回复开关继续失败关闭。PostgreSQL 容器的 localhost 规则允许 trust，因此口令正反例必须从 backend 容器经 `postgres:5432` 验证；backend 被重建后必须重启 proxy 以刷新 Nginx 上游地址，再检查三个公开健康端点。staging 部署门禁和回滚演练已将 proxy 重启及健康等待纳入自动流程。

成功轮换的 root-only 恢复副本位于 `/var/backups/crm-staging/secrets/20260921T080357Z/crm-staging.env.before`。两次失败尝试在变更前/回滚后留下的受限重复副本尚未删除；删除必须另立 `MAINT-CLEANUP-*` 任务和精确批次。TikTok Partner Center 与 DeepSeek 的外部凭据仍为空，待对应 G1/G4 真实验收时由用户在服务器受限通道注入；production 未变更、未发布。

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

1. 在维护窗口验证镜像、配置、模型哈希和数据库迁移，当前迁移头为 `023_marketing_review_idempotency`。
2. 部署前完成数据库和对象存储备份，并验证可读取性。
3. 先迁移再启动应用；健康检查、Webhook、SSE 和关键人工流程通过后再切入口。
4. 回滚使用已验证的上一镜像和兼容迁移路径；禁止 `git reset --hard` 或手工改生产表。
5. 真实恢复和回滚演练证据缺失时，发布门禁保持阻塞。

## 发布入口

当前发布状态见 `docs/operations/RELEASE-GATES.md`，最新测试摘要见 `docs/quality/TEST-STATUS.md`，固定资产与评测集见 `release/baselines/` 和 `release/evidence/`。部署说明不替代真实签署。
