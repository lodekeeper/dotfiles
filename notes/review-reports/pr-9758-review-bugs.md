# Review Findings — review-bugs — 9758

Reviewer: review-bugs
Reviewed commit: 4b02d4bda1e5af34ac96930cad7d043b6c076854
Generated at: 2026-08-03 15:47 UTC

Reviewer: review-bugs
Reviewed commit: 4b02d4bda1e5af34ac96930cad7d043b6c076854

# Findings

1. **packages/builder/src/builder.ts:35** — **Bug** — The new builder package fails typechecking because `noUnusedLocals` reports the unused private fields declared at lines 35-38 (`index`, `config`, `api`, and `logger`). Verified with `pnpm --filter @lodestar/builder check-types`, which exits 2 with TS6133 errors in this file.

   **Impact** — `pnpm -r check-types` fails for the workspace as soon as this package is included, blocking CI for the PR even though the package builds for emit.

   **Fix** — Remove these private fields and their constructor assignments until runtime code reads them, or add real usage/accessors for the stored builder state.
