# 双服务器入口分离 Rootless Staging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `38.55.145.52` 作为 `staging.overselfx.com` 的唯一公网 Nginx/TLS 入口，通过受限反向 SSH 隧道访问 `192.168.110.210` 上的 Rootless Docker CRM，并完成失败关闭部署与 G0 证据。

**Architecture:** 公网服务器只代理 `127.0.0.1:18080`；业务服务器的 `crmdeploy` 用户以 systemd 保持 `-R 127.0.0.1:18080:127.0.0.1:10080` 隧道。Rootless Compose 只在回环发布一个明文 HTTP proxy 端口，TLS、域名和外部转发头全部由公网 Nginx 管理。

**Tech Stack:** Docker Compose、Rootless Docker、Nginx、OpenSSH、systemd user services、PowerShell 7、pytest、GitHub Actions、GHCR、宝塔 Linux 面板

**Spec:** `docs/superpowers/specs/2026-09-11-split-ingress-rootless-staging-design.md`

## Global Constraints

- 不停止、重启、重建、迁移或接管业务服务器的公司系统 Docker 和现有容器。
- Rootless socket 固定为 `unix:///run/user/1004/docker.sock`，Compose 项目名固定为 `crm-staging`。
- 业务服务器只发布 `127.0.0.1:10080`；公网服务器隧道端口只监听 `127.0.0.1:18080`。
- 公网入口域名固定为 `staging.overselfx.com`，DNS A 最终指向 `38.55.145.52`。
- OAuth callback 固定为 `https://staging.overselfx.com/v1/integrations/tiktok/oauth/callback`。
- backend、frontend、retrieval 和外部基础镜像都必须使用 `repository@sha256:<64-hex>`。
- 模型固定使用仓库外 `/home/crmdeploy/assets/models` 六个文件，并在启动时校验 SHA-256。
- 首次部署必须关闭 Mock、全部真实 TikTok、LLM live eval、翻译、营销、自动回复和高风险写入。
- TLS 只在 `38.55.145.52` 终止；业务服务器不得保存本 staging 的活动 TLS 私钥。
- production 部署方式、Shopee/Amazon 真实接入、自动回复和营销发送不在本计划范围。
- 任何密钥、Token、证书私钥、客户正文、模型权重和环境文件正文不得进入 Git、日志或 Actions 制品。

---

### Task 1: 实现 Rootless 隧道专用 HTTP proxy

**Files:**
- Create: `CRM智能聊天系统/backend/tests/test_split_ingress_staging_assets.py`
- Modify: `CRM智能聊天系统/backend/tests/test_rootless_staging_assets.py`
- Create: `CRM智能聊天系统/deploy/nginx/nginx-tunnel.conf`
- Modify: `CRM智能聊天系统/docker-compose.rootless-staging.yml`
- Modify: `CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1`
- Modify: `CRM智能聊天系统/scripts/Invoke-StagingRollbackDrill.ps1`
- Modify: `CRM智能聊天系统/backend/tests/test_production_gate_scripts.py`

**Interfaces:**
- Consumes: `docker-compose.rootless-staging.yml`、现有生产 Compose 和 Rootless 资产目录。
- Produces: 唯一宿主机入口 `127.0.0.1:10080`、内层安全 Nginx 配置和门禁校验。

- [ ] **Step 1: 新增 Rootless overlay 失败测试**

```python
def test_rootless_overlay_exposes_only_tunnel_http_port() -> None:
    source = ROOTLESS_OVERLAY.read_text(encoding="utf-8")
    assert '"127.0.0.1:10080:80"' in source
    assert "10443" not in source
    assert "nginx-tunnel.conf" in source
```

- [ ] **Step 2: 新增内层 Nginx 失败测试**

```python
def test_inner_proxy_preserves_https_origin_without_tls() -> None:
    source = ROOTLESS_TUNNEL_NGINX.read_text(encoding="utf-8")
    assert "listen 80 default_server" in source
    assert "listen 443" not in source
    assert "proxy_set_header X-Forwarded-Proto https" in source
    assert "proxy_buffering off" in source
    assert "error_log /dev/null" in source
```

