# Rootless Docker Staging Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不影响公司现有系统 Docker 的前提下，为 `staging.hophorsefit.com` 建立可审计、可回滚的 Rootless Docker staging 运行面，并完成失败关闭部署证据。

**Architecture:** `crmdeploy` 的 Rootless Docker 只在回环地址发布 `10080/10443`，root 管理的 systemd socket proxy 将公网 `80/443` 转发到这些端口。仓库通过精确环境域名契约、Rootless Compose overlay 和 staging-only 门禁脚本支持该运行面；GitHub Actions self-hosted runner 以 `crmdeploy` 身份使用 Rootless socket 和不可变 GHCR RepoDigest。

**Tech Stack:** Python 3.11、Pydantic Settings、pytest、PowerShell 7.6.5、Docker Engine 29.6.2 Rootless、Docker Compose 5.3.1、systemd 259、GitHub Actions Runner 2.336.0、Ubuntu 26.04 LTS、Nginx、GitHub Flow。

**Spec:** `docs/superpowers/specs/2026-09-09-rootless-staging-deployment-design.md`

## Global Constraints

- 不停止、重启、重建、改名、迁移或接管系统 Docker 及现有公司容器。
- 不修改系统 Docker 的 `/var/lib/docker`、daemon socket、网络或数据卷。
- Rootless 用户固定为 `crmdeploy`，UID/GID 为 `1004`，数据必须位于 `/home/crmdeploy`。
- Rootless Docker socket 固定为 `unix:///run/user/1004/docker.sock`，禁止 Docker API TCP 监听。
- Rootless proxy 只绑定 `127.0.0.1:10080` 和 `127.0.0.1:10443`；公网只开放 `80/443`。
- staging 域名固定为 `staging.hophorsefit.com`；production 域名继续固定为 `www.hophorsefit.com`。
- staging OAuth callback 固定为 `https://staging.hophorsefit.com/v1/integrations/tiktok/oauth/callback`。
- production OAuth callback 固定为 `https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback`。
- staging Compose 项目名固定为 `crm-staging`。
- 初次部署时 `ALLOW_MOCK_PLATFORM_ADAPTERS`、全部 `REAL_TIKTOK_*`、`LLM_ENABLED`、`LLM_LIVE_EVAL`、`AI_TRANSLATION_ENABLED`、`AI_MARKETING_ENABLED` 和 `AUTO_REPLY_ENABLED` 必须为 `false`。
- `.env`、真实密钥、Token、证书私钥、凭证池、模型权重和完整业务数据不得进入 Git 或低敏证据。
- BGE 模型必须放在 checkout 外，只读挂载，并按现有清单执行 SHA-256 校验。
- 代码和缺陷修改必须遵守 TDD；声明完成前必须使用 `superpowers:verification-before-completion`。
- 每个 PR 必须通过 CI、人工审阅和安全检查，默认 squash merge，并删除短期分支。

---

## File Responsibility Map

- `CRM智能聊天系统/backend/app/shared/config/settings.py`：按真实环境选择唯一合法 TikTok OAuth 回调。
- `CRM智能聊天系统/backend/tests/test_real_runtime_config.py`：环境域名和 Rootless Compose 静态契约测试。
- `CRM智能聊天系统/docker-compose.rootless-staging.yml`：仅覆盖 staging 环境名与回环端口。
- `CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1`：Rootless staging validate/deploy 门禁。
- `CRM智能聊天系统/scripts/Invoke-StagingRollbackDrill.ps1`：Rootless staging 镜像回滚门禁。
- `CRM智能聊天系统/backend/tests/test_production_gate_scripts.py`：两个 PowerShell 门禁的失败关闭测试。
- `.github/workflows/staging-gates.yml`：在 self-hosted runner 上推导 Rootless socket并传给门禁脚本。
- `CRM智能聊天系统/deploy/staging/rootless/bootstrap-host.sh`：安装最小主机依赖并配置 Rootless Docker。
- `CRM智能聊天系统/deploy/staging/rootless/install-entry-proxy.sh`：安装可逆的 `80/443` systemd TCP 转发。
- `CRM智能聊天系统/deploy/staging/rootless/install-runner.sh`：校验固定下载摘要并安装 runner/PowerShell。
- `CRM智能聊天系统/deploy/staging/rootless/systemd/*`：公网入口和用户 runner 的 systemd 单元。
- `CRM智能聊天系统/deploy/staging/rootless/toolchain-manifest.json`：固定 runner 和 PowerShell URL/SHA-256。
- `CRM智能聊天系统/deploy/staging/rootless/README.md`：运维顺序、停点、证据和清理说明。
- `CRM智能聊天系统/backend/tests/test_rootless_staging_assets.py`：bootstrap、systemd、供应链与权限契约测试。
- `架构师/ADR-007-INFRA-Rootless-Staging部署边界-v1.0.md`：新增 staging 运行面架构决策。
- `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md`：只更新已取得的 staging 事实，不提前放行。
- `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-Rootless-Staging运行面-综合测试-007.md`：工程和真实主机验证证据。
- `共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-Rootless-Staging部署-001.md`：实施记录。
- `共享记忆文档/测试报告索引.md`、`共享记忆文档/实施记录索引.md`：新增索引项。

---

### Task 1: Make TikTok OAuth Redirect Environment-Specific

**Files:**
- Modify: `CRM智能聊天系统/backend/app/shared/config/settings.py:18-24,420-430`
- Modify: `CRM智能聊天系统/backend/tests/test_real_runtime_config.py:146-175`

**Interfaces:**
- Consumes: `Settings.app_env: str` and `Settings.tiktok_oauth_redirect_uri: str | None`.
- Produces: `TIKTOK_OAUTH_FIXED_REDIRECT_URIS: dict[str, str]` and environment-specific exact-match validation.

- [ ] **Step 1: Replace the shared acceptance test with environment-specific failing tests**

Extend the existing settings import with:

```python
from app.shared.config.settings import (
    TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI,
    TIKTOK_OAUTH_STAGING_REDIRECT_URI,
)
```

