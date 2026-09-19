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

当前仓库已实现该路径，但真实服务器部署、正确 SAN 证书、公开健康、恢复和回滚只有在本轮现场证据完成后才能记为通过；工程资产存在不等于 staging 或 production 放行。

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
