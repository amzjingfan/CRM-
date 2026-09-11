# 双服务器 Staging 入口分离

状态：已确认（架构与仓库工程）；真实 DNS、TLS、部署和 G0～G6 待执行
日期：2026-09-11

## 1. 决策摘要

`staging.overselfx.com` 使用两台服务器分工：`38.55.145.52` 是唯一公网入口并终止 TLS，`192.168.110.210` 只在 `/home/crmdeploy` 的 Rootless Docker 中运行 CRM。业务服务器主动建立受限反向 SSH 隧道，公网 Nginx 只访问本机 `127.0.0.1:18080`，该端口映射到业务服务器 `127.0.0.1:10080`。

本 ADR 取代 ADR-007 第 3.2 节的业务服务器 80/443 socket proxy 和 Rootless 10443 入口。Rootless 隔离、公司容器保护、GitHub Flow、不可变镜像、外部模型和逐级能力门禁继续沿用。

## 2. 背景与边界

- `38.55.145.52` 已有宝塔 Nginx 和其他网站，先前只读预检观察到公网 80/443 可达；实施前后必须复核其他 vhost 响应不变。
- `192.168.110.210` 根盘空间紧张、`/home` 容量充足，且公司系统 Docker 正在承载既有容器。本项目无权停止、重启、迁移、修复或接管这些容器。
- `183.158.225.78` 是公司网络对外地址，不再作为本 staging 的入口依赖，也不需要为本方案保留 80/443 NAT 映射。
- staging 的业务出口 IP 与公网入口 IP 是两个概念。TikTok 白名单必须登记业务服务器实际出口，不能因域名指向 `38.55.145.52` 就假定出口相同。
- 本次只覆盖 TikTok 人工辅助首版：OAuth、读取、Webhook、人工发送、AI 建议、RAG、工作台、知识库和看板。产品与 UI 保留 Shopee/Amazon，但不实现其真实接入。
- production 部署方式不在本决策中；staging 验证通过不等于 production 采用 Rootless 或同一双机拓扑。

## 3. 固定拓扑

```text
Internet
  → staging.overselfx.com A = 38.55.145.52
  → public Nginx :80/:443（TLS 只在此终止）
  → 127.0.0.1:18080
  → OpenSSH restricted remote forwarding
  → 192.168.110.210 / crmdeploy / 127.0.0.1:10080
  → Rootless Nginx HTTP
  → frontend:3000 或 backend:8000
```

| 层 | 固定值 | 禁止项 |
| --- | --- | --- |
| DNS/公网入口 | `staging.overselfx.com → 38.55.145.52` | 指向业务内网地址或旧入口 |
| 公网 Web | 宝塔 Nginx 80/443、证书在 `/etc/letsencrypt/live/staging.overselfx.com/` | 公网直连业务服务器或容器 |
| 隧道远端 | `127.0.0.1:18080` | `0.0.0.0`、公网网卡或 `GatewayPorts yes` |
| 隧道本地 | `127.0.0.1:10080` | 数据库、Docker socket 或其他端口转发 |
| Rootless | `unix:///run/user/1004/docker.sock`、项目 `crm-staging` | 系统 Docker、TCP Docker API、宿主机 80/443 |
| OAuth callback | `https://staging.overselfx.com/v1/integrations/tiktok/oauth/callback` | HTTP、其他域名、query 或 fragment |

## 4. 安全决策

### 4.1 隧道身份

业务服务器为本隧道生成独立 Ed25519 密钥，私钥只存在于 `/home/crmdeploy/secrets/tunnel/id_ed25519`，目录 `0700`、文件 `0600`、UID 1004。`known_hosts` 固定公网服务器已人工核对的 Ed25519 主机指纹，禁止 `StrictHostKeyChecking=no`。

公网服务器使用独立 `crm-tunnel` 账号：密码锁定、shell 为 `nologin`，授权密钥包含 `command="/usr/bin/false",restrict,port-forwarding,permitlisten="127.0.0.1:18080"`。sshd 保持 `GatewayPorts no`。该账号不运行应用、不持有部署密钥，也不能访问系统 Docker。