```python
@pytest.mark.parametrize(
    ("app_env", "redirect_uri"),
    [
        ("integration", TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI),
        ("staging", TIKTOK_OAUTH_STAGING_REDIRECT_URI),
        ("production", TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI),
    ],
)
def test_real_environments_accept_only_their_fixed_oauth_redirect_uri(
    app_env: str,
    redirect_uri: str,
) -> None:
    settings = production_settings(APP_ENV=app_env, TIKTOK_OAUTH_REDIRECT_URI=redirect_uri)
    assert settings.tiktok_oauth_redirect_uri == redirect_uri


@pytest.mark.parametrize(
    ("app_env", "redirect_uri"),
    [
        ("staging", TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI),
        ("production", TIKTOK_OAUTH_STAGING_REDIRECT_URI),
    ],
)
def test_real_environments_reject_another_environments_oauth_redirect(
    app_env: str,
    redirect_uri: str,
) -> None:
    with pytest.raises(ValidationError, match="TIKTOK_OAUTH_REDIRECT_URI"):
        production_settings(APP_ENV=app_env, TIKTOK_OAUTH_REDIRECT_URI=redirect_uri)
```

- [ ] **Step 2: Run the focused tests and verify the staging acceptance case fails**

Run:

```powershell
& 'E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe' -m pytest tests/test_real_runtime_config.py -q
```

Expected: FAIL because staging still only accepts `www.hophorsefit.com`.

- [ ] **Step 3: Implement the minimal exact environment mapping**

```python
TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI = f"https://www.hophorsefit.com{TIKTOK_OAUTH_PUBLIC_CALLBACK_PATH}"
TIKTOK_OAUTH_STAGING_REDIRECT_URI = f"https://staging.hophorsefit.com{TIKTOK_OAUTH_PUBLIC_CALLBACK_PATH}"
TIKTOK_OAUTH_FIXED_REDIRECT_URI = TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI
TIKTOK_OAUTH_FIXED_REDIRECT_URIS = {
    "integration": TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI,
    "staging": TIKTOK_OAUTH_STAGING_REDIRECT_URI,
    "production": TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI,
}
```

Update `validate_tiktok_oauth_redirect_uri()` to compare `value` with
`TIKTOK_OAUTH_FIXED_REDIRECT_URIS[self.app_env]` after the existing HTTPS/path checks. Keep the production
alias so callers importing `TIKTOK_OAUTH_FIXED_REDIRECT_URI` do not break.

- [ ] **Step 4: Run OAuth and runtime tests**

Run:

```powershell
& 'E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe' -m pytest tests/test_real_runtime_config.py tests/test_tiktok_oauth.py -q
```

Expected: all tests PASS; production still rejects the staging host and staging rejects the production host.

- [ ] **Step 5: Commit the environment contract**

```powershell
git add -- 'CRM智能聊天系统/backend/app/shared/config/settings.py' 'CRM智能聊天系统/backend/tests/test_real_runtime_config.py'
git commit -m "feat: isolate staging TikTok callback"
```

---

### Task 2: Add the Rootless Staging Compose Overlay

**Files:**
- Create: `CRM智能聊天系统/docker-compose.rootless-staging.yml`
- Modify: `CRM智能聊天系统/backend/tests/test_real_runtime_config.py:356-418`

**Interfaces:**
- Consumes: services from `docker-compose.yml` and `docker-compose.prod.yml`.
- Produces: a fixed overlay with `APP_ENV=staging` and loopback-only proxy ports.

- [ ] **Step 1: Add a failing static contract test**

```python
def test_rootless_staging_overlay_is_loopback_only_and_fail_closed() -> None:
    overlay = (PROJECT_ROOT / "docker-compose.rootless-staging.yml").read_text(encoding="utf-8")
    assert '"127.0.0.1:10080:80"' in overlay
    assert '"127.0.0.1:10443:443"' in overlay
    assert '"0.0.0.0:10080:80"' not in overlay
    assert '"0.0.0.0:10443:443"' not in overlay
    for service_name in ("backend", "worker", "jobs", "agent-worker"):
        assert 'APP_ENV: "staging"' in compose_service_block(overlay, service_name)
    for name in (
        "REAL_TIKTOK_READ_ENABLED",
        "REAL_TIKTOK_WEBHOOK_ENABLED",
        "REAL_TIKTOK_MESSAGE_WRITE_ENABLED",
        "REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED",
        "LLM_ENABLED",
        "AUTO_REPLY_ENABLED",
    ):
        assert f'{name}: "false"' in overlay
```

- [ ] **Step 2: Run the focused test and verify it fails because the overlay is absent**

Run:

```powershell
& 'E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe' -m pytest tests/test_real_runtime_config.py::test_rootless_staging_overlay_is_loopback_only_and_fail_closed -q
```

Expected: FAIL with `FileNotFoundError`.

- [ ] **Step 3: Create the minimal overlay**

```yaml
services:
  backend:
    environment:
      APP_ENV: "staging"
      REAL_TIKTOK_READ_ENABLED: "false"
      REAL_TIKTOK_WEBHOOK_ENABLED: "false"
      REAL_TIKTOK_MESSAGE_WRITE_ENABLED: "false"
      REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED: "false"
      LLM_ENABLED: "false"
      AUTO_REPLY_ENABLED: "false"
  worker:
    environment:
      APP_ENV: "staging"
      REAL_TIKTOK_READ_ENABLED: "false"
      REAL_TIKTOK_WEBHOOK_ENABLED: "false"
      REAL_TIKTOK_MESSAGE_WRITE_ENABLED: "false"
      REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED: "false"
      LLM_ENABLED: "false"
      AUTO_REPLY_ENABLED: "false"
  jobs:
    environment:
      APP_ENV: "staging"
      LLM_ENABLED: "false"
      AUTO_REPLY_ENABLED: "false"
  agent-worker:
    environment:
      APP_ENV: "staging"
      LLM_ENABLED: "false"
      AUTO_REPLY_ENABLED: "false"
  proxy:
    ports: !override
      - "127.0.0.1:10080:80"
      - "127.0.0.1:10443:443"
```

Also pin `LLM_LIVE_EVAL`, `AI_TRANSLATION_ENABLED`, `AI_MARKETING_ENABLED` and
`ALLOW_MOCK_PLATFORM_ADAPTERS` to `"false"` in every service that can consume them. Do not change
`docker-compose.prod.yml`.

- [ ] **Step 4: Validate the overlay statically and with Docker Compose**

Run:

```powershell
& 'E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe' -m pytest tests/test_real_runtime_config.py -q
& 'E:\soft\DockerDesktop\resources\bin\docker.exe' compose --project-name crm-staging --env-file 'CRM智能聊天系统/.env.example' -f 'CRM智能聊天系统/docker-compose.yml' -f 'CRM智能聊天系统/docker-compose.prod.yml' -f 'CRM智能聊天系统/docker-compose.rootless-staging.yml' config --services
```

