# Split-Ingress Staging Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task in the current task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变旧服务器 GitLab 和其他公司负载的前提下，把 `staging.overselfx.com` 部署为新服务器宝塔 Nginx/TLS 经受限 SSH 反向隧道访问旧服务器 Rootless CRM 的失败关闭 staging 环境。

**Architecture:** 新服务器 `38.55.145.52` 在公网终止 TLS，将请求代理到回环 `127.0.0.1:18080`；旧服务器 `192.168.110.210` 的 `crmdeploy` 主动建立 `18080 → 127.0.0.1:18081` 的受限反向隧道，Rootless Compose proxy 只发布 `127.0.0.1:18081:80`。仓库实现、远端 main、不可变 GHCR 镜像、两台服务器部署和低敏证据按顺序推进，每个阶段失败都回到 staging `503`，不回退到 GitLab。

**Tech Stack:** Git/GitHub Flow、GitHub Actions/GHCR、Docker Compose、Rootless Docker、PowerShell 7、Bash、systemd user services、OpenSSH reverse forwarding、宝塔 Nginx 1.30.4、pytest、Ruff、mypy、Next.js、FastAPI。

**Spec:** `docs/superpowers/specs/2026-09-19-split-ingress-staging-deployment-design.md`

## Global Constraints

- `38.55.145.52` 只承载宝塔 Nginx、TLS 和回环 SSH 反向监听，不运行 CRM 数据或模型服务。
- `192.168.110.210` 使用 `/home/crmdeploy`、UID 1004 和 `unix:///run/user/1004/docker.sock`；系统 Docker socket、容器、网络、卷和 data-root 禁止修改。
- GitLab 的 `0.0.0.0:10080/10443` 保持不变；CRM 只能发布 `127.0.0.1:18081:80`。
- SSH 远端监听只能是 `127.0.0.1:18080`，禁止 `GatewayPorts=yes`、PTY、agent/X11 转发或额外端口转发。
- staging 公共地址固定为 `https://staging.overselfx.com`；证书 SAN 必须包含该域名。
- backend、frontend、retrieval-model-service 必须来自最终远端 main SHA，并使用 `repository@sha256:` 加 64 位小写十六进制摘要；禁止服务器 build、浮动标签和历史 `f7c0f9f9` 候选。
- 首次部署固定关闭真实 TikTok、LLM、翻译、营销、自动回复和高风险写入；TikTok 应用身份与 DeepSeek Key 可以留空。
- 不打印或提交 `.env` 正文、私钥、Token、证书私钥、模型、备份或业务数据。
- 任何 Nginx 变更必须先通过 `/www/server/nginx/sbin/nginx -t`，只 reload，不 restart。
- 首次部署没有兼容上一版 CRM；失败时恢复 staging `503`、停止候选容器并保留卷，不删除数据，不把流量恢复到 GitLab。
- 本计划只完成 split-ingress 与失败关闭 staging 部署；G1～G6 和 production 放行不在本次范围。

## Review Focus

- **旧端口冲突：** `10080/10443` 已被 GitLab 占用；测试和现场预检必须拒绝 CRM 使用这两个端口，只接受旧服务器回环 `18081`。
- **隧道权限扩大：** 键选项、systemd unit 或 sshd 配置不得产生公网 `18080`、额外 listen/forward、交互 shell 或宽泛账号能力。
- **错误站点或证书：** staging 证书不匹配、隧道断开或 CRM 未就绪时只能得到明确 `502/503`，不能得到 GitLab、默认站点或忽略证书校验后的“成功”。
- **镜像与源码漂移：** 三个应用镜像的 OCI revision 必须等于远端 main SHA，RepoDigest 必须等于发布工作流证据；任何不一致停止部署。
- **公司负载漂移：** 系统 Docker 容器 ID、名称、镜像 ID、StartedAt、运行状态和端口的规范化摘要前后必须一致；不一致立即恢复 staging `503` 并停止后续步骤。

## Acceptance Mapping

| Acceptance criterion | Implemented and verified by |
| --- | --- |
| AC-01 | Tasks 2～4：split-ingress runtime、入口资产和当前文档 |
| AC-02 | Tasks 7、10：公司负载基线、部署后逐字复核和失败关闭 |
| AC-03 | Tasks 1、2、8：Rootless 唯一回环发布 `18081` 和现场监听验证 |
| AC-04 | Tasks 1、3、7：受限 SSH 账号、回环 `18080` 和隧道目标 `18081` |
| AC-05 | Task 9：宝塔证书 SAN/链/有效期和 HTTP→HTTPS |
| AC-06 | Tasks 3、7、9：公网 Nginx 只代理回环隧道且不得泄漏 query |
| AC-07 | Tasks 8、9：内链路与公网健康检查，明确拒绝 GitLab 响应 |
| AC-08 | Tasks 2、8、10：能力开关失败关闭、容器健康和恢复演练 |
| AC-09 | Tasks 7、9、10：503 持有、Nginx 原子切换和可恢复备份 |
| AC-10 | Tasks 5、10：本地/现场证据、IR/TR/RR、索引和任务状态闭环 |

