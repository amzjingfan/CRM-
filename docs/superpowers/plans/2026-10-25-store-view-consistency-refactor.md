# Store view consistency and guarded refactor

**Goal:** Store changes never expose another store's detail or stale data. Knowledge FAQ and RAG document details share a stable layout while keeping their valid, distinct operations. Refactor other confirmed store state races without changing business permissions or data.

**Base:** `5b619a754c3c7cdecb652b6872aeb3e3691d5a9c` (`origin/main`). **Target:** `origin/main`. **Task:** `MVP-STORE-VIEW-CONSISTENCY-001`.

## Evidence and limits

- The user screenshots show an FAQ in one store and a document file in another. Their detail branches and CSS widths differ; a store change leaves `detailRow` open.
- Current knowledge list separately paginates FAQ and files and combines their results; the next-page guard uses `max(total, documentTotal)`. This covers both streams but yields up to 40 mixed rows per page. The status/type selectors filter only fetched rows, so their results are page-local.
- File versions are immutable in the current API; FAQ edit/archive/delete endpoints do not apply to files. The user chose replacement/classification changes for editing, plus auditable soft archive and delete. Keep all existing versions immutable and extend file management with scoped lifecycle endpoints.
- Preserve tenant checks, authorization, CSRF, audit, ingestion versions, and current manual review mode. No production deployment or live data mutation in verification.
- Project-wide cleanup must be evidence-led. Unknown files are protected; tracked deletion requires a separate cleanup task and reviewable diff.

## Steps

1. Add browser regressions for switching stores with an open FAQ/file drawer, stale async detail responses, and consistent drawer geometry. Run them red.
2. Reset store-scoped knowledge selection, overlays and detail request generation atomically on switch. Use one detail layout for both types while keeping type-specific content and valid actions.
3. Audit combined pagination and store-scoped loading. Preserve the paired 20+20 pagination contract in this scoped fix, verify that every record remains reachable, and label the status/type selectors as page-local until a unified server-side search is designed.
4. Audit dashboard, workspace, marketing and agent store switch lifecycles. Fix only reproduced stale-selection or request races; avoid unrelated rewrites.
5. Inspect backend file-list query count and remove proven N+1 work without changing response shape or permissions. Add a targeted test if changed.
6. Add scoped file category, archive, restore and soft-delete actions with migration, audit, idempotency and worker safeguards. Wire replacement and category actions into the shared file detail shell. Verify file history and tenant boundaries.
7. Run affected browser and contract tests, frontend lint/typecheck/build, relevant backend tests and review. Record IR/TR/RR as required. Merge only after applicable gates; staging deployment is a separate release action.
