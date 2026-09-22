# TikTok Fixed Egress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every staging TikTok server-side request fail closed through the stable public IP `38.55.145.52`, while preserving the existing split-ingress tunnel and leaving production undeployed.

**Architecture:** Add a TikTok-only HTTPX client factory configured with `socks5h://tiktok-egress:1080`, a hardened Rootless Compose SSH dynamic-forward helper, and a separate least-privilege `crm-egress` account on `38.55.145.52`. Merge the implementation first so immutable images are published from the real `main` SHA, then deploy and close the task in a second evidence-only branch.

**Tech Stack:** Python 3.11, Pydantic Settings, HTTPX 0.28 with `socksio`, Docker Compose v2, Rootless Docker, OpenSSH, PowerShell 5.1+, pytest, Ruff, mypy, GitHub Actions/GHCR.

**Spec:** `docs/superpowers/specs/2026-09-21-tiktok-fixed-egress-design.md`

## Global Constraints

- `BASE_SHA=99800c3bfac29df31392a05344e7dcb9a2d34fb1`; implementation branch is `feature/tiktok-fixed-egress`; target is `origin/main`.
- The existing ingress path, `crm-tunnel` account, Nginx 80/443, loopback `18080 → 18081`, GitLab `10080/10443`, system Docker, data volumes and model assets are out of scope and must not change.
- Staging declares `TIKTOK_EGRESS_IP=38.55.145.52`; production gets the reusable contract only and remains undeployed.
- `REAL_TIKTOK_READ_ENABLED`, `REAL_TIKTOK_WEBHOOK_ENABLED`, `REAL_TIKTOK_MESSAGE_WRITE_ENABLED`, `REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED`, `LLM_ENABLED` and `AUTO_REPLY_ENABLED` remain `false` throughout infrastructure deployment.
- TikTok clients must use one explicit SOCKS5H transport with `trust_env=False`; failure must never fall back to a direct connection.
- The private egress key stays only in `/home/crmdeploy/secrets/tiktok-egress`, mode `0600`, owner UID/GID 1004; it never enters Git, an image, a log, a report, or another container.
- The public edge adds no proxy daemon or proxy listener. Existing SSHD may create only outbound connections allowed by `PermitOpen`.
- Server writes happen only after implementation is merged and immutable image evidence names the merged `main` SHA.
- The approved spec has a sequencing conflict: its live test requires an image published from merged `main`, while its merge boundary requires that live test first. Approval of this plan resolves that loop with two integrations: the behavior branch may merge only in `VERIFYING` with every real capability disabled; the merged-main image is then deployed and tested; a documentation/evidence-only branch records the result and is the merge that moves `MVP-EGRESS-001` to `DONE`. This is not a reuse of any prior gate exemption.
- All code changes use TDD. Every test is observed RED for the intended reason before production code is written.
- No server-side build, floating image, force push, history rewrite, destructive Git, production deployment, real TikTok business call, or customer data operation is permitted.

## Review Focus

1. A `socks5://`, HTTP proxy, credential-bearing proxy URL, path/query/fragment, or non-fixed staging/production service address must fail Settings validation; Task 1 tests each class.
2. A missing egress proxy must not silently create a direct HTTPX client even if a caller instantiates a TikTok client outside the normal route; Task 1 tests factory refusal and Task 2 tests all three clients use the factory.
3. A stopped or unhealthy helper must not let Compose start TikTok-capable application services or let the verification command succeed; Tasks 3 and 5 test dependency ordering and failure propagation, and Task 7 exercises it live.
4. A changed edge account, extra authorized key, remote-forward permission, extra destination, or invalid SSHD config must stop installation without overwriting the unknown state; Task 4 tests the installer contract and Task 7 verifies the effective live policy.
5. Rolling application images back to a pre-egress backend must not replace the helper with an image that lacks OpenSSH; Task 5 pins `TIKTOK_EGRESS_IMAGE` to the reviewed candidate image while application services use previous digests.
6. The task must remain `VERIFYING` across the implementation merge, and the evidence-only branch must contain no behavior change; Tasks 6–8 enforce and review this two-phase boundary.

---

### Task 1: Register the task and add the fail-closed proxy contract

**Files:**
- Modify: `docs/tasks/TASKS.md`
- Modify: `src/backend/app/shared/config/settings.py`
- Create: `src/backend/app/integrations/tiktok_http.py`
- Modify: `src/tests/backend/runtime_infrastructure/test_real_runtime_config.py`
- Create: `src/tests/backend/platform/test_tiktok_http.py`

**Interfaces:**
- Consumes: approved spec and existing `Settings.request_timeout_seconds`.
- Produces: `TIKTOK_EGRESS_PROXY_URL`, constant `TIKTOK_FIXED_EGRESS_PROXY_URL`, and `create_tiktok_http_client(settings: Settings) -> httpx.AsyncClient` for Task 2.

- [ ] **Step 1: Add `MVP-EGRESS-001` in `DOING` state before product code**

Add a P0 row after `MVP-STAGING-001` with branch `feature/tiktok-fixed-egress`, dependency `MVP-STAGING-001`, `BASE_SHA=99800c3bfac29df31392a05344e7dcb9a2d34fb1`, required RR, blank evidence fields, and the verifiable result “TikTok server-side traffic exits only through `38.55.145.52` and fails closed when the tunnel is unavailable.” Update `MVP-002` dependencies to `MVP-001, MVP-EGRESS-001`.

- [ ] **Step 2: Write failing Settings tests for every accepted and rejected proxy shape**

Extend the safe `production_settings` sample with:

```python
"TIKTOK_EGRESS_PROXY_URL": "socks5h://tiktok-egress:1080",
```

Add tests equivalent to:

```python
@pytest.mark.parametrize(
    "unsafe_proxy",
    [
        None,
        "socks5://tiktok-egress:1080",
        "http://tiktok-egress:1080",
        "socks5h://user:secret@tiktok-egress:1080",
        "socks5h://tiktok-egress:1080/path",
        "socks5h://tiktok-egress:1080?route=direct",
        "socks5h://tiktok-egress:1080#fragment",
        "socks5h://other-proxy:1080",
    ],
)
def test_real_tiktok_rejects_unsafe_egress_proxy(unsafe_proxy: str | None) -> None:
    with pytest.raises(ValidationError, match="TIKTOK_EGRESS_PROXY_URL"):
        production_settings(
            REAL_TIKTOK_READ_ENABLED=True,
            TIKTOK_APP_KEY="real-app-key",
            TIKTOK_SERVICE_ID="real-service-id",
            TIKTOK_APP_SECRET="unit-test-app-secret",
            TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-32-characters",
            TIKTOK_EGRESS_PROXY_URL=unsafe_proxy,
        )


def test_real_tiktok_accepts_fixed_socks5h_egress_proxy() -> None:
    settings = production_settings(
        REAL_TIKTOK_READ_ENABLED=True,
        TIKTOK_APP_KEY="real-app-key",
        TIKTOK_SERVICE_ID="real-service-id",
        TIKTOK_APP_SECRET="unit-test-app-secret",
        TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-32-characters",
    )
    assert settings.tiktok_egress_proxy_url == "socks5h://tiktok-egress:1080"
```

- [ ] **Step 3: Run the Settings tests and observe RED**

Run:

```powershell
Set-Location src/backend
uv run pytest ../tests/backend/runtime_infrastructure/test_real_runtime_config.py -q
```

Expected: failures show `TIKTOK_EGRESS_PROXY_URL` is unknown/unvalidated or unsafe values are accepted.

- [ ] **Step 4: Implement the Settings field and validator**

In `settings.py`, add:

```python
TIKTOK_FIXED_EGRESS_PROXY_URL = "socks5h://tiktok-egress:1080"

tiktok_egress_proxy_url: str | None = Field(default=None, validation_alias="TIKTOK_EGRESS_PROXY_URL")
```

When any real TikTok flag is enabled, call a validator that requires a URL, catches invalid ports, requires `socks5h`, a hostname and explicit port, rejects userinfo/path/query/fragment, and requires the constant above for `staging` and `production`.

- [ ] **Step 5: Re-run the Settings tests and observe GREEN**

Run the Step 3 command.

Expected: all tests in `test_real_runtime_config.py` pass.

- [ ] **Step 6: Write failing factory tests**

Create `test_tiktok_http.py` with a constructor capture and refusal test:

```python
def test_tiktok_http_client_uses_explicit_socks_and_ignores_proxy_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_async_client(**kwargs: object) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(tiktok_http.httpx, "AsyncClient", fake_async_client)
    settings = Settings(
        _env_file=None,
        APP_ENV="development",
        TIKTOK_EGRESS_PROXY_URL="socks5h://127.0.0.1:1080",
    )

    assert tiktok_http.create_tiktok_http_client(settings) is sentinel
    assert captured == {
        "timeout": settings.request_timeout_seconds,
        "proxy": "socks5h://127.0.0.1:1080",
        "trust_env": False,
    }


def test_tiktok_http_client_refuses_direct_fallback() -> None:
    with pytest.raises(AppError, match="固定出口"):
        tiktok_http.create_tiktok_http_client(Settings(_env_file=None))
```

- [ ] **Step 7: Run the factory tests and observe RED**

Run:

```powershell
Set-Location src/backend
uv run pytest ../tests/backend/platform/test_tiktok_http.py -q
```

Expected: collection fails because `app.integrations.tiktok_http` does not exist.

- [ ] **Step 8: Implement the minimal factory**

Create `tiktok_http.py`:

```python
"""TikTok 专用、失败关闭的固定出口 HTTP 客户端。"""

import httpx

from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError, ErrorCode


def create_tiktok_http_client(settings: Settings) -> httpx.AsyncClient:
    """构造只走显式 SOCKS5H 的客户端；缺失代理时禁止直连回退。"""
    proxy = settings.tiktok_egress_proxy_url
    if not proxy:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 固定出口尚未配置", 503)
    return httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        proxy=proxy,
        trust_env=False,
    )
```

- [ ] **Step 9: Run Task 1 tests**

Run:

```powershell
Set-Location src/backend
uv run pytest ../tests/backend/runtime_infrastructure/test_real_runtime_config.py ../tests/backend/platform/test_tiktok_http.py -q
```

Expected: both files pass with zero failures.

- [ ] **Step 10: Commit Task 1**

```powershell
git add docs/tasks/TASKS.md src/backend/app/shared/config/settings.py src/backend/app/integrations/tiktok_http.py src/tests/backend/runtime_infrastructure/test_real_runtime_config.py src/tests/backend/platform/test_tiktok_http.py
git commit -m "feat: require TikTok fixed egress proxy"
```

---

### Task 2: Route every TikTok client through the factory

**Files:**
- Modify: `src/backend/app/integrations/tiktok_oauth.py`
- Modify: `src/backend/app/integrations/tiktok_read.py`
- Modify: `src/backend/app/integrations/tiktok_write.py`
- Modify: `src/backend/pyproject.toml`
- Modify: `src/backend/uv.lock`
- Modify: `src/tests/backend/platform/test_tiktok_oauth.py`
- Modify: `src/tests/backend/platform/test_tiktok_read.py`
- Modify: `src/tests/backend/platform/test_tiktok_write.py`
- Modify: `src/tests/backend/platform/test_platform_adapters.py`
- Modify: `src/tests/backend/runtime_infrastructure/test_real_fs05_sse_runtime.py`