---

### Task 1: 建立任务状态与 Split-Ingress 失败测试

**Files:**
- Modify: `docs/tasks/TASKS.md`
- Create: `src/tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py`
- Modify: `src/tests/backend/runtime_infrastructure/test_real_runtime_config.py`
- Modify: `src/tests/backend/runtime_infrastructure/test_production_gate_scripts.py`

**Interfaces:**
- Consumes: 规格中的 AC-01～AC-10、`BASE_SHA=98414c2b51bfd403365aa6c72e0585f045d4a26a`。
- Produces: `MVP-STAGING-001` 的 `DOING` 任务记录，以及固定端口、代理、SSH 和失败关闭契约的 RED 测试。

- [ ] **Step 1: 把实现分支改名并复核 Git 身份**

```powershell
git branch -m feature/split-ingress-staging-20260919
git status --short --branch
git rev-parse HEAD
git rev-parse --git-common-dir
```

Expected: 当前分支为 `feature/split-ingress-staging-20260919`，工作区干净，HEAD 包含已提交规格和计划。

- [ ] **Step 2: 在任务表增加 MVP-STAGING-001**

新增 P0 行，状态 `DOING`，分支为当前 feature 分支，依赖 `MVP-DOMAIN-001`，验收引用本规格 AC-01～AC-10，RR 为 required，最终 SHA 留空。

- [ ] **Step 3: 编写 Rootless overlay 的失败测试**

```python
def test_rootless_overlay_exposes_only_split_ingress_http_port() -> None:
    source = ROOTLESS_OVERLAY.read_text(encoding="utf-8")
    assert '"127.0.0.1:18081:80"' in source
    assert "10080" not in source
    assert "10443" not in source
    assert "nginx-tunnel.conf" in source
```

- [ ] **Step 4: 编写隧道和公网入口的失败测试**

```python
def test_reverse_tunnel_is_loopback_only_and_targets_crm_port() -> None:
    unit = TUNNEL_UNIT.read_text(encoding="utf-8")
    assert "-R 127.0.0.1:18080:127.0.0.1:18081" in unit
    assert "ExitOnForwardFailure=yes" in unit
    assert "StrictHostKeyChecking=yes" in unit
    assert "Restart=always" in unit
    assert "StrictHostKeyChecking=no" not in unit


def test_public_vhost_never_targets_gitlab_or_private_host() -> None:
    source = HTTPS_VHOST.read_text(encoding="utf-8")
    assert "proxy_pass http://127.0.0.1:18080" in source
    assert "192.168.110.210" not in source
    assert ":10080" not in source
    assert "$request_uri" not in source
```

- [ ] **Step 5: 更新门禁夹具的期望端口并运行 RED**

把测试生成的 proxy ports 改为单条 `127.0.0.1:18081→80`，增加“第二端口、非回环、`10080`、`10443`、可写 Nginx 挂载、TLS 证书挂载”均被拒绝的参数化用例。

```powershell
Set-Location src/backend
$env:GIT_CONFIG_COUNT='1'
$env:GIT_CONFIG_KEY_0='safe.directory'
$env:GIT_CONFIG_VALUE_0=(git rev-parse --show-toplevel)
uv run pytest -c pyproject.toml -q -p no:cacheprovider `
  ../tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py `
  ../tests/backend/runtime_infrastructure/test_real_runtime_config.py `
  ../tests/backend/runtime_infrastructure/test_production_gate_scripts.py