- [ ] **Step 3: 运行聚焦测试并确认 RED**

Run:

```powershell
Set-Location CRM智能聊天系统
$env:PYTHONPATH = (Get-Location).Path
uv run --project backend pytest backend/tests/test_split_ingress_staging_assets.py backend/tests/test_rootless_staging_assets.py -q
```

Expected: 新资产不存在或 overlay 仍包含 `10443`，测试非零退出。

- [ ] **Step 4: 创建明文内层 Nginx 配置**

配置只监听 80，保留 `safe_json` 的 `$uri` 日志、OAuth 精确路由低敏错误日志、SSE 无缓冲、
`client_max_body_size 10m`，并把所有上游请求固定标记为原始协议 HTTPS。

```nginx
server {
    listen 80 default_server;
    location = /healthz { access_log off; return 200 "ok\n"; }
    location = /v1/chat/query {
        proxy_pass http://backend:8000;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_read_timeout 240s;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

- [ ] **Step 5: 把 Rootless overlay 改为单端口和只读配置覆盖**

```yaml
proxy:
  ports: !override
    - "127.0.0.1:10080:80"
  volumes: !override
    - type: bind
      source: ./deploy/nginx/nginx-tunnel.conf
      target: /etc/nginx/nginx.conf
      read_only: true
```

- [ ] **Step 6: 修改部署和回滚门禁**

两个 PowerShell 脚本都必须断言：proxy 端口总数为 1、绑定精确等于
`127.0.0.1:10080→80`、配置挂载源文件名为 `nginx-tunnel.conf`、目标为
`/etc/nginx/nginx.conf` 且只读、没有 `/etc/nginx/certs` 挂载。

- [ ] **Step 7: 运行聚焦测试并确认 GREEN**

Run:

```powershell
Set-Location CRM智能聊天系统
$env:PYTHONPATH = (Get-Location).Path
uv run --project backend pytest backend/tests/test_split_ingress_staging_assets.py backend/tests/test_rootless_staging_assets.py backend/tests/test_production_gate_scripts.py -q
```

Expected: 全部通过；被刻意改成 `10443`、非回环或可写挂载的夹具失败关闭。

- [ ] **Step 8: 提交 Rootless proxy 改造**

```powershell
git add CRM智能聊天系统/deploy/nginx/nginx-tunnel.conf CRM智能聊天系统/docker-compose.rootless-staging.yml CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1 CRM智能聊天系统/scripts/Invoke-StagingRollbackDrill.ps1 CRM智能聊天系统/backend/tests
git commit -m "build: route staging through tunnel-only proxy"
```

---

### Task 2: 实现受限反向 SSH 隧道资产

**Files:**
- Create: `CRM智能聊天系统/deploy/staging/rootless/systemd/user/crm-staging-tunnel.service`
- Create: `CRM智能聊天系统/deploy/staging/rootless/install-reverse-tunnel.sh`
- Create: `CRM智能聊天系统/deploy/staging/rootless/install-public-tunnel-account.sh`
- Modify: `CRM智能聊天系统/backend/tests/test_split_ingress_staging_assets.py`
- Modify: `.gitattributes`

**Interfaces:**
- Consumes: `/home/crmdeploy/secrets/tunnel/id_ed25519`、独立 `known_hosts`、公网服务器受限账号。
- Produces: `crm-staging-tunnel.service`，远端回环 `18080` 到业务回环 `10080`。

- [ ] **Step 1: 扩展失败测试覆盖安装器安全边界**

断言安装器包含：UID 1004、真实路径校验、符号链接拒绝、私钥 `0600`、目录 `0700`、
`ssh-keygen -F` 主机指纹检查、`systemd-analyze --user verify`、不出现
`StrictHostKeyChecking=no`、不打印密钥正文；并增加
`test_reverse_tunnel_unit_is_loopback_only_and_fail_closed`，固定
`127.0.0.1:18080:127.0.0.1:10080`、`ExitOnForwardFailure=yes` 和 `Restart=always`。

- [ ] **Step 2: 创建用户级 systemd unit**

```ini
[Service]
ExecStart=/usr/bin/ssh -NT -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o UserKnownHostsFile=/home/crmdeploy/secrets/tunnel/known_hosts -i /home/crmdeploy/secrets/tunnel/id_ed25519 -R 127.0.0.1:18080:127.0.0.1:10080 crm-tunnel@38.55.145.52
Restart=always
RestartSec=5
```

- [ ] **Step 3: 创建业务服务器安装器**

安装器只在 `crmdeploy`、UID 1004 下运行；验证密钥/主机指纹/端口后，把已校验 unit 安装到
`~/.config/systemd/user/`，执行 daemon-reload、enable 和 start。失败时不得更改 Rootless
Compose 或公司系统 Docker。

- [ ] **Step 4: 创建公网受限账号安装器**

以 root 运行，创建或复用 `crm-tunnel`，锁定密码、不授予 sudo，把单条 Ed25519 公钥写成：

```text
restrict,port-forwarding,permitlisten="127.0.0.1:18080" ssh-ed25519 <validated-key>
```

安装器拒绝多行、公钥类型错误、额外选项、目标家目录符号链接或组/其他用户可写路径。

- [ ] **Step 5: 运行测试、Bash 语法和 unit 校验**

Run:

```powershell
Set-Location CRM智能聊天系统
$env:PYTHONPATH = (Get-Location).Path
uv run --project backend pytest backend/tests/test_split_ingress_staging_assets.py -q
bash -n deploy/staging/rootless/install-reverse-tunnel.sh
bash -n deploy/staging/rootless/install-public-tunnel-account.sh
```

Expected: 测试和两项语法检查全部通过。

- [ ] **Step 6: 提交隧道资产**

```powershell
git add .gitattributes CRM智能聊天系统/deploy/staging/rootless CRM智能聊天系统/backend/tests/test_split_ingress_staging_assets.py
git commit -m "build: add restricted staging reverse tunnel"
```

---

### Task 3: 实现公网宝塔 Nginx vhost 资产

**Files:**
- Create: `CRM智能聊天系统/deploy/staging/rootless/public-nginx/staging.overselfx.com-http.conf`
- Create: `CRM智能聊天系统/deploy/staging/rootless/public-nginx/staging.overselfx.com.conf`
- Create: `CRM智能聊天系统/deploy/staging/rootless/verify-split-ingress.sh`
- Modify: `CRM智能聊天系统/backend/tests/test_split_ingress_staging_assets.py`

**Interfaces:**
- Consumes: 公网回环隧道端口 `127.0.0.1:18080` 和标准 Let's Encrypt 证书路径。
- Produces: 精确域名 HTTP/HTTPS vhost，以及不会读取密钥正文的全链路验证脚本。

- [ ] **Step 1: 先补 vhost 和验证脚本失败测试**

断言：HTTP 配置只处理精确域名和 ACME webroot；HTTPS 配置固定 TLSv1.2/1.3、上游回环、
覆盖 `Host` 与 `X-Forwarded-Proto`、SSE 双层无缓冲、OAuth 路由不记录 query；不得包含
`proxy_pass` 到 `192.168.110.210` 或任何公网地址。增加
`test_public_vhost_uses_only_loopback_upstream`，固定
`proxy_pass http://127.0.0.1:18080` 并拒绝在日志格式中使用 `$request_uri`。