Expected: pytest PASS and Compose prints only service names without exposing expanded environment values.

- [ ] **Step 5: Commit the overlay**

```powershell
git add -- 'CRM智能聊天系统/docker-compose.rootless-staging.yml' 'CRM智能聊天系统/backend/tests/test_real_runtime_config.py'
git commit -m "build: add rootless staging compose overlay"
```

---

### Task 3: Enforce Rootless Runtime in Staging Gate Scripts

**Files:**
- Modify: `CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1:4-31,333-443`
- Modify: `CRM智能聊天系统/scripts/Invoke-StagingRollbackDrill.ps1:4-43,340-466`
- Modify: `CRM智能聊天系统/backend/tests/test_production_gate_scripts.py:78-145,730-970`

**Interfaces:**
- Consumes: mandatory `-DockerHost unix:///run/user/<uid>/docker.sock` and the repository-fixed overlay.
- Produces: Compose calls with `--project-name crm-staging`, three Compose files, restored process environment, and low-sensitive evidence fields.

- [ ] **Step 1: Update the fixture and invocations, then add failing Rootless safety tests**

Change the test fixture public values to:

```python
"CORS_ORIGINS=https://staging.hophorsefit.com",
"PUBLIC_BASE_URL=https://staging.hophorsefit.com",
"PUBLIC_API_BASE_URL=https://staging.hophorsefit.com/v1",
"TIKTOK_OAUTH_REDIRECT_URI=https://staging.hophorsefit.com/v1/integrations/tiktok/oauth/callback",
```

Add `-DockerHost`, `unix:///run/user/1004/docker.sock` to every valid script invocation and add:

```python
@pytest.mark.parametrize("docker_host", ["tcp://127.0.0.1:2375", "unix:///var/run/docker.sock", ""])
def test_staging_gates_reject_non_rootless_docker_hosts(
    docker_host: str,
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment", "staging",
        "-EnvFile", str(staging_env_file),
        "-BackendImage", BACKEND_IMAGE,
        "-FrontendImage", FRONTEND_IMAGE,
        "-RetrievalModelImage", RETRIEVAL_MODEL_IMAGE,
        "-BaseUrl", "https://staging.hophorsefit.com",
        "-EvidenceFile", str(tmp_path / "evidence.json"),
        "-ConfirmTarget", "staging",
        "-DockerHost", docker_host,
        "-ValidateOnly",
    )
    assert result.returncode != 0
    assert "rootless docker host" in normalized_process_output(result)
```

Add a source-contract test asserting `--project-name`, `crm-staging`, and
`docker-compose.rootless-staging.yml` occur before `config`, `pull`, and `up`.

- [ ] **Step 2: Run the gate tests and verify the new cases fail**

Run:

```powershell
& 'E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe' -m pytest tests/test_production_gate_scripts.py -q
```

Expected: FAIL because neither script accepts or validates `-DockerHost` yet.

- [ ] **Step 3: Implement the Rootless host and fixed overlay contract in both scripts**

Add the mandatory parameter:

```powershell
[Parameter(Mandatory = $true)]
[string]$DockerHost
```

Add and call:

```powershell
function Assert-RootlessDockerHost {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ($Value -notmatch '^unix:///run/user/[1-9][0-9]*/docker\.sock$') {
        throw "DockerHost must identify the crmdeploy rootless Docker host."
    }
}
```

Resolve only the repository-fixed overlay and add it to `$composeArguments`:

```powershell
$rootlessOverlay = Join-Path $projectRoot "docker-compose.rootless-staging.yml"
$composeArguments = @(
    "--project-name", "crm-staging",
    "--profile", "ai",
    "--env-file", (Resolve-Path -LiteralPath $EnvFile).Path,
    "-f", (Join-Path $projectRoot "docker-compose.yml"),
    "-f", (Join-Path $projectRoot "docker-compose.prod.yml"),
    "-f", (Resolve-Path -LiteralPath $rootlessOverlay).Path
)
```

Before resolving Docker, save the current process value, set `$env:DOCKER_HOST = $DockerHost`, and restore it
in `finally`. Extend merged Compose validation to require `APP_ENV=staging` for backend/worker/jobs/agent-worker
and proxy host bindings `127.0.0.1:10080` and `127.0.0.1:10443`. Add only these low-sensitive fields to JSON:

```powershell
compose_project = "crm-staging"
docker_transport = "rootless_unix_socket"
rootless_overlay_sha256 = (Get-FileHash -LiteralPath $rootlessOverlay -Algorithm SHA256).Hash.ToLowerInvariant()
```

Never write the full socket value or expanded environment configuration to evidence.

- [ ] **Step 4: Run all gate tests**

Run:

```powershell
& 'E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe' -m pytest tests/test_production_gate_scripts.py -q
```

Expected: all tests PASS, including WhatIf, unhealthy Compose, model path and secret sentinel cases.

- [ ] **Step 5: Commit the gate changes**

```powershell
git add -- 'CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1' 'CRM智能聊天系统/scripts/Invoke-StagingRollbackDrill.ps1' 'CRM智能聊天系统/backend/tests/test_production_gate_scripts.py'
git commit -m "build: enforce rootless staging gates"
```

---

### Task 4: Add Reproducible Host and Entry-Proxy Assets

**Files:**
- Create: `CRM智能聊天系统/deploy/staging/rootless/bootstrap-host.sh`
- Create: `CRM智能聊天系统/deploy/staging/rootless/install-entry-proxy.sh`
- Create: `CRM智能聊天系统/deploy/staging/rootless/systemd/crm-staging-http.socket`
- Create: `CRM智能聊天系统/deploy/staging/rootless/systemd/crm-staging-http.service`
- Create: `CRM智能聊天系统/deploy/staging/rootless/systemd/crm-staging-https.socket`
- Create: `CRM智能聊天系统/deploy/staging/rootless/systemd/crm-staging-https.service`
- Create: `CRM智能聊天系统/backend/tests/test_rootless_staging_assets.py`

**Interfaces:**
- Consumes: Ubuntu 26.04, existing user `crmdeploy`, `/usr/bin/dockerd-rootless-setuptool.sh`, systemd 259.
- Produces: a user Rootless daemon and reversible root-owned TCP forwarding units.

- [ ] **Step 1: Write failing asset-contract tests**