```

Expected: 新资产不存在、overlay 仍使用 `10080/10443`、门禁仍要求两端口，测试非零退出。

- [ ] **Step 6: 提交测试与任务起点**

```powershell
git add -- docs/tasks/TASKS.md src/tests/backend/runtime_infrastructure
git commit -m "test: define split ingress staging contracts"
```

---

### Task 2: 实现 Tunnel-Only Rootless Runtime 和门禁

**Files:**
- Create: `src/deploy/nginx/nginx-tunnel.conf`
- Modify: `src/compose/docker-compose.rootless-staging.yml`
- Modify: `src/scripts/Test-StagingProductionGates.ps1`
- Modify: `src/scripts/Invoke-StagingRollbackDrill.ps1`
- Test: `src/tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py`
- Test: `src/tests/backend/runtime_infrastructure/test_real_runtime_config.py`
- Test: `src/tests/backend/runtime_infrastructure/test_production_gate_scripts.py`

**Interfaces:**
- Consumes: 单端口 RED 契约和现有 base/prod Compose。
- Produces: 内层明文 Nginx、`127.0.0.1:18081:80` 唯一宿主机发布，以及 `Assert-ProductionComposeContract` 的单端口失败关闭校验。

- [ ] **Step 1: 创建内层明文 Nginx 配置**

配置保留现有 frontend/backend 路由和安全头，只监听 `80`；对所有上游覆盖 `X-Forwarded-Proto https`。SSE 路由包含：

```nginx
location = /v1/chat/query {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_request_buffering off;
    proxy_read_timeout 240s;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

日志格式只使用 `$uri`，OAuth callback 使用关闭或低敏 access log；配置不得引用证书文件、监听 443 或把错误日志写入响应。

- [ ] **Step 2: 把 Rootless overlay 改为单端口与只读配置覆盖**

```yaml
proxy:
  ports: !override
    - "127.0.0.1:18081:80"
  volumes: !override
    - type: bind
      source: ../deploy/nginx/nginx-tunnel.conf
      target: /etc/nginx/nginx.conf
      read_only: true
```

- [ ] **Step 3: 修改两个 PowerShell 门禁**

在两个 `Assert-ProductionComposeContract` 中：

```powershell
if (@($proxyService.ports).Count -ne 1) {
    throw "Staging Compose proxy must expose exactly one loopback HTTP port."
}
$expectedBinding = @{ host_ip = "127.0.0.1"; published = "18081"; target = "80" }
```

同时校验唯一只读挂载源为 `nginx-tunnel.conf`、目标 `/etc/nginx/nginx.conf`，不存在 `/etc/nginx/certs`；staging 必填变量中移除 `TLS_CERT_DIR`，production Compose 本身保持不变。

- [ ] **Step 4: 运行聚焦 GREEN**

```powershell
Set-Location src/backend
uv run pytest -c pyproject.toml -q -p no:cacheprovider `
  ../tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py `
  ../tests/backend/runtime_infrastructure/test_real_runtime_config.py `
  ../tests/backend/runtime_infrastructure/test_production_gate_scripts.py
```

Expected: 全部通过；负向夹具仍逐项失败关闭。

- [ ] **Step 5: 提交 runtime 变更**

```powershell
git add -- src/deploy/nginx/nginx-tunnel.conf src/compose/docker-compose.rootless-staging.yml `
  src/scripts/Test-StagingProductionGates.ps1 src/scripts/Invoke-StagingRollbackDrill.ps1 `
  src/tests/backend/runtime_infrastructure
git commit -m "build: route staging through tunnel-only proxy"
```

---

### Task 3: 恢复并收紧反向隧道与宝塔入口资产

**Files:**
- Create: `src/deploy/staging/rootless/install-public-tunnel-account.sh`
- Create: `src/deploy/staging/rootless/install-reverse-tunnel.sh`
- Create: `src/deploy/staging/rootless/systemd/user/crm-staging-tunnel.service`
- Create: `src/deploy/staging/rootless/public-nginx/staging.overselfx.com-http.conf`
- Create: `src/deploy/staging/rootless/public-nginx/staging.overselfx.com.conf`
- Create: `src/deploy/staging/rootless/verify-split-ingress.sh`
- Modify: `.gitattributes`
- Test: `src/tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py`

**Interfaces:**
- Consumes: `127.0.0.1:18081` Rootless 上游、现有 `/home/crmdeploy/secrets/tunnel/` 和新服务器 `crm-tunnel` 账号。
- Produces: 可重复安装的受限 systemd 隧道、失败关闭 HTTP vhost、正式 HTTPS vhost和低敏验证脚本。

- [ ] **Step 1: 从已审查历史版本移植资产**

逐文件以 `git show` 读取提交 `960e62afcee40160f15a4aaf0f31e803f6c0a2ea` 下列精确路径并移植到当前 `src/` 路径；不得 checkout 整个旧提交：

```text
CRM智能聊天系统/deploy/staging/rootless/install-public-tunnel-account.sh
CRM智能聊天系统/deploy/staging/rootless/install-reverse-tunnel.sh
CRM智能聊天系统/deploy/staging/rootless/systemd/user/crm-staging-tunnel.service
CRM智能聊天系统/deploy/staging/rootless/public-nginx/staging.overselfx.com-http.conf
CRM智能聊天系统/deploy/staging/rootless/public-nginx/staging.overselfx.com.conf
CRM智能聊天系统/deploy/staging/rootless/verify-split-ingress.sh
```

所有隧道目标从历史 `127.0.0.1:10080` 改为 `127.0.0.1:18081`。

- [ ] **Step 2: 固定 systemd 隧道单元**

```ini
[Service]
ExecStart=/usr/bin/ssh -NT -o BatchMode=yes -o ConnectTimeout=10 -o ExitOnForwardFailure=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o UserKnownHostsFile=/home/crmdeploy/secrets/tunnel/known_hosts -i /home/crmdeploy/secrets/tunnel/id_ed25519 -R 127.0.0.1:18080:127.0.0.1:18081 crm-tunnel@38.55.145.52
Restart=always
RestartSec=5
```

安装器必须核验 `crmdeploy`/UID 1004、目录 `0700`、私钥和 known_hosts `0600`、无符号链接、固定主机指纹和 `systemd-analyze --user verify`。

- [ ] **Step 3: 固定公网隧道账号权限**

公网安装器只接受单条 Ed25519 公钥并写成：

```bash
IFS= read -r validated_public_key
case "$validated_public_key" in ssh-ed25519\ *) ;; *) exit 1 ;; esac
printf 'command="/usr/bin/false",restrict,port-forwarding,permitlisten="127.0.0.1:18080" %s\n' "$validated_public_key"
```

脚本拒绝多行、额外选项、软链接、宽松目录权限和已有非本项目授权行；不得输出公钥正文或修改 sshd 全局 `GatewayPorts`。

- [ ] **Step 4: 创建 HTTP 持有页和正式 HTTPS vhost**

HTTP 持有配置只允许 `/.well-known/acme-challenge/`，其余返回 `503`；正式配置的 80 除 ACME 外 301 到 HTTPS，443 读取宝塔站点专属证书并代理 `http://127.0.0.1:18080`。SSE 路由关闭双层 buffering，OAuth callback 日志不使用 `$request_uri`/`$args`。

