# CI run 39576553124

## Goal
Fix the failing unstable type check and open a minimal reviewed PR.

## Source and scope
Nico, Discord #lodestar-private, 2026-10-21 10:34 UTC.
Run: https://github.com/ChainSafe/lodestar/actions/runs/39576553124
Failed source: 23bc3d7be9e301110912ce4e8af6aae9623c3248.
Worktree: /home/openclaw/lodestar-archiver-test-mock-types
Base: 88c15a0731b. Branch: fix/archiver-test-mock-types.
Test-only fix; no production changes, deployment, restart, or merge.

## Findings
TS2322 at blockArchiver.test.ts lines 120 and 175: real repository instances are assigned to MockedBeaconDb properties. The shared helper already creates isolated mocked execution envelope repositories with get/getBinary returning null. Remove redundant replacement instances and unused imports, preserve explicit getBinary null spies and all assertions.

## Review
Native archiver_fix_review approved approach before implementation. Exact four-deletion diff independently approved, no findings.

## Verification
Fresh independent node_modules/virtual store, pnpm 11 frozen install succeeded. Build passed. Original beacon-node typecheck reproduced exactly two TS2322 errors. After fix: full pnpm lint (1891 files), full pnpm check-types, and 44 archiveStore tests across 7 files all passed. Retain command logs in this directory.

## Spec Compliance Artifacts
N/A (fixture typing only, no production code or spec behavior changed; no spec vectors required).

## Next
Signed commit/push/PR as verified lodekeeper. All implementation/review/verification gates complete.

## Completed
Opened https://github.com/ChainSafe/lodestar/pull/10452 as verified lodekeeper against unstable. Signed commit 680c9af45bf4cd6c1356885be1a34d868bfc0e56; GPG verification G. Live PR author/title/body/head/diff/state confirmed: OPEN, ready, one file/four deletions. Worktree clean. Remote CI pending; no merge/deployment.
