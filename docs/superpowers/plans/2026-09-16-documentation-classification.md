# Documentation Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the maintained `docs/` files by stable responsibility while preserving their facts and repairing every active reference.

**Architecture:** Keep `docs/README.md` as the single navigation entry, move ten maintained documents into product, architecture, engineering, quality, operations, governance, and history domains, and leave task, memory, quality strategy, and Superpowers process history in their existing locations. Update only active references; historical specifications and plans retain the paths that were true when written.

**Tech Stack:** Git worktree, Markdown, PowerShell, Git path and diff validation

**Spec:** `docs/superpowers/specs/2026-09-16-documentation-classification-design.md`

## Global Constraints

- Governance tier remains `STANDARD`.
- Do not modify application source, test source, dependencies, CI, containers, runtime configuration, product facts, interface conclusions, test conclusions, or release conclusions.
- `docs/README.md` remains the only documentation navigation entry.
- `docs/tasks/TASKS.md` remains the only task-state source.
- Keep `docs/superpowers/specs/` and `docs/superpowers/plans/` in place and do not rewrite older files in those directories.
- Do not create compatibility copies, category-level `README.md` files, redirects, generators, or new dependencies.
- This is a static documentation change; run documentation and Git validation, not unrelated product regression tests.
- Do not push, create or merge a Pull Request, tag, release, or deploy.

---

### Task 1: Register the documentation maintenance task and move the canonical files

**Files:**
- Modify: `docs/tasks/TASKS.md`
- Move: `docs/product.md` → `docs/product/PRODUCT.md`
- Move: `docs/architecture.md` → `docs/architecture/SYSTEM.md`
- Move: `docs/api.md` → `docs/architecture/API.md`
- Move: `docs/ai.md` → `docs/architecture/AI.md`
- Move: `docs/development.md` → `docs/engineering/DEVELOPMENT.md`
- Move: `docs/test-status.md` → `docs/quality/TEST-STATUS.md`
- Move: `docs/deployment.md` → `docs/operations/DEPLOYMENT.md`
- Move: `docs/release-gates.md` → `docs/operations/RELEASE-GATES.md`
- Move: `docs/governance.md` → `docs/governance/GOVERNANCE.md`
- Move: `docs/history.md` → `docs/history/PROJECT-HISTORY.md`

**Interfaces:**
- Consumes: the approved mapping in the design specification and base SHA `318d0e0272a580e0eb36f17e6188944276d2c9be`.
- Produces: one canonical location for every maintained document and a `DOCS-001` task row in `DOING` state on branch `codex/docs-classify-documentation`.

- [ ] **Step 1: Add the maintenance task before changing canonical paths**

Add a `P2：仓库与文档维护` section to `docs/tasks/TASKS.md` with this row:

```markdown
| DOCS-001 | 按职责域分类 `docs/` 当前文档并修复活动引用，不改变项目事实 | 本设计规格的 7 项验收标准 | DOING | codex/docs-classify-documentation | none | N/A | N/A | N/A（纯文档路径重组） | |
```

Keep the task table columns identical to the existing tables. Use `apply_patch` so the diff remains reviewable.

- [ ] **Step 2: Create the target directories and move tracked files**

Run these exact moves from the isolated worktree:

```powershell
New-Item -ItemType Directory -Force docs/product,docs/architecture,docs/engineering,docs/operations,docs/governance,docs/history | Out-Null
git mv docs/product.md docs/product/PRODUCT.md
git mv docs/architecture.md docs/architecture/SYSTEM.md
git mv docs/api.md docs/architecture/API.md
git mv docs/ai.md docs/architecture/AI.md
git mv docs/development.md docs/engineering/DEVELOPMENT.md
git mv docs/test-status.md docs/quality/TEST-STATUS.md
git mv docs/deployment.md docs/operations/DEPLOYMENT.md
git mv docs/release-gates.md docs/operations/RELEASE-GATES.md
git mv docs/governance.md docs/governance/GOVERNANCE.md
git mv docs/history.md docs/history/PROJECT-HISTORY.md
```

- [ ] **Step 3: Verify the mapping before reference edits**

Run:

```powershell
git status --short
git diff --summary
```

Expected: ten delete/add or rename pairs plus the intentional task-file edit; no source or configuration paths.

- [ ] **Step 4: Commit the canonical path moves**

```powershell
git add docs/tasks/TASKS.md docs/product docs/architecture docs/engineering docs/quality docs/operations docs/governance docs/history
git commit -m "docs: classify canonical documentation"
```

