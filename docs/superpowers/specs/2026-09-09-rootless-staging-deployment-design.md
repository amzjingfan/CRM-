# Rootless Docker Staging 部署设计

日期：2026-09-09；2026-09-10 更新 staging 域名
状态：已批准
目标环境：`staging`
目标域名：`staging.overselfx.com`

## 1. 目标

在不停止、不重启、不迁移公司现有系统 Docker 及其运行中容器的前提下，在服务器
`192.168.110.210`（公网 `183.158.225.78`）上建立独立的 Rootless Docker staging
环境，部署 CRM 智能聊天系统并形成可复现的真实环境门禁证据。

本次 staging 用于证明以下内容：

- Rootless Docker 能承载项目完整 Compose 拓扑；
- 不可变 GHCR 镜像可以由受控 runner 拉取、部署和回滚；
- PostgreSQL、Redis、MinIO、应用服务和 BGE 模型服务可以在 `/home` 独立运行；
- 独立 HTTPS 域名可以承载 TikTok OAuth、Webhook、人工消息和内部 AI 建议链路；
- G0～G6 可以按既定顺序收集真实证据。

## 2. 非目标和安全边界

- 本次不迁移 production，也不决定 production 最终采用 Rootless 还是 rootful Docker。
- 不停止、重启、重建、改名或接管现有公司容器。
- 不修改系统 Docker 的 `data-root`、socket、网络或数据卷。
- 不把 `crmdeploy` 加入 `docker` 或 `sudo` 组。
- 不启用 Shopee、Amazon、TikTok 高风险写操作、自动回复、营销或无人值守发送。
- staging 基础部署不等于真实 TikTok/DeepSeek 门禁通过，更不等于生产放行。
- 密钥、Token、证书私钥、模型权重、真实凭证池和完整业务数据不得进入 Git、Actions
  制品、命令历史或低敏测试报告。

## 3. 现状依据

- 系统 Docker 29.6.2 和 Compose 5.3.1 正在承载公司容器。
- 根分区剩余空间约 2.9 GB，`/home` 剩余空间约 354 GB。
- `crmdeploy` 已存在，UID/GID 为 1004，已配置 SSH 公钥且密码登录锁定。
- `docker-ce-rootless-extras`、RootlessKit、cgroup v2、systemd 和 subuid/subgid 已具备；
  仅缺少 `uidmap`。
- 宿主机 `80/443` 和 `10080/10443` 当前未被占用；公司现有代理使用其他端口。
- 防火墙已允许 `80/443`；Rootless 高端口将只绑定回环地址，不直接暴露公网。
- `staging.overselfx.com` 已解析到 `183.158.225.78`；用户确认上游 NAT 已配置，公网 TCP/TLS 待入口监听后复验。

## 4. 方案选择

采用“Rootless Docker + 回环高端口 + systemd TCP 入口转发”。

```text
Internet
  → staging.overselfx.com:80/443
  → root 管理的 systemd socket/proxy
  → 127.0.0.1:10080/10443
  → crmdeploy Rootless Docker proxy 容器
  → frontend / backend / PostgreSQL / Redis / MinIO / BGE
```

不采用给 RootlessKit 增加低端口 capability 的方案，避免扩大 RootlessKit 权限范围及软件
升级后 capability 丢失。不采用仅暴露高端口的方案，因为 TikTok OAuth 和 Webhook 需要标准
HTTPS 公网地址。

## 5. 主机与运行时设计

### 5.1 Rootless Docker

- 以 `crmdeploy` 执行 `dockerd-rootless-setuptool.sh install --force`，允许与系统 Docker 共存。
- 安装 `uidmap`，启用 `loginctl enable-linger crmdeploy`，由 `systemd --user` 管理 Rootless
  Docker 开机自启。
- Rootless socket 固定为 `/run/user/1004/docker.sock`。
- Rootless 数据保存在 `/home/crmdeploy/.local/share/docker`，不占用 `/var/lib/docker`。
- Docker CLI 通过显式 `DOCKER_HOST=unix:///run/user/1004/docker.sock` 使用 Rootless daemon，
  不创建 TCP Docker API。
- staging Compose 项目名固定为 `crm-staging`，与其他 Compose 项目隔离网络、容器和卷。

### 5.2 公网入口

- Rootless Compose 仅绑定：
  - `127.0.0.1:10080 → proxy:80`
  - `127.0.0.1:10443 → proxy:443`
- root 管理的 systemd socket/proxy 仅转发：
  - `0.0.0.0:80 → 127.0.0.1:10080`
  - `0.0.0.0:443 → 127.0.0.1:10443`
- 该入口不依赖系统 Docker，不接触现有容器；服务配置应可单独启停和删除。
- 高端口不监听公网地址，即使防火墙存在允许规则，也不能绕过 Nginx/TLS 入口。