- [ ] **Step 5: 创建低敏现场验证脚本**

脚本必须验证 DNS A、证书 SAN/链/有效期、18080 回环监听、18081 回环监听、HTTP→HTTPS、首页和三个健康端点；检测 `X-Gitlab-` 或 `/users/sign_in` 立即失败。脚本不得使用 `curl -k`。

- [ ] **Step 6: 运行资产测试与语法验证**

```powershell
Set-Location src/backend
uv run pytest -c pyproject.toml -q -p no:cacheprovider `
  ../tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py
Set-Location ../..
bash -n src/deploy/staging/rootless/install-public-tunnel-account.sh
bash -n src/deploy/staging/rootless/install-reverse-tunnel.sh
bash -n src/deploy/staging/rootless/verify-split-ingress.sh
```

Expected: 全部退出 0。

- [ ] **Step 7: 提交入口资产**

```powershell
git add -- .gitattributes src/deploy/staging/rootless src/tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py
git commit -m "build: restore split ingress staging assets"
```

---

### Task 4: 同步当前事实、运行手册和发布门禁

**Files:**
- Modify: `docs/architecture/SYSTEM.md`
- Modify: `docs/operations/DEPLOYMENT.md`
- Modify: `docs/operations/RELEASE-GATES.md`
- Modify: `docs/memory/PROJECT-STATE.md`
- Modify: `src/deploy/staging/rootless/README.md`
- Modify: `src/deploy/production/README.md`
- Modify: `README.md`
- Modify: `docs/tasks/TASKS.md`

**Interfaces:**
- Consumes: Tasks 1～3 的实际实现与已批准规格。
- Produces: 唯一活动 split-ingress 操作路径、准确的“已实现/待真实验证”状态，以及进入 `VERIFYING` 的任务。

- [ ] **Step 1: 更新当前架构和部署文档**

把同机 systemd `80/443 → 10080/10443` 从当前 staging 方案改为历史说明；当前拓扑固定为新服务器 `443 → 18080 → SSH → 18081 → Rootless proxy`。production 只保留公共域名契约，不继承 staging 服务器拓扑。

- [ ] **Step 2: 重写 Rootless staging 活动运行顺序**

运行手册依次为：保护基线 → 版本化资产 → HTTP 持有 vhost → 隧道 18081 → 镜像/配置 validate → Rootless deploy → 宝塔证书 → 正式 HTTPS vhost → 动态验证 → 隧道重连 → 公司负载复核 → 失败关闭回退。

- [ ] **Step 3: 更新门禁和项目状态**

G0 保持“已实现，待真实验证”，明确当前已知 TLS 不匹配、CRM 未部署和现有隧道误指 GitLab；`MVP-STAGING-001` 转 `VERIFYING`，不得提前写 `DONE`。

- [ ] **Step 4: 运行文档契约与 diff 检查**

```powershell
git grep -n -I -E '127\.0\.0\.1:10080|127\.0\.0\.1:10443' -- docs src/deploy src/compose src/scripts
git diff --check
```

Expected: `10080/10443` 只出现在明确的 GitLab 冲突、历史说明或负向测试中；活动 CRM 配置全部使用 `18081`。

- [ ] **Step 5: 提交文档同步**

```powershell
git add -- README.md docs/architecture/SYSTEM.md docs/operations/DEPLOYMENT.md `
  docs/operations/RELEASE-GATES.md docs/memory/PROJECT-STATE.md docs/tasks/TASKS.md `
  src/deploy/staging/rootless/README.md src/deploy/production/README.md
