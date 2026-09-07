# GitHub Flow and MVP Release Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Initialize and govern the workspace-root Git repository with GitHub Flow, then freeze a traceable `v0.1.0-mvp.20260907` engineering baseline without committing secrets, model weights, dependencies, caches, or temporary test output.

**Architecture:** Keep one monorepo at the workspace root so code, architecture, tests, evidence, and shared project facts share the same immutable history. Bootstrap the repository on `main`, perform baseline implementation on `docs/release-baseline-20260907` in an isolated worktree, locally squash-merge because no remote exists, and tag the verified result. Treat source/config hashes, local Docker image IDs, and registry RepoDigests as different evidence types.

**Tech Stack:** Git 2.x, GitHub Flow, GitHub Actions, PowerShell, Python 3.11 with uv, Next.js/Node.js 20, Docker Compose, Markdown, JSON, SHA-256.

**Spec:** `docs/superpowers/specs/2026-09-07-github-flow-release-baseline-design.md`

## Global Constraints

- The Git repository root is exactly `E:\develop\CRM智能聊天系统`.
- The only long-lived branch is `main`; implementation branch is `docs/release-baseline-20260907`.
- The release tag is `v0.1.0-mvp.20260907`, application version is `0.1.0`, and Alembic head is `023_marketing_review_idempotency`.
- Never read, stage, hash, print, or copy any `.env` value; only `.env.example` is versioned.
- Do not track model weights, `.venv`, `node_modules`, caches, build outputs, logs, or test temporary directories.
- Do not call a local Docker image ID a RepoDigest; use JSON `null` when no registry RepoDigest exists.
- Do not claim production release: real platform integration, 50-client real-model SSE, five-day availability, backup/restore, and remaining production gates stay explicit.
- Formal test conclusions live only in `测试工程师/`; shared memory stores only the test index.

---

### Task 1: Bootstrap worktree safety and create the isolated GitHub Flow branch

**Files:**
- Modify: `.gitignore`
- Modify: `docs/superpowers/specs/2026-09-07-github-flow-release-baseline-design.md`
- Create: `docs/superpowers/plans/2026-09-07-github-flow-release-baseline.md`

**Interfaces:**
- Consumes: bootstrap commit `49a1c4d` on `main`.
- Produces: a clean `main` with `.worktrees/` ignored and an isolated `docs/release-baseline-20260907` worktree.

- [ ] **Step 1: Confirm the specification status is `已确认` and the plan contains no placeholders**

Run:

```powershell
Select-String -Path docs/superpowers/specs/2026-09-07-github-flow-release-baseline-design.md,docs/superpowers/plans/2026-09-07-github-flow-release-baseline.md -Pattern 'TBD|TODO|待定|待补充'
```

Expected: no output.

- [ ] **Step 2: Verify the worktree directory is ignored**

Run:

```powershell
git check-ignore -v .worktrees/probe
```

Expected: `.gitignore` rule `/.worktrees/` is reported.

- [ ] **Step 3: Commit the confirmed spec, implementation plan, and worktree safety rule**

Run:

```powershell
git add -- .gitignore docs/superpowers/specs/2026-09-07-github-flow-release-baseline-design.md docs/superpowers/plans/2026-09-07-github-flow-release-baseline.md
git commit -m "docs: plan GitHub Flow release baseline"
```

Expected: one commit on `main`; no other workspace file is staged.

- [ ] **Step 4: Create the isolated implementation worktree**

Run:

```powershell
git worktree add .worktrees/release-baseline-20260907 -b docs/release-baseline-20260907
git -C .worktrees/release-baseline-20260907 branch --show-current
```

Expected: branch output is `docs/release-baseline-20260907`.

### Task 2: Establish repository ignore, text, PR, and CI controls

**Files:**
- Modify: `.gitignore`
- Create: `.gitattributes`
- Create: `.github/pull_request_template.md`
- Create: `.github/workflows/ci.yml`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: root repository boundary from the approved spec.
- Produces: repository-wide tracking rules and PR checks used by every later branch.

- [ ] **Step 1: Expand root ignore rules**

Add explicit rules for secret files, model weights, virtual environments, Node dependencies, Python/Next.js caches, coverage, browser reports, logs, local databases, temporary test output, and `.worktrees/`. Re-include `.env.example`, model README/license metadata, and `model-manifest.json`.