- [ ] **Step 2: 创建 HTTP 引导 vhost**

HTTP 引导配置提供 `/.well-known/acme-challenge/` 和 `/healthz` 到隧道，其余请求在证书签发前
返回 503；证书就绪后替换为正式 vhost 的 301 HTTPS 跳转。

- [ ] **Step 3: 创建正式 HTTPS vhost**

证书固定读取：

```text
/etc/letsencrypt/live/staging.overselfx.com/fullchain.pem
/etc/letsencrypt/live/staging.overselfx.com/privkey.pem
```

正式 vhost 对 `/v1/chat/query`、OAuth callback、`/v1/` 和 `/` 分别转发到
`http://127.0.0.1:18080`，并保留安全头和 10 MiB 上传限制。

- [ ] **Step 4: 创建低敏验证脚本**

脚本只检查 DNS A、证书 SAN/有效期、远端回环监听、三个健康端点、SSE 响应类型和 HTTP→HTTPS；
不打印证书私钥、环境文件、容器环境或 OAuth query。

- [ ] **Step 5: 运行测试和语法检查**

Run:

```powershell
Set-Location CRM智能聊天系统
$env:PYTHONPATH = (Get-Location).Path
uv run --project backend pytest backend/tests/test_split_ingress_staging_assets.py -q
bash -n deploy/staging/rootless/verify-split-ingress.sh
```