### 5.3 目录布局

```text
/home/crmdeploy/
├── src/CRM/                     # GitHub Actions checkout 或受控源码副本
├── config/crm-staging.env       # 0600，仓库外，仅保存 staging 配置
├── assets/models/               # BGE 六个固定文件，仓库外，只读挂载
├── secrets/tls/staging.overselfx.com/
│   ├── fullchain.pem
│   └── privkey.pem
├── evidence/                    # 低敏门禁证据
├── backups/                     # PostgreSQL/MinIO staging 备份
├── runner/                      # GitHub Actions self-hosted runner
└── tools/                       # 便携 PowerShell 等 runner 工具
```

所有目录归 `crmdeploy`；配置和私钥使用最小权限。模型和备份不放在 checkout 内，也不通过
GitHub Secret 或 Actions 制品传输。

## 6. 域名、TLS 与 TikTok 外部契约

- DNS A 记录：`staging.overselfx.com → 183.158.225.78`。
- TLS 证书必须覆盖 `staging.overselfx.com`，证书放在仓库外目录。
- staging 公共配置：

```text
PUBLIC_BASE_URL=https://staging.overselfx.com
PUBLIC_API_BASE_URL=https://staging.overselfx.com/v1
CORS_ORIGINS=https://staging.overselfx.com
TIKTOK_OAUTH_REDIRECT_URI=https://staging.overselfx.com/v1/integrations/tiktok/oauth/callback
```

- Partner Center Webhook：
  `https://staging.overselfx.com/v1/webhooks/tiktok`。
- production 继续只接受 `https://www.overselfx.com/...`，不放宽为任意主机。
- 应用按 `APP_ENV` 对 staging 和 production 分别执行精确 scheme、host、path 校验，拒绝
  HTTP、任意子域、query、fragment 和错误路径。
- DNS、TLS 和 Partner Center 配置完成前，只能标记基础运行面就绪，不能标记 G1/G2 通过。

## 7. 仓库改动设计

### 7.1 Compose

新增 Rootless staging 覆盖文件，职责仅包括：

- 将应用环境覆盖为 `staging`；
- 把 proxy 端口改为 `127.0.0.1:10080/10443`；
- 保持 production Compose 的不可变镜像、密钥最小化、内部端口不暴露和失败关闭规则；
- 不改变 production 的 `80/443` 行为。

基础启动时所有真实能力保持 `false`。TikTok 人工辅助和 DeepSeek 内部建议只能通过现有受控
叠加文件逐步开启，高风险写入和自动回复继续固定关闭。

### 7.2 配置与 OAuth 校验

- 新增 staging 域名的精确配置契约及单元测试。
- 保持 production 固定回调契约不变。
- 对错误环境、主机、scheme、path、query 和 fragment 增加失败关闭测试。
- 更新 `.env.example`、生产/部署 README、ADR、放行检查表和共享索引。

### 7.3 部署与门禁脚本

- 增加可复现的 Rootless 主机 bootstrap 脚本及 systemd 单元模板。
- staging 脚本显式使用 Rootless socket、固定 Compose 项目名和 Rootless overlay。
- 脚本只执行 `docker compose config --services` 等低敏检查，不输出展开后的完整配置。
- validate、deploy、rollback 继续强制 `Environment=staging` 和人工确认词。
- 记录候选/上一版 RepoDigest、Git SHA、迁移 head、配置摘要、健康状态和时间戳。

## 8. GitHub Actions Runner 与 GHCR

- Runner 安装到 `/home/crmdeploy/runner`，标签为 `self-hosted,linux,x64,crm-staging`。
- 便携 PowerShell 安装到 `/home/crmdeploy/tools`，不占用根分区。
- Runner 和 Rootless Docker 都由 `crmdeploy` 用户级 systemd 服务管理并启用 linger。
- Runner 仅服务 `CP11-gh/CRM`，仓库 registration token 只用于注册，不持久化。
- GHCR 拉取继续使用工作流当前运行的短期 `GITHUB_TOKEN` 和 `packages: read`；服务器环境文件
  不保存 GitHub PAT。
- GitHub `staging` Environment 只保存环境文件路径变量/Secret 和基础 URL，不保存环境文件正文。
- 工作流仅从经审阅的 `main` checkout 部署完整 RepoDigest，保持手工触发和不并发部署。

## 9. 实施顺序

### 阶段 1：仓库工程改造

1. 先补失败测试，再修改 staging OAuth 域名校验。
2. 新增 Rootless Compose overlay、bootstrap、systemd 模板和门禁参数。
3. 更新文档、ADR、测试索引和实施索引。
4. 执行后端、Compose、脚本和文档一致性验证。
5. 提交 PR，完成 CI、人工审阅和 squash merge。