**Interfaces:**
- Consumes: `create_tiktok_http_client(settings)` from Task 1.
- Produces: OAuth, read and write clients with no direct default path; backend dependency includes `httpx[socks]`/`socksio`.

- [ ] **Step 1: Add a failing default-client test to each TikTok client test file**

For OAuth, read and write, add one test that monkeypatches the module-local `create_tiktok_http_client`, returns an `httpx.AsyncClient` using `MockTransport`, executes a normal operation without passing the injectable client, and asserts the factory was called exactly once with the same Settings object. Use platform responses already present in each test file so contract assertions remain real.

The write test must also add a failure case where the factory raises `httpx.ConnectError`; expected result is `status="unknown"` and exactly one attempted construction, proving there is no second direct send.

- [ ] **Step 2: Add `TIKTOK_EGRESS_PROXY_URL` to all real-capability test fixtures**

Use `socks5h://127.0.0.1:1080` for development-only fixtures and `socks5h://tiktok-egress:1080` for staging/production fixtures. Do not weaken the Settings validator to preserve old fixtures.

- [ ] **Step 3: Run the platform tests and observe RED**

Run:

```powershell
Set-Location src/backend
uv run pytest ../tests/backend/platform/test_tiktok_oauth.py ../tests/backend/platform/test_tiktok_read.py ../tests/backend/platform/test_tiktok_write.py ../tests/backend/platform/test_platform_adapters.py ../tests/backend/runtime_infrastructure/test_real_fs05_sse_runtime.py -q
```

Expected: the new tests fail because the modules still construct `httpx.AsyncClient` directly; existing real fixtures initially fail until the proxy value is added.

- [ ] **Step 4: Replace direct client construction**

Import the Task 1 factory in all three modules and replace each production branch:

```python
async with create_tiktok_http_client(self.settings) as client:
    response = await client.request(...)
```

Preserve the explicit `self.client` test injection branch exactly. Keep all existing retry, error mapping, signature and unknown-result behavior unchanged.

- [ ] **Step 5: Install the SOCKS dependency in the lockfile**

Change the dependency to:

```toml
"httpx[socks]>=0.27,<1.0",
```

Then run:

```powershell
Set-Location src/backend
uv lock
```

Expected: `uv.lock` contains `socksio`, and HTTPX remains within the existing `<1.0` bound.

- [ ] **Step 6: Re-run Task 2 tests**

Run the Step 3 command.

Expected: all named tests pass, including the no-fallback write case.

- [ ] **Step 7: Run lint and type checking for the backend**

```powershell
Set-Location src/backend
uv run ruff check app ../tests/backend/platform ../tests/backend/runtime_infrastructure/test_real_runtime_config.py ../tests/backend/runtime_infrastructure/test_real_fs05_sse_runtime.py
uv run mypy app
```

Expected: both commands exit 0.

- [ ] **Step 8: Commit Task 2**

```powershell
git add src/backend/app/integrations/tiktok_oauth.py src/backend/app/integrations/tiktok_read.py src/backend/app/integrations/tiktok_write.py src/backend/pyproject.toml src/backend/uv.lock src/tests/backend/platform src/tests/backend/runtime_infrastructure/test_real_fs05_sse_runtime.py
git commit -m "feat: route TikTok clients through fixed egress"
```

---

### Task 3: Add the hardened Rootless egress helper

**Files:**
- Modify: `src/docker/Dockerfile.backend`
- Create: `src/compose/docker-compose.tiktok-egress.yml`
- Modify: `src/config/.env.example`
- Modify: `src/tests/backend/runtime_infrastructure/test_real_runtime_config.py`
- Modify: `src/tests/frontend/contract/compose.test.mjs`

**Interfaces:**
- Consumes: fixed proxy URL from Task 1 and immutable backend image contract.
- Produces: `tiktok-egress` service, `tiktok-egress` network, `TIKTOK_EGRESS_IMAGE`, `TIKTOK_EGRESS_SECRET_DIR`, and application service dependencies used by Task 5.

- [ ] **Step 1: Write failing Compose and Dockerfile contract tests**

Add tests that read the new overlay and merged-service text and assert:

```python
assert "tiktok-egress:" in overlay
assert "${TIKTOK_EGRESS_IMAGE:?TIKTOK_EGRESS_IMAGE is required}" in overlay
assert "socks5h://tiktok-egress:1080" in overlay
assert "0.0.0.0:1080" in overlay
assert "ports:" not in compose_service_block(overlay, "tiktok-egress")
assert "read_only: true" in egress_block
assert "cap_drop:" in egress_block and "ALL" in egress_block
assert "no-new-privileges:true" in egress_block
assert "StrictHostKeyChecking=yes" in egress_block
assert "StrictHostKeyChecking=no" not in egress_block
assert "/run/secrets/tiktok-egress" in egress_block
```

Also assert the backend Dockerfile installs `openssh-client` before `USER crm`, uses `--no-install-recommends`, and removes `/var/lib/apt/lists/*`. Verify backend, worker and jobs join both `default` and `tiktok-egress`, depend on helper health, and receive only the non-secret proxy URL—not the key mount.

- [ ] **Step 2: Run the contract tests and observe RED**

Run:

```powershell
Set-Location src/backend
uv run pytest ../tests/backend/runtime_infrastructure/test_real_runtime_config.py -q
Set-Location ../frontend
npm test
```

Expected: backend and frontend contract tests fail because the overlay and OpenSSH package do not exist.

- [ ] **Step 3: Install OpenSSH client in the backend image**

Before creating the `crm` user, add one root layer:

```dockerfile
RUN apt-get update \
    && apt-get install --no-install-recommends -y openssh-client \
    && rm -rf /var/lib/apt/lists/*
```

Do not install an SSH server, supervisor, proxy daemon, curl, sudo or network debugging suite.

- [ ] **Step 4: Create `docker-compose.tiktok-egress.yml`**

Define `tiktok-egress` with the reviewed backend image alias, command-array SSH options, no ports, read-only rootfs, dropped capabilities, no-new-privileges, read-only secret bind, isolated network and socket health check. The command must include:

```yaml
command:
  - /usr/bin/ssh
  - -NT
  - -D
  - 0.0.0.0:1080
  - -o
  - BatchMode=yes
  - -o
  - ExitOnForwardFailure=yes
  - -o
  - IdentitiesOnly=yes
  - -o
  - StrictHostKeyChecking=yes
  - -o
  - UserKnownHostsFile=/run/secrets/tiktok-egress/known_hosts
  - -o
  - ServerAliveInterval=30
  - -o
  - ServerAliveCountMax=3
  - -i
  - /run/secrets/tiktok-egress/id_ed25519
  - crm-egress@38.55.145.52
```

Use `${TIKTOK_EGRESS_IMAGE:?TIKTOK_EGRESS_IMAGE is required}` rather than `${BACKEND_IMAGE}` so rollback can keep a known egress-capable helper image while application containers return to an older backend.

- [ ] **Step 5: Document the non-secret variables**

Add to `.env.example`:

```env
TIKTOK_EGRESS_IP=
TIKTOK_EGRESS_SECRET_DIR=
TIKTOK_EGRESS_IMAGE=
# TIKTOK_EGRESS_PROXY_URL is fixed by docker-compose.tiktok-egress.yml.
```

Keep example values empty; do not add key material or a production path as an active development default.

- [ ] **Step 6: Run Task 3 tests and Compose rendering**

Run the Step 2 tests, then render with non-secret test values:

```powershell
$env:TIKTOK_EGRESS_IMAGE='ghcr.io/cp11-gh/crm-backend@sha256:' + ('1' * 64)
$env:TIKTOK_EGRESS_SECRET_DIR=(Resolve-Path 'src/tests').Path
docker compose -f src/compose/docker-compose.yml -f src/compose/docker-compose.prod.yml -f src/compose/docker-compose.tiktok-egress.yml -f src/compose/docker-compose.rootless-staging.yml config --format json | Out-Null
```

Expected: tests pass and Compose exits 0 without publishing a helper port.

- [ ] **Step 7: Commit Task 3**

```powershell
git add src/docker/Dockerfile.backend src/compose/docker-compose.tiktok-egress.yml src/config/.env.example src/tests/backend/runtime_infrastructure/test_real_runtime_config.py src/tests/frontend/contract/compose.test.mjs
git commit -m "build: add hardened TikTok egress helper"
```

---

### Task 4: Add edge-account provisioning and an application-path verifier

**Files:**
- Create: `src/deploy/staging/rootless/install-public-egress-account.sh`
- Create: `src/backend/scripts/verify_tiktok_egress.py`
- Create: `src/tests/backend/runtime_infrastructure/test_tiktok_egress_runtime.py`
- Modify: `src/tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py`

**Interfaces:**
- Consumes: edge IP, allowed domains, fixed proxy URL and secret paths from Tasks 1–3.
- Produces: a fail-closed edge installer and JSON verifier consumed by Task 5 and the live run in Task 7.

- [ ] **Step 1: Write failing installer asset tests**

Extend the split-ingress asset tests to require all of these exact properties:

```python
for required in (
    "crm-egress",
    "/home/crm-egress",
    "AllowTcpForwarding local",
    "PermitOpen auth.tiktok-shops.com:443 open-api.tiktokglobalshop.com:443 checkip.amazonaws.com:443",
    "PermitListen none",
    "GatewayPorts no",
    "ForceCommand /usr/bin/false",
    "restrict,port-forwarding",
    'permitopen="auth.tiktok-shops.com:443"',
    'permitopen="open-api.tiktokglobalshop.com:443"',
    'permitopen="checkip.amazonaws.com:443"',
    "sshd -t",
    "systemctl reload ssh",
):
    assert required in installer
assert "systemctl restart ssh" not in installer
assert "crm-tunnel" not in installer
```

Also require the script to reject more than one public-key line, non-Ed25519 keys, an unknown existing authorized file, symlinks, sudo membership and duplicate/unknown SSHD Match configuration.

- [ ] **Step 2: Write failing verifier tests**

Create tests for a pure comparison helper and `main()` using a fake HTTPX client:

```python
@pytest.mark.parametrize("payload", ["", "not-an-ip", "38.55.145.52 extra"])
def test_parse_observed_egress_rejects_invalid_payload(payload: str) -> None:
    with pytest.raises(ValueError):
        parse_observed_egress("38.55.145.52", payload)


def test_parse_observed_egress_rejects_mismatch() -> None:
    with pytest.raises(ValueError, match="does not match"):
        parse_observed_egress("38.55.145.52", "122.234.23.242\n")


def test_parse_observed_egress_accepts_exact_ip() -> None:
    assert parse_observed_egress("38.55.145.52", "38.55.145.52\n") == "38.55.145.52"
```