- [ ] **Step 2: Add line-ending and binary handling rules**

Create `.gitattributes` with `* text=auto`, LF for source/docs/config, CRLF for `*.ps1`, and `-text` for images, archives, office files, fonts, and model weight extensions.

- [ ] **Step 3: Add the PR template and CI workflow**

The PR template must require scope, linked task/defect, verification, document synchronization, migration/config impact, sensitive-file confirmation, and known risks.

The CI workflow must run on pull requests and `main` pushes, use Python 3.11 and Node 20, and execute:

```powershell
cd CRM智能聊天系统/backend
uv sync --frozen --all-groups
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run mypy app scripts
uv run pytest

cd ../frontend
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
```

- [ ] **Step 4: Add mandatory GitHub Flow rules to root Agent instructions**

Document branch checks before changes, no direct daily development on `main`, small commits, required PR/CI, implementation record synchronization, and the prohibited file classes.

- [ ] **Step 5: Verify ignore behavior without revealing secret contents**

Run:

```powershell
git check-ignore -v CRM智能聊天系统/.env
git check-ignore -v CRM智能聊天系统/backend/.venv/pyvenv.cfg
git check-ignore -v CRM智能聊天系统/frontend/node_modules/.package-lock.json
git check-ignore -v CRM智能聊天系统/deploy/models/bge-m3/pytorch_model.bin
git check-ignore -v CRM智能聊天系统/.env.example
```

Expected: the first four paths are ignored; `.env.example` is not ignored.

- [ ] **Step 6: Commit repository governance controls**

Run:

```powershell
git add -- .gitignore .gitattributes .github AGENTS.md
git commit -m "chore: establish repository governance controls"
```

### Task 3: Document the GitHub Flow operating procedure

**Files:**
- Create: `共享记忆文档/Git与GitHub Flow开发规范.md`
- Modify: `CRM智能聊天系统/README.md`

**Interfaces:**
- Consumes: branch, commit, PR, and baseline rules from Task 2.
- Produces: daily commands for humans and agents, including remote setup without inventing a URL.

- [ ] **Step 1: Write the team GitHub Flow guide**

Cover initial identity check, feature branch/worktree creation, status review, selective staging, Conventional Commits, push/PR, squash merge, cleanup, rollback with `git revert`, release tags, and the one-time remote commands using a user-supplied URL variable.

- [ ] **Step 2: Synchronize the product README**

Change migration coverage from `001–021` to `001–023`, identify head `023_marketing_review_idempotency`, add the root repository/GitHub Flow entry point and baseline tag, and state that the tag is an engineering baseline rather than production approval.

- [ ] **Step 3: Verify documented commands and paths**

Run:

```powershell
Test-Path '共享记忆文档/Git与GitHub Flow开发规范.md'
Select-String -Path 'CRM智能聊天系统/README.md' -Pattern '001.?023|023_marketing_review_idempotency|v0.1.0-mvp.20260907|GitHub Flow'
```

Expected: the file exists and all four concepts are found.

- [ ] **Step 4: Commit workflow documentation**

Run:

```powershell
git add -- '共享记忆文档/Git与GitHub Flow开发规范.md' 'CRM智能聊天系统/README.md'
git commit -m "docs: document GitHub Flow development workflow"
```

### Task 4: Reconstruct the two missing historical documents without fabricating evidence

**Files:**
- Create: `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-真实环境配置与基础设施-综合测试-005.md`
- Create: `共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-环境变量注释完善-001.md`
- Modify: `共享记忆文档/测试报告索引.md`
- Modify: `共享记忆文档/实施记录索引.md`

**Interfaces:**
- Consumes: existing index rows, reports 001–004 and later infrastructure reports, current `.env.example` comments, and current repository checks.
- Produces: explicitly marked evidence-recovery documents and valid index targets.

- [ ] **Step 1: Extract only recoverable historical facts**

Run targeted searches for the missing filenames, related defect IDs, original dates, conclusions, and implementation references. Do not read `.env`; inspect `.env.example` only.

- [ ] **Step 2: Perform current non-secret verification**

Check current configuration comments, Docker/Compose configuration file presence, migration head, and current relevant tests. Record current execution date separately from historical dates.

- [ ] **Step 3: Write the missing test report as a recovery supplement**

