# `src/` Engineering Root Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every application, test, script, deployment, Docker, Compose, and local environment asset under `src/` while preserving the `crm` runtime identity and proving the relocated project starts successfully.

**Architecture:** Treat `src/` as the only engineering root and keep repository metadata, current documentation, and frozen release evidence at the Git root. Preserve backend and frontend build contexts, make path discovery work in both normal checkouts and linked worktrees, and expose a source-relative PowerShell startup entrypoint.

**Tech Stack:** Git worktrees, Python 3.11, uv, FastAPI, pytest, Node.js 20, Next.js, npm, PowerShell 5.1/7, Docker Compose

**Spec:** `docs/superpowers/specs/2026-09-16-src-engineering-root-migration-design.md`

## Global Constraints

- Governance remains `STANDARD`; base SHA is `6b726a32502a364040ccf0a0b251a320d379ee7d`.
- Do not change product behavior, APIs, database schema, migrations, permissions, safety switches, prompts, models, or release-gate conclusions.
- Keep `.github/`, `docs/`, `release/`, Git/Codex metadata, `README.md`, and `design-qa.md` at the repository root.
- Do not leave root-level compatibility copies of moved Docker, Compose, application, test, script, deploy, or environment files.
- Keep Compose project name `crm` and the existing `crm_*` network and named-volume contract.
- Delete `deploy/cloudflared/config.example.yml` as explicitly authorized; do not create `src/deploy/cloudflared/config.example.yml`.
- Do not rewrite historical `docs/superpowers/**`, frozen `release/baselines/**`, or `release/evidence/**` path facts.
- The five accepted baseline path failures must pass after migration; no test may be removed or weakened.
- Do not push, create or merge a PR, publish images, or deploy staging/production.

---

### Task 1: Register the migration and establish path-contract red tests

**Files:**
- Modify: `docs/tasks/TASKS.md`
- Modify after move: `src/backend/tests/test_production_gate_scripts.py`
- Modify after move: `src/backend/tests/test_real_runtime_config.py`
- Modify after move: `src/backend/tests/test_real_fs05_sse_runtime.py`
- Modify after move: `src/backend/tests/test_rootless_staging_assets.py`
- Modify after move: `src/frontend/tests/compose.test.mjs`
- Create after move: `src/backend/tests/test_repository_layout.py`

**Interfaces:**
- Consumes: approved spec and base SHA.
- Produces: task `REPO-001` in `DOING`, explicit `SOURCE_ROOT`/`REPOSITORY_ROOT` contracts, and tests that fail until the new paths exist.

- [ ] **Step 1: Add `REPO-001` to the P2 maintenance table**

Use `apply_patch` to add this row without changing existing completed tasks:

```markdown
| REPO-001 | 将全部工程代码与运行资产迁入 `src/`，并通过完整构建和实际启动验证 | `src/` 工程根迁移设计的 9 项验收标准；`BASE_SHA=6b726a32502a364040ccf0a0b251a320d379ee7d` | DOING | codex/src-layout-migration | none | required | required | required | |
```

- [ ] **Step 2: Perform the tracked moves before editing content**

Create `src/docker`, `src/compose`, and `src/config`, then run exact `git mv` operations for `backend`, `frontend`, `tests`, `scripts`, `deploy`, four Dockerfiles, eight Compose files, and `.env.example` according to the spec. Remove only:

```text
src/deploy/cloudflared/config.example.yml
```

Verify `git status --short` shows moves/deletion and no unrelated path.

- [ ] **Step 3: Add the repository-layout contract test**

Create `src/backend/tests/test_repository_layout.py` with a root finder that walks upward until it finds `.git`, then assert:

```python
from pathlib import Path


def repository_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    raise AssertionError("Git repository root was not found")


REPOSITORY_ROOT = repository_root(Path(__file__).resolve())
SOURCE_ROOT = REPOSITORY_ROOT / "src"


def test_engineering_assets_live_under_src() -> None:
    required = (
        "backend",
        "frontend",
        "tests",
        "scripts",
        "deploy",
        "docker",
        "compose",
        "config/.env.example",
    )
    assert all((SOURCE_ROOT / path).exists() for path in required)
    forbidden = ("backend", "frontend", "tests", "scripts", "deploy", "Dockerfile.backend", "docker-compose.yml")
    assert all(not (REPOSITORY_ROOT / path).exists() for path in forbidden)
    assert not (SOURCE_ROOT / "deploy/cloudflared/config.example.yml").exists()
```

- [ ] **Step 4: Update path constants in existing tests but not runtime configuration**