git commit -m "docs: adopt split ingress staging operations"
```

---

### Task 5: 完成候选验证、审查与候选冻结

**Files:**
- Verify: all files changed in Tasks 1～4
- Create draft: `docs/records/implementation/IR-MVP-STAGING-001-20260919-R01.md`
- Create draft: `docs/reports/tests/TR-MVP-STAGING-001-20260919-R01.md`
- Create draft: `docs/reports/reviews/RR-MVP-STAGING-001-20260919-R01.md`

**Interfaces:**
- Consumes: 完整 feature 分支。
- Produces: 经本地验证和安全审查的候选 subject SHA；远端发布前的明确恢复点。

- [ ] **Step 1: 运行聚焦验证**

```powershell
Set-Location src/backend
$env:GIT_CONFIG_COUNT='1'
$env:GIT_CONFIG_KEY_0='safe.directory'
$env:GIT_CONFIG_VALUE_0=(git rev-parse --show-toplevel)
uv run pytest -c pyproject.toml -q -p no:cacheprovider `
  ../tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py `
  ../tests/backend/runtime_infrastructure/test_real_runtime_config.py `
  ../tests/backend/runtime_infrastructure/test_production_gate_scripts.py `
  ../tests/backend/runtime_infrastructure/test_rootless_staging_assets.py
```

- [ ] **Step 2: 运行静态与完整回归**

```powershell
uv run ruff check app scripts ../tests/backend
uv run ruff format --check app scripts ../tests/backend
uv run mypy app scripts
uv run pytest -c pyproject.toml -q -p no:cacheprovider
```

Expected: 所有命令退出 0；跳过项和既有 warning 原样记录。

- [ ] **Step 3: 验证 Compose、Shell、前端与敏感信息**

```powershell
Set-Location ../..
docker compose --project-name crm-staging --env-file src/config/.env.example `
  -f src/compose/docker-compose.yml -f src/compose/docker-compose.prod.yml `
  -f src/compose/docker-compose.rootless-staging.yml --profile ai config --quiet
bash -n src/deploy/staging/rootless/install-public-tunnel-account.sh
bash -n src/deploy/staging/rootless/install-reverse-tunnel.sh
bash -n src/deploy/staging/rootless/verify-split-ingress.sh
npm --prefix src/frontend ci
npm --prefix src/frontend run lint
npm --prefix src/frontend run typecheck
npm --prefix src/frontend run build
git grep -n -I -E 'BEGIN (OPENSSH |RSA |EC )?PRIVATE KEY|ghp_|github_pat_|sk-[A-Za-z0-9]+' -- .
git diff --check
```

Expected: 构建和检查通过；secret grep 无命中。

- [ ] **Step 4: 形成候选 IR/TR/RR 草稿并提交**

记录真实命令、结果、候选 SHA、AC 映射和未执行的服务器步骤；RR 聚焦端口冲突、SSH 权限、Nginx query 日志、镜像供应链、公司负载隔离和回滚。服务器未执行项必须标记 `PENDING_LIVE_EXECUTION`。

- [ ] **Step 5: 冻结候选 SHA 并复核分支状态**

```powershell
$candidateSha = (git rev-parse HEAD).Trim()
git status --short --branch
git diff main...HEAD --check
git log --oneline --decorate main..HEAD
```

Expected: feature 分支干净，候选提交完整，尚未合入本地或远端 main；失败时不推送远端。

---

### Task 6: 对齐远端 main 并发布不可变镜像

**Files:**
- Remote GitHub state: `origin/main`
- Workflow: `.github/workflows/publish-images.yml`
- Artifact: `image-repo-digests-$mainSha/repo-digests.json`

**Interfaces:**
- Consumes: 本地已验证 main、当前 GitHub 登录、`image-publishing` Environment。
- Produces: 远端 main 精确 SHA和三个与该 SHA 绑定的 GHCR RepoDigest。

- [ ] **Step 1: 重新读取远端并验证只能快进**

```powershell
git fetch origin main
git merge-base --is-ancestor origin/main main
git rev-list --left-right --count origin/main...main
git status --short --branch
```

Expected: `origin/main` 是本地 main 祖先、左侧为 0、本地 main 可以普通 fast-forward 推送，两个工作区都干净。否则停止，不 rebase、不 force push。

- [ ] **Step 2: 快进同步既有本地 main 基线**

```powershell
git push origin main:main
```

Expected: 普通 fast-forward；若分支保护拒绝，停止并报告，不改保护规则。

- [ ] **Step 3: 通过 feature PR 合入 split-ingress**

```powershell
git push -u origin feature/split-ingress-staging-20260919
gh pr create --repo CP11-gh/CRM --base main --head feature/split-ingress-staging-20260919 `
  --title "build: restore split ingress staging" `
  --body "Implements MVP-STAGING-001 AC-01 through AC-10; keeps live rollout gated."
