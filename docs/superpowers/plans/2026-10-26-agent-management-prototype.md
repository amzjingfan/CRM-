# Agent Management Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Agent management page match the supplied v3 prototype, persist safe settings and file bindings, and retrieve approved bound files in the Agent workflow with an end-to-end RAG timeout.

**Architecture:** Extend the existing Agent configuration JSON contract with a type and validated file IDs. Add version-level internal approval and a bound-file retrieval port, reusing existing structured generation and safety review. Bound-file Embedding, SQL and Rerank share a hard deadline. Render the prototype as a scoped React page using real store data; keep model, Prompt and automatic-send demonstration outside runtime configuration.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Next.js, React, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-26-agent-management-prototype-design.md`

## Global Constraints

- No TikTok send, real model call, or document retrieval from the local preview. Real Agent runs may call the approved bound-file RAG path.
- Bind only imported files in the authorized store; exclude archived/deleted files from new bindings.
- Only an explicitly approved current ready version may enter file retrieval; timeout fails closed.
- Keep existing Agent and knowledge APIs compatible with historical configurations.

## Review Focus

- Store switch while file or log request is pending: old response must not render.
- Deleted or archived bound file: show unavailable state and permit unbinding.
- Enabled service changed to operations: disable it atomically.
- Invalid model/Prompt payload: still rejected by the API.
- Missing Agent or store: page remains usable with clear empty state.
- Bound file replaced, archived or deleted after approval: it must disappear from retrieval immediately.
- Embedding, SQL or Rerank hangs: total RAG deadline wins and leaves a fixed failed run code.

---

### Task 1: Persist safe Agent metadata and file bindings

**Files:** `src/backend/app/agent_management/{schemas,service,repository}.py`, `src/tests/backend/domain/test_phase4_domain.py`, new focused backend tests.

- [ ] Add failing tests for type/defaults, file scope rejection and operations enable guard.
- [ ] Implement typed `agent_type` and `file_ids`, scoped validation, audited updates and read view.
- [ ] Run focused backend tests, Ruff, format and mypy.

### Task 2: Build the prototype page using real APIs

**Files:** `src/frontend/app/agents/page.tsx`, `src/frontend/app/agents/agent-prototype.css`, `src/frontend/lib/api.ts`, `src/frontend/components/AppShell.tsx` if shared navigation needs parity.

- [ ] Add browser tests for store scope, create/edit, tabs, file binding, preview and modal.
- [ ] Implement the prototype layout and interactions with request generation guards.
- [ ] Verify responsive layout and no model/TikTok request in preview.

### Task 3: Approve and retrieve bound file versions safely

**Files:** `src/backend/app/knowledge_base/{document_models,document_router,document_service,document_api_schemas,document_vector_port}.py`, `src/backend/app/agent/{rag,workflow,schemas,factory,reply_rendering}.py`, `src/backend/app/chat/service.py`, migration `033`, focused backend/integration tests.

- [ ] Add failing tests for approval, store/current-version gates, file hits and retrieval deadline.
- [ ] Implement migration, API, file search port, workflow wiring and fixed timeout error.
- [ ] Run focused unit/integration tests, Ruff, format and mypy.

### Task 4: Synchronize facts and close evidence

**Files:** `docs/{product/PRODUCT,architecture/API,architecture/SYSTEM,architecture/AI,tasks/TASKS,memory/PROJECT-STATE}.md`, IR/TR/RR and indexes as required.

- [ ] Run affected frontend and backend suites, build and browser tests.
- [ ] Review security and compatibility; record the production and model-eval release boundary.
- [ ] Commit subject and evidence with real SHA, then follow repository PR/merge gate.