Expected: 全部通过。

- [ ] **Step 6: 提交公网入口资产**

```powershell
git add CRM智能聊天系统/deploy/staging/rootless/public-nginx CRM智能聊天系统/deploy/staging/rootless/verify-split-ingress.sh CRM智能聊天系统/backend/tests/test_split_ingress_staging_assets.py
git commit -m "build: add staging public gateway assets"
```

---

### Task 4: 同步架构、运行手册、检查表和索引

**Files:**
- Create: `架构师/ADR-008-INFRA-双服务器Staging入口分离-v1.0.md`
- Modify: `架构师/ADR-007-INFRA-Rootless-Staging部署边界-v1.0.md`
- Modify: `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md`
- Modify: `CRM智能聊天系统/deploy/staging/rootless/README.md`
- Modify: `CRM智能聊天系统/deploy/production/README.md`
- Modify: `CRM智能聊天系统/README.md`
- Create: `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-双服务器Staging入口-综合测试-008.md`
- Create: `共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-双服务器Staging入口-001.md`
- Modify: `共享记忆文档/测试报告索引.md`
- Modify: `共享记忆文档/实施记录索引.md`

**Interfaces:**
- Consumes: 已批准设计和 Tasks 1～3 的实际文件/测试结果。
- Produces: 唯一活动入口操作步骤、架构取代关系、工程证据报告和可追溯索引。

- [ ] **Step 1: 新增 ADR-008 并标记 ADR-007 入口部分被取代**

ADR-008 固定两台服务器职责、单端口隧道、入口/出口 IP 区分、TLS 所属、Rootless 隔离和
production 非目标。ADR-007 只增加 dated 勘误，不重写历史证据。

- [ ] **Step 2: 重写 Rootless 运行手册的活动入口步骤**

手册按“预检 → 公网受限账号 → 隧道 → HTTP vhost → DNS → TLS → 正式 vhost → validate →
deploy → G0 → G1～G6”排列。旧 80/443 socket proxy 命令移到历史/停用说明，不能作为当前步骤。

- [ ] **Step 3: 更新检查表、产品/production README**

明确入口 IP `38.55.145.52`、业务服务器/出口独立、TLS 在公网服务器、production 未决定、
Shopee/Amazon UI 保留但不实现。

- [ ] **Step 4: 生成实施记录和测试报告**

报告只登记本次实际执行过的静态/动态结果；服务器、DNS、TLS、部署、恢复、回滚和 G1～G6
未执行的部分必须标记未执行，禁止写成通过。

- [ ] **Step 5: 更新两个索引并做路径/占位符检查**

Run:

```powershell
rg -n "183\.158\.225\.78|crm-staging-http\.socket|crm-staging-https\.socket" CRM智能聊天系统/deploy/staging/rootless 架构师/ADR-008-INFRA-双服务器Staging入口分离-v1.0.md
git diff --check
```

Expected: 旧地址/入口只出现在明确历史说明；计划和设计无占位符；diff check 无输出。

- [ ] **Step 6: 提交文档同步**

```powershell
git add 架构师 共享记忆文档 测试工程师 CRM智能聊天系统/README.md CRM智能聊天系统/deploy
git commit -m "docs: adopt split ingress staging operations"
```

---

### Task 5: 完成仓库验证、PR 与不可变候选