The `main()` test must assert `proxy="socks5h://tiktok-egress:1080"`, `trust_env=False`, timeout is finite, and stdout is JSON containing only schema version, status and the observed/configured IP—never environment values or credentials.

- [ ] **Step 3: Run Task 4 tests and observe RED**

```powershell
Set-Location src/backend
uv run pytest ../tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py ../tests/backend/runtime_infrastructure/test_tiktok_egress_runtime.py -q
```

Expected: failures report missing installer and verifier modules.

- [ ] **Step 4: Implement the edge installer**

The script takes exactly one argument—the public-key file—runs only as root, uses a fixed PATH and umask, and performs this sequence:

1. Validate a single nonempty `ssh-ed25519` public key without printing it.
2. Inspect or create locked `crm-egress` with `/usr/sbin/nologin`, private home, no sudo and no extra groups.
3. Refuse symlinked home/`.ssh`/authorized_keys/config paths.
4. Install one authorized line containing `restrict,port-forwarding` and the three repeated `permitopen` options; refuse any differing existing line.
5. Install an exact `/etc/ssh/sshd_config.d/91-crm-egress.conf` Match block; refuse a differing existing file.
6. Run `/usr/sbin/sshd -t`; only on success run `systemctl reload ssh`.
7. Verify `sshd -T -C user=crm-egress,host=localhost,addr=192.168.110.210` yields public-key-only, no TTY/agent/X11, local-only forwarding, no permit-listen and the exact three permit-open destinations.

- [ ] **Step 5: Implement the verifier**

Use `ipaddress.ip_address`, a fixed URL `https://checkip.amazonaws.com`, `httpx.Client(proxy=..., trust_env=False, timeout=10)`, `raise_for_status()`, exact IP comparison, and JSON output. Missing variables, malformed output, request failure or mismatch must exit nonzero. Do not implement a direct retry.

- [ ] **Step 6: Re-run Task 4 tests**

Run the Step 3 command.

Expected: both files pass; POSIX behavioral tests may skip on Windows only where the existing suite already uses that rule.

- [ ] **Step 7: Commit Task 4**

```powershell
git add src/deploy/staging/rootless/install-public-egress-account.sh src/backend/scripts/verify_tiktok_egress.py src/tests/backend/runtime_infrastructure/test_tiktok_egress_runtime.py src/tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py
git commit -m "feat: provision and verify TikTok egress"
```

---

### Task 5: Integrate the egress overlay into staging deploy and rollback gates

**Files:**
- Modify: `src/scripts/Test-StagingProductionGates.ps1`
- Modify: `src/scripts/Invoke-StagingRollbackDrill.ps1`
- Modify: `src/tests/backend/runtime_infrastructure/test_production_gate_scripts.py`

**Interfaces:**
- Consumes: overlay and verifier from Tasks 3–4.
- Produces: fixed staging Compose order, helper image pinning, live egress verification before passed evidence, and rollback compatibility.

- [ ] **Step 1: Write failing preflight/deploy tests**

Extend fake environment files with an existing absolute `TIKTOK_EGRESS_SECRET_DIR`. Assert every Compose invocation uses files in this order:

```text
docker-compose.yml
docker-compose.prod.yml
docker-compose.tiktok-egress.yml
docker-compose.rootless-staging.yml
```

Assert merged config contains `tiktok-egress` with image equal to candidate backend, no ports, read-only root, exact secret mount, only the egress network, dropped capabilities and no-new-privileges. Assert deployment starts healthy `tiktok-egress` before backend/worker/jobs and runs:

```text
run --rm --no-deps backend python scripts/verify_tiktok_egress.py
```

before public health checks and before writing `status=passed`.

- [ ] **Step 2: Write failing mismatch and rollback tests**

Teach the fake Compose runtime to return nonzero for the verifier. Assert the gate returns nonzero and either writes no evidence or evidence whose status is not `passed`.

For rollback, assert:

- application services use the previous backend digest;
- `tiktok-egress` continues using the candidate backend digest through `TIKTOK_EGRESS_IMAGE`;
- all real capability flags are false before image switching;
- rollback evidence records both overlay hashes and never claims production release.

- [ ] **Step 3: Run gate tests and observe RED**

```powershell
Set-Location src/backend
uv run pytest ../tests/backend/runtime_infrastructure/test_production_gate_scripts.py -q
```

Expected: new assertions fail because the egress overlay, service and verifier command are absent.

- [ ] **Step 4: Update the deployment gate**

Add `TIKTOK_EGRESS_SECRET_DIR` to required non-secret environment variables and validate it is an existing absolute directory outside the Git checkout with no path reparse point. Add and hash the egress overlay, set `TIKTOK_EGRESS_IMAGE=$BackendImage`, include `tiktok-egress` in expected images and pulls, validate its merged security contract, start it with `--wait` before application services, run the verifier, parse its JSON and include this object in low-sensitive evidence:

```json
{
  "status": "passed",
  "configured_ip": "38.55.145.52",
  "observed_ip": "38.55.145.52"
}
```

Never include the proxy URL, key path contents, key fingerprint, environment file contents or TikTok credentials in evidence.

- [ ] **Step 5: Update rollback semantics**

Include the overlay in config validation and set `TIKTOK_EGRESS_IMAGE=$CandidateBackendImage` for the whole rollback. Do not attempt to run the helper from a previous backend digest that predates OpenSSH. Keep real capabilities false; if the helper is unhealthy, rollback may stop it and report failure, but must not enable direct TikTok access.

- [ ] **Step 6: Re-run gate tests**

Run the Step 3 command.

