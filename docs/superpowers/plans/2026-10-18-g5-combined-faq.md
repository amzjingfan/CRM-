# G5 Combined FAQ Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax for tracking.

**Goal:** Reduce the supported FAQ path from three serial model calls to two while preserving independent safety review and G5 gates.

**Architecture:** Resolve store-scoped approved FAQ evidence first for non-tool questions. A registered strict structured request returns intent plus FAQ draft; existing deterministic validation and independent review decide whether any safe SSE content can appear. Other routes remain conservative.

**Tech Stack:** Python, Pydantic, LangGraph, DeepSeek Provider, pytest.

**Spec:** `docs/superpowers/specs/2026-10-18-g5-combined-faq-design.md`

## Global Constraints

- Keep store isolation, DLP, citations, strict schema, thresholds, independent review, manual-send limits and no TikTok outbound messages.
- Keep staging deployment manual; do not use GitHub Actions.
- G5 single first safe delta `<3000 ms`; 50-concurrent P99 `<5000 ms` is not waived.

## Review Focus

- Refusal and low-confidence combined outputs must never expose a draft.
- Tool-requiring questions must not take the combined FAQ path.
- Cross-store or invented citation IDs must fail closed.
- Provider invalid schema and cancellation must not bypass safety review.
- A performance gain on one sample must not stand in for 50-concurrent P99 evidence.

## Task 1: Combined output contract and registered prompt

- [ ] Add failing tests for the combined Pydantic schema, prompt registration and strict Responses route.
- [ ] Run focused tests and confirm the intended failures.
- [ ] Add the minimal schema, prompt builder/version/hash registration and Provider routing.
- [ ] Run focused tests and static checks.

## Task 2: FAQ fast path in workflow

- [ ] Add failing workflow tests for FAQ success, no knowledge, tool, refusal, low confidence, invalid draft, bad citation, Provider failure and cancellation.
- [ ] Run focused tests and confirm the intended failures.
- [ ] Implement fast path with existing independent safety review and failure-closed routing.
- [ ] Run focused tests, full backend tests, Ruff and mypy.

## Task 3: Evidence and integration

- [ ] Update current AI/quality/task docs and write IR/TR/RR with actual subject and test evidence.
- [ ] Review diff, sensitive-data boundary and manual deployment contracts; commit and merge through PR.
- [ ] Manually build/publish immutable backend image from main and verify OCI revision/digest.
- [ ] In staging run prefetch/validate, one synthetic SSE, conditional 50-concurrent test, and restore with low-sensitivity evidence.
- [ ] Mark G5 done only if every G5 gate has authoritative passing evidence.