### 4.2 TLS 和代理

活动 TLS 私钥只保存在公网服务器。业务服务器的 Rootless proxy 使用专用 `nginx-tunnel.conf`，只监听 HTTP 80 并固定上游原始协议为 HTTPS。公网和内层两层都关闭 SSE 缓冲；访问日志只记录 `$uri`，OAuth callback 的代理错误日志关闭，避免 code/state 或查询串进入日志。

错误 Host 在内层返回 444。公网 vhost 只代理 `127.0.0.1:18080`，不得写入 `192.168.110.210`、旧公网地址或直接应用端口。

### 4.3 运行与供应链

Rootless Compose 只发布 `127.0.0.1:10080:80`。backend、frontend、retrieval 和外部基础镜像必须固定为 `repository@sha256:<64-hex>`；应用候选必须关联合并后的完整 main SHA。模型固定为仓库外 `/home/crmdeploy/assets/models` 六文件并在启动时逐项校验 SHA-256。

初次部署固定关闭 Mock、真实 TikTok 读取/Webhook/写入、高风险写入、LLM live eval、翻译、营销和自动回复。G1～G6 只能按独立 overlay、授权和证据逐级开启。

## 5. 部署顺序与失败关闭

唯一活动顺序为：

1. 两台服务器只读预检并冻结公司容器及其他 vhost 基线。
2. 安装公网受限账号，核对主机指纹并启动用户级反向隧道。
3. 安装 HTTP 引导 vhost，只开放 ACME、健康路由和 503 失败响应。
4. 把 DNS A 切到 `38.55.145.52`，使用三个公共解析器复核。
5. 签发公信 TLS，核对 SAN、有效期、链和私钥权限。
6. 原子切换正式 vhost，`nginx -t` 通过后才 reload。
7. validate 不可变候选与三层 Compose，再执行 Rootless deploy。
8. 完成 G0 健康、迁移、模型、备份恢复、重启恢复、回滚和隔离复核。
9. G0 通过后才进入 G1～G6。

任一步失败均保留真实失败状态，不生成 `passed` 证据、不放宽 Host/TLS/密钥/能力开关，也不切换到公司系统 Docker。

## 6. 回滚与撤除

- 应用异常先关闭尚未批准的真实能力，再使用已证明兼容 staging callback、迁移 023 和当前配置的上一版三摘要回滚；不自动降级数据库或删除数据。
- 隧道异常只停止 `crm-staging-tunnel.service`；公网 18080 随 SSH 连接消失，Nginx 返回 502，属于失败关闭。
- 公网 vhost 回滚使用变更前备份，恢复后必须 `nginx -t` 再 reload，并复核其他站点。
- 旧 `crm-staging-http/https.socket/.service` 不属于活动入口，不得启用；如现场仍存在，只能在核对来源后保持 disabled，删除需单独批准。
- Rootless 卸载、卷/镜像/备份删除、runner 注销和任何系统 Docker 操作均需单独授权。

## 7. 验收状态

| 结论 | 当前状态 | 判定边界 |
| --- | --- | --- |
| 仓库工程资产 | 实施中 | 代码、配置、测试和文档待 PR/CI/squash merge |
| 双机入口现场 | 未执行 | DNS、证书、隧道、Nginx 和其他 vhost 不变待现场证据 |
| 失败关闭部署 G0 | 未执行 | 不可变镜像、迁移、健康、模型、恢复/回滚待现场证据 |
| TikTok G1～G6 | 未执行 | 真实 Partner Center、店铺、DeepSeek、50 凭据和五日证据未提供 |
| production 放行 | 阻塞 | 方案未决定，G8 未签署 |

工程测试通过不能替代服务器、DNS、TLS、真实店铺或真实模型证据。最终状态以测试工程师正式报告和生产放行检查表为准。