**Files:**
- Verify: `CRM智能聊天系统/backend/tests/test_split_ingress_staging_assets.py`
- Verify: `CRM智能聊天系统/backend/tests/test_rootless_staging_assets.py`
- Verify: `CRM智能聊天系统/backend/tests/test_production_gate_scripts.py`
- Verify: `CRM智能聊天系统/deploy/nginx/nginx-tunnel.conf`
- Verify: `CRM智能聊天系统/deploy/staging/rootless/`
- Verify: `CRM智能聊天系统/docker-compose.rootless-staging.yml`
- Verify: `CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1`
- Verify: `CRM智能聊天系统/scripts/Invoke-StagingRollbackDrill.ps1`

**Interfaces:**
- Consumes: Tasks 1～4 的代码、配置和文档。
- Produces: 通过 CI 的 PR、squash merge 后完整 main SHA 和三条新候选 RepoDigest。

- [ ] **Step 1: 执行聚焦和全量后端验证**

```powershell
Set-Location CRM智能聊天系统
$env:PYTHONPATH = (Get-Location).Path
$env:TMPDIR = (Join-Path $env:TEMP 'crm-split-ingress-tests')
uv run --project backend pytest backend/tests/test_split_ingress_staging_assets.py backend/tests/test_rootless_staging_assets.py backend/tests/test_production_gate_scripts.py -q
uv run --project backend pytest backend/tests -q
uv run --project backend ruff check backend
uv run --project backend ruff format --check backend
```

Expected: 全部命令退出 0；跳过项和既有 warning 单独记录，不计为通过。

- [ ] **Step 2: 验证前端、Compose、Shell 和文档**

```powershell
Set-Location frontend
npm ci
npm run lint
npm run typecheck
npm test -- --runInBand
npm run build
Set-Location ..
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.rootless-staging.yml --profile ai config --format json | Out-Null
bash -n deploy/staging/rootless/install-reverse-tunnel.sh
bash -n deploy/staging/rootless/install-public-tunnel-account.sh
bash -n deploy/staging/rootless/verify-split-ingress.sh
git diff --check
```

Expected: 全部退出 0；Compose 只发布回环 `10080`。

- [ ] **Step 3: 推送分支并创建 PR**

```powershell
git push -u origin feature/split-ingress-staging
gh pr create --repo CP11-gh/CRM --base main --head feature/split-ingress-staging --title "build: split staging public ingress from rootless runtime" --fill
```

Expected: PR 创建成功；CI 运行在该 PR 的 HEAD。

- [ ] **Step 4: 人工审阅、CI 通过后 squash merge**

审阅重点：公司容器隔离、回环端口、SSH key restriction、Nginx query 日志、SSE、Compose 摘要、
生产边界和文档事实。所有 required checks 成功后执行 squash merge，并删除远程短期分支。

- [ ] **Step 5: 获取新 main SHA 和候选摘要**

等待发布工作流完成，使用 GitHub API/Actions 制品把完整 main SHA 与 backend、frontend、
retrieval 三条 `repository@sha256` 关联；逐条执行 `docker buildx imagetools inspect` 复核。

---

### Task 6: 在两台服务器实施入口、隧道和失败关闭部署

**Files:**
- Server-only, repository-external: `/www/server/panel/vhost/nginx/staging.overselfx.com.conf`
- Server-only, repository-external: `/home/crm-tunnel/.ssh/authorized_keys`
- Server-only, repository-external: `/home/crmdeploy/secrets/tunnel/*`
- Server-only, repository-external: `/home/crmdeploy/config/crm-staging.env`
- Evidence only: `/home/crmdeploy/evidence/*`

**Interfaces:**
- Consumes: squash merge 后 main、三条候选摘要、现有六文件模型、两个 root SSH key。
- Produces: 真实公网 HTTPS → 隧道 → Rootless CRM 链路和 G0 低敏证据。

- [ ] **Step 1: 只读预检并冻结保护基线**

在两台服务器记录 OS、磁盘、内存、监听端口、Nginx vhost；在业务服务器记录系统 Docker
容器 ID/名称/镜像/启动时间/状态/端口 SHA-256，以及 Rootless info。任何公司容器漂移立即停止。

- [ ] **Step 2: 安装公网受限账号并建立隧道**

在业务服务器为本隧道生成独立 Ed25519 key 和固定 `known_hosts`；只把公钥传到公网服务器。
运行两个已合并安装器，验证公网只出现 `127.0.0.1:18080`，公网网卡地址不监听 18080。

