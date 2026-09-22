# TikTok 固定出口设计

日期：2026-09-21
状态：已批准
目标环境：staging；production 只建立可复用配置契约，不在本次部署

## 1. 背景与现场证据

TikTok Shop 真实 OAuth、读取和人工消息请求需要稳定、可加入平台白名单的公网出口 IP。当前业务服务器 `192.168.110.210` 的 `TIKTOK_EGRESS_IP` 配置为 `183.158.225.78`，但 2026-09-21 的只读现场检查得到以下事实：

- 业务服务器只有一个本机默认路由：`default via 192.168.110.1`；主机、`crmdeploy` 和 backend 容器均未配置 HTTP、HTTPS 或 SOCKS 代理。
- 从同一主机和同一 backend 容器连续请求公网 IP 检测服务时，源地址在 `115.206.210.45` 与 `122.234.23.242` 之间切换；`183.158.225.78` 未出现。
- 多出口发生在上游网关/NAT，而不是 CRM、Docker 或业务服务器路由表。
- 公网服务器 `38.55.145.52` 只有一个默认路由，三个独立检测地址连续九次均返回 `38.55.145.52`。
- `38.55.145.52` 能完成 `auth.tiktok-shops.com` 与 `open-api.tiktokglobalshop.com` 的 DNS 解析、TLS 校验和 HTTPS 连接。
- 现有 `crm-tunnel` 账号的有效 SSHD 策略是 `AllowTcpForwarding remote` 且只允许 `127.0.0.1:18080`，不能也不应复用于出站代理。

因此，单独把 `TIKTOK_EGRESS_IP` 改成当前观察到的任意地址都不能固定实际流量。固定出口必须通过可验证的网络路径实现。

## 2. 目标、成功标准与非目标

### 2.1 目标

1. staging 中所有 TikTok 服务端出站请求固定经 `38.55.145.52` 访问平台。
2. TikTok 请求不得因隧道故障而回退到业务服务器的随机公网出口。
3. 保持现有入口链路不变：`staging.overselfx.com → 38.55.145.52 Nginx/TLS → crm-tunnel 反向隧道 → Rootless CRM`。
4. 不在公网服务器部署 CRM、数据库、模型、通用代理或新的公网监听服务。
5. 不影响旧服务器系统 Docker、GitLab `10080/10443`、DeepSeek、MinIO、内部模型和非 TikTok 出站流量。
6. 为 production 建立同一套失败关闭配置和 Compose 组合方式，但 production 的服务器、密钥与实际出口需要独立发布批准。

### 2.2 成功标准

- 经应用实际使用的 SOCKS5 路径访问固定检测地址时，观测值与 `TIKTOK_EGRESS_IP=38.55.145.52` 完全一致。
- TikTok OAuth、读取和人工消息客户端全部使用显式代理，且 `trust_env=False`，不受宿主机代理环境变量影响。
- 删除或停止出站隧道后，TikTok 请求以传输错误失败；抓取或检测不到直连回退。
- 公网服务器没有新增 `1080`、`3128` 等公网或回环代理监听；只有现有 SSHD 进程承载受限转发。
- 现有 `crm-tunnel` 授权行、入口端口、Nginx 配置和 GitLab 基线保持不变。
- 代码、配置、部署资产、测试、操作手册和低敏证据使用同一 subject SHA。

### 2.3 非目标

- 不修复或接管公司上游网关 `192.168.110.1` 的多 WAN/NAT 策略。
- 不让 DeepSeek、普通网页访问或系统更新统一经过 `38.55.145.52`。
- 不开启 `REAL_TIKTOK_READ_ENABLED`、`REAL_TIKTOK_WEBHOOK_ENABLED`、`REAL_TIKTOK_MESSAGE_WRITE_ENABLED` 或任何高风险写入。
- 不把 `TIKTOK_WEBHOOK_SECRET` 当作 TikTok 平台凭据；真实 Webhook 仍使用 `TIKTOK_APP_SECRET` 验签。
- 不在本次变更中部署 production 或决定 production 是否复用 staging 公网服务器。

