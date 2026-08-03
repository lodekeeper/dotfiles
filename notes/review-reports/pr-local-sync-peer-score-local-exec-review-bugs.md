# Local Review: sync peer score local exec

Reviewer: review-bugs
Reviewed commit: aa562e67935b01d71a593c3dd770f16265927d01

## Scope

- `packages/beacon-node/src/sync/range/batch.ts`
- `packages/beacon-node/test/unit/sync/range/batch.test.ts`

## Findings

No functional bugs found in the reviewed diff.

## Verification

- Reviewed `git diff -- packages/beacon-node/src/sync/range/batch.ts packages/beacon-node/test/unit/sync/range/batch.test.ts`
- Ran `git diff --check -- packages/beacon-node/src/sync/range/batch.ts packages/beacon-node/test/unit/sync/range/batch.test.ts`
- Ran `pnpm vitest run --project unit packages/beacon-node/test/unit/sync/range/batch.test.ts`
  - Passed: 1 test file, 26 tests
  - Note: pnpm warned that the current Node.js version is `v22.19.0`, while the repo wants `^24.13.0`