$prNumber = (gh pr view feature/split-ingress-staging-20260919 --repo CP11-gh/CRM --json number --jq .number).Trim()
gh pr checks $prNumber --repo CP11-gh/CRM --watch
gh pr merge $prNumber --repo CP11-gh/CRM --squash --delete-branch
```

Expected: required checks 通过后 squash merge；任何失败先修同一分支，不绕过门禁。

- [ ] **Step 4: 快进本地 main 到已合并远端 main**

```powershell
git -C 'E:\develop\CRM智能聊天系统' fetch origin main
git -C 'E:\develop\CRM智能聊天系统' merge --ff-only origin/main
git -C 'E:\develop\CRM智能聊天系统' status --short --branch
```

Expected: 主 checkout 干净并精确指向远端 main；不把 feature 分支直接合到 main。

- [ ] **Step 5: 获取远端 main SHA 并发布镜像**

```powershell
$mainSha = (gh api repos/CP11-gh/CRM/commits/main --jq .sha).Trim()
gh workflow run publish-images.yml --repo CP11-gh/CRM --ref main -f source_sha=$mainSha
$runId = gh run list --repo CP11-gh/CRM --workflow publish-images.yml --branch main `
  --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId'
gh run watch $runId --repo CP11-gh/CRM --exit-status
gh run download $runId --repo CP11-gh/CRM --name "image-repo-digests-$mainSha" `
  --dir "src/tests/.artifacts/mvp-staging-001/images"
```

Expected: 三个 build 和 evidence job 成功；JSON 的 `source_sha` 等于 `$mainSha`，三个 reference 都以 `repository@sha256:` 开头并跟随完整 64 位小写十六进制 SHA-256。

- [ ] **Step 6: 验证 OCI revision 与证据一致**

对 artifact 中三条 reference 执行 `docker buildx imagetools inspect`，核对 manifest digest；拉取后使用 `docker image inspect` 核对 `org.opencontainers.image.revision=$mainSha`。任一不一致停止，不部署。

---

### Task 7: 建立现场保护基线并安全替换错误隧道

**Files:**
- Server-only: `/home/crmdeploy/src/split-ingress-$mainSha/`
- Server-only: `/home/crmdeploy/evidence/mvp-staging-001/$runId/`
- Server-only: `/www/server/panel/vhost/nginx/staging.overselfx.com.conf`
- Server-only: `/root/crm-staging-backups/$runId/`

**Interfaces:**
- Consumes: 远端 main 资产、两把受保护的临时管理员密钥、现场现有 tunnel 账号/密钥。
- Produces: 可恢复的 HTTP `503` 持有入口、目标改为 `18081` 的隧道和不可变前置证据。

- [ ] **Step 1: 创建版本化资产目录，不覆盖旧资产**

本地从远端 main 导出 `src/deploy/staging/rootless` 和需要的 Compose/脚本到只含跟踪文件的临时包，计算 SHA-256；旧服务器创建精确 `/home/crmdeploy/src/split-ingress-$mainSha`，确认不存在后上传并设为 `crmdeploy:crmdeploy 0750`。

- [ ] **Step 2: 记录公司系统 Docker 与新服务器站点基线**

旧服务器把系统 Docker 的容器 ID、名称、镜像 ID、StartedAt、状态、端口按名称排序后写入 `0600` 证据文件并计算 SHA-256；同时记录 Rootless info、端口和磁盘。新服务器记录全部 vhost 文件名/摘要、Nginx 版本、监听和 staging 配置摘要，不复制私钥。

- [ ] **Step 3: 把公网 staging 置于 HTTP 503 持有模式**

先把现有 staging vhost 精确备份到 `/root/crm-staging-backups/$runId`，安装已合并 HTTP 持有配置，执行 Nginx 语法测试后 reload。验证 `/` 返回项目定义的 503，且不再代理 `/healthz` 到 GitLab。

- [ ] **Step 4: 验证现有受限账号并更新隧道 unit**

复核 `crm-tunnel` 无 sudo、nologin、授权行只含 `permitlisten="127.0.0.1:18080"`。在旧服务器以 `crmdeploy` 运行版本化安装器，把 unit 更新为 `18080 → 18081`，daemon-reload 后 restart。

- [ ] **Step 5: 验证新旧回环边界**

```text
新服务器：127.0.0.1:18080 必须由 sshd/crm-tunnel 监听，公网地址和 0.0.0.0 不得监听。
旧服务器：18081 在 CRM 启动前必须空闲；10080/10443 仍由原 GitLab 占用且进程/容器不变。
```

隧道存在但 18081 尚无服务时连接失败属于预期；公网保持 503。

---

### Task 8: 配置 GitHub Staging Environment 并部署 Rootless CRM

**Files:**
- GitHub Environment: `staging`
- Existing secret value: `CRM_STAGING_ENV_FILE=/home/crmdeploy/config/crm-staging.env`
- Existing variable: `CRM_STAGING_BASE_URL=https://staging.overselfx.com`
- Server data: `/home/crmdeploy/.local/share/docker/`