## 3. 方案选择

采用独立 SSH 动态转发方案：业务服务器 Rootless Compose 中运行一个只服务于 TikTok 的 SOCKS5 helper；helper 使用独立密钥连接 `crm-egress@38.55.145.52`，公网 SSHD 只允许该账号向批准的 TikTok 域名建立本地转发。

未采用的方案：

- 上游网关源地址策略路由：长期最简单，但当前没有 `192.168.110.1` 的管理入口或固定运营商地址合同，无法由本项目验证和恢复。
- WireGuard 加策略路由：会改变宿主机或容器路由与公网服务器 NAT，故障面大于 MVP 所需。
- 公网 HTTP/SOCKS 代理服务：需要新增守护进程和代理监听，扩大公网服务器职责与攻击面。
- 复用 `crm-tunnel`：会混合入口和出口权限，并要求放宽已验证的 remote-only SSH 边界。

## 4. 目标架构与数据流

入口流量保持原样：

```text
staging.overselfx.com:443
  → 38.55.145.52 Nginx/TLS
  → crm-tunnel 受限 SSH 反向隧道
  → 192.168.110.210 Rootless CRM
```

新增的 TikTok 出站流量：

```text
backend / worker / jobs
  → 显式 HTTPX SOCKS5H 代理 socks5h://tiktok-egress:1080
  → Rootless Compose tiktok-egress helper
  → 独立 SSH 动态转发
  → crm-egress@38.55.145.52:22
  → 仅批准域名的 TCP/443
  → TikTok Shop
```

`socks5h` 要求目标域名由 SOCKS 远端解析，避免业务服务器本地 DNS 解析后以 IP 形式绕开 SSHD 的域名允许列表。HTTPX 使用 `httpx[socks]` 提供 SOCKS 支持；当前锁定的 HTTPX 0.28.1 支持 `socks5h`。

## 5. 组件设计

### 5.1 应用侧 TikTok HTTP 客户端

新增单一工厂模块，负责生成 TikTok 专用 `httpx.AsyncClient` 参数：

- timeout 继续使用 `REQUEST_TIMEOUT_SECONDS`；
- proxy 使用 `TIKTOK_EGRESS_PROXY_URL`；
- `trust_env=False`，禁止 `HTTP_PROXY`、`HTTPS_PROXY` 或 `ALL_PROXY` 改写路径；
- OAuth token/shop、真实只读和人工消息三个客户端统一调用该工厂；测试注入的显式 client 保持原契约。

`TIKTOK_EGRESS_PROXY_URL` 的规则：

- 开启任何真实 TikTok 能力时必须存在；
- 只接受 `socks5h`；
- 禁止用户名、密码、路径、查询串和片段；
- staging/production 固定为 `socks5h://tiktok-egress:1080`；
- development/test 在不开启真实能力时可为空。

### 5.2 Rootless Compose helper

新增 `docker-compose.tiktok-egress.yml`，由 staging 固定叠加，production 在启用真实 TikTok 时与 `docker-compose.tiktok-manual.yml` 一起叠加。

为避免新增第四种发布镜像，helper 复用同一 subject SHA 的不可变 backend 镜像，并为 backend 镜像安装发行版 `openssh-client`。helper 只覆盖 command 运行 `/usr/bin/ssh`，不启动应用代码，并设置：

- `read_only: true`；
- `cap_drop: [ALL]`；
- `no-new-privileges:true`；
- 仅挂载 `/home/crmdeploy/secrets/tiktok-egress` 到 `/run/secrets/tiktok-egress:ro`；
- 只加入独立 `tiktok-egress` Compose 网络；backend、worker、jobs 同时加入 default 与该网络；
- 不发布宿主机端口；SOCKS 只监听容器网络的 `0.0.0.0:1080`；
- SSH 使用 `BatchMode`、`IdentitiesOnly`、固定 known_hosts、`ExitOnForwardFailure` 与 keepalive；
- 容器健康检查只确认 SSH 进程与本地 SOCKS listener 存活；真正出口 IP 由独立发布门禁验证。