### Task 2: Rebuild navigation and repair all active references

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: `docs/tasks/TASKS.md`
- Modify: `docs/memory/PROJECT-STATE.md`
- Modify: `docs/quality/TEST-STRATEGY.md`
- Modify: `docs/quality/TEST-STATUS.md`
- Modify: `docs/operations/DEPLOYMENT.md`
- Modify: `docs/governance/GOVERNANCE.md`

**Interfaces:**
- Consumes: canonical paths created by Task 1.
- Produces: current instructions and navigation that resolve only to the new canonical paths; historical `docs/superpowers/**` content remains untouched.

- [ ] **Step 1: Replace repository-relative rule references in `AGENTS.md`**

Use `apply_patch` for these exact mappings:

```text
docs/product.md        -> docs/product/PRODUCT.md
docs/development.md    -> docs/engineering/DEVELOPMENT.md
docs/governance.md     -> docs/governance/GOVERNANCE.md
```

- [ ] **Step 2: Rewrite the `docs/README.md` map by responsibility**

Keep the facts-priority and maintenance rules, but replace every old path with the new canonical path. Group the map under these responsibilities:

```text
产品：product/PRODUCT.md
架构与接口：architecture/SYSTEM.md, architecture/API.md, architecture/AI.md
工程：engineering/DEVELOPMENT.md
质量：quality/TEST-STRATEGY.md, quality/TEST-STATUS.md
运维与发布：operations/DEPLOYMENT.md, operations/RELEASE-GATES.md
治理与任务：governance/GOVERNANCE.md, tasks/TASKS.md
恢复与历史：memory/PROJECT-STATE.md, history/PROJECT-HISTORY.md
过程文档：superpowers/specs/, superpowers/plans/
```

State explicitly that category directories do not add their own indexes and that older Superpowers documents are historical records.

- [ ] **Step 3: Repair relative links from nested maintained documents**

Use `apply_patch` and these target paths:

```text
docs/memory/PROJECT-STATE.md:
  ../product.md              -> ../product/PRODUCT.md
  ../architecture.md         -> ../architecture/SYSTEM.md
  ../api.md                  -> ../architecture/API.md
  ../ai.md                   -> ../architecture/AI.md
  ../development.md          -> ../engineering/DEVELOPMENT.md
  ../governance.md           -> ../governance/GOVERNANCE.md
  ../test-status.md          -> ../quality/TEST-STATUS.md
  ../deployment.md           -> ../operations/DEPLOYMENT.md
  ../release-gates.md        -> ../operations/RELEASE-GATES.md

docs/tasks/TASKS.md:
  ../product.md              -> ../product/PRODUCT.md
  ../release-gates.md        -> ../operations/RELEASE-GATES.md
  ../governance.md           -> ../governance/GOVERNANCE.md

Repository-relative prose in current documents:
  docs/product.md            -> docs/product/PRODUCT.md
  docs/api.md                -> docs/architecture/API.md
  docs/architecture.md       -> docs/architecture/SYSTEM.md
  docs/ai.md                 -> docs/architecture/AI.md
  docs/development.md        -> docs/engineering/DEVELOPMENT.md
  docs/deployment.md         -> docs/operations/DEPLOYMENT.md
  docs/release-gates.md      -> docs/operations/RELEASE-GATES.md
  docs/test-status.md        -> docs/quality/TEST-STATUS.md
  docs/governance.md         -> docs/governance/GOVERNANCE.md
  docs/history.md            -> docs/history/PROJECT-HISTORY.md
```

This includes the known references in `docs/quality/TEST-STRATEGY.md`, `docs/quality/TEST-STATUS.md`, `docs/operations/DEPLOYMENT.md`, and `docs/governance/GOVERNANCE.md`.

- [ ] **Step 4: Move `DOCS-001` to `VERIFYING`**

In `docs/tasks/TASKS.md`, change only the `DOCS-001` state from `DOING` to `VERIFYING`.

- [ ] **Step 5: Scan active files for old paths**

Run:

```powershell
git grep -n -E '(docs/|\.\./)?(product|api|architecture|ai|development|deployment|release-gates|test-status|governance|history)\.md' -- ':!docs/superpowers/**'
```

Expected: no output. If output appears, update only active references and rerun until empty.

- [ ] **Step 6: Commit navigation and reference repairs**

```powershell
git add AGENTS.md docs
git commit -m "docs: repair classified documentation links"
```

Record the resulting commit SHA as `CANDIDATE_SUBJECT_SHA` for Task 3.

### Task 3: Validate the classified documentation and close the task

**Files:**
- Modify: `docs/tasks/TASKS.md`

**Interfaces:**
- Consumes: the `CANDIDATE_SUBJECT_SHA` produced by Task 2.
- Produces: validation evidence in command output and a `DOCS-001` row in `DONE` state whose final SHA points to the validated subject commit.