For affected backend tests, use a `.git` upward search to define `REPOSITORY_ROOT`, then `SOURCE_ROOT = REPOSITORY_ROOT / "src"`. Read Compose, deploy, backend, and scripts from `SOURCE_ROOT`; read `.github` and `release` from `REPOSITORY_ROOT`.

For `src/frontend/tests/compose.test.mjs`, define:

```javascript
const sourceRoot = new URL("../../", import.meta.url);
const repositoryRoot = new URL("../../../", import.meta.url);
```

Read Compose/Docker/deploy from `sourceRoot` subdirectories and `.github`/`release` from `repositoryRoot`.

- [ ] **Step 5: Run focused tests and observe the intended red state**

```powershell
Set-Location src/backend
$env:UV_CACHE_DIR = (Join-Path (Get-Location) '.uv-cache')
uv run pytest tests/test_repository_layout.py tests/test_real_runtime_config.py tests/test_real_fs05_sse_runtime.py tests/test_production_gate_scripts.py tests/test_rootless_staging_assets.py -q
Set-Location ../frontend
npm run test
```

Expected: layout existence passes, while Compose/runtime/script assertions fail on old internal paths or the missing startup script. No business-behavior test should fail.

- [ ] **Step 6: Commit structure and red contracts**

```powershell
git add --all
git commit -m "chore: move engineering assets under src"
```

### Task 2: Make runtime, Compose, Docker, and scripts source-relative

**Files:**
- Modify: `src/backend/app/shared/config/settings.py`
- Modify: `src/compose/docker-compose.yml`
- Modify: `src/compose/docker-compose.prod.yml`
- Modify: `src/compose/docker-compose.*.yml`
- Modify: `src/scripts/*.ps1`
- Create: `src/scripts/start-local.ps1`
- Modify: `src/backend/tests/test_repository_layout.py`
- Modify: focused path-contract tests from Task 1

**Interfaces:**
- Consumes: physical layout and red tests from Task 1.
- Produces: `src/config/.env` loading, stable `crm` Compose identity, valid source-relative build/mount paths, and a local startup command compatible with both Compose entrypoints.

- [ ] **Step 1: Update backend environment-file location**

In `settings.py`, replace the repository-root `.env` assumption with:

```python
SOURCE_ROOT = Path(__file__).resolve().parents[4]
PROJECT_ENV_FILE = SOURCE_ROOT / "config" / ".env"
```

Update the nearby comment to state that containers receive values through Compose and do not require the file inside the image.

- [ ] **Step 2: Update the base Compose contract**

At the beginning of `src/compose/docker-compose.yml`, add:

```yaml
name: crm
```

Apply these exact path rules throughout the Compose set:

```text
backend context/mount: ../backend
frontend context/mount: ../frontend
backend Dockerfile from backend context: ../docker/Dockerfile.backend
model Dockerfile from backend context: ../docker/Dockerfile.model-service
frontend Dockerfile from frontend context: ../docker/Dockerfile.frontend
model assets from compose directory: ../deploy/models
Nginx config from compose directory: ../deploy/nginx/nginx.conf
env_file from compose directory: ../config/.env
```

Do not change service commands, ports, health checks, security values, or image references.

- [ ] **Step 3: Update operational scripts**

In every `src/scripts/*.ps1`, use:

```powershell
$sourceRoot = Split-Path -Parent $PSScriptRoot
```

Use `$sourceRoot/backend`, `$sourceRoot/frontend`, `$sourceRoot/compose`, and `$sourceRoot/deploy` as appropriate. Staging scripts must continue resolving the Git checkout root with Git for the external-model boundary.

- [ ] **Step 4: Create the local startup script**

Create `src/scripts/start-local.ps1` with this contract:

```powershell
#requires -Version 5.1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$sourceRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $sourceRoot "config/.env"
$envTemplate = Join-Path $sourceRoot "config/.env.example"
$composeFile = Join-Path $sourceRoot "compose/docker-compose.yml"

foreach ($path in @($envTemplate, $composeFile)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required local startup asset is missing: $path"
    }
}
if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "Create src/config/.env from src/config/.env.example before starting the project."
}

$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($null -ne $docker) {
    & $docker.Source compose version *> $null
}
if ($null -ne $docker -and $LASTEXITCODE -eq 0) {
    $executable = $docker.Source
    $prefix = @("compose")
}
else {
    $standalone = Get-Command docker-compose -ErrorAction SilentlyContinue
    if ($null -eq $standalone) {
        throw "Docker Compose is required."
    }
    & $standalone.Source version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose is unavailable."
    }
    $executable = $standalone.Source
    $prefix = @()
}

& $executable @($prefix + @(
    "--project-name", "crm",
    "--env-file", $envFile,
    "-f", $composeFile,
    "up", "-d", "--build"
))
if ($LASTEXITCODE -ne 0) {
    throw "Local project startup failed with exit code $LASTEXITCODE."
}
```