Use the mandated Phase 4 report fields. Explicitly state which conclusions come from the existing index/later reports, which checks were rerun on 2026-09-07, and which historical raw logs cannot be recovered. Do not backdate or invent screenshots.

- [ ] **Step 4: Write the missing implementation record as a recovery supplement**

Use every section in the implementation-record template. Mark API/database/AI changes as not applicable, list the actual `.env.example` evidence, and record unavailable historical command output as unavailable.

- [ ] **Step 5: Repair both indexes**

Keep existing report conclusions intact unless current authoritative evidence proves a correction. Mark both restored files as `2026-09-07 补档` so readers do not mistake reconstruction for original contemporaneous evidence.

- [ ] **Step 6: Validate every indexed Markdown target**

Use a PowerShell parser to extract backtick-wrapped `.md` paths from both indexes and verify that non-template paths exist. Expected: no missing real report or implementation-record path.

- [ ] **Step 7: Commit recovered records**

Run:

```powershell
git add -- '测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-真实环境配置与基础设施-综合测试-005.md' '共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-环境变量注释完善-001.md' '共享记忆文档/测试报告索引.md' '共享记忆文档/实施记录索引.md'
git commit -m "docs: restore missing infrastructure evidence records"
```

### Task 5: Synchronize architecture v1.5 and production-release gate v1.1

**Files:**
- Create: `架构师/ARCH-001-SYS-系统总体架构设计-v1.5.md`
- Create: `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md`

**Interfaces:**
- Consumes: v1.4 architecture, v1.0 checklist, migration 023, latest authoritative test reports, GitHub Flow governance, and baseline evidence.
- Produces: current architecture and release-gate status without changing product APIs.

- [ ] **Step 1: Write architecture v1.5 as an incremental successor**

Inherit unchanged v1.4 decisions, replace migration 018 with head 023, add the root-monorepo/GitHub Flow/release-manifest design, and update real TikTok, AI evaluation, SSE, translation, and production status from authoritative evidence.

- [ ] **Step 2: Write checklist v1.1 while preserving v1.0**

Mark individual G0 evidence items accurately. Keep G0 overall incomplete while secret rotation, backup/restore, rollback rehearsal, or registry RepoDigest remain unverified. Keep every real-platform/performance/stability gate at its evidenced state and retain `G8=阻塞` until all required gates pass.

- [ ] **Step 3: Verify version and status consistency**

Run:

```powershell
Select-String -Path '架构师/ARCH-001-SYS-系统总体架构设计-v1.5.md' -Pattern '023_marketing_review_idempotency|GitHub Flow|v0.1.0-mvp.20260907'
Select-String -Path '架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md' -Pattern 'G0|G8|阻塞|RepoDigest'
```

Expected: all baseline and blocking-state concepts are present.

- [ ] **Step 4: Commit architecture synchronization**

Run:

```powershell
git add -- '架构师/ARCH-001-SYS-系统总体架构设计-v1.5.md' '架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md'
git commit -m "docs: synchronize architecture and production gates"
```

### Task 6: Build the machine-readable release baseline

**Files:**
- Create: `release/baselines/v0.1.0-mvp.20260907.json`

**Interfaces:**
- Consumes: actual source/config/evaluation files and Docker inspection output.
- Produces: a low-sensitive JSON manifest with verified SHA-256 values and explicit unavailable evidence.

- [ ] **Step 1: Discover and verify the migration head**

Run Alembic history/head inspection from `CRM智能聊天系统/backend` and hash the exact 023 migration file with `Get-FileHash -Algorithm SHA256`.

- [ ] **Step 2: Calculate configuration and evaluation hashes**

Hash `.env.example`, lock files, package manifests, Dockerfiles, Compose overlays, the independent evaluation dataset, manifest, and result file. Compare the three frozen evaluation hashes with the approved spec; stop if any mismatch occurs.

- [ ] **Step 3: Attempt Docker startup and application image builds**

Run a read-only Docker daemon check first. If available, build the application services without exposing or expanding environment values, then inspect image tags, `Id`, and `RepoDigests`. If unavailable or a build fails, record the exact low-sensitive failure category and continue with source/config evidence.

- [ ] **Step 4: Write and validate the JSON manifest**

Use UTF-8 JSON, sorted path entries, lowercase SHA-256 strings, `null` for missing RepoDigests, and no secret values. Validate with:

```powershell
Get-Content -LiteralPath 'release/baselines/v0.1.0-mvp.20260907.json' -Raw | ConvertFrom-Json | Out-Null
```

- [ ] **Step 5: Commit the baseline manifest**

Run:

```powershell
git add -- 'release/baselines/v0.1.0-mvp.20260907.json'
git commit -m "build: freeze MVP engineering baseline metadata"
```

### Task 7: Create the implementation record and run final verification

**Files:**
- Create: `共享记忆文档/实施记录/PhaseX-PX-00-架构师Agent-GitHubFlow与发布基线治理-001.md`
- Modify: `共享记忆文档/实施记录索引.md`
- Modify if evidence changed: `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md`
- Modify if evidence changed: `release/baselines/v0.1.0-mvp.20260907.json`

**Interfaces:**
- Consumes: Tasks 1–6 commits and actual verification outputs.
- Produces: complete audit trail, verified implementation branch, and final pre-merge documentation.

- [ ] **Step 1: Run repository safety checks**

Verify no tracked `.env`, model weight, virtual environment, `node_modules`, cache, log, or temporary test file. List tracked files over 25 MiB by path and size; expected: none unless an intentional test evidence artifact is documented.

- [ ] **Step 2: Run backend quality gates**

From `CRM智能聊天系统/backend` run `uv lock --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app scripts`, and `uv run pytest`. Record exact pass/skip/failure counts.

- [ ] **Step 3: Run frontend quality gates**

From `CRM智能聊天系统/frontend` run `npm run lint`, `npm run typecheck`, `npm run test`, and `npm run build`. Record exact test and page counts.

- [ ] **Step 4: Run repository and document consistency checks**

Validate JSON, YAML parseability where available, every real indexed Markdown target, migration 023 presence, frozen evaluation hashes, ignored-path behavior, and `git diff --check`.

- [ ] **Step 5: Write the implementation record and index entry**

Use all eleven mandated sections. Mark the status `已完成` only if the Git/source baseline and document synchronization pass; separately identify unavailable Docker/registry and production gates. Include every actual command and result without claiming skipped gates passed.

- [ ] **Step 6: Commit the final audit trail**

Run:

```powershell
git add -- '共享记忆文档/实施记录/PhaseX-PX-00-架构师Agent-GitHubFlow与发布基线治理-001.md' '共享记忆文档/实施记录索引.md' '架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md' 'release/baselines/v0.1.0-mvp.20260907.json'
git commit -m "docs: record GitHub Flow baseline implementation"
```

Expected: only files with final evidence changes are included.

### Task 8: Review, squash-merge, and tag the baseline

**Files:**
- No new files; Git history and annotated tag only.

**Interfaces:**
- Consumes: verified `docs/release-baseline-20260907` branch.
- Produces: one reviewed squash commit on `main` and annotated tag `v0.1.0-mvp.20260907`.

- [ ] **Step 1: Review the complete branch diff and commit list**

Run:

```powershell
git diff --check main...docs/release-baseline-20260907
git diff --stat main...docs/release-baseline-20260907
git log --oneline main..docs/release-baseline-20260907
```

Expected: no whitespace errors; changes match the approved scope.

- [ ] **Step 2: Confirm the branch is clean**

Run `git status --short`. Expected: no output.

- [ ] **Step 3: Locally squash-merge the bootstrap branch**

In the primary checkout:

```powershell
git switch main
git merge --squash docs/release-baseline-20260907
git commit -m "chore: establish GitHub Flow MVP baseline"
```

This is the documented no-remote bootstrap exception; future changes require GitHub Pull Requests.

- [ ] **Step 4: Create and verify the annotated tag**

Run:

```powershell
git tag -a v0.1.0-mvp.20260907 -m "MVP engineering baseline 2026-09-07; production not released"
git rev-list -n 1 v0.1.0-mvp.20260907
git show --no-patch --decorate v0.1.0-mvp.20260907
```

Expected: the tag resolves to the new `main` squash commit and the annotation states production is not released.

- [ ] **Step 5: Leave the repository ready for remote setup**

Do not invent or add a remote. Report the exact `main` commit, tag, Docker/image evidence status, tests, remaining production blockers, and the command sequence that the user should run after providing a GitHub repository URL.