Expected: all staging preflight/deploy/rollback tests pass, including verifier failure and WhatIf behavior.

- [ ] **Step 7: Commit Task 5**

```powershell
git add src/scripts/Test-StagingProductionGates.ps1 src/scripts/Invoke-StagingRollbackDrill.ps1 src/tests/backend/runtime_infrastructure/test_production_gate_scripts.py
git commit -m "ci: gate staging on verified TikTok egress"
```

---

### Task 6: Synchronize operations docs and verify the implementation branch

**Files:**
- Modify: `docs/superpowers/specs/2026-09-21-tiktok-fixed-egress-design.md`
- Modify: `docs/architecture/SYSTEM.md`
- Modify: `docs/operations/DEPLOYMENT.md`
- Modify: `docs/operations/RELEASE-GATES.md`
- Modify: `src/deploy/staging/rootless/README.md`
- Modify: `src/deploy/production/README.md`
- Modify: `README.md`
- Modify: `docs/memory/PROJECT-STATE.md`
- Modify: `docs/tasks/TASKS.md`
- Create: `docs/records/implementation/IR-MVP-EGRESS-001-20260922-R01.md`
- Create: `docs/reports/tests/TR-MVP-EGRESS-001-20260922-R01.md`
- Create: `docs/reports/reviews/RR-MVP-EGRESS-001-20260922-R01.md`
- Modify: `docs/records/implementation/IMPLEMENTATION-INDEX.md`
- Modify: `docs/reports/tests/TEST-INDEX.md`
- Modify: `docs/reports/reviews/REVIEW-INDEX.md`

**Interfaces:**
- Consumes: completed Tasks 1–5 and their fresh test outputs.
- Produces: a reviewable implementation branch in `VERIFYING`, ready for the first merge; live sections remain factually marked “not executed” rather than passed.

- [ ] **Step 1: Update the current-fact documentation**

Mark the spec `状态：已批准` and record the plan-approved two-phase integration clarification from Global Constraints without changing the security, runtime or production boundaries. Document the outbound path separately from ingress, exact overlay order, key paths and permissions, allowed destinations, no-direct-fallback behavior, verifier command, staging rollback rule, and production-not-deployed boundary. Update `PROJECT-STATE.md` with no more than three next actions.

- [ ] **Step 2: Move `MVP-EGRESS-001` to `VERIFYING`**

Keep IR/TR/RR links present. Keep final SHA blank because no merged candidate exists yet. State that automated verification is complete and live staging verification awaits a merged-main immutable image.

- [ ] **Step 3: Run the complete automated gate set and capture fresh output**

From `src/backend`:

```powershell
uv run ruff check app ../tests/backend
uv run mypy app
uv run pytest -q
```

From `src/frontend`:

```powershell
npm test
npm run lint
npm run typecheck
npm run build
```

From repository root:

```powershell
docker build --file src/docker/Dockerfile.backend --tag crm-backend:tiktok-egress-plan src/backend
git diff --check origin/main...HEAD
```

Expected: every command exits 0. If Docker/network dependency retrieval is unavailable, record the exact failure and do not merge until an equivalent trusted build succeeds.

- [ ] **Step 4: Perform the whole-branch standards/spec review**

Review `origin/main...HEAD` against `AGENTS.md`, the approved spec and this plan. Grade findings by effect. Fix every Critical/Important through a new RED→GREEN test cycle; record Minor findings without silently fixing unrelated polish. Confirm no secret material, absolute local key path, private key, environment file or raw server snapshot is tracked.

- [ ] **Step 5: Write factual IR/TR/RR revision R01**

Bind reports to the current implementation HEAD and list every command/result from Step 3. The live-staging section must explicitly say `NOT_EXECUTED — requires merged main image`; it must not contain blank placeholders or claim completion. RR records the whole-branch review and any rulings/deferred minors. Update the three indexes.

- [ ] **Step 6: Commit Task 6**

```powershell
git add docs README.md src/deploy/staging/rootless/README.md src/deploy/production/README.md
git commit -m "docs: document TikTok fixed egress operations"
```

- [ ] **Step 7: Re-run the exact full verification on the final branch tree**

Repeat Step 3 after the documentation commit and read every exit code. Record the final branch HEAD and command summaries in TR R01; if that changes the report, commit the evidence-only adjustment with:

```powershell
git add docs/records docs/reports docs/tasks/TASKS.md docs/memory/PROJECT-STATE.md
git commit -m "docs: record TikTok egress predeployment evidence"
```

Expected: clean worktree and all gates green.

---

### Task 7: Merge implementation, publish immutable images, and deploy staging

**Files/External state:**
- GitHub branch/PR: `feature/tiktok-fixed-egress` → `main`
- GitHub workflow: `.github/workflows/publish-images.yml`
- Edge host: `38.55.145.52`
- Business host: `192.168.110.210`
- Business env: `/home/crmdeploy/config/crm-staging.env`
- Business secret directory: `/home/crmdeploy/secrets/tiktok-egress`

**Interfaces:**
- Consumes: green implementation branch and server access explicitly authorized by the user.
- Produces: merged-main image digests, live helper, verified source IP, failure-closed evidence and unchanged company workload baselines for Task 8.

- [ ] **Step 1: Push, create the implementation PR, and merge after checks**