**Interfaces:**
- Consumes: Task 6 的三个 RepoDigest、Task 7 的安全隧道、现有 `0600` 环境文件和模型六文件。
- Produces: 全部真实能力关闭且监听旧服务器回环 18081 的健康 `crm-staging` Compose 项目。

- [ ] **Step 1: 验证 runner 与 Environment 配置**

```powershell
gh api repos/CP11-gh/CRM/actions/runners --jq '.runners[] | select(.name=="crm-staging-192-168-110-210") | {name,status,busy,labels:[.labels[].name]}'
gh variable set CRM_STAGING_BASE_URL --repo CP11-gh/CRM --env staging --body 'https://staging.overselfx.com'
gh secret set CRM_STAGING_ENV_FILE --repo CP11-gh/CRM --env staging --body '/home/crmdeploy/config/crm-staging.env'
```

Expected: runner online、不 busy，标签包含 `self-hosted,linux,x64,crm-staging`。

- [ ] **Step 2: 对环境文件做不泄密契约检查**

远端只输出变量名和 `SET/EMPTY`；确认公网 URL 使用 overselfx、模型路径为 `/home/crmdeploy/assets/models`、安全开关均为 false、核心随机密钥非空、TikTok/DeepSeek 可为空。禁止输出值。

- [ ] **Step 3: 触发 validate 工作流**

```powershell
$artifact = Get-Content -Raw 'src/tests/.artifacts/mvp-staging-001/images/repo-digests.json' | ConvertFrom-Json
$backendImage = $artifact.backend.reference
$frontendImage = $artifact.frontend.reference
$retrievalImage = $artifact.retrieval_model.reference
gh workflow run staging-gates.yml --repo CP11-gh/CRM --ref main `
  -f operation=validate -f confirm_target=staging `
  -f "backend_image=$backendImage" `
  -f "frontend_image=$frontendImage" `
  -f "retrieval_model_image=$retrievalImage"
```

从 artifact JSON 程序化读取三个 reference，不手工重输。等待 run 完成并下载 validate evidence；退出非零则停止。

- [ ] **Step 4: 记录数据库/MinIO 首次部署恢复边界**

确认当前 Rootless 没有 CRM 容器和卷；首次部署没有上一镜像可回滚。创建部署前证据目录，不创建伪备份；回退定义为保持卷、停止候选和公网 503。

- [ ] **Step 5: 触发 deploy 工作流**

用与 validate 完全相同的三条 reference，`operation=deploy`、`confirm_target=staging`。等待 `--no-build --wait --wait-timeout 600` 完成；任何容器不健康停止，不自动重试。

- [ ] **Step 6: 在公网仍为 503 时验证内链路**

旧服务器检查 Rootless proxy 仅监听 `127.0.0.1:18081`，容器全部 healthy，数据库迁移头等于当前仓库头；新服务器使用 `curl -H 'Host: staging.overselfx.com' http://127.0.0.1:18080/healthz` 验证 SSH→CRM 链路，响应不得含 GitLab 标头。

---

### Task 9: 通过宝塔签发证书并切换正式 HTTPS

**Files:**
- BaoTa site: `staging.overselfx.com`
- Certificate directory managed by BaoTa: `/www/server/panel/vhost/cert/staging.overselfx.com/`
- Vhost: `/www/server/panel/vhost/nginx/staging.overselfx.com.conf`

**Interfaces:**
- Consumes: 可公网访问的 ACME webroot、健康 CRM 隧道和已经指向 `38.55.145.52` 的 DNS。
- Produces: 正确 SAN 的公信证书、HTTP→HTTPS 和正式 CRM 公网入口。

- [ ] **Step 1: 验证 DNS 与 ACME 文件路径**

从本机、`1.1.1.1` 和 `8.8.8.8` 查询 A 记录，均须为 `38.55.145.52`。在 webroot 写入随机低敏 challenge 文件，公网 HTTP 精确读取后立即删除该文件；不更改其他路径。

- [ ] **Step 2: 使用宝塔现有证书流程申请 Let's Encrypt RSA2048**

