# Centralized Test Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every test source, AI eval dataset, and ordinary eval result into one categorized `src/tests/` tree while preserving all existing test behavior, CI gates, hashes, and startup behavior.

**Architecture:** Keep Python dependencies and application imports rooted at `src/backend/`, and Node dependencies rooted at `src/frontend/`, but make `src/tests/` the only tracked test-asset root. Framework commands discover sibling test directories through explicit configuration, path-sensitive tests use verified repository/source roots, and production images exclude test/eval assets because their build contexts remain module-scoped.

**Tech Stack:** Python 3.11, pytest, Ruff, mypy, Node.js 20 test runner, ESLint, Next.js, PowerShell, GitHub Actions, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-16-centralized-test-layout-design.md`

## Global Constraints

- `TEST_LAYOUT` becomes `centralized`; `src/tests/` is the only tracked root for test source, test-only data, ordinary AI eval datasets, and ordinary AI eval results.
- Keep formal TR files in `docs/reports/tests/` and frozen low-sensitivity release evidence in `release/evidence/`.
- Do not rewrite historical `docs/superpowers/**`, `docs/history/**`, or frozen `release/baselines/**` path facts.
- Do not change test assertions, product behavior, model thresholds, dataset contents, result contents, or release conclusions merely to make the move pass.
- Do not add empty `fixtures/`, `helpers/`, or `.artifacts/` directories. `src/tests/.artifacts/` remains ignored and is created only by commands that need it.
- Keep backend and frontend build contexts at `src/backend/` and `src/frontend/`; production images must not copy `src/tests/`.
- Preserve every moved eval file byte-for-byte; verify Git blob IDs against base SHA `17bb9bf9501ead60aafe8eed6bddc331f26c43f0`.
- Protect the unrelated clean worktree `docs/centralized-test-layout-design`; do not remove, switch, or modify it.

---

### Task 1: Centralize and classify backend tests

**Files:**
- Create: `src/tests/backend/_support.py`
- Move to `src/tests/backend/agent/`: all `src/backend/tests/test_agent_*.py`, plus `test_bge_fullstack.py`, `test_business_prompt_registry.py`, `test_knowledge_safety_metadata.py`, `test_local_retrieval_models.py`, `test_real_ai04_regressions.py`, `test_real_model_evaluation.py`, `test_real_model_evaluation_remediation.py`, `test_retrieval_model_service.py`, `test_retrieval_runtime_dependencies.py`, `test_tool_executor.py`
- Move to `src/tests/backend/auth_security/`: `test_auth_cookies.py`, `test_security.py`
- Move to `src/tests/backend/domain/`: `test_marketing_review_idempotency.py`, `test_phase3_domain.py`, `test_phase4_domain.py`
- Move to `src/tests/backend/platform/`: `test_platform_adapters.py`, `test_tiktok_oauth.py`, `test_tiktok_read.py`, `test_tiktok_write.py`
- Move to `src/tests/backend/runtime_infrastructure/`: `test_chat_worker_logging.py`, `test_health.py`, `test_production_gate_scripts.py`, `test_real_fs05_sse_runtime.py`, `test_real_runtime_config.py`, `test_repository_layout.py`, `test_rootless_staging_assets.py`, `test_sse_load_test.py`
- Modify: `src/backend/pyproject.toml`

**Interfaces:**
- Consumes: existing backend tests collected from `src/backend/tests/`, backend application imports from `src/backend/app/`, and current integration tests at `src/tests/integration/`.
- Produces: categorized backend tests, `BACKEND_ROOT`, `SOURCE_ROOT`, `REPOSITORY_ROOT`, and `TESTS_ROOT` constants from `_support.py`, plus pytest discovery of the new backend tree.

- [ ] **Step 1: Strengthen the layout test before moving files**

Add a failing test to the current `src/backend/tests/test_repository_layout.py`:

```python
def test_backend_tests_use_central_test_root() -> None:
    assert (SOURCE_ROOT / "tests" / "backend").is_dir()
    assert not (SOURCE_ROOT / "backend" / "tests").exists()
```

- [ ] **Step 2: Run the new contract and confirm the red state**

Run from `src/backend/`:

```powershell
uv run pytest tests/test_repository_layout.py::test_backend_tests_use_central_test_root -q
```

Expected: FAIL because `src/tests/backend/` does not exist and `src/backend/tests/` still exists.

- [ ] **Step 3: Create exact category directories and move all 40 backend tests**

Use `New-Item -ItemType Directory` for the five nonempty category directories, then `Move-Item -LiteralPath` for each explicit file listed in this task. Do not use a recursive wildcard move. Confirm:

```powershell
$old = @(Get-ChildItem -LiteralPath src/backend/tests -File -ErrorAction SilentlyContinue)
if ($old.Count -ne 0) { throw "Unmoved backend tests: $($old.Name -join ', ')" }
```

Remove the now-empty `src/backend/tests/` directory only after that check.

- [ ] **Step 4: Add stable Python path roots**

Create `src/tests/backend/_support.py` with:

```python
from pathlib import Path


def find_repository_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    raise AssertionError("Git repository root was not found")


REPOSITORY_ROOT = find_repository_root(Path(__file__).resolve())
SOURCE_ROOT = REPOSITORY_ROOT / "src"
BACKEND_ROOT = SOURCE_ROOT / "backend"
TESTS_ROOT = SOURCE_ROOT / "tests"
```

Replace fixed `parents[n]` and old test-relative backend paths in these moved files with imports from `_support`: `test_production_gate_scripts.py`, `test_real_fs05_sse_runtime.py`, `test_real_runtime_config.py`, `test_repository_layout.py`, `test_retrieval_runtime_dependencies.py`, and `test_rootless_staging_assets.py`. Logging-only uses of `__file__` remain unchanged.

- [ ] **Step 5: Update pytest discovery without moving integration tests yet**

Set in `src/backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["../tests/backend", "../tests/integration"]
pythonpath = [".", "../tests/backend"]
cache_dir = "../tests/.artifacts/pytest-cache"
```

- [ ] **Step 6: Run the backend layout and full deterministic suite**

Run from `src/backend/`:

```powershell
uv run pytest ../tests/backend/runtime_infrastructure/test_repository_layout.py -q
uv run pytest -q -rs
```

Expected: layout contract passes; full suite collects the same backend and integration tests as the base branch, with only environment-gated skips.

- [ ] **Step 7: Commit backend test centralization**

```powershell
git add -A -- src/backend/tests src/tests/backend src/backend/pyproject.toml
git commit -m "test: centralize backend test suites"
```

### Task 2: Put PostgreSQL integration tests in their final category

**Files:**
- Move: `src/tests/integration/README.md` to `src/tests/integration/postgres/README.md`
- Move: all six `src/tests/integration/test_*_postgres.py` files to `src/tests/integration/postgres/`
- Modify: `src/backend/pyproject.toml`
- Modify if command text names the old path: `src/scripts/run-postgres-integration-tests.ps1`

**Interfaces:**
- Consumes: pytest discovery and backend Python path from Task 1.
- Produces: one explicit PostgreSQL/pgvector integration category discovered by both `uv run pytest` and the isolated database script.

- [ ] **Step 1: Extend the layout test for the PostgreSQL category**

Add to `src/tests/backend/runtime_infrastructure/test_repository_layout.py`:

```python
def test_postgres_integration_tests_have_one_category() -> None:
    assert (TESTS_ROOT / "integration" / "postgres").is_dir()
    assert not list((TESTS_ROOT / "integration").glob("test_*.py"))
```

- [ ] **Step 2: Verify the new category contract fails**

```powershell
Set-Location src/backend
uv run pytest ../tests/backend/runtime_infrastructure/test_repository_layout.py::test_postgres_integration_tests_have_one_category -q
```

Expected: FAIL because tests still live directly under `src/tests/integration/`.

- [ ] **Step 3: Move the README and six tests with literal paths**

Create `src/tests/integration/postgres/`, move the seven tracked files, and remove the empty old directory. Change pytest configuration to:

```toml
testpaths = ["../tests/backend", "../tests/integration/postgres"]
```

- [ ] **Step 4: Verify discovery and the isolated database entry point**

Run:

```powershell
Set-Location src/backend
uv run pytest ../tests/integration/postgres --collect-only -q
Set-Location ../..
.\src\scripts\run-postgres-integration-tests.ps1
```

Expected: six PostgreSQL files are collected; the script runs migrations and the full pytest command against its isolated database, then removes the temporary test service.

- [ ] **Step 5: Commit integration classification**

```powershell
git add -A -- src/tests/integration src/backend/pyproject.toml src/scripts/run-postgres-integration-tests.ps1
git commit -m "test: classify postgres integration suites"
```

### Task 3: Move AI eval assets and repair all active consumers

**Files:**
- Move: five root files from `src/backend/evals/` to `src/tests/ai/datasets/`
- Move: all files from `src/backend/evals/results/` to `src/tests/ai/results/`
- Modify: `src/backend/scripts/evaluate_intents.py`
- Modify: `src/backend/scripts/evaluate_real_model.py`
- Modify: `src/backend/app/agent/security.py`
- Modify: moved tests `test_agent_evaluation.py`, `test_agent_phase4.py`, `test_real_model_evaluation.py`, `test_real_model_evaluation_remediation.py`
- Modify: `src/backend/.dockerignore`

**Interfaces:**
- Consumes: `TESTS_ROOT` from Task 1 and the byte-identical eval assets at base SHA.
- Produces: `src/tests/ai/datasets/`, `src/tests/ai/results/`, and CWD-independent defaults in evaluation scripts.

- [ ] **Step 1: Add a failing eval-location contract**

Add to the moved `test_agent_evaluation.py`:

```python
from _support import TESTS_ROOT


def test_versioned_eval_datasets_live_under_central_test_root() -> None:
    datasets = TESTS_ROOT / "ai" / "datasets"
    assert (datasets / "intent-classifier-v1.0.0.jsonl").is_file()
    assert (datasets / "faq-rag-v1.0.0.jsonl").is_file()
    assert not (TESTS_ROOT.parent / "backend" / "evals").exists()
```

- [ ] **Step 2: Verify the eval-location contract fails**

```powershell
Set-Location src/backend
uv run pytest ../tests/backend/agent/test_agent_evaluation.py::test_versioned_eval_datasets_live_under_central_test_root -q
```

Expected: FAIL because datasets still live under `src/backend/evals/`.

- [ ] **Step 3: Move datasets and results without editing contents**

Move these exact dataset files:

```text
agent-phase4-v1.0.0.jsonl
faq-rag-v1.0.0.jsonl
intent-classifier-v1.0.0.jsonl
real-model-v1.0.0.jsonl
real-model-v1.0.0.manifest.json
```

Move every tracked `src/backend/evals/results/*` file to `src/tests/ai/results/`, preserving each basename. Remove the empty `src/backend/evals/` tree.

- [ ] **Step 4: Make script defaults independent of the current directory**

In both `evaluate_intents.py` and `evaluate_real_model.py`, derive:

```python
TESTS_ROOT = Path(__file__).resolve().parents[2] / "tests"
DATASETS_ROOT = TESTS_ROOT / "ai" / "datasets"
```

Use `DATASETS_ROOT` for `DEFAULT_DATASET` and `DEFAULT_MANIFEST`. Keep `evaluate_rag.py` and `evaluate_phase4.py` explicit-argument interfaces unchanged. Change moved tests to use `_support.TESTS_ROOT / "ai" / "datasets"` rather than `Path("evals/..." )`. Update the security comment to name `src/tests/ai/datasets/real-model-v1.0.0.jsonl`.

- [ ] **Step 5: Remove the stale Docker ignore rule**

Delete only the obsolete `evals/reports` entry from `src/backend/.dockerignore`. Do not widen the backend build context and do not add `src/tests/` to the image.

- [ ] **Step 6: Prove byte identity and run eval-related tests**

For each moved asset, compare the base blob with the current file:

```powershell
$base = '17bb9bf9501ead60aafe8eed6bddc331f26c43f0'
$newRoots = @('src/tests/ai/datasets', 'src/tests/ai/results')
foreach ($newRoot in $newRoots) {
  Get-ChildItem -LiteralPath $newRoot -File | ForEach-Object {
    $oldRoot = if ($newRoot.EndsWith('datasets')) { 'src/backend/evals' } else { 'src/backend/evals/results' }
    $oldPath = "$oldRoot/$($_.Name)"
    $oldBlob = git rev-parse "$base`:$oldPath"
    $newBlob = git hash-object -- $_.FullName
    if ($oldBlob -ne $newBlob) { throw "Eval asset changed: $oldPath" }
  }
}
```

Then run from `src/backend/`:

```powershell
uv run pytest ../tests/backend/agent/test_agent_evaluation.py ../tests/backend/agent/test_agent_phase4.py ../tests/backend/agent/test_real_model_evaluation.py ../tests/backend/agent/test_real_model_evaluation_remediation.py -q
uv run python -c "from scripts.evaluate_intents import DEFAULT_DATASET; from scripts.evaluate_real_model import DEFAULT_DATASET as REAL, DEFAULT_MANIFEST; assert DEFAULT_DATASET.is_file() and REAL.is_file() and DEFAULT_MANIFEST.is_file()"
```

- [ ] **Step 7: Commit the eval migration**

```powershell
git add -A -- src/backend/evals src/tests/ai src/backend/scripts src/backend/app/agent/security.py src/tests/backend/agent src/backend/.dockerignore
git commit -m "test: centralize ai evaluation assets"
```

### Task 4: Centralize frontend contract tests

**Files:**
- Create: `src/tests/frontend/helpers/paths.mjs`
- Move: all five `src/frontend/tests/*.test.mjs` to `src/tests/frontend/contract/`
- Modify: all moved frontend tests that resolve source files
- Modify: `src/frontend/package.json`

**Interfaces:**
- Consumes: frontend source at `src/frontend/`, source-wide Compose/deploy assets at `src/`, and repository assets at the Git root.
- Produces: `sourceRoot`, `frontendRoot`, `repositoryRoot`, and `testsRoot` URL constants plus stable `npm run test` and `npm run lint` entry points.

- [ ] **Step 1: Extend the layout contract for frontend tests**

Add to `test_repository_layout.py`:

```python
def test_frontend_tests_use_central_test_root() -> None:
    assert (TESTS_ROOT / "frontend" / "contract").is_dir()
    assert not (SOURCE_ROOT / "frontend" / "tests").exists()
```

- [ ] **Step 2: Verify the frontend contract is red**

Run the single Python layout function and confirm it fails before the move.

- [ ] **Step 3: Move the five Node test files and create the shared path helper**

Create `src/tests/frontend/helpers/paths.mjs`:

```javascript
export const sourceRoot = new URL("../../../", import.meta.url);
export const repositoryRoot = new URL("../../../../", import.meta.url);
export const frontendRoot = new URL("../../../frontend/", import.meta.url);
export const testsRoot = new URL("../../", import.meta.url);
```

Move `compose.test.mjs`, `phase3.test.mjs`, `phase4.test.mjs`, `security.test.mjs`, and `tiktok-oauth.test.mjs` into `src/tests/frontend/contract/`. Import the helper with `../helpers/paths.mjs` and replace every old `../app`, `../lib`, `../components`, `../../`, and `../../../` source-location assumption with URLs based on the exported roots.

- [ ] **Step 4: Update frontend scripts**

Set in `src/frontend/package.json`:

```json
"lint": "eslint . ../tests/frontend",
"test": "node --test ../tests/frontend/contract/*.test.mjs"
```

- [ ] **Step 5: Run all frontend gates**

From `src/frontend/` run:

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```

Expected: lint has no errors, typecheck passes, all 40 Node assertions pass, and the production build completes.

- [ ] **Step 6: Commit frontend centralization**

```powershell
git add -A -- src/frontend/tests src/tests/frontend src/frontend/package.json
git commit -m "test: centralize frontend contract tests"
```

### Task 5: Make CI, documentation, and layout enforcement authoritative

**Files:**
- Modify: `AGENTS.md`
- Modify: `.gitignore`
- Modify: `.github/workflows/ci.yml`
- Modify if ownership is path-specific: `.github/CODEOWNERS`
- Modify: `README.md`
- Modify: `docs/governance/GOVERNANCE.md`
- Modify: `docs/engineering/DEVELOPMENT.md`
- Modify: `docs/quality/TEST-STRATEGY.md`
- Modify: `docs/quality/TEST-STATUS.md` only where current paths are named
- Modify: `src/tests/README.md`
- Modify: `src/tests/integration/postgres/README.md`
- Modify: `src/backend/app/agent/README.md`
- Modify: `src/tests/backend/runtime_infrastructure/test_repository_layout.py`
- Modify: `docs/memory/PROJECT-STATE.md`

**Interfaces:**
- Consumes: final directory layout and commands from Tasks 1–4.
- Produces: `TEST_LAYOUT: centralized`, one documented entry point, CI coverage of sibling tests, and a regression contract that rejects legacy test roots.

- [ ] **Step 1: Add the final centralized-layout regression assertions**

The repository layout test must assert:

```python
legacy_roots = (
    SOURCE_ROOT / "backend" / "tests",
    SOURCE_ROOT / "frontend" / "tests",
    SOURCE_ROOT / "backend" / "evals",
)
assert all(not path.exists() for path in legacy_roots)
assert (TESTS_ROOT / "backend").is_dir()
assert (TESTS_ROOT / "frontend" / "contract").is_dir()
assert (TESTS_ROOT / "integration" / "postgres").is_dir()
assert (TESTS_ROOT / "ai" / "datasets").is_dir()
assert (TESTS_ROOT / "ai" / "results").is_dir()
```

Use `git ls-files` only for stable tracked-path classification. Explicitly exempt `docs/reports/tests/`, `release/evidence/`, historical `docs/superpowers/`, and frozen `release/baselines/`.

- [ ] **Step 2: Route all project-local temporary output to the ignored artifact root**

Add `/src/tests/.artifacts/` to `.gitignore`. Document it as the only project-local test output root. Keep existing generic ignore rules for tool compatibility and prevent tracked artifacts with the layout test.

- [ ] **Step 3: Update CI quality paths**

In `.github/workflows/ci.yml`, keep job working directories unchanged and set backend commands to:

```yaml
- name: Run Ruff lint
  run: uv run ruff check . ../tests/backend ../tests/integration/postgres
- name: Check Ruff formatting
  run: uv run ruff format --check . ../tests/backend ../tests/integration/postgres
- name: Run backend tests
  run: uv run pytest
```

The frontend job continues to use `npm run lint` and `npm run test`, which now include sibling tests through `package.json`.

- [ ] **Step 4: Update current governance and developer documentation**

Change every active `TEST_LAYOUT: hybrid` statement to `TEST_LAYOUT: centralized`; document the exact target tree and commands. Add the rule that future tests, test-only fixtures/data, ordinary eval inputs/results, and local test outputs belong under `src/tests/`. Keep formal TR and release evidence exceptions explicit.

Update root and Agent README eval commands to use paths such as:

```powershell
uv run python -m scripts.evaluate_phase4 --dataset ../tests/ai/datasets/agent-phase4-v1.0.0.jsonl --output ../tests/.artifacts/ai/agent-phase4-deterministic.json
```

- [ ] **Step 5: Scan active files for old test paths**

Run `git grep` for `src/backend/tests`, `src/frontend/tests`, `src/backend/evals`, bare `evals/`, and `TEST_LAYOUT: hybrid`, excluding only historical specs/plans/history and frozen release baselines. Every remaining active match must be corrected or be an explicit legacy-path rejection assertion.

- [ ] **Step 6: Validate static configuration and links**

Run:

```powershell
git diff --check
Get-Content .github/workflows/ci.yml -Raw
Get-Content src/frontend/package.json -Raw | ConvertFrom-Json | Out-Null
Get-Content src/backend/pyproject.toml -Raw
```

Run a local Markdown link checker across changed current docs and parse every changed JSON file.

- [ ] **Step 7: Commit the centralized test contract**

```powershell
git add -- AGENTS.md .gitignore .github README.md docs src/tests src/backend/app/agent/README.md
git commit -m "ci: enforce centralized test layout"
```

### Task 6: Run final verification, review, and evidence closure

**Files:**
- Create: `docs/records/implementation/IR-TEST-001-20260916-R01.md`
- Create: `docs/reports/tests/TR-TEST-001-20260916-R01.md`
- Create: `docs/reports/reviews/RR-TEST-001-20260916-R01.md`
- Modify: `docs/records/implementation/IMPLEMENTATION-INDEX.md`
- Modify: `docs/reports/tests/TEST-INDEX.md`
- Modify: `docs/reports/reviews/REVIEW-INDEX.md`
- Modify: `docs/tasks/TASKS.md`
- Modify: `docs/memory/PROJECT-STATE.md`
- Modify: this implementation plan to mark completed checkboxes

**Interfaces:**
- Consumes: final centralized layout, commands, and acceptance criteria from the design.
- Produces: one candidate subject SHA, reproducible verification evidence, independent review, and an evidence-only tail.

- [ ] **Step 1: Mark the task `VERIFYING` and commit the final delivery subject**

Update `TEST-001` to `VERIFYING`, mark implementation-plan checkboxes complete as real steps finish, run `git diff --check`, and commit all remaining delivery files. Record `git rev-parse HEAD` as `CANDIDATE_SUBJECT_SHA`.

- [ ] **Step 2: Run complete backend quality gates on the candidate SHA**

From `src/backend/` run:

```powershell
uv lock --check
uv run ruff check . ../tests/backend ../tests/integration/postgres
uv run ruff format --check . ../tests/backend ../tests/integration/postgres
uv run mypy app scripts
uv run pytest -q -rs
```

Then run `.\src\scripts\run-postgres-integration-tests.ps1` from the repository root. Record pass/skip counts and confirm no collected test disappeared relative to the base.

- [ ] **Step 3: Run complete frontend gates on the candidate SHA**

From `src/frontend/` run:

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```

Record the Node assertion count and build result.

- [ ] **Step 4: Validate assets, paths, security, Compose, images, and startup**

Verify eval Git blob identity against the base SHA, parse changed JSON/YAML/PowerShell, check Markdown links, run `git diff --check`, scan added lines for secret patterns, and confirm no legacy active path remains.

Run all applicable Compose `config --quiet` combinations already listed in `TR-REPO-001-20260916-R01.md`. Build fresh backend and frontend images from the final candidate. Start an isolated Compose project with fresh volumes, verify backend health/readiness and frontend login return HTTP 200, then remove only that isolated project and its volumes.

- [ ] **Step 5: Request independent review**

Use `superpowers:requesting-code-review` with base SHA `17bb9bf9501ead60aafe8eed6bddc331f26c43f0` and the actual candidate subject SHA. Require review of classification completeness, test collection, CWD-independent paths, CI lint coverage, Docker context effects, eval hashes, documentation truth, and rollback. Fix every Critical/Important issue and rerun affected gates.

- [ ] **Step 6: Finalize IR/TR/RR and indexes**

Write FINAL/PASS/APPROVE records using the actual commands, counts, environment, residual risks, and candidate SHA. Regenerate all three indexes from source records. The evidence tail after the candidate may contain only IR/TR/RR, their indexes, `TASKS.md`, `PROJECT-STATE.md`, and this plan's completion bookkeeping.

- [ ] **Step 7: Close the task and commit evidence**

Set `TEST-001` to `DONE`, put the candidate subject SHA in its final column, set `PROJECT-STATE.md` to the real branch/subject and `Workspace hygiene: CLEAN`, then commit with:

```powershell
git add -- docs/records docs/reports docs/tasks/TASKS.md docs/memory/PROJECT-STATE.md docs/superpowers/plans/2026-09-16-centralized-test-layout.md
git commit -m "docs: record centralized test layout evidence"
```

- [ ] **Step 8: Merge locally and clean the task branch**

Use `superpowers:finishing-a-development-branch`. Because the user already selected local merge for this task, fast-forward local `main` only after merged-result verification passes. Do not pull, push, create a PR, or modify the remote. Delete `feature/unified-test-layout` with ordinary `git branch -d` and remove only the worktree created for that branch; preserve the unrelated `docs/centralized-test-layout-design` worktree.