```powershell
git push -u origin feature/tiktok-fixed-egress
$prUrl = gh pr create --base main --head feature/tiktok-fixed-egress --title "feat: add fixed TikTok egress" --body "Implements the VERIFYING phase of MVP-EGRESS-001. Spec: docs/superpowers/specs/2026-09-21-tiktok-fixed-egress-design.md. Plan: docs/superpowers/plans/2026-09-22-tiktok-fixed-egress.md. Automated IR/TR/RR: IR-MVP-EGRESS-001-20260922-R01, TR-MVP-EGRESS-001-20260922-R01, RR-MVP-EGRESS-001-20260922-R01. Live staging deployment follows the merged-main immutable image; the task is not DONE and production remains undeployed."
$prNumber = gh pr view $prUrl --json number --jq '.number'
gh pr checks $prNumber --watch
gh pr merge $prNumber --squash --delete-branch
git fetch origin main
```

The PR body must link `MVP-EGRESS-001`, spec, plan, IR/TR/RR and state that live deployment follows the merged image. Do not merge with failing or missing required checks.

- [ ] **Step 2: Publish images from the actual merged `main` SHA**

```powershell
$subjectSha = git rev-parse origin/main
gh workflow run publish-images.yml --ref main -f source_sha=$subjectSha
$runId = $null
foreach ($attempt in 1..12) {
    $runId = gh run list --workflow publish-images.yml --branch main --event workflow_dispatch --commit $subjectSha --limit 1 --json databaseId --jq '.[0].databaseId'
    if ($runId) { break }
    Start-Sleep -Seconds 5
}
if (-not $runId) { throw "Timed out locating the image publication run for $subjectSha" }
gh run watch $runId --exit-status
$artifactRoot = Join-Path (Get-Location).Path 'src/tests/.artifacts'
New-Item -ItemType Directory -Path $artifactRoot -Force -ErrorAction Stop | Out-Null
$artifactDir = Join-Path $artifactRoot "tiktok-egress-images-$subjectSha"
New-Item -ItemType Directory -Path $artifactDir -Force -ErrorAction Stop | Out-Null
gh run download $runId --name "image-repo-digests-$subjectSha" --dir $artifactDir
```

Verify the artifact `source_sha` equals `$subjectSha`, all three references match `^[^@]+@sha256:[0-9a-f]{64}$`, and the backend image label `org.opencontainers.image.revision` equals `$subjectSha`.

- [ ] **Step 3: Capture pre-change baselines on both servers**

Using restricted temporary local copies of the user-provided SSH keys, record low-sensitive hashes/status for:

- edge Nginx config files, 22/80/443/18080 listeners, `crm-tunnel` authorized line hash and other vhost hashes;
- business system-Docker six-field GitLab baseline, Rootless container/image/port set, existing ingress tunnel argv and public health endpoints;
- current staging env key names and capability values without printing any secret value.

Store raw snapshots only in root-owned or `crmdeploy`-owned `0700` server directories. Delete local temporary key copies after use.

- [ ] **Step 4: Generate the dedicated identity on the business host**

As `crmdeploy`, create `/home/crmdeploy/secrets/tiktok-egress` mode `0700`. If no identity exists, run:

```bash
ssh-keygen -q -t ed25519 -N '' -C crm-staging-tiktok-egress \
  -f /home/crmdeploy/secrets/tiktok-egress/id_ed25519
```

Set private key and known_hosts to `0600`, public key to `0600`, owner UID/GID 1004. Copy only the already-pinned `38.55.145.52` Ed25519 host line from the ingress tunnel known_hosts, verify fingerprint `SHA256:PPupiUWQYpCvIzPtolycQELbt5o49rqp1Hu1RHHE3XU`, and never use `ssh-keyscan` as trust establishment.

- [ ] **Step 5: Install the public egress account on the edge**

Export only the generated public key through the existing management channel, upload the merged-main installer, execute it as root, then verify:

```bash
id crm-egress
sshd -t
sshd -T -C user=crm-egress,host=localhost,addr=192.168.110.210 \
  | grep -E '^(allowtcpforwarding|permitopen|permitlisten|gatewayports|permittty|forcecommand|passwordauthentication|pubkeyauthentication) '
```

Expected: publickey-only, local-only forwarding, no listen/TTY/shell, exact three permit-open destinations. Re-read the original `crm-tunnel` effective policy and authorized-line hash; it must be unchanged.

- [ ] **Step 6: Upload merged assets and update staging’s non-secret egress fields**

Create a new versioned source directory bound to `$subjectSha`; never overwrite a prior SHA directory. Back up the current environment file to a new root-only recovery directory, then atomically set only:

```env
TIKTOK_EGRESS_IP=38.55.145.52
TIKTOK_EGRESS_SECRET_DIR=/home/crmdeploy/secrets/tiktok-egress
```

Keep file owner `crmdeploy:crmdeploy`, mode `0600`, and all real capability flags false. Do not populate `TIKTOK_WEBHOOK_SECRET` and do not echo any secret value.

- [ ] **Step 7: Validate and deploy through the reviewed staging gate**

Run `Test-StagingProductionGates.ps1` first with `-ValidateOnly`, then with `-Deploy`, using the exact downloaded RepoDigests, Rootless socket, `staging.overselfx.com`, and distinct evidence paths. The gate must start `tiktok-egress`, run `verify_tiktok_egress.py`, apply migrations/check heads, start applications and obtain 200 from all three health endpoints.

- [ ] **Step 8: Exercise failure closure once**

Stop only the Rootless `crm-staging-tiktok-egress-1` container. Run the same verifier from a one-off backend container and require nonzero. Confirm no backend/jobs process established a direct connection to either TikTok hostname/IP during the window. Restart only the helper, wait healthy, and require the verifier to return JSON with both IPs equal to `38.55.145.52`.

Do not stop SSHD, Nginx, system Docker, GitLab, ingress tunnel, database, Redis, MinIO or model service.