- [ ] **Step 1: Verify exact old and new paths**

Run a PowerShell assertion over all ten mappings. Expected: every old path is absent and every new path is a tracked file.

```powershell
$mapping = [ordered]@{
  'docs/product.md'='docs/product/PRODUCT.md'; 'docs/architecture.md'='docs/architecture/SYSTEM.md';
  'docs/api.md'='docs/architecture/API.md'; 'docs/ai.md'='docs/architecture/AI.md';
  'docs/development.md'='docs/engineering/DEVELOPMENT.md'; 'docs/test-status.md'='docs/quality/TEST-STATUS.md';
  'docs/deployment.md'='docs/operations/DEPLOYMENT.md'; 'docs/release-gates.md'='docs/operations/RELEASE-GATES.md';
  'docs/governance.md'='docs/governance/GOVERNANCE.md'; 'docs/history.md'='docs/history/PROJECT-HISTORY.md'
}
foreach ($pair in $mapping.GetEnumerator()) {
  if (Test-Path -LiteralPath $pair.Key) { throw "Old path remains: $($pair.Key)" }
  if (-not (Test-Path -LiteralPath $pair.Value -PathType Leaf)) { throw "New path missing: $($pair.Value)" }
  git ls-files --error-unmatch -- $pair.Value | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "New path is untracked: $($pair.Value)" }
}
```

- [ ] **Step 2: Validate active Markdown local links**

Run this read-only PowerShell link checker over tracked Markdown files. It excludes historical Superpowers documents, external URLs, mail links and same-file anchors. Expected: `broken_links=0`.

```powershell
$broken = [System.Collections.Generic.List[string]]::new()
$markdownFiles = git ls-files '*.md' | Where-Object { $_ -notlike 'docs/superpowers/*' }
foreach ($file in $markdownFiles) {
  $content = Get-Content -Raw -LiteralPath $file
  foreach ($match in [regex]::Matches($content, '!?(?:\[[^\]]*\])\((?<target>[^)]+)\)')) {
    $target = $match.Groups['target'].Value.Trim().Trim('<','>')
    if ($target -match '^(?:https?://|mailto:|#)' -or [string]::IsNullOrWhiteSpace($target)) { continue }
    $pathPart = [uri]::UnescapeDataString(($target -split '#', 2)[0])
    if ([string]::IsNullOrWhiteSpace($pathPart)) { continue }
    $resolved = Join-Path (Split-Path -Parent $file) $pathPart
    if (-not (Test-Path -LiteralPath $resolved)) { $broken.Add("$file -> $target") }
  }
}
if ($broken.Count -gt 0) { $broken; throw "Broken local Markdown links: $($broken.Count)" }
"broken_links=$($broken.Count)"
```

- [ ] **Step 3: Validate scope and formatting**

Run:

```powershell
git diff --check 318d0e0272a580e0eb36f17e6188944276d2c9be..HEAD
git diff --name-only 318d0e0272a580e0eb36f17e6188944276d2c9be..HEAD
git status --short --branch
```

Expected: `git diff --check` is empty; changed files are limited to `AGENTS.md` and `docs/**`; the worktree is clean before the task-closing edit.

- [ ] **Step 4: Scan changed content for obvious sensitive material**

Run this case-insensitive scan of added branch-diff lines for private keys and common secret assignments. Expected: `sensitive_matches=0`.

```powershell
$added = git diff --unified=0 318d0e0272a580e0eb36f17e6188944276d2c9be..HEAD | Where-Object { $_ -match '^\+(?!\+\+)' }
$sensitive = $added | Select-String -Pattern '-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?i)(?:token|secret|password|api[_-]?key)\s*[:=]\s*["'']?[A-Za-z0-9_./+=-]{8,}'
if ($sensitive) { $sensitive; throw "Sensitive-looking added content found" }
'sensitive_matches=0'
```

- [ ] **Step 5: Close `DOCS-001` with real evidence**

After Steps 1–4 pass, use `apply_patch` to change the task state from `VERIFYING` to `DONE` and set `最终 SHA` to the Task 2 `CANDIDATE_SUBJECT_SHA`. Keep IR/TR/RR as the documented `N/A` values because this change is static documentation organization, not product behavior.

- [ ] **Step 6: Commit task closure and rerun final Git checks**

```powershell
git add docs/tasks/TASKS.md
git commit -m "docs: close documentation classification task"
git diff --check 318d0e0272a580e0eb36f17e6188944276d2c9be..HEAD
git status --short --branch
```

Expected: final diff check is empty and the worktree is clean. Do not claim push, PR, merge, release, or deployment.