- [ ] **Step 5: Run focused path and runtime tests**

Run the Task 1 focused backend tests and `npm run test` from `src/frontend`. Expected: all pass.

- [ ] **Step 6: Validate Compose resolution**

Use the available Compose command to run `config` for the base file and supported overlay combinations. Confirm the rendered project name is `crm`, build contexts point inside `src/backend`/`src/frontend`, deploy mounts point inside `src/deploy`, and named volumes remain `crm_*`.

- [ ] **Step 7: Commit runtime path repairs**

```powershell
git add src
git commit -m "build: make runtime paths source-relative"
```

### Task 3: Update CI, repository metadata, and active documentation

**Files:**
- Modify: `.github/CODEOWNERS`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/publish-images.yml`
- Modify: `.github/workflows/staging-gates.yml`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/architecture/SYSTEM.md`
- Modify: `docs/engineering/DEVELOPMENT.md`
- Modify: `docs/operations/DEPLOYMENT.md`
- Modify: `docs/quality/TEST-STRATEGY.md`
- Modify: `docs/memory/PROJECT-STATE.md`
- Modify: `docs/tasks/TASKS.md`
- Modify: maintained Markdown under `src/deploy/**`
- Modify: `src/tests/README.md`

**Interfaces:**
- Consumes: final source-relative paths from Task 2.
- Produces: CI, publishing, staging, developer instructions, and current facts that all point to the new canonical paths.

- [ ] **Step 1: Update CI and image publishing**

Use these exact canonical paths:

```text
backend working directory: src/backend
frontend working directory: src/frontend
npm cache lock file: src/frontend/package-lock.json
backend/model build context: src/backend
frontend build context: src/frontend
Dockerfiles: src/docker/Dockerfile.backend, src/docker/Dockerfile.frontend.prod, src/docker/Dockerfile.model-service
staging scripts: ./src/scripts/Test-StagingProductionGates.ps1 and ./src/scripts/Invoke-StagingRollbackDrill.ps1
```

- [ ] **Step 2: Update CODEOWNERS**

Replace root Docker/Compose/backend migration rules with `/src/docker/`, `/src/compose/`, `/src/deploy/`, and `/src/backend/migrations/`. Keep root metadata, docs, and release owners unchanged.

- [ ] **Step 3: Update active docs and examples**

Use `apply_patch` to update current paths and commands in maintained files. The primary local command becomes:

```powershell
Copy-Item src/config/.env.example src/config/.env
.\src\scripts\start-local.ps1
```

Production and overlay examples must use `src/compose/*.yml`; backend/frontend commands must use `src/backend` and `src/frontend`; operational commands must use `src/scripts` and `src/deploy`.

Do not edit historical `docs/superpowers/**` other than this task's spec/plan, or frozen `release/**` records.

- [ ] **Step 4: Scan active references**

Exclude `docs/superpowers/**` and `release/**`, then scan for old root-level `backend/`, `frontend/`, `tests/`, `scripts/`, `deploy/`, `Dockerfile.*`, `docker-compose*.yml`, and `.env.example` references. Every remaining match must either be a clearly documented path mapping in this task's current spec/plan or be corrected.

- [ ] **Step 5: Move `REPO-001` to `VERIFYING` and commit**

```powershell
git add .github AGENTS.md README.md docs src
git commit -m "docs: align repository paths with src layout"
```

### Task 4: Run full quality, build, and startup verification

**Files:**
- Modify only if a verification exposes an in-scope migration defect.

**Interfaces:**
- Consumes: migrated repository candidate.
- Produces: a final `CANDIDATE_SUBJECT_SHA` with all applicable checks passing and an isolated successful startup.

- [ ] **Step 1: Run backend gates from `src/backend`**

```powershell
$env:UV_CACHE_DIR = (Join-Path (Get-Location) '.uv-cache')
uv sync --frozen --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy app scripts
uv run pytest
```

Use a unique repository-external pytest temp directory if the sandbox default is not writable. Expected: no failures; skipped environment-gated tests remain reported.

- [ ] **Step 2: Run frontend gates from `src/frontend`**

```powershell
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
```

Expected: zero errors and zero test failures. Existing lint warnings may be recorded but not increased.

- [ ] **Step 3: Validate PowerShell parsing**

Parse every `src/scripts/*.ps1` with Windows PowerShell 5.1 and PowerShell 7 when both are installed. Expected: no parser errors.

- [ ] **Step 4: Build all four images from new contexts**