- [ ] **Step 3: 配置 HTTP vhost 并测试 `--resolve` 链路**

把已合并 HTTP 配置安装为独立宝塔 vhost，执行 `/www/server/nginx/sbin/nginx -t` 后 reload。
在不改 DNS 的情况下使用 `curl --resolve staging.overselfx.com:80:38.55.145.52` 验证请求进入隧道。

- [ ] **Step 4: 切换 DNS 并签发 TLS**

把 A 记录切到 `38.55.145.52`，至少使用三个外部解析器验证；使用 ACME HTTP-01、无邮箱模式签发
公信证书。证书 SAN 必须精确包含域名，私钥权限只允许 root/宝塔 Nginx 所需账户读取。

- [ ] **Step 5: 安装正式 vhost**

先保存旧 staging vhost SHA-256，再原子安装正式配置；只有 Nginx 语法通过才 reload。验证 HTTP
301、HTTPS、OAuth query 不入日志、SSE 无缓冲，以及其他站点响应前后不变。

- [ ] **Step 6: 准备失败关闭环境并部署 Rootless Compose**

在业务服务器本地生成 JWT、数据库、MinIO、retrieval Token 等随机密钥；实测业务出口 IP；
写入 `0600` 环境文件但不输出正文。使用新候选摘要先 validate，再 deploy；执行迁移到 `023`。

- [ ] **Step 7: 完成 G0 动态验证**

验证所有容器 healthy、三个健康端点、登录页、迁移、模型六文件启动校验、Rootless data-root、
隧道重连、容器重启恢复、前端 npm audit、数据库/MinIO 备份、隔离恢复和兼容上一版回滚。

- [ ] **Step 8: 复核公司负载并同步现场证据**

重新计算公司系统 Docker 五字段 SHA-256 和公网其他站点摘要，必须与基线一致。把低敏结果追加到
008 测试报告和实施记录；原始配置、私钥、Token、客户数据和模型文件不进入 Git。

---

### Task 7: 按 G1～G6 验证 TikTok 人工辅助首版

**Files:**
- Modify: `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-双服务器Staging入口-综合测试-008.md`
- Modify: `共享记忆文档/测试报告索引.md`
- Modify: `共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-双服务器Staging入口-001.md`
- Modify: `共享记忆文档/实施记录索引.md`

**Interfaces:**
- Consumes: TikTok Partner Center 配置、真实店铺授权、批准的 DeepSeek key、独立开放集和 50 组授权凭据。
- Produces: G1～G6 权威证据和准确的 TikTok v0.1 状态结论。

- [ ] **Step 1: G1 OAuth/读取**

配置 callback、Scope 和业务出口白名单；执行真实 OAuth、Token 生命周期、唯一店铺、订单、物流、
会话和消息读取。任何 Mock 命中都判失败。

- [ ] **Step 2: G2 Webhook**

启用只读和 Webhook overlay，验证公网投递、官方签名、重复通知、未知主题、订单补全、撤权和
Worker 重启恢复。

- [ ] **Step 3: G3 人工普通消息**

只对单店铺、单账号、单操作员开启人工消息 overlay；验证确认、幂等、`sent/failed/unknown`、
熔断和管理员对账。自动回复、高风险写入和营销保持关闭。

- [ ] **Step 4: G4 AI/RAG**

在批准的数据出境边界内启用 DeepSeek 内部建议，验证 BGE Top-5、DLP、安全声明、人工使用建议、
Provider 失败和不自动发送。

- [ ] **Step 5: G5/G6 性能与稳定性**

使用 50 个独立授权客户端验证首个安全输出 P99 `<3000ms`、总耗时 P99 `<5000ms` 和完整
`done`；随后连续五个真实日历日验证 99.5% 可用性、审计和自动恢复。

- [ ] **Step 6: 形成最终结论**

只有 G0～G6 全部有权威证据时，结论才可写“TikTok 人工辅助 v0.1 可用”。不得写“三平台完整
MVP 完成”或“production 放行”；任一外部材料缺失时精确记录阻塞项。