```python
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOTLESS_DIR = PROJECT_ROOT / "deploy" / "staging" / "rootless"
SYSTEMD_DIR = ROOTLESS_DIR / "systemd"


def test_bootstrap_never_reconfigures_system_docker() -> None:
    source = (ROOTLESS_DIR / "bootstrap-host.sh").read_text(encoding="utf-8")
    forbidden = ("daemon.json", "data-root", "systemctl restart docker", "usermod -aG docker")
    assert all(token not in source for token in forbidden)
    assert "apt-get install --no-install-recommends -y uidmap" in source
    assert "dockerd-rootless-setuptool.sh install --force" in source
    assert "loginctl enable-linger crmdeploy" in source


def test_entry_proxy_targets_loopback_high_ports() -> None:
    files = {path.name: path.read_text(encoding="utf-8") for path in SYSTEMD_DIR.iterdir()}
    assert "ListenStream=80" in files["crm-staging-http.socket"]
    assert "127.0.0.1:10080" in files["crm-staging-http.service"]
    assert "ListenStream=443" in files["crm-staging-https.socket"]
    assert "127.0.0.1:10443" in files["crm-staging-https.service"]
    assert all("/usr/lib/systemd/systemd-socket-proxyd" in text for name, text in files.items() if name.endswith(".service"))
```

- [ ] **Step 2: Run the tests and verify they fail because assets are absent**

Run:

```powershell
& 'E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe' -m pytest tests/test_rootless_staging_assets.py -q
```

Expected: FAIL with missing files.

- [ ] **Step 3: Implement a fail-safe Rootless bootstrap**

The script must start with:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
[[ $(id -u) -eq 0 ]] || { echo "bootstrap-host.sh must run as root" >&2; exit 1; }
[[ $(. /etc/os-release; printf '%s' "$ID") == ubuntu ]] || { echo "Ubuntu is required" >&2; exit 1; }
[[ $(getent passwd crmdeploy | cut -d: -f6) == /home/crmdeploy ]] || { echo "Unexpected crmdeploy home" >&2; exit 1; }
root_free_kb=$(df --output=avail / | tail -1 | tr -d ' ')
(( root_free_kb >= 1572864 )) || { echo "Root filesystem requires at least 1.5 GiB free" >&2; exit 1; }
```

Record `docker ps --no-trunc --format '{{json .}}'` and `df -B1 / /home` under
`/home/crmdeploy/evidence/host-baseline-before/`, then install only `uidmap`:

```bash
apt-get update
apt-get install --no-install-recommends -y uidmap
loginctl enable-linger crmdeploy
systemctl start user@1004.service
runuser -u crmdeploy -- env HOME=/home/crmdeploy XDG_RUNTIME_DIR=/run/user/1004 \
  /usr/bin/dockerd-rootless-setuptool.sh install --force
runuser -u crmdeploy -- env HOME=/home/crmdeploy XDG_RUNTIME_DIR=/run/user/1004 \
  systemctl --user enable --now docker.service
```

Finish by verifying the Rootless socket, `docker info` security options/data root, and an unchanged sorted
system-container snapshot. Exit non-zero if any pre-existing container ID or start timestamp changed.

- [ ] **Step 4: Implement systemd socket proxy units and installer**

Use this service shape for each port:

```ini
[Unit]
Description=CRM staging HTTP socket proxy
After=network-online.target

[Service]
ExecStart=/usr/lib/systemd/systemd-socket-proxyd 127.0.0.1:10080
PrivateTmp=yes
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
```

The root installer must refuse installation if `80/443` are held by a process other than the exact
`crm-staging-http.socket`/`crm-staging-https.socket` units. It copies only the four exact units, runs
`systemctl daemon-reload`, enables both sockets, and records `systemctl status` plus `ss -lntp` in the evidence
directory. Services remain socket-activated.

- [ ] **Step 5: Validate Python contracts and Bash syntax**

Run locally:

```powershell
& 'E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe' -m pytest tests/test_rootless_staging_assets.py -q
```

Run on the Ubuntu target before installation:

```bash
bash -n bootstrap-host.sh
bash -n install-entry-proxy.sh
```

Expected: all checks PASS.

- [ ] **Step 6: Commit the host assets**

```powershell
git add -- 'CRM智能聊天系统/deploy/staging/rootless' 'CRM智能聊天系统/backend/tests/test_rootless_staging_assets.py'
git commit -m "build: add rootless staging host bootstrap"
```

---

### Task 5: Add Pinned Runner Toolchain and Rootless Workflow Wiring

**Files:**
- Create: `CRM智能聊天系统/deploy/staging/rootless/toolchain-manifest.json`
- Create: `CRM智能聊天系统/deploy/staging/rootless/install-runner.sh`
- Create: `CRM智能聊天系统/deploy/staging/rootless/systemd/user/crm-staging-runner.service`
- Modify: `.github/workflows/staging-gates.yml:75-133`
- Modify: `CRM智能聊天系统/backend/tests/test_rootless_staging_assets.py`
- Modify: `CRM智能聊天系统/backend/tests/test_production_gate_scripts.py`

**Interfaces:**
- Consumes: one-hour GitHub runner registration token via stdin and official release archives.
- Produces: `/home/crmdeploy/runner`, `/home/crmdeploy/tools/powershell`, user service `crm-staging-runner`, and workflow `-DockerHost` input.

- [ ] **Step 1: Add failing manifest, service and workflow tests**

```python
def test_toolchain_manifest_pins_official_linux_x64_archives() -> None:
    manifest = json.loads((ROOTLESS_DIR / "toolchain-manifest.json").read_text(encoding="utf-8"))
    assert manifest["actions_runner"]["version"] == "2.336.0"
    assert manifest["actions_runner"]["sha256"] == "04cf0be1aff4c3ec3554466c39124ca250e3effd8873bb7e8d68535aa9505d5d"
    assert manifest["powershell"]["version"] == "7.6.5"
    assert manifest["powershell"]["sha256"] == "b34ab3b19acac1d3d4d0d3cfdb02acf62f457b0b6a962ff008132033f7566844"


def test_runner_service_uses_rootless_socket_and_home_toolchain() -> None:
    unit = (SYSTEMD_DIR / "user" / "crm-staging-runner.service").read_text(encoding="utf-8")
    assert "User=" not in unit
    assert "DOCKER_HOST=unix:///run/user/1004/docker.sock" in unit
    assert "/home/crmdeploy/tools/powershell" in unit
    assert "ExecStart=/home/crmdeploy/runner/run.sh" in unit