Build backend, frontend development, frontend production, and retrieval-model-service images using `src/backend` or `src/frontend` contexts and `src/docker/Dockerfile.*`. Use task-scoped local tags and do not push.

- [ ] **Step 5: Prove actual startup in an isolated Compose project**

Copy the example to an ignored `src/config/.env` only if absent. Use project name `crm-src-layout-verification` and `src/compose/docker-compose.yml` to run `up -d --build`. Verify:

```text
GET http://127.0.0.1:8000/v1/health       -> 2xx
GET http://127.0.0.1:8000/v1/health/ready -> 2xx
GET http://127.0.0.1:3000/login           -> 2xx
```

Before starting, confirm the verification project does not already exist. After evidence is captured, remove only `crm-src-layout-verification` containers, network, and volumes; never remove `crm_*` volumes.

- [ ] **Step 6: Run final structural and secret checks**

Verify target paths, absence of old root engineering paths, active-reference scan, Markdown links, `git diff --check`, changed-file scope, and added-line secret patterns. Commit any in-scope verification fix and rerun affected gates. The last delivery-changing commit is `CANDIDATE_SUBJECT_SHA`.

### Task 5: Create final IR, TR, RR, indexes, and task closure

**Files:**
- Create: `docs/records/implementation/IR-REPO-001-20260916-R01.md`
- Create: `docs/reports/tests/TR-REPO-001-20260916-R01.md`
- Create: `docs/reports/reviews/RR-REPO-001-20260916-R01.md`
- Create: `docs/records/implementation/IMPLEMENTATION-INDEX.md`
- Create: `docs/reports/tests/TEST-INDEX.md`
- Create: `docs/reports/reviews/REVIEW-INDEX.md`
- Modify: `docs/tasks/TASKS.md`
- Modify: `docs/memory/PROJECT-STATE.md`

**Interfaces:**
- Consumes: verified `CANDIDATE_SUBJECT_SHA` and fresh command results from Task 4.
- Produces: final evidence records, deterministic indexes, `REPO-001=DONE`, and an evidence-only head.

- [ ] **Step 1: Write final implementation and test records**

Use the governance frontmatter exactly. Bind `final_sha`/`tested_sha` to the real candidate SHA, list every command and result, record the accepted pre-migration path failures separately from post-migration results, and state any unexecuted external/staging gates.

- [ ] **Step 2: Perform and record the infrastructure review**

Review correctness, build-context boundaries, environment-file loading, Compose merge behavior, project/volume identity, secret propagation, CI paths, staging script checkout boundaries, startup evidence, cleanup isolation, and revert recovery. Set RR to `APPROVE` only when no unresolved P0/P1/P2 finding remains.

- [ ] **Step 3: Create deterministic indexes**

Create the three first-use indexes with `Record ID | Task ID | Revision | Status | SHA | REQ/AC or Focus | Updated | Source path`, and mark the branch view `CANDIDATE_VIEW`.

- [ ] **Step 4: Close the task and update recovery state**

Set `REPO-001` to `DONE`, link IR/TR/RR, and set `最终 SHA` to the candidate SHA. Update `PROJECT-STATE.md` with the new source root and evidence entries without duplicating the task table.

- [ ] **Step 5: Commit evidence and verify the tail**

```powershell
git add docs
git commit -m "docs: record src layout migration evidence"
```

Verify `CANDIDATE_SUBJECT_SHA..HEAD` contains only records, indexes, task state, and recovery-state files. Re-run `git diff --check` and final status checks.

### Task 6: Merge locally and clean up the feature workspace

**Files:**
- No new content changes.

**Interfaces:**
- Consumes: clean verified branch and the user's explicit instruction to merge locally.
- Produces: local `main` containing the migration, with the temporary worktree and feature branch removed.

- [ ] **Step 1: Verify merge safety**

Confirm feature worktree is clean, feature base is `main`, and the only pre-existing main worktree change is the now-authorized deletion that the feature branch also records. Stop on any other main modification.

- [ ] **Step 2: Fast-forward local main**

Use `git merge --ff-only codex/src-layout-migration`. Do not pull, push, or alter the remote.

- [ ] **Step 3: Re-run structural, path, Compose config, and startup smoke checks on merged main**

Use the new canonical locations and confirm no unexpected working-tree change remains. Product tests may rely on the already verified candidate SHA because fast-forward preserves it; path and startup checks must be fresh on merged main.

- [ ] **Step 4: Remove the clean worktree and merged branch**

After merged verification succeeds, remove `.worktrees/src-layout-migration`, prune worktree metadata, and delete `codex/src-layout-migration` with normal `git branch -d`.
