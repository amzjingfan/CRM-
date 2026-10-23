# Basic Reception UI and Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add screenshot-aligned basic reception management and workspace quick replies while preserving manual confirmation and disabling all automatic buyer sends.

**Architecture:** A new `app.reception` module owns configuration tables and routes independent of the marketing worker. Marketing subpages use those APIs; the workspace picker loads only replies available to the current store and inserts text into the existing draft/review flow.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, PostgreSQL, Next.js 16, React 19, TypeScript, Phosphor icons.

**Spec:** [2026-10-23-basic-reception-ui-config-design.md](../specs/2026-10-23-basic-reception-ui-config-design.md)

## Global Constraints

- No automatic TikTok send, no marketing worker hook, no production release.
- All configuration requests enforce allowed store IDs; personal replies belong only to their owner.
- Team writes and policy writes require `marketing.manage`; quick reply use still requires the existing manual review before real send.
- Only text segments are persisted and sent; media controls explicitly report unavailable.
- Tests and temporary output stay under `src/tests/`; migration revision follows 027.

## Review Focus

- A user with one store must not read or modify another store's groups, replies, or policies.
- A different employee must not see private replies; an agent must not modify team content.
- Editing a multi-store policy must not silently retain or attach an unauthorized store.
- A quick reply with multiple segments must not exceed 2000 characters when joined into one draft.
- Enabling a strategy configuration must not create an event, invoke a worker, or send a TikTok message.

---

### Task 1: Backend configuration contracts

**Files:** Create `src/backend/app/reception/{models,schemas,repository,service,router}.py`, `src/backend/migrations/versions/028_basic_reception_config.py`; modify `src/backend/app/api/v1/router.py`, `src/backend/app/shared/database/models.py`; test in `src/tests/backend/domain/test_reception_config.py` and `src/tests/backend/auth_security/test_reception_access.py`.

**Interfaces:** Produce GET/POST/PATCH/DELETE for `/marketing/reception/groups`, `/replies`, `/policies` with the spec's fields. List replies takes `store_id`, `scope`, optional `group_id`/`q`; policy list takes `store_id`, `kind`. Every policy view includes `delivery_enabled: false`.

- [ ] Write failing tests for personal/team visibility, cross-store 404, content/shortcut validation, policy store edits, and enabled configuration without send/event creation.
- [ ] Run only those tests and confirm the expected failures.
- [ ] Implement models/migration, service and routes using current auth/CSRF/idempotency/audit patterns; keep `marketing.worker` untouched.
- [ ] Run focused pytest, Ruff, format, mypy, and migration upgrade/downgrade/upgrade in isolated test PostgreSQL.
- [ ] Commit the backend and test files as one reviewed unit.

### Task 2: Marketing management pages

**Files:** Create `src/frontend/lib/reception.ts`, `src/frontend/components/QuickReplyManager.tsx`, `src/frontend/components/ReceptionPolicyManager.tsx`, `src/frontend/app/marketing/reception/{quick-replies,timeout,welcome}/page.tsx`, `src/frontend/app/marketing/reception/reception.css`; modify `src/frontend/components/AppShell.tsx`; test under `src/tests/frontend/contract/` and `src/tests/frontend/browser/`.

**Interfaces:** `reception.ts` exports `QuickReplyGroup`, `QuickReply`, `ReceptionPolicy`, and CRUD functions matching Task 1. It exports `listQuickReplies(storeId, scope)` for Task 3. Management pages use the existing `requestApi` helper, select an authorized store, and never call a send endpoint.

- [ ] Write failing contract/browser tests for navigation, personal/team tabs, group modal, reply form/preview/search, policy list/filter/CRUD and config-only banner.
- [ ] Implement manager pages and scoped styles, reusing existing buttons, states and Phosphor icons.
- [ ] Verify text-only validation, error retention, delete confirmation, keyboard access and narrow viewport.
- [ ] Run focused frontend tests, lint, typecheck and build; commit this unit.

### Task 3: Workspace composer and picker

**Files:** Create `src/frontend/components/QuickReplyPicker.tsx` and `src/frontend/app/workspace/quick-reply.css`; modify `src/frontend/app/workspace/page.tsx`; test under `src/tests/frontend/contract/` and `src/tests/frontend/browser/`.

**Interfaces:** Picker consumes `QuickReply` and `listQuickReplies(storeId, scope)`; callbacks `onDraft(content)` and `onReview(content)` respectively fill the current session draft and open the existing exact-content confirmation. Its API does not call `sendMessage`.

- [ ] Write failing browser tests for opening/filtering picker, slash shortcut, inserting editable draft, existing review dialog, media-disabled state, session switch and logistics-card coexistence.
- [ ] Implement toolbar/picker with compact, accessible popover and preserve existing translation and send controls.
- [ ] Run focused browser/contract tests, lint, typecheck and build; commit this unit.

### Task 4: Docs, integrated verification and staging handoff

**Files:** Modify `docs/product/PRODUCT.md`, `docs/architecture/{API,SYSTEM}.md`, `docs/tasks/TASKS.md`, `docs/memory/PROJECT-STATE.md`; write actual IR/TR/RR and update derived indexes after running checks.

- [ ] Reconcile API, non-execution boundary, task state and migration facts in current docs.
- [ ] Run backend/frontend affected suites and migration checks against final subject SHA; record exact results and unrun risks.
- [ ] Review diff, secrets and workspace hygiene; open the task PR and merge only after applicable gates.
- [ ] If staging is deployed, use direct manual preflight, backup, immutable images, migration, health and authenticated read-only UI checks; leave production No-Go.
