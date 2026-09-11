# 双服务器入口分离 Rootless Staging 部署设计

日期：2026-09-11  
状态：已批准  
目标环境：`staging`  
公共域名：`staging.overselfx.com`

## 1. 目标

在不停止、不重启、不迁移公司现有系统 Docker 及其运行中容器的前提下，把 CRM staging
拆为公网入口和业务运行两个节点：

- `38.55.145.52` 只承担域名、TLS 和宝塔 Nginx 公网入口；
- `192.168.110.210` 使用已经就绪的 `crmdeploy` Rootless Docker 运行完整 CRM Compose；
- 业务服务器主动建立到公网服务器的受限反向 SSH 隧道，避免继续依赖
  `183.158.225.78` 的公网入站 NAT；
- 保留不可变 GHCR 镜像、模型六文件 SHA-256、迁移 `023`、失败关闭和 G0～G6 证据边界；
- staging 只验证 ADR-006 定义的 TikTok 人工辅助首版，不决定 production 最终部署方式。

本设计属于架构调整。它取代
`docs/superpowers/specs/2026-09-09-rootless-staging-deployment-design.md` 和 ADR-007 中
“公网直接进入业务服务器 80/443”的入口部分；Rootless 运行隔离、供应链、模型、Runner、
应用能力和验收边界继续有效。

## 2. 范围与非目标

### 2.1 范围

- 为 `staging.overselfx.com` 建立独立宝塔 Nginx 站点和公信 TLS；
- 建立业务服务器到公网服务器的回环反向 SSH 隧道；
- 为 Rootless staging proxy 增加仅供隧道使用的明文 HTTP 上游入口；
- 更新 staging 部署脚本、工作流、运行手册、架构决策、放行检查表和两个索引；
- 以全部真实能力关闭的状态完成首次部署，再按 G0～G6 逐项开启和验证；
- 验证公司系统 Docker 容器、网络、端口、数据卷和 data-root 前后不变。

### 2.2 非目标

- 不把 CRM 部署到 `38.55.145.52`，该服务器资源只用于入口；
- 不修改公司系统 Docker 的 `/var/lib/docker`、daemon、网络、卷或现有容器；
- 不要求公网服务器访问 `192.168.110.210` 的内网地址；
- 不开放 Rootless Docker API、数据库、Redis、MinIO、后端或模型服务到公网；
- 不实现 Shopee/Amazon 真实接入，不删除其产品和 UI 占位；
- 不启用 TikTok 高风险写入、自动回复、自动营销或无人值守发送；
- 不把 staging 的 Rootless 决策自动延伸到 production。

## 3. 现状与约束

### 3.1 公网入口服务器 `38.55.145.52`

- Ubuntu 24.04.1，2 vCPU、约 2 GiB 内存、根盘约 31 GiB 可用；
- 公网地址直接绑定网卡，外部 TCP 80/443 已验证可达；
- 宝塔 Nginx 1.30.4 已承载其他站点；
- SSH 允许 TCP 转发，`GatewayPorts=no`，可保证反向端口仅监听回环；
- 资源不足以稳定承载 CRM、PostgreSQL、MinIO 和两个 BGE 模型。

### 3.2 业务服务器 `192.168.110.210`

- 8 vCPU、约 30 GiB 内存，`/home` 约 348 GiB 可用；
- 根分区约 97% 已使用，禁止把 CRM 镜像和数据写入系统 Docker data-root；
- 系统 Docker 有 14 个容器、其中 12 个运行，属于公司既有负载；
- `crmdeploy` Rootless Docker、用户级 systemd、专用 GitHub Runner 和
  `/home/crmdeploy/assets/models` 六个模型文件已经就绪；
- Rootless 数据位于 `/home/crmdeploy/.local/share/docker`；
- 业务服务器可以主动访问 `38.55.145.52:22/443`；
- `183.158.225.78` 不是业务服务器网卡地址，既有公网 80/443 入站探测未到达该主机。

## 4. 方案选择

采用“公网宝塔 Nginx + 受限反向 SSH 隧道 + 业务服务器 Rootless Docker”。

```text
浏览器 / TikTok
    │ HTTPS :443
    ▼
38.55.145.52 宝塔 Nginx
    │ HTTP → 127.0.0.1:18080
    ▼
受限 SSH 反向隧道
    │ 38.55.145.52:127.0.0.1:18080
    │       → 192.168.110.210:127.0.0.1:10080
    ▼
crmdeploy Rootless Docker proxy
    ├── frontend
    ├── backend / workers
    ├── retrieval-model-service
    ├── PostgreSQL + pgvector
    ├── Redis
    └── MinIO
```