```

Add a workflow source test requiring `id -u`, `unix:///run/user/`, `-DockerHost`, and an exact
`https://staging.hophorsefit.com` base URL guard.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
& 'E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe' -m pytest tests/test_rootless_staging_assets.py tests/test_production_gate_scripts.py -q
```

Expected: FAIL because the manifest, installer, unit and workflow wiring do not exist.

- [ ] **Step 3: Add exact official release metadata**

```json
{
  "schema_version": 1,
  "platform": "linux-x64",
  "actions_runner": {
    "version": "2.336.0",
    "url": "https://github.com/actions/runner/releases/download/v2.336.0/actions-runner-linux-x64-2.336.0.tar.gz",
    "sha256": "04cf0be1aff4c3ec3554466c39124ca250e3effd8873bb7e8d68535aa9505d5d"
  },
  "powershell": {
    "version": "7.6.5",
    "url": "https://github.com/PowerShell/PowerShell/releases/download/v7.6.5/powershell-7.6.5-linux-x64.tar.gz",
    "sha256": "b34ab3b19acac1d3d4d0d3cfdb02acf62f457b0b6a962ff008132033f7566844"
  }
}
```

- [ ] **Step 4: Implement the non-root runner installer**

The script must require `id -un == crmdeploy`, `umask 077`, read the registration token silently from stdin,
download to `/home/crmdeploy/.cache/crm-toolchain`, verify `sha256sum -c`, extract only after verification, and run:

```bash
./config.sh --unattended --url https://github.com/CP11-gh/CRM \
  --token "$runner_token" --name crm-staging-192-168-110-210 \
  --labels crm-staging --work /home/crmdeploy/runner/_work --replace