私钥只挂载到 helper，不进入 backend、worker、jobs、镜像、Git、日志或 Compose 展开证据。helper 在 Rootless Docker 中以容器 root 读取 `0600` 文件；该 root 映射到宿主机 `crmdeploy`，不取得宿主机 root 权限。

### 5.3 公网 `crm-egress` 账号

在 `38.55.145.52` 新建与 `crm-tunnel` 完全分离的系统账号：

- 锁定口令、nologin、无 sudo、无附加组；
- 只接受单个 Ed25519 公钥；
- 禁止 shell、命令、TTY、X11、agent forwarding、用户 rc 和 remote forwarding；
- 只允许 local/dynamic forwarding；
- `GatewayPorts no`；
- `PermitOpen` 仅包含：
  - `auth.tiktok-shops.com:443`
  - `open-api.tiktokglobalshop.com:443`
  - `checkip.amazonaws.com:443`（只用于自动化出口门禁）
- 修改 SSHD 配置前保存精确备份，必须先 `sshd -t`，再 reload；禁止 restart SSHD。

安装脚本遇到未知账号、未知授权行、重复 Match 块、无效公钥或现有策略漂移时失败关闭，不覆盖未知状态。

### 5.4 密钥与主机身份

- 在 `192.168.110.210` 以 `crmdeploy` 生成新的 Ed25519 身份，不复用入口隧道私钥。
- 目录 `/home/crmdeploy/secrets/tiktok-egress` 为 `0700`，私钥和 known_hosts 为 `0600`，所有者为 UID/GID 1004。
- known_hosts 固定 `38.55.145.52` 当前 Ed25519 主机指纹；不使用 `StrictHostKeyChecking=no` 或自动替换。
- 公钥通过现有 root 管理通道安装到 `crm-egress`；私钥不离开业务服务器。

## 6. 配置与发布契约

新增非秘密配置：

```env
TIKTOK_EGRESS_IP=38.55.145.52
TIKTOK_EGRESS_PROXY_URL=socks5h://tiktok-egress:1080
TIKTOK_EGRESS_SECRET_DIR=/home/crmdeploy/secrets/tiktok-egress
```

其中 `TIKTOK_EGRESS_PROXY_URL` 由 Compose overlay 固定注入，`TIKTOK_EGRESS_SECRET_DIR` 只供 Compose 解析宿主机只读挂载；二者不得包含凭据。staging 环境文件将旧的 `183.158.225.78` 替换为 `38.55.145.52`，但只有在代理路径验证成功后才视为有效。

staging 的 Compose 顺序更新为：

```text
docker-compose.yml
docker-compose.prod.yml
docker-compose.tiktok-egress.yml
docker-compose.rootless-staging.yml
```

真实 TikTok 灰度在此基础上再叠加 `docker-compose.tiktok-manual.yml`。production 只有在独立拓扑与发布批准后，才提供 production 自己的 `TIKTOK_EGRESS_IP`、密钥目录和 SSH 服务端。

## 7. 失败处理与回滚

### 7.1 运行时失败

- helper 或 SSH 隧道断开：TikTok 专用 HTTPX 请求发生连接/传输错误，沿用现有 OAuth 502、只读 502 和人工消息 `unknown`/失败关闭语义。
- 禁止从代理失败自动切换为 direct client；工厂只构造一个显式代理 transport。
- DNS、TLS 或 TikTok 平台错误继续由现有客户端分类，不重试不安全的写入。

### 7.2 部署失败

- SSHD 配置校验失败：恢复备份，不 reload，不启动 helper。
- helper 不健康或出口不等于声明 IP：真实 TikTok 开关保持 false；现有 CRM 入口继续服务。
- 新 backend 镜像异常：使用已验证的上一 backend RepoDigest 回滚应用；出站账号可以保持锁定且无活动连接，不影响入口。
- 回滚不得删除业务数据、Rootless 卷、入口 `crm-tunnel`、Nginx、GitLab 或公司容器。