不采用以下方案：

- 公网服务器运行完整 CRM：内存不足，模型和数据库运行风险高；
- 业务服务器原生部署：重复安装和维护 PostgreSQL、pgvector、Redis、MinIO、Node 和 Python；
- 业务服务器系统 Docker：根盘空间不足，并与公司容器共享高权限 daemon；
- 继续依赖 `183.158.225.78` NAT：外部探测没有到达业务服务器，链路不受项目控制。

## 5. 组件与端口

### 5.1 公网服务器

宝塔 Nginx 新增且只修改 `staging.overselfx.com` 对应 vhost：

- `80/tcp`：只把该域名重定向到 HTTPS；
- `443/tcp`：终止 TLS，转发到 `http://127.0.0.1:18080`；
- `/v1/chat/query`：关闭 proxy buffering，保留 SSE 心跳和 120 秒以上读取超时；
- `/v1/integrations/tiktok/oauth/callback`：访问日志不记录 query string，错误日志不得记录
  `code`、`state` 或 Token；
- `/healthz`、`/v1/health`、`/v1/health/ready`：用于全链路、存活和就绪检查；
- 传递受控的 `Host`、`X-Forwarded-Proto=https`、`X-Forwarded-For` 和 WebSocket/SSE
  所需头部，不信任客户端伪造的转发头。

反向隧道远端监听固定为 `127.0.0.1:18080`。实施前必须验证端口未占用，不能改用公网地址
或 `GatewayPorts=yes` 绕过回环边界。

### 5.2 业务服务器

Rootless Compose 项目名固定为 `crm-staging`，Docker socket 固定为
`unix:///run/user/1004/docker.sock`。只发布：

```text
127.0.0.1:10080 → Rootless proxy 明文 HTTP 入口
```

TLS 只在公网服务器终止。业务服务器不再需要 staging TLS 私钥，也不发布 `10443` 作为活动
入口。既有 CRM 80/443 systemd socket proxy 保持禁用；只有逐字核验属于本项目的单元后才可
调整，不删除公司或其他站点配置。

Rootless proxy 到 frontend/backend 使用 Compose 内部网络。PostgreSQL、Redis、MinIO、
retrieval-model-service、backend 和 workers 不发布宿主机端口。

### 5.3 持久化目录

继续使用：

```text
/home/crmdeploy/
├── config/crm-staging.env
├── assets/models/
├── evidence/
├── backups/
├── runner/
├── tools/
└── .local/share/docker/
```

真实环境文件保持 `0600`，模型只读挂载，备份和证据不进入 checkout。日志设置容量和轮转
上限，禁止持续写满根分区。

## 6. SSH 隧道安全设计

- 公网服务器创建无 sudo、无密码登录的专用隧道账号；
- 独立 Ed25519 密钥只用于本隧道，不复用管理员或 GitHub Runner 密钥；
- `authorized_keys` 限制该密钥只能监听 `127.0.0.1:18080`，禁止 agent/X11 转发、PTY
  和其他端口转发；
- 私钥位于业务服务器 `/home/crmdeploy` 的仓库外 `0700/0600` 目录和文件中；
- `crmdeploy` 用户级 systemd 使用 `ssh -NT`，设置
  `ExitOnForwardFailure=yes`、`ServerAliveInterval`、`ServerAliveCountMax` 和自动重启；
- 主机指纹固定写入独立 `known_hosts`，禁止 `StrictHostKeyChecking=no`；
- 安装过程只输出指纹、状态和端口等低敏信息，不输出私钥、公钥授权行或环境正文。

隧道断开时公网入口返回明确的 502/503，绝不回退到公网服务器上的其他站点或公司服务。

## 7. 域名、TLS 与外部契约

- DNS A 记录改为 `staging.overselfx.com → 38.55.145.52`；
- 公信证书在 `38.55.145.52` 的宝塔站点中申请和续期；
- staging 公共配置保持：

```text
PUBLIC_BASE_URL=https://staging.overselfx.com
PUBLIC_API_BASE_URL=https://staging.overselfx.com/v1
CORS_ORIGINS=https://staging.overselfx.com
TIKTOK_OAUTH_REDIRECT_URI=https://staging.overselfx.com/v1/integrations/tiktok/oauth/callback
```

- TikTok Partner Center callback：
  `https://staging.overselfx.com/v1/integrations/tiktok/oauth/callback`；
- TikTok Partner Center Webhook：
  `https://staging.overselfx.com/v1/webhooks/tiktok`；