在已认证的宝塔站点 SSL 页面选择 `staging.overselfx.com`、Let's Encrypt、RSA2048、文件验证。若当前 Codex 浏览器没有已认证会话或宝塔 API 未配置，不安装新的 ACME 客户端、不读取面板数据库凭据，停止并要求用户完成面板登录后继续。

- [ ] **Step 3: 验证证书后安装正式 vhost**

只读取公开证书信息验证 SAN、issuer、notBefore/notAfter 和链；用 OpenSSL 验证证书/私钥公钥摘要匹配但不输出私钥。原子替换为已合并 HTTPS vhost，`nginx -t` 成功后 reload。

- [ ] **Step 4: 执行公网 HTTPS 冒烟**

```powershell
curl.exe --fail --proto '=https' https://staging.overselfx.com/
curl.exe --fail --proto '=https' https://staging.overselfx.com/healthz
curl.exe --fail --proto '=https' https://staging.overselfx.com/v1/health
curl.exe --fail --proto '=https' https://staging.overselfx.com/v1/health/ready
```

另验证 HTTP 301、证书链、响应无 `X-Gitlab-*` 和 `/users/sign_in`，OAuth callback 带虚假 query 的日志不含 query 值。

---

### Task 10: 故障恢复、最终证据与任务收尾

**Files:**
- Modify draft to final: `docs/records/implementation/IR-MVP-STAGING-001-20260919-R01.md`
- Modify draft to final: `docs/reports/tests/TR-MVP-STAGING-001-20260919-R01.md`
- Modify draft to final: `docs/reports/reviews/RR-MVP-STAGING-001-20260919-R01.md`
- Modify: `docs/records/implementation/IMPLEMENTATION-INDEX.md`
- Modify: `docs/reports/tests/TEST-INDEX.md`
- Modify: `docs/reports/reviews/REVIEW-INDEX.md`
- Modify: `docs/tasks/TASKS.md`
- Modify: `docs/quality/TEST-STATUS.md`
- Modify: `docs/operations/RELEASE-GATES.md`
- Modify: `docs/memory/PROJECT-STATE.md`

**Interfaces:**
- Consumes: 仓库验证、GitHub run/artifact、两台服务器低敏证据和公网动态结果。
- Produces: 可审计的 `MVP-STAGING-001` 完成结论；G0 仍只按真实证据更新，不推导 G1～G6。

- [ ] **Step 1: 验证隧道自动恢复**

在旧服务器仅 restart `crm-staging-tunnel.service`，记录断开期间公网为 `502/503`、重新监听和健康恢复时间。不得重启 sshd、Nginx、系统 Docker 或公司容器。

- [ ] **Step 2: 验证 CRM 容器恢复**

只重启 Rootless `crm-staging` proxy/backend 的一个低风险实例，验证 healthcheck、数据库状态和公网恢复；不重启 PostgreSQL/MinIO 做破坏性演练，不删除卷。

- [ ] **Step 3: 复核公司负载与其他站点**

重新生成系统 Docker 五字段规范化摘要并与 Task 7 基线逐字比较；复核新服务器其他 vhost 文件摘要和选定站点 HTTP 状态未变化。任何差异把任务标记 `BLOCKED` 并恢复 staging 503。

- [ ] **Step 4: 定稿 IR/TR/RR 与状态**

IR/TR/RR 绑定实际 subject SHA、GitHub main SHA、镜像 RepoDigest、workflow run ID、配置摘要和 AC-01～AC-10；原始远程证据仅保存在受限服务器目录，仓库只写低敏摘要。任务在全部 AC 通过后转 `DONE`；RELEASE-GATES 只把已取得的 G0 子项标为真实通过，备份恢复/兼容回滚等未执行项继续阻塞。

- [ ] **Step 5: 提交并通过证据 PR 合入 main**

从最新远端 main 创建 `docs/mvp-staging-001-evidence`，只提交允许的 IR/TR/RR、索引、TASK、TEST-STATUS、RELEASE-GATES 和 PROJECT-STATE。运行链接、SHA、索引和 `git diff --check` 验证后推送、创建 PR、等待检查、squash merge。

- [ ] **Step 6: 删除临时管理员私钥副本**

先确认没有活动 ssh/scp 进程引用 `C:\Users\Administrator\AppData\Local\Temp\codex-crm-staging-8114b6122658440d8e38270918baf8a4`，解析并核对目标仍位于系统临时目录且名称精确匹配；随后删除该单一目录。原始 `E:\soft\VMware\*_id_ed25519` 不修改、不删除。

- [ ] **Step 7: 最终验证**

重新读取远端 main、GitHub workflow、两台服务器监听/服务、Rootless Compose、公网 TLS/健康、任务状态和工作区状态。最终报告准确区分：split-ingress 已部署、失败关闭 staging 可达、TikTok G1～G6 未完成、production 未放行。