### 阶段 2：服务器 Rootless 基线

1. 记录系统 Docker 容器 ID、启动时间、镜像和端口作为保护基线。
2. 安装 `uidmap`，配置 `crmdeploy` Rootless Docker 和 linger。
3. 验证 Rootless daemon 的 socket、security options、data root 和 cgroup。
4. 再次核对现有公司容器未停止、未重建、未改变。
5. 安装 runner 工具链并注册专用 runner。

### 阶段 3：公网和失败关闭部署

1. 用户配置 DNS，验证公网 `80/443` 到达服务器。
2. 签发/安装 staging TLS 证书并验证证书链和主机名。
3. 准备仓库外环境文件、BGE 六个模型文件和固定 RepoDigest。
4. 先运行 validate，再以全部真实能力关闭的状态 deploy。
5. 验证首页、`/healthz`、`/v1/health`、`/v1/health/ready` 和容器健康。

### 阶段 4：恢复与回滚

1. 执行 PostgreSQL 和 MinIO 备份。
2. 在隔离 staging 数据中执行恢复演练并核对迁移 `023`。
3. 执行候选镜像到上一版镜像的真实回滚，再切回候选版本。
4. 验证功能开关紧急关闭、审计和低敏证据。

### 阶段 5：真实功能门禁

按 G0 → G1 → G2 → G3 → G4 → G5 → G6 顺序执行：

1. G0：基线、密钥轮换、日志复测、备份恢复和回滚。
2. G1：TikTok OAuth、Scope、Token 生命周期、只读 API 和店铺隔离。
3. G2：Partner Center 真实 Webhook、签名、重试、幂等和 Worker 恢复。
4. G3：单店铺、单账号、单操作员人工普通消息和 `unknown` 对账。
5. G4：AI 建议、RAG、DLP 和真实 DeepSeek 质量。
6. G5：50 个独立授权客户端真实 SSE 性能。
7. G6：连续五日、99.5% 可用性和审计完整性。

任一阶段失败时关闭最小开关并停止推进，不通过删除业务数据回滚。

## 10. 验证与验收标准

基础设施就绪必须同时满足：

- 系统 Docker 的既有公司容器在实施前后 ID、启动时间和运行状态不变；
- Rootless Docker 报告 `rootless` security option，data root 位于 `/home/crmdeploy`；
- Rootless socket 不监听 TCP；高端口只监听 `127.0.0.1`；
- 公网只通过标准 `80/443` 到达 staging Nginx；
- staging 容器、卷、网络和备份与系统 Docker 完全隔离；
- 三个应用镜像均以 `repository@sha256:<64-hex>` 拉取；
- 模型六个文件位于 checkout 外且启动时 SHA-256 复核通过；
- 初次部署的所有真实平台、LLM、翻译、营销和自动回复开关均为关闭；
- 三个健康端点通过且不泄露连接串、路径、Token 或底层异常；
- validate、deploy、backup/restore、rollback 生成低敏可复现证据。

真实 staging 通过还必须以放行检查表中的 G0～G6 独立报告为准。基础部署完成不得替代这些
报告，也不得宣称 v0.1 已生产放行。

## 11. 外部依赖与用户动作

实施过程中需要用户或系统管理员完成：

- 维持 `staging.overselfx.com` A 记录指向 `183.158.225.78`，并在入口监听后从外部网络
  复验用户已配置的公网 `80/443` NAT/安全组链路；
- 通过安全渠道把 staging TLS、TikTok、DeepSeek 和应用密钥放入服务器仓库外配置；
- 把 BGE 六个固定模型文件放入 `/home/crmdeploy/assets/models`；
- 在 TikTok Partner Center 配置 staging Redirect URL、Webhook、Scope 和白名单；
- 在 GitHub `staging` Environment 完成 runner、变量和必要审批配置；
- 提供允许真实店铺人工验证的时间窗口、测试账号和操作员范围。

若这些依赖尚未到位，仍可完成仓库改造、Rootless 基线、runner 安装和失败关闭静态验证；相应
真实门禁保持“未执行/阻塞”，不得降级为 Mock 通过。

## 12. 回滚和清理

- 应用异常：先关闭最小能力开关，再用固定上一版 RepoDigest 回滚。
- Rootless staging 异常：停止 `crmdeploy` 用户服务和入口代理，不影响系统 Docker。
- Runner 异常：先从 GitHub 移除 runner，再删除用户级服务；不删除 staging 数据。
- 完整撤除只删除明确命名的 staging systemd 单元、Rootless Compose 项目和
  `/home/crmdeploy` 下经复核的 staging 目录；任何清理前都要再次确认绝对路径和备份。
- production 部署方案在 staging 全部适用门禁通过后另行评审，本设计不自动延伸到 production。
