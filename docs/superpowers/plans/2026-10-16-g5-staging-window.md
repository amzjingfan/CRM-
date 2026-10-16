# G5 Staging SSE Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reviewed, reversible staging configuration mode for G5 SSE testing without activating it in this change.

**Architecture:** Reuse the current `staging-gates.yml` dispatch and `Test-StagingProductionGates.ps1` validation/deployment path. A fixed last Compose overlay enables DeepSeek suggestions and a 60-request single-IP limit only for backend. The default staging overlay explicitly restores LLM off, SSE test off, and limit 10. The gate validates the merged config before any deployment and checks runtime flags and health after deployment.

**Tech Stack:** GitHub Actions, PowerShell, Docker Compose, Python/pytest contract tests.

**Spec:** `docs/tasks/TASKS.md` MVP-006; `docs/quality/TEST-STRATEGY.md` G5; approved in-chat G5 staging window design, 2026-10-16.

## Global Constraints

- Code and CI only in this change; no staging switch, DeepSeek call, or production deployment.
- Staging mode requires exact immutable backend, frontend, and retrieval image digests and Rootless Docker.
- G5 mode and TikTok Webhook read mode are mutually exclusive.
- Only backend may have LLM and SSE load testing enabled; TikTok writes, automatic replies, translation, marketing, and worker model use remain disabled.
- Default mode must restore `LLM_ENABLED=false`, `SSE_LOAD_TEST_ENABLED=false`, and `CHAT_QUERY_LIMIT=10`.

## Review Focus

- Wrong environment or combination of G2 and G5 modes must fail before Docker mutation.
- A merged Compose config that enables model use in worker, jobs, or agent-worker must fail closed.
- A rate limit below 50 or above the approved 60 must not count as G5 mode.
- Missing DeepSeek configuration must fail without printing secret values.
- Post-deployment runtime configuration or health mismatch must not create a passing evidence record.

---

### Task 1: Compose and dispatch contract

**Files:** `src/compose/docker-compose.rootless-staging.yml`, `src/compose/docker-compose.rootless-staging-g5-sse.yml`, `.github/workflows/staging-gates.yml`, `src/tests/backend/runtime_infrastructure/test_production_gate_scripts.py`.

- [ ] Add failing contract tests for the fixed G5 overlay, default restoration, opt-in dispatch, and mode exclusion.
- [ ] Run targeted pytest and confirm failure due to missing behavior.
- [ ] Add the minimal Compose overlay and dispatch plumbing.
- [ ] Run targeted pytest until green.

### Task 2: Gate and runtime checks

**Files:** `src/scripts/Test-StagingProductionGates.ps1`, `src/tests/backend/runtime_infrastructure/test_production_gate_scripts.py`.

- [ ] Add failing tests for valid/invalid merged G5 config and runtime flags.
- [ ] Run targeted pytest and confirm expected failures.
- [ ] Extend the existing gate with fixed mode checks, low-sensitive evidence, and post-deployment runtime validation.
- [ ] Run targeted pytest until green, then PowerShell syntax and relevant safety regression tests.

### Task 3: Documentation and evidence

**Files:** `docs/operations/DEPLOYMENT.md`, `docs/quality/TEST-STRATEGY.md`, `src/deploy/staging/rootless/README.md`, `docs/records/implementation/`, `docs/reports/tests/`, `docs/reports/reviews/`, `docs/memory/PROJECT-STATE.md`.

- [ ] Document validation, precise staging activation, default-mode recovery, and the remaining G5 gates.
- [ ] Run relevant format/lint/tests and inspect the final diff for secrets and scope.
- [ ] Commit the subject, record its SHA in IR/TR/RR, open a task-linked PR, verify CI, and merge under the project gate.