- 用户入口 IP 是 `38.55.145.52`；TikTok API 请求的出口 IP 是业务服务器实际公网出口，必须
  单独实测并用于 TikTok 白名单，不能用入口 IP 推断；
- DNS、TLS、callback、Webhook、Scope 和出口白名单任何一项缺失时，真实 TikTok 门禁失败关闭。

## 8. 发布与配置

### 8.1 GitHub Flow

- 所有改动在短期分支完成，经 PR、CI、安全检查和人工审阅后 squash merge；
- 只有合并后的完整 `main` SHA 可以构建 staging 候选镜像；
- backend、frontend、retrieval 镜像和所有外部运行镜像都使用
  `repository@sha256:<64-hex>`，禁止 `latest`；
- GitHub `staging` Environment 继续使用专用 self-hosted runner；
- runner 用短期 `GITHUB_TOKEN` 拉取 GHCR，不把 PAT 写入服务器环境文件；
- 工作流保持手工触发、不并发部署、精确 `confirm_target=staging` 和失败关闭。

### 8.2 首次部署顺序

1. 记录两台服务器状态、公网 vhost 清单和公司系统 Docker 五字段基线；
2. 配置并验证受限反向 SSH 隧道，但暂不修改 DNS；
3. 新建 staging vhost，语法测试通过后再加载 Nginx；
4. 把 DNS A 记录切到 `38.55.145.52`，验证多地 80/443；
5. 申请公信 TLS，验证 SAN、证书链、有效期和私钥匹配；
6. 准备仓库外环境文件、六个模型文件和候选 RepoDigest；
7. 先执行 validate，再以全部真实能力关闭的状态部署 Rootless Compose；
8. 迁移数据库到 `023_marketing_review_idempotency`；
9. 通过首页、三个健康端点、SSE 协议和容器健康后完成 G0；
10. 按 G1～G6 逐项启用真实能力，任一门禁失败立即停止后续阶段。

### 8.3 初始失败关闭配置

首次部署固定关闭：

- 所有 Mock 适配器；
- `REAL_TIKTOK_READ_ENABLED`；
- `REAL_TIKTOK_WEBHOOK_ENABLED`；
- `REAL_TIKTOK_MESSAGE_WRITE_ENABLED`；
- `REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED`；
- `LLM_ENABLED`、`LLM_LIVE_EVAL`；
- AI 翻译、AI 营销、自动回复和所有自动平台写入。

真实 TikTok 读取、Webhook、人工普通消息、DeepSeek 建议和 RAG 只能使用现有受控 overlay 分阶段
开启。自动回复和营销发送不属于本次放行。

## 9. 回滚与故障处理

### 9.1 应用回滚

- 部署前记录候选和上一版三个应用摘要、外部镜像摘要、配置版本/SHA-256、迁移和时间；
- 只回滚到已验证兼容 staging callback 和迁移 `023` 的上一版本；
- 应用故障先关闭最小能力开关，再用固定上一版 RepoDigest 重建 `crm-staging`；
- 不使用 `latest`、不在服务器 build、不删除卷实现“回滚”；
- 数据库采用向后兼容迁移；必须恢复时，只在隔离目标验证备份后执行受控恢复。

### 9.2 入口回滚

- 新 vhost 变更前保存并校验原文件摘要；
- Nginx 配置测试失败时禁止 reload；
- 入口故障只回滚 `staging.overselfx.com` vhost 和隧道，不修改其他站点；
- 停止隧道不会停止 Rootless Compose；停止 Rootless Compose 不影响系统 Docker；
- 任何删除容器、卷、备份、证书、账号或服务器目录的动作都不属于自动回滚。

### 9.3 自动恢复与可观测性

- Rootless Docker、Runner 和 SSH 隧道使用用户级 systemd 自动恢复；
- Compose 服务使用既有 healthcheck 和依赖就绪关系；
- `/healthz` 验证公网 Nginx、隧道和 Rootless proxy 全链路；
- `/v1/health` 验证应用存活；`/v1/health/ready` 验证 PostgreSQL、Redis、MinIO 和启用的模型；
- 日志只记录 UUID trace/run ID、稳定错误码和低敏时延，不记录 query、Token、Prompt、客户正文
  或密钥；
- 隧道连续失败、容器不健康、根盘低于安全阈值或公司容器基线漂移时停止推进并保留证据。

## 10. 验收门禁

### G0 基础设施与供应链

- DNS、TLS、反向隧道、全链路健康、Rootless 隔离和迁移 `023` 全部通过；
- 公司系统 Docker 容器 ID、启动时间、镜像、状态和端口前后不变；
- 应用和外部镜像摘要、配置 SHA-256、模型六文件 SHA-256 可追溯；
- 前端生产依赖 High/Critical 为零；
- PostgreSQL/MinIO 备份、隔离恢复和兼容上一版真实回滚演练通过。