## 8. 验证与证据

### 8.1 自动化测试

- Settings：缺失、错误 scheme、内嵌凭据、路径/查询/片段、真实环境非固定 service URL 均拒绝；合法 `socks5h://tiktok-egress:1080` 接受。
- TikTok 客户端：OAuth、只读和写入在未注入测试 client 时都取得 `proxy` 与 `trust_env=False`；注入 client 时不新建 transport。
- Compose：helper 不发布端口、只读挂载、能力清空、独立网络、固定命令和健康检查；staging 门禁包含 egress overlay。
- 部署资产：公网账号限制、域名允许列表、密钥权限、固定主机指纹和脚本失败关闭行为。
- 出口验证脚本：合法相同 IP 通过，格式错误或不一致失败，错误输出不包含凭据。

### 8.2 真实 staging 验证

1. 记录变更前公网 SSHD、Nginx、入口隧道、Rootless CRM、系统 Docker/GitLab 与其他 vhost 的低敏基线。
2. 安装独立账号和密钥，确认有效策略是 local-only 且 `PermitOpen` 精确匹配。
3. 部署与合并 main SHA 绑定的 backend RepoDigest 和 egress overlay，保持全部真实 TikTok 开关 false。
4. 从应用实际 HTTPX 代理路径请求 `checkip.amazonaws.com`，必须返回 `38.55.145.52`。
5. 暂停 helper 一次，确认请求失败且没有观察到 `115.206.210.45`、`122.234.23.242` 或直连成功；随后恢复 helper。
6. 验证两个 TikTok 官方域名的 DNS/TLS 可达性，但不携带 App Secret、Token 或业务数据发起真实业务调用。
7. 复核入口健康端点、隧道、Nginx、GitLab、公司容器和其他 vhost 与基线一致。
8. 仓库只保存时间、subject/evidence SHA、配置键名、状态、允许域名和 IP；不保存私钥、完整公钥、Token、环境文件或服务器原始敏感快照。

## 9. 文档、任务与两阶段集成边界

- 新建单主题任务并在 `docs/tasks/TASKS.md` 按 `READY → DOING → VERIFYING → DONE` 推进。
- 同步 `docs/architecture/SYSTEM.md`、`docs/operations/DEPLOYMENT.md`、`docs/operations/RELEASE-GATES.md`、`src/config/.env.example` 与 staging/production 运行手册。
- 建立与风险相称的 IR/TR/RR 和 release evidence；实现分支的候选 SHA、合并后的 main SHA、镜像 RepoDigest 与现场证据分别按真实阶段绑定，不用尚未产生的提交或镜像填充占位结论。
- 第一阶段在完整自动化门禁、镜像本地构建、整分支审查和文档同步通过后，把仍处于 `VERIFYING` 的实现分支合并到创建分支时记录的 `origin/main` 基线。此时 live-staging 结论必须写为 `NOT_EXECUTED — requires merged main image`，不得把合并描述为任务完成或 staging 放行。
- 第二阶段从合并后的 main 发布不可变 backend 镜像，使用该 RepoDigest 和固定 egress overlay 部署 staging，完成出口 IP、无直连回退、入口与公司负载零变化验证；随后只在证据分支定稿 IR/TR/RR、release evidence 和 `DONE` 状态并再次合并。
- 合并不等于 production 放行；production 保持未部署。

## 10. 已批准决定

用户已于 2026-09-21 在会话中批准采用独立 `crm-egress` SSH/SOCKS5 固定出口方案，staging 的声明与实际出口目标为 `38.55.145.52`；并于 2026-09-22 明确确认本规格与两阶段实施计划。production 只复用配置契约，服务器、账号、密钥、出口和实际部署仍需独立批准。