```

Clear `runner_token` immediately after configuration. Install the user unit under
`/home/crmdeploy/.config/systemd/user/`, then run `systemctl --user daemon-reload` and enable the service.
The script must never echo the token or use `set -x`.

- [ ] **Step 5: Wire the workflow to the current runner UID**

Before building `$common`, add:

```powershell
$runnerUid = (& id -u).Trim()
if ($LASTEXITCODE -ne 0 -or $runnerUid -notmatch '^[1-9][0-9]*$') {
  throw "Unable to resolve the self-hosted runner UID"
}
$dockerHost = "unix:///run/user/$runnerUid/docker.sock"
```

Set `$common["DockerHost"] = $dockerHost`, and require
`CRM_STAGING_BASE_URL == "https://staging.hophorsefit.com"`. Keep GHCR login on the short-lived
`${{ secrets.GITHUB_TOKEN }}` with only `contents: read` and `packages: read`.

- [ ] **Step 6: Run tests**

Run:

```powershell
& 'E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe' -m pytest tests/test_rootless_staging_assets.py tests/test_production_gate_scripts.py -q
```

Expected: all tests PASS.

- [ ] **Step 7: Commit runner and workflow changes**

```powershell
git add -- '.github/workflows/staging-gates.yml' 'CRM智能聊天系统/deploy/staging/rootless' 'CRM智能聊天系统/backend/tests/test_rootless_staging_assets.py' 'CRM智能聊天系统/backend/tests/test_production_gate_scripts.py'
git commit -m "ci: connect staging gates to rootless runner"
```

---

### Task 6: Synchronize Architecture, Runbook, and Traceability Documents

**Files:**
- Create: `CRM智能聊天系统/deploy/staging/rootless/README.md`
- Create: `架构师/ADR-007-INFRA-Rootless-Staging部署边界-v1.0.md`
- Modify: `CRM智能聊天系统/.env.example:108-116,196-204`
- Modify: `CRM智能聊天系统/deploy/production/README.md`
- Modify: `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md:32-56`
- Modify: `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md:12-48`
- Create: `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-Rootless-Staging运行面-综合测试-007.md`
- Create: `共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-Rootless-Staging部署-001.md`
- Modify: `共享记忆文档/测试报告索引.md`
- Modify: `共享记忆文档/实施记录索引.md`

**Interfaces:**
- Consumes: verified code/tests from Tasks 1-5.
- Produces: one authoritative runbook, one ADR, one engineering report, one implementation record and updated indexes.

- [ ] **Step 1: Write the runbook with exact safe commands and stop conditions**

The runbook must include:

```text
DOCKER_HOST=unix:///run/user/1004/docker.sock
COMPOSE_PROJECT_NAME=crm-staging
CRM_STAGING_ENV_FILE=/home/crmdeploy/config/crm-staging.env
CRM_STAGING_BASE_URL=https://staging.hophorsefit.com
```

It must explicitly separate `基础运行面就绪`, `失败关闭部署通过`, `G1～G6 真实门禁通过`, and
`production 放行`; none implies the next. Include exact uninstall/stop commands for the four CRM systemd
units but state that data deletion requires a separate explicit approval.

- [ ] **Step 2: Record the architecture decision**

ADR-007 must state:

```text
staging temporarily uses Rootless Docker on /home;
production runtime remains undecided;
system Docker and company containers are out of scope;
staging uses a dedicated domain and environment-specific exact OAuth callback;
the only public ingress is systemd socket proxy on 80/443;
```

Update ADR-004 so its fixed-address table contains separate staging and production rows without changing the
production URL.

- [ ] **Step 3: Update example configuration and production guide**

Add commented staging examples for `PUBLIC_BASE_URL`, `PUBLIC_API_BASE_URL`, `CORS_ORIGINS` and
`TIKTOK_OAUTH_REDIRECT_URI`. Keep all secret example values empty or obviously non-secret, and keep the three
production image references tied to the machine-readable release manifest.

- [ ] **Step 4: Create engineering evidence documents without premature claims**

The test report must list local test commands, exact pass/fail counts, pending live-host checks, and state
`独立测试结论：待测试工程师复核`. The implementation record must contain Phase, task number, responsible
Agent, collaborators, files, commits, validation, server changes and residual risks per
`共享记忆文档/实施记录文档规范.md`.

- [ ] **Step 5: Validate documentation consistency**

Run:

```powershell
git grep -n 'www.hophorsefit.com/v1/integrations/tiktok/oauth/callback'
git grep -n 'staging.hophorsefit.com/v1/integrations/tiktok/oauth/callback'
git diff --check
```

Expected: production references remain; staging references appear only in staging/configuration context; no
whitespace errors.

- [ ] **Step 6: Commit documentation and records**

```powershell
git add -- 'CRM智能聊天系统/.env.example' 'CRM智能聊天系统/deploy' '架构师' '测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-Rootless-Staging运行面-综合测试-007.md' '共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-Rootless-Staging部署-001.md' '共享记忆文档/测试报告索引.md' '共享记忆文档/实施记录索引.md'
git commit -m "docs: document rootless staging operations"
```

---

### Task 7: Verify and Merge the Repository Implementation

**Files:**
- Verify all files changed by Tasks 1-6.
- No new files unless verification exposes a defect.

**Interfaces:**
- Consumes: complete feature branch.
- Produces: reviewed main commit and published candidate images.

- [ ] **Step 1: Run the focused backend suites**

Run:

```powershell
& 'E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe' -m pytest tests/test_real_runtime_config.py tests/test_tiktok_oauth.py tests/test_production_gate_scripts.py tests/test_rootless_staging_assets.py -q
```

Expected: all tests PASS.

- [ ] **Step 2: Run the full backend test suite**

Run:

```powershell
& 'E:\develop\CRM智能聊天系统\CRM智能聊天系统\backend\.venv\Scripts\python.exe' -m pytest -q
```

Expected: all tests PASS with zero failures.

- [ ] **Step 3: Run repository hygiene checks**

Run:

```powershell
git diff --check main...HEAD
git status --short --branch
git log --oneline main..HEAD
```

Expected: no whitespace errors, no untracked secrets/weights, and only scoped commits.

- [ ] **Step 4: Request code review and fix verified findings**

Invoke `superpowers:requesting-code-review`. Review must cover callback isolation, Compose port exposure,
Docker socket handling, secret output, shell privilege boundaries, systemd hardening and existing-container
protection. Apply only reproduced findings and rerun Steps 1-3.

- [ ] **Step 5: Push and open the engineering PR**

```powershell
git push -u origin feature/rootless-staging
gh pr create --repo CP11-gh/CRM --base main --head feature/rootless-staging --title "build: add rootless staging deployment" --body-file '.github/PULL_REQUEST_TEMPLATE.md'
```

Populate the PR body with actual scope, test counts, risk, rollback and the statement `production_release=false`.

- [ ] **Step 6: Complete CI, human review and squash merge**

Run:

```powershell
gh pr checks --repo CP11-gh/CRM --watch
gh pr view --repo CP11-gh/CRM --json reviewDecision,mergeStateStatus,statusCheckRollup
gh pr merge --repo CP11-gh/CRM --squash --delete-branch
```

Expected: required checks succeed, human review is recorded, merge is squash, short branch is deleted.

- [ ] **Step 7: Publish immutable images for the merged main commit**

Read the merged full SHA from GitHub, dispatch `.github/workflows/publish-images.yml` with that exact SHA, wait
for completion, download the low-sensitive digest artifact, and verify all three references match
`repository@sha256:<64-hex>`. Do not use `latest`.

---

### Task 8: Provision Rootless Docker Without Touching Company Containers

**Files:**
- Execute: merged `CRM智能聊天系统/deploy/staging/rootless/bootstrap-host.sh`
- Evidence target: `/home/crmdeploy/evidence/host-baseline-*`

**Interfaces:**
- Consumes: root SSH access and merged bootstrap asset.
- Produces: active Rootless Docker at `/run/user/1004/docker.sock` with data under `/home`.

- [ ] **Step 1: Capture an external protection baseline**

Over SSH as root, record to `/home/crmdeploy/evidence/host-baseline-before/`:

```bash
docker ps --no-trunc --format '{{json .}}'
docker info --format '{{json .DockerRootDir}}'
df -B1 / /home
ss -lntp
```

Expected: system Docker root remains `/var/lib/docker`, company containers are running, and ports `80/443` are
free.

- [ ] **Step 2: Transfer and syntax-check the merged bootstrap assets**

Copy only `deploy/staging/rootless` to `/home/crmdeploy/src/rootless-staging-bootstrap`, set ownership to
`crmdeploy:crmdeploy`, then run:

```bash
bash -n /home/crmdeploy/src/rootless-staging-bootstrap/bootstrap-host.sh
bash -n /home/crmdeploy/src/rootless-staging-bootstrap/install-entry-proxy.sh
bash -n /home/crmdeploy/src/rootless-staging-bootstrap/install-runner.sh
```

Expected: all commands exit 0.

- [ ] **Step 3: Execute the root bootstrap**

Run as root:

```bash
/home/crmdeploy/src/rootless-staging-bootstrap/bootstrap-host.sh
```

Expected: only `uidmap` is installed on the root filesystem; Rootless Docker starts under `crmdeploy`.

- [ ] **Step 4: Verify Rootless isolation**

Run:

```bash
runuser -u crmdeploy -- env HOME=/home/crmdeploy XDG_RUNTIME_DIR=/run/user/1004 DOCKER_HOST=unix:///run/user/1004/docker.sock docker info
runuser -u crmdeploy -- env HOME=/home/crmdeploy XDG_RUNTIME_DIR=/run/user/1004 systemctl --user is-enabled docker.service
runuser -u crmdeploy -- env HOME=/home/crmdeploy XDG_RUNTIME_DIR=/run/user/1004 systemctl --user is-active docker.service
```

Expected: security options contain `rootless`, Docker root is under `/home/crmdeploy`, and the user service is
enabled/active.

- [ ] **Step 5: Compare the company-container protection baseline**

Repeat the system Docker snapshot and compare sorted container IDs, names, image IDs and `RunningFor`/start
timestamps. Stop immediately if any existing container changed; do not attempt automatic repair.

---

### Task 9: Install and Register the Self-Hosted Runner Securely

**Files:**
- Execute: merged `CRM智能聊天系统/deploy/staging/rootless/install-runner.sh`
- Evidence target: `/home/crmdeploy/evidence/runner-install/`

**Interfaces:**
- Consumes: pinned toolchain manifest and a one-hour GitHub registration token.
- Produces: online runner `crm-staging-192-168-110-210` with label `crm-staging`.

- [ ] **Step 1: Verify the repository authorizes a self-hosted runner**

Run locally:

```powershell
gh api repos/CP11-gh/CRM/actions/runners --jq '.total_count'
```

Expected: command succeeds with repository admin permission. If it returns 403, stop and request repository
administrator action; do not create a PAT workaround.

- [ ] **Step 2: Generate a short-lived registration token in memory and pipe it to the installer**

Use a local PowerShell variable without printing it:

```powershell
$runnerToken = gh api -X POST repos/CP11-gh/CRM/actions/runners/registration-token --jq '.token'
if ([string]::IsNullOrWhiteSpace($runnerToken)) { throw 'Runner registration token was not returned' }
$runnerToken | ssh -i $env:CRM_STAGING_SSH_KEY crmdeploy@192.168.110.210 '/home/crmdeploy/src/rootless-staging-bootstrap/install-runner.sh'
$runnerToken = $null
```

`CRM_STAGING_SSH_KEY` must point to the protected temporary copy of the provided key; delete that temporary
copy after the SSH command. The token must not be written to disk or command output.

- [ ] **Step 3: Verify toolchain hashes and versions on the server**

Run as `crmdeploy`:

```bash
/home/crmdeploy/tools/powershell/pwsh --version
/home/crmdeploy/runner/bin/Runner.Listener --version
systemctl --user is-active crm-staging-runner.service
```

Expected: PowerShell `7.6.5`, runner `2.336.0` or a GitHub-performed authenticated update, service active.

- [ ] **Step 4: Verify GitHub sees the runner online**

Run locally:

```powershell
gh api repos/CP11-gh/CRM/actions/runners --jq '.runners[] | select(.name=="crm-staging-192-168-110-210") | {name,status,busy,labels:[.labels[].name]}'
```

Expected: `status=online`, `busy=false`, and label `crm-staging` present.

---

### Task 10: Satisfy DNS, TLS, Model and Secret Preconditions

**Files:**
- Server-only: `/home/crmdeploy/config/crm-staging.env`
- Server-only: `/home/crmdeploy/assets/models/`
- Server-only: `/home/crmdeploy/secrets/tls/staging.hophorsefit.com/`

**Interfaces:**
- Consumes: user-controlled DNS/TLS/TikTok/DeepSeek inputs and six approved BGE files.
- Produces: repository-external inputs accepted by the staging gate.

- [ ] **Step 1: Verify DNS and public routing**

The user must create the A record `staging.hophorsefit.com → 183.158.225.78`. Then run from a network outside
the server LAN:

```powershell
Resolve-DnsName staging.hophorsefit.com -Type A
Test-NetConnection staging.hophorsefit.com -Port 80
Test-NetConnection staging.hophorsefit.com -Port 443
```

Expected: the A record returns `183.158.225.78` and both TCP ports are reachable. If not, stop before TikTok
configuration.

- [ ] **Step 2: Receive and validate a publicly trusted TLS certificate outside Git**

Pause and ask the domain administrator to issue the certificate through the company's approved CA/ACME process
and securely place two regular files at the exact paths below. Certificate issuance is intentionally not
automated by this repository because DNS account control and CA account ownership are external security
boundaries.

```text
/home/crmdeploy/secrets/tls/staging.hophorsefit.com/fullchain.pem
/home/crmdeploy/secrets/tls/staging.hophorsefit.com/privkey.pem
```

As root, set the exact ownership and modes, then verify without printing the private key:

```bash
chown root:crmdeploy /home/crmdeploy/secrets/tls/staging.hophorsefit.com
chown root:crmdeploy /home/crmdeploy/secrets/tls/staging.hophorsefit.com/fullchain.pem
chown root:crmdeploy /home/crmdeploy/secrets/tls/staging.hophorsefit.com/privkey.pem
chmod 0750 /home/crmdeploy/secrets/tls/staging.hophorsefit.com
chmod 0640 /home/crmdeploy/secrets/tls/staging.hophorsefit.com/fullchain.pem
chmod 0640 /home/crmdeploy/secrets/tls/staging.hophorsefit.com/privkey.pem
test ! -L /home/crmdeploy/secrets/tls/staging.hophorsefit.com/fullchain.pem
test ! -L /home/crmdeploy/secrets/tls/staging.hophorsefit.com/privkey.pem
```

Verify the public certificate with:

```bash
openssl x509 -in /home/crmdeploy/secrets/tls/staging.hophorsefit.com/fullchain.pem -noout -subject -issuer -dates -ext subjectAltName
```

Expected: SAN contains exactly or includes `DNS:staging.hophorsefit.com`, certificate is not expired, and
`crmdeploy` can read but not modify the private key.

- [ ] **Step 3: Validate and transfer the six BGE files**

Transfer the six regular BGE files to `/home/crmdeploy/assets/models` and reject symlinks, including parent
path components. The current `CRM智能聊天系统/deploy/models/model-manifest.json` authoritatively records only
the two weight SHA-256 values; verify those two first. It does not contain hashes for the four auxiliary
`config.json`/`tokenizer.json` files. Obtain their authoritative hashes from trusted sources and add them to
a reviewed machine-readable authority before starting any model container, unless an architect explicitly
approves a reduced requirement. Missing auxiliary hash evidence is a hard stop; do not claim that six hashes
match. This 2026-09-09 correction supersedes the original six-hash assumption; live verification is pending.

- [ ] **Step 4: Create the fail-closed staging environment file**

Create `/home/crmdeploy/config/crm-staging.env` with `umask 077`. Generate PostgreSQL, MinIO, JWT and internal
service secrets on the server with `openssl rand`; do not print them. Set the four exact staging public values,
the merged-main application RepoDigests, the fixed external image digests from
`release/images/mvp-production-gates.json`, TLS/model absolute paths, and every capability switch to `false`.
Leave TikTok and DeepSeek provider credentials empty until their individual gate windows.

- [ ] **Step 5: Configure GitHub staging Environment metadata**

Set only:

```text
Secret CRM_STAGING_ENV_FILE=/home/crmdeploy/config/crm-staging.env
Variable CRM_STAGING_BASE_URL=https://staging.hophorsefit.com
```

The secret is a path, not the file content. Confirm the Environment deployment branch remains restricted to
`main`.

- [ ] **Step 6: Run validate-only through GitHub Actions**

Dispatch `Staging production gates` with `operation=validate`, `confirm_target=staging`, and the three exact
merged-main RepoDigests. Expected: workflow PASS and a low-sensitive `validated` artifact; no containers are
changed.

---

### Task 11: Deploy Fail-Closed Staging and Prove Rollback

**Files:**
- Execute: merged staging workflow and scripts.
- Evidence target: GitHub artifact plus `/home/crmdeploy/evidence/`.

**Interfaces:**
- Consumes: all Task 10 prerequisites and current/previous immutable image triples.
- Produces: healthy fail-closed staging deployment, backup/restore evidence and a real image rollback result.

- [ ] **Step 1: Install the public entry proxy**

Before the first deploy, install the socket entry as root; backend readiness on
`127.0.0.1:10080/10443` is not a prerequisite for this installation:

```bash
bash /home/crmdeploy/src/rootless-staging-bootstrap/install-entry-proxy.sh
```

At this stage verify only systemd listening/ownership of public `80/443` and the configured forwarding targets
`127.0.0.1:10080/10443`; listening does not prove backend readiness or forwarding success. Company containers
must remain unchanged; any difference is a hard stop, not authorization to repair them. After deploy succeeds,
Step 3 proves actual connections/public health and repeats the installer to verify activated-socket idempotency.

- [ ] **Step 2: Deploy with all capabilities forced off**

Dispatch `operation=deploy` with the merged-main RepoDigests and `confirm_target=staging`. Expected: workflow
PASS, Compose project `crm-staging`, no host build, all services running/healthy, and
`production_release=false` in evidence.

- [ ] **Step 3: Verify external HTTPS and secret-safe health**

Run:

```powershell
curl.exe --fail --proto '=https' https://staging.hophorsefit.com/healthz
curl.exe --fail --proto '=https' https://staging.hophorsefit.com/v1/health
curl.exe --fail --proto '=https' https://staging.hophorsefit.com/v1/health/ready
```

Expected: HTTP 2xx; responses contain no database URL, Redis URL, model path, token, secret or raw exception.

Establish actual connections to both public `80/443`, including the HTTPS checks above, then rerun the same
`bash /home/crmdeploy/src/rootless-staging-bootstrap/install-entry-proxy.sh`
as root. Verify `listening` → `running` activation, forwarding to the Rootless loopback targets and repeat-install
idempotency, while company containers remain unchanged. These are pending live checks, not results inferred
from the pre-deploy listeners.

- [ ] **Step 4: Prove capability fail-closed state**

Inspect only selected environment variable names/boolean values inside backend, worker, jobs and agent-worker.
Expected: Mock, all TikTok real switches, LLM, live eval, translation, marketing and auto reply are all `false`.
Do not dump complete container environments.

- [ ] **Step 5: Run PostgreSQL and MinIO backup/restore in staging**

Use the existing backup/restore scripts with the Rootless socket and `/home/crmdeploy/backups`. Restore into an
isolated staging verification target, confirm Alembic head `023_marketing_review_idempotency`, object counts and
checksums, then remove only the temporary verification target after explicit path validation.

- [ ] **Step 6: Execute the immutable image rollback drill**

Use the merged-main images as candidate. Require a reviewed previous backend/frontend/retrieval three-digest
set, each immutable and different from its candidate counterpart, compatible with the staging callback,
migration `023_marketing_review_idempotency` and the configuration. Without such a compatible set, the real
rollback is blocked. Historical `f7c0f9f9` references in `release/images/mvp-production-gates.json` support only
the www callback and are incompatible evidence, not an approved successful rollback target. Do not change
staging to the production domain or claim rollback passed to bypass this prerequisite.

Only after compatibility approval, dispatch `operation=rollback`. Expected order: disable capabilities,
deploy the approved previous digests and pass three health checks; then redeploy the merged-main candidate
with a separate `deploy` run. These outcomes remain pending actual execution.

- [ ] **Step 7: Reconfirm existing system Docker containers and disk isolation**

Compare the original system Docker snapshot again. Expected: company container IDs/start times unchanged,
`/var/lib/docker` has not gained CRM images/volumes, Rootless usage is under `/home`, and root filesystem retains
at least 1.5 GiB free.

---

### Task 12: Record Live Evidence and Define the Real-Gate Stop Point

**Files:**
- Modify: `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-Rootless-Staging运行面-综合测试-007.md`
- Modify: `共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-Rootless-Staging部署-001.md`
- Modify: `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md`
- Modify: `共享记忆文档/测试报告索引.md`
- Modify: `共享记忆文档/实施记录索引.md`

**Interfaces:**
- Consumes: low-sensitive live evidence from Tasks 8-11.
- Produces: a second GitHub Flow evidence PR and an explicit G1～G6 readiness boundary.

- [ ] **Step 1: Update documents with facts only**

Record exact timestamps, Git SHA, RepoDigests, overlay SHA-256, host OS, Rootless data root, container protection
comparison, health results, backup/restore result and rollback workflow run IDs. Do not include secrets, tokens,
full environment configuration, customer data or model weights.

- [ ] **Step 2: Preserve unresolved gates**

Mark only verified G0 sub-items complete. Keep G1/G2/G3 blocked until TikTok Partner Center and real store
testing, G4/G5 blocked until approved DeepSeek credentials/data-exit window, and G6 blocked until five actual
consecutive days reach 99.5% availability. Do not treat Rootless feasibility as v0.1 production release.

- [ ] **Step 3: Verify evidence redaction and consistency**

Run secret-pattern scanning over only the staged Markdown/JSON evidence, `git diff --check`, and the focused
test suite. Expected: no credential-shaped values, no `.env`, no model files and no unsupported pass claim.

- [ ] **Step 4: Create and merge the evidence PR**

Create a new `test/rootless-staging-evidence` branch from the updated `main`, commit with:

```powershell
git commit -m "test: record rootless staging deployment evidence"
```

Open a PR, wait for CI, complete human review, squash merge and delete the branch.

- [ ] **Step 5: Hand off the next gate sequence**

Request the user's approved real-store test window and secure placement of TikTok credentials before G1. After
G1 succeeds, proceed to G2 Webhook, then G3 single-operator manual message. Request DeepSeek approval/key before
G4/G5. Start a separate five-day monitoring run only after G0～G5 pass; final G6 evidence must cover five real
calendar days and 99.5% availability.

---

## Final Verification Checklist

- [ ] Engineering PR and live-evidence PR were squash merged through GitHub Flow.
- [ ] All backend tests pass from a clean merged-main checkout.
- [ ] `docker compose config --services` succeeds with the Rootless overlay and prints no expanded secrets.
- [ ] Existing company container IDs and start times are unchanged across host bootstrap and deployment.
- [ ] Rootless Docker reports `rootless`, uses `/home/crmdeploy`, and exposes no TCP Docker API.
- [ ] Public `80/443` are owned only by the CRM systemd socket proxy; high ports bind only to loopback.
- [ ] `staging.hophorsefit.com` resolves to `183.158.225.78` and presents a trusted matching certificate.
- [ ] All staging services are healthy using immutable RepoDigests; no application image was built on the host.
- [ ] Backup/restore and previous-image rollback completed with low-sensitive evidence.
- [ ] Initial capability state is entirely fail-closed.
- [ ] G1～G6 and production remain explicitly unapproved until their independent real evidence exists.
