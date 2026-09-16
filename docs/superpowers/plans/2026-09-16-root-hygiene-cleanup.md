# Root Hygiene Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove inactive generated remnants from the repository root without deleting project assets or violating the mandatory retention window.

**Architecture:** Record one governed maintenance task and one cleanup batch, then move the two local-only candidates into the ignored persistent quarantine. Keep required root assets and the project worktree entry, verify the active root no longer contains the candidates, and defer permanent deletion until the recorded retention deadline.

**Tech Stack:** Git worktrees, PowerShell 7/Windows PowerShell, Markdown, JSON, Docker Compose configuration validation.

**Spec:** `docs/governance/GOVERNANCE.md` section eleven and the user-authorized root hygiene request of 2026-09-16.

## Global Constraints

- Do not delete or modify `.git/`, tracked project assets, release evidence, secrets, data, backups, migrations, or active worktrees.
- Keep `.worktrees/` because the project explicitly uses it as the ignored worktree root.
- Treat `frontend/` and `.test-tmp/` as local-only generated/test remnants; quarantine them under `.maintenance/quarantine/CLEANUP-20260916-001/`.
- Retain quarantined data through `2026-09-23T14:00:00+08:00`; permanent deletion requires a fresh exact-path authorization after that deadline.
- Do not run unrelated product regressions because no product source, runtime configuration, dependency, or behavior changes.

---

### Task 1: Register the cleanup candidate

**Files:**
- Modify: `docs/tasks/TASKS.md`
- Modify: `docs/memory/PROJECT-STATE.md`
- Create: `docs/operations/cleanup/CLEANUP-INDEX.md`
- Create: `docs/operations/cleanup/CLEANUP-20260916-001.md`
- Create: `docs/operations/cleanup/manifests/CLEANUP-20260916-001.json`

**Interfaces:**
- Consumes: Git baseline `c9128a5b2e1b6d102d90699b6b50da84a63820df` and the read-only root inventory.
- Produces: Task `MAINT-CLEANUP-20260916-001`, batch `CLEANUP-20260916-001`, exact candidates, hashes, restore commands, and retention deadline.

- [x] **Step 1: Add the maintenance task in `DOING` state**

Record the branch, base SHA, cleanup batch link, local-only scope, and verification criteria in `docs/tasks/TASKS.md`.

- [x] **Step 2: Create the batch record and manifest**

Record `frontend/` as a zero-byte generated cache tree containing only empty `.next/` and `node_modules/`, and `.test-tmp/` as a zero-byte test artifact containing the empty SHA-256 value `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

- [x] **Step 3: Update project recovery state**

Set workspace hygiene to `CANDIDATE` and identify the active cleanup task and batch without storing machine absolute paths.

- [x] **Step 4: Validate and commit the candidate records**

Run JSON parsing, Markdown link validation, `git diff --check`, and `git status --short`, then commit with `docs: register root hygiene cleanup batch`.

### Task 2: Quarantine and verify the local remnants

**Files:**
- Move locally: `frontend/` to `.maintenance/quarantine/CLEANUP-20260916-001/frontend/`
- Move locally: `.test-tmp/` to `.maintenance/quarantine/CLEANUP-20260916-001/.test-tmp/`
- Modify: `docs/operations/cleanup/CLEANUP-20260916-001.md`
- Modify: `docs/operations/cleanup/manifests/CLEANUP-20260916-001.json`
- Modify: `docs/operations/cleanup/CLEANUP-INDEX.md`
- Modify: `docs/tasks/TASKS.md`
- Modify: `docs/memory/PROJECT-STATE.md`

**Interfaces:**
- Consumes: The candidate manifest and the primary checkout containing the local-only remnants.
- Produces: A root without the two inactive paths, a persistent recoverable quarantine, and verified recovery metadata.

- [x] **Step 1: Reconfirm exact candidates immediately before movement**

Verify both paths resolve beneath the repository root, are not reparse points, are untracked, contain no nonempty file, have no tracked references, and are unrelated to an active worktree.

- [x] **Step 2: Move candidates into persistent quarantine**

Create `.maintenance/quarantine/CLEANUP-20260916-001/`, then use literal-path moves for the exact `frontend` and `.test-tmp` directories. Do not use wildcards or recursive deletion.

- [x] **Step 3: Verify active-root removal and restoration metadata**

Confirm the original paths no longer exist, the quarantine copies match the manifest, `.worktrees/` remains available, tracked files are unchanged, and Docker Compose parses from `src/compose/docker-compose.yml`.

- [x] **Step 4: Finalize the batch as `VERIFIED_UNUSED`**

Update the batch, manifest, index, task, and project state with the actual result. Keep permanent deletion pending until the retention deadline.

- [x] **Step 5: Validate and commit the final records**

Run JSON parsing, Markdown link validation, `git diff --check`, and focused repository layout checks, then commit with `docs: record quarantined root remnants`.
