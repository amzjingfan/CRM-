# Department Reception Assignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make fixed customer-service roles and store-specific automatic consultation assignment work for one department while retaining ordinary-agent manual transfer.

**Architecture:** Extend the existing modular monolith with store reception configuration, short-lived presence and one assignment module called by both inbound paths and the existing Worker queue loop. Reuse `user_roles`, `department_members`, `Conversation.assigned_user_id`, audit and existing workspace routes; keep all platform-send switches unchanged.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Next.js/React, TypeScript, pytest, Node contract/browser tests.

**Spec:** `docs/superpowers/specs/2026-10-29-department-reception-assignment-design.md`

## Global Constraints

- Single active customer-service department in this phase; no cross-department routing or arbitrary role builder.
- Existing `agent` transfer remains available; department membership alone never grants store access.
- Store auto-assignment defaults off; no TikTok message is sent by assignment.
- All new test assets stay under `src/tests/`; staging deployment requires the user's explicit approval.
- Collect all discovered defects and fix them on this branch before one PR and one deployment request.

## Review Focus

- A user with `supervisor` on store A and `agent` on store B must never gain reply access to store A through a global permission union.
- A duplicate or concurrent inbound event must never overwrite a manual transfer or allocate two owners.
- A historical read-only backfill must never flood the live assignment queue.
- A stale or forged heartbeat must never make another user eligible.
- A revoked or disabled agent must never receive new work or retain effective write access.

---

### Task 1: Role and ownership enforcement

**Files:** `src/backend/app/auth/store_access.py`, `src/backend/app/workspace/service.py`, `src/backend/app/workspace/repository.py`, `src/backend/app/users/department_service.py`, `src/tests/backend/auth_security/`, `src/tests/integration/postgres/`.

- [ ] Add failing cross-store, other-owner, self-transfer, supervisor-view and revoked-role tests.
- [ ] Implement store-scoped permission queries and server-enforced conversation visibility/write rules; preserve administrator bypass and agent transfer of own conversations.
- [ ] Run focused auth/workspace tests and repair every discovered regression.

### Task 2: Reception settings, presence and migration

**Files:** new migration after `041_merge_agent_multishop_collab`, `src/backend/app/users/models.py`, `src/backend/app/conversations/models.py`, new reception assignment module and routes, `src/tests/backend/domain/`, `src/tests/integration/postgres/`.

- [ ] Add failing tests for admin-only configuration, store/department intersection, CSRF, audit, self-only heartbeat, timeout, capacity and default-off migration.
- [ ] Implement reversible schema and configuration routes; no external platform operations.
- [ ] Verify upgrade/downgrade in isolated PostgreSQL and all permission negatives.

### Task 3: Deterministic dispatch and queue

**Files:** new `src/backend/app/reception_assignment/` module, `src/backend/app/integrations/service.py`, `src/backend/app/integrations/conversation_sync.py`, `src/backend/app/integrations/worker.py`, `src/backend/app/workspace/service.py`, focused tests.

- [ ] Add failing tests for owner preservation, last human responder, least pending, tie-break, idempotency, concurrent Worker, no candidates, retry, manual precedence and no outgoing message.
- [ ] Implement one transactional assignment path and shared invocation from Webhook/sync; retry existing unassigned queue without rewriting historical conversations.
- [ ] Run focused domain and PostgreSQL concurrency tests; fix all discovered issues before moving to UI.

### Task 4: Department and workspace UI

**Files:** `src/frontend/app/settings/team/departments/page.tsx`, `src/frontend/app/workspace/page.tsx`, `src/frontend/lib/api.ts`, affected CSS and tests under `src/tests/frontend/`.

- [ ] Add failing contract/browser cases for fixed role display, store reception configuration, unavailable agents, heartbeat/pause, ordinary-agent transfer and queue information.
- [ ] Implement the controls and API types using existing page patterns and explicit failure states.
- [ ] Run lint, typecheck, contract, browser and production build; repair the full list of defects on this branch.

### Task 5: Integrated verification, docs and release gate

**Files:** `docs/product/PRODUCT.md`, `docs/architecture/API.md`, `docs/architecture/SYSTEM.md`, `docs/quality/TEST-STATUS.md`, `docs/tasks/TASKS.md`, IR/TR/RR and derived indexes.

- [ ] Run full affected backend and frontend suites, isolated migration/concurrency tests, secret scan and manual security review on the final subject SHA.
- [ ] Record real commands and results, update current docs and evidence, review the complete diff and inspect the full defect list.
- [ ] Create one PR only after all known defects are fixed; meet repository merge gate and verify main. Prepare staging backup, ValidateOnly and rollout review, then request the user's explicit deployment approval before Deploy.
