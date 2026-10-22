# Employee Accounts and Departments Implementation Plan

**Goal:** Make the system settings account and department pages match the supplied UI and work with real, scoped management APIs.

**Architecture:** Extend the existing User and team service for account metadata and login identifiers. Add department tables and a small service/router in the same backend. Keep department membership separate from RBAC; the frontend consumes typed APIs through the existing settings frame.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy/Alembic, PostgreSQL, Next.js/React, TypeScript, Playwright.

**Spec:** [员工账号与部门管理设计](../specs/2026-10-22-team-accounts-departments-design.md)

## Constraints and review focus

- Preserve email login, all existing RBAC/store assignments, CSRF and audit. No production deployment or real account writes during tests.
- Review duplicate identifiers, missing email, legacy users, last-admin protection, reset-token invalidation, and cross-store department reads.
- Role changes, permission edits and concurrent-session enforcement remain deferred and must not silently execute.

## Work

1. **Account migration and login.** Add nullable login name/email support, phone, timezone, session setting and auth version to User. Add reversible migration. Write failing tests for both login identifiers, legacy email, duplicate login and reset-token invalidation; implement schema, lookup and token checks.
2. **Account management.** Extend typed team create/read/update contracts and service. Add admin password reset with audit and token-version bump; retain disable and last-admin protection. Test normal, invalid and unauthorized paths.
3. **Departments.** Add department/store/member tables, schemas, service and routes. Test scoped reads, admin-only writes, member add/remove, empty-only delete and unchanged RBAC assignments.
4. **Account page.** Build the reference table, account search, create/edit/reset drawers and More menu using existing design tokens and API helpers. Add browser tests for primary flows, disabled controls and errors.
5. **Department page.** Add navigation, department list, account table and add/remove member flows. Show role/permission actions as deferred; list responsible stores without routing changes. Add browser tests and check narrow viewport behavior.
6. **Verification and delivery.** Run backend lint/typecheck/tests, migration upgrade/downgrade/upgrade in isolation, frontend lint/typecheck/contract/build/browser, and security review. Sync product/API/system/test/deployment facts, create IR/TR/RR and candidate indexes. Push one reviewed PR, merge only after applicable gates; deploy staging only with exact source, backup and rollback evidence, then request real-page acceptance.