- [ ] **Step 9: Verify TikTok reachability without business credentials**

Through the application proxy path, perform TLS requests without App Secret or Token:

- token endpoint returns an HTTP response with TLS verification success;
- authorized-shops endpoint returns an expected unauthenticated/invalid-request response with TLS verification success.

No OAuth code, access token, webhook, message, order or customer data is sent.

- [ ] **Step 10: Compare post-change baselines**

Require byte-for-byte equality for system-Docker container baseline, GitLab ports/state, ingress tunnel policy/hash, non-staging vhost hashes, and forbidden listeners. Public `/healthz`, `/v1/health`, `/v1/health/ready` must be 200. Any drift triggers the documented rollback and leaves all real TikTok flags false.

---

### Task 8: Finalize evidence, close the task, and merge the evidence branch

**Files:**
- Create: `release/evidence/staging/crm-staging-tiktok-egress-20260922.json`
- Modify: `docs/records/implementation/IR-MVP-EGRESS-001-20260922-R01.md`
- Modify: `docs/reports/tests/TR-MVP-EGRESS-001-20260922-R01.md`
- Modify: `docs/reports/reviews/RR-MVP-EGRESS-001-20260922-R01.md`
- Modify: `docs/tasks/TASKS.md`
- Modify: `docs/memory/PROJECT-STATE.md`
- Modify: `docs/operations/DEPLOYMENT.md`
- Modify: `docs/operations/RELEASE-GATES.md`
- Modify: `docs/records/implementation/IMPLEMENTATION-INDEX.md`
- Modify: `docs/reports/tests/TEST-INDEX.md`
- Modify: `docs/reports/reviews/REVIEW-INDEX.md`

**Interfaces:**
- Consumes: merged implementation subject SHA, image artifact, gate JSON, live failure test, reachability checks and before/after baselines.
- Produces: final low-sensitive evidence, `MVP-EGRESS-001=DONE`, and a second evidence-only merge whose tail contains no behavior change.

- [ ] **Step 1: Create an evidence-only branch from the deployed main**

After fetching the merged implementation:

```powershell
git fetch origin main
$candidateSubjectSha = git rev-parse origin/main
git switch -c docs/mvp-egress-001-evidence origin/main
```

Record `$candidateSubjectSha` as `CANDIDATE_SUBJECT_SHA`, the implementation merge SHA. This branch may modify only reports, evidence, indexes, task status, project state and current deployment/release facts.

- [ ] **Step 2: Write the low-sensitive machine evidence**

Create schema-versioned JSON containing:

- environment `staging`, `production_release=false`;
- candidate subject SHA and image RepoDigests;
- declared/observed egress IP `38.55.145.52`;
- helper health, failure-closure result, allowed destination names and proxy scheme (no key path contents);
- ingress/Nginx/GitLab/company workload comparison status;
- public health status codes;
- real capability flags all false;
- rollback state and remaining production boundary.

Do not include environment values other than approved non-secrets, private/public key bodies, tokens, cookies, certificates, raw server snapshots or customer data.

- [ ] **Step 3: Finalize IR/TR/RR and indexes**

Replace the factual `NOT_EXECUTED` live section with actual UTC window, commands at safe summary level, result counts, subject/evidence SHA relationship, rollback outcome and residual risks. RR must confirm Critical/Important findings are zero or fixed with RED→GREEN evidence. Update indexes.

- [ ] **Step 4: Mark `MVP-EGRESS-001` DONE**

Set task state to `DONE`, final SHA to `CANDIDATE_SUBJECT_SHA`, preserve the two-phase branch/PR history, link final IR/TR/RR, and keep production explicitly blocked/undeployed. Update `PROJECT-STATE.md` with at most three next actions, led by completing remaining `MVP-001` external credentials and starting `MVP-002` only after Partner Center whitelist confirmation.

- [ ] **Step 5: Verify evidence-only tail and repository health**

```powershell
git diff --check
git diff --name-only $candidateSubjectSha...HEAD
Set-Location src/backend
uv run pytest ../tests/backend/runtime_infrastructure/test_real_runtime_config.py ../tests/backend/runtime_infrastructure/test_production_gate_scripts.py ../tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py ../tests/backend/runtime_infrastructure/test_tiktok_egress_runtime.py ../tests/backend/platform/test_tiktok_http.py ../tests/backend/platform/test_tiktok_oauth.py ../tests/backend/platform/test_tiktok_read.py ../tests/backend/platform/test_tiktok_write.py -q
```

Expected: diff contains only allowed evidence/current-fact paths and all focused tests pass.

- [ ] **Step 6: Commit, review, push and merge the evidence branch**

```powershell
git add release/evidence/staging docs
git commit -m "docs: close TikTok fixed egress deployment"
git push -u origin docs/mvp-egress-001-evidence
$evidencePrUrl = gh pr create --base main --head docs/mvp-egress-001-evidence --title "docs: close TikTok fixed egress deployment" --body "Closes MVP-EGRESS-001 with low-sensitive staging deployment evidence, final IR/TR/RR and task status. Candidate subject is the already merged implementation SHA; this branch changes evidence and current-fact documentation only. Production remains undeployed."
$evidencePrNumber = gh pr view $evidencePrUrl --json number --jq '.number'
gh pr checks $evidencePrNumber --watch
gh pr merge $evidencePrNumber --squash --delete-branch
git fetch origin main
```

Require the merged main to contain the final evidence and task `DONE`. Re-run the focused tests against `origin/main` in a clean integration worktree before removing the owned worktree and local short-term branches. Do not modify the user’s dirty/diverged primary checkout.