### G1 产品基础能力

- 登录/退出、JWT、RBAC 和店铺隔离通过；
- 工作台、知识库、看板和数据持久化通过；
- 页面刷新、容器重启和隧道重连后状态正确。

### G2 TikTok OAuth 与读取

- 真实账号 OAuth、Scope、Token 加密/刷新/失效和唯一店铺绑定通过；
- 订单、物流、会话、消息和订阅核对按真实契约通过；
- 真实出口 IP 和 TikTok 白名单完成核对。

### G3 Webhook 与人工消息

- Webhook 公网投递、验签、幂等、重复通知和 Worker 恢复通过；
- 单店铺、单账号、单操作员人工确认消息发送通过；
- `sent/failed/unknown`、对账熔断、审计和不自动重试行为通过。

### G4 AI 建议与 RAG

- BGE-M3 1024 维、Top-5、发布审批、店铺/版本隔离和 Reranker 通过；
- AI 建议使用真实批准 Provider，不允许 Mock 静默兜底；
- 建议只填入人工输入框，DLP、安全声明和转人工策略通过；
- AI 不可用时返回稳定错误，不触发自动平台写入。

### G5 性能与 G6 稳定性

- 50 个独立授权客户端的首个安全输出 P99 严格 `<3000ms`、总耗时 P99 严格 `<5000ms`；
- 全部请求产生安全 `delta` 并以 `done(reason=completed)` 完整结束；
- 连续五个真实日历日达到 99.5% 可用性，审计与恢复行为完整。

任何必选项失败、High/Critical 未清零、真实 TikTok/AI 链路未验证、恢复或回滚未完成，都只能
标记“代码完成/待验证”，不能宣布 TikTok 人工辅助 v0.1 可用。即使 G0～G6 全部通过，也不能
宣称三平台、自动回复和主动触达完整 MVP 已完成。

## 11. 测试与证据

权威测试报告保存在 `测试工程师/`，共享目录只更新索引。至少形成：

- 双服务器入口与 Rootless 部署综合测试报告；
- TikTok OAuth/读取/Webhook/人工消息真实链路报告；
- AI/RAG 独立复测报告；
- 前端漏洞独立复测报告；
- 备份恢复、回滚和隧道重连报告；
- G5 性能和 G6 五日稳定性报告；
- Git SHA、RepoDigest、迁移、配置、模型和评测数据 SHA-256 低敏清单。

不得把模拟结果、入口监听、容器 running、`/health` 单点成功或部署脚本退出 0 单独解释为
staging/MVP 放行。

## 12. 风险与控制

| 风险 | 影响 | 控制 |
| --- | --- | --- |
| 公网服务器已有网站 | 错误 reload 或 vhost 冲突 | 只改精确 staging vhost，保存摘要，先 `nginx -t` 后 reload |
| 隧道账号越权 | 公网服务器被横向使用 | 独立密钥、无 sudo、回环 permitlisten、禁 PTY/其他转发 |
| SSH 隧道中断 | staging 502/503 | systemd 自动重启、ServerAlive、双层健康检查 |
| 双层 Nginx 破坏 SSE | AI 流中断或缓冲 | 两层关闭 buffering、延长超时、执行完整 SSE 协议测试 |
| 错误信任转发头 | Origin/限流绕过 | 公网层覆盖可信头，内部层只接受回环来源 |
| 公司容器受影响 | 公司业务故障 | 前后五字段快照、Rootless socket 固定、任何漂移硬停 |
| 根盘写满 | 系统故障 | 镜像/卷/模型/备份放 `/home`，日志限额与根盘门槛 |
| 入口/出口 IP 混淆 | TikTok 白名单失败 | 分别实测并记录，入口 38.55.145.52 不替代业务出口 |
| 基础部署被误当 MVP 通过 | 提前放行 | G0～G6 独立报告与四层状态结论 |

## 13. 完成定义

本次实施完成必须同时满足：

1. 仓库改造经 PR、CI、人工审阅和 squash merge；
2. 公网 vhost、TLS、受限隧道和 Rootless Compose 真实运行；
3. 公司现有容器和其他网站前后状态不变；
4. 迁移、健康、备份恢复、兼容上一版回滚和安全扫描通过；
5. G1～G6 均有测试工程师权威证据；
6. 实施记录、架构决策、运行手册、放行检查表和两个索引同步；
7. 最终结论准确区分基础设施就绪、失败关闭部署、TikTok v0.1 可用和 production 放行。

