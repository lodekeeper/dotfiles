# Legacy column archiver implementation

- Worktree: `/home/openclaw/lodestar-archive-column-compaction`
- Branch: `fix/archive-legacy-column-compaction`
- Base and tested HEAD: `3da261f88e8937caa501bde255bec77a9991057f`
- Final uncommitted diff: `green-final.patch`, SHA256 `11cfa04735481a8b69e668689408c6d53f57c15f2a50bb1b86b5d93f9a308f7a`
- Scope: five tracked files, 132 insertions and 118 deletions. No commit, push, external posting, live node changes, cleanup or config changes.

## Implementation

1. Removed the canonical legacy data-column migration call, helper and now-unused `fromAsync` import. Block, blob, execution-envelope archival, noncanonical FULL/EMPTY cleanup, flat-file pruning and legacy cold fallback are unchanged.
2. Exposed the existing `compactRange(start: K, end: K): Promise<void>` controller method on `DatabaseController`.
3. Awaited compaction after deleting the legacy hot-column bucket, bounded by `encodeKey(57, empty)` and `encodeKey(58, empty)`. Compaction is unconditional, including databases with tombstones from previous startups. This runs on each startup and can add startup latency; it makes no exact reclamation/performance guarantee.

## Tests first: red

With production unchanged at the base commit, adapted the existing archiver migration tests into Fulu/Gloas negative-call tests and extended the real-LevelDB prune tests.

```sh
source ~/.nvm/nvm.sh && nvm use 24
pnpm --config.verify-deps-before-run=false vitest run --project unit packages/beacon-node/test/unit/db/beacon.test.ts packages/beacon-node/test/unit/chain/archiveStore/blockArchiver.test.ts
```

Exit 1: 9 failed, 9 passed, no skips, 2 files. Four expected failures show legacy column accesses during canonical Fulu/Gloas archiving, including already-archived boundaries. Five expected failures show missing startup compaction (0/1/8 roots, previously deleted empty bucket, waiting for completion). The real flat-column preservation case passed before the fix.

Artifacts: `red-tests.patch` and `red-tests.log`. The first green typecheck subsequently caught test-only type issues in fork-union serialization and `Promise.withResolvers` under the configured library target. Corrected those using the existing `config.getForkTypes(0)` and `defer<void>()` APIs; the regression assertions are unchanged. The first-attempt diagnostics remain in `green-types.log`.

## Final green validation

All commands ran from the worktree root with Node v24.21.0 and the existing dependency cache. No install or manual `lib/` edits.

```sh
source ~/.nvm/nvm.sh && nvm use 24
pnpm --config.verify-deps-before-run=false --filter @lodestar/db build
pnpm --config.verify-deps-before-run=false vitest run --project unit packages/beacon-node/test/unit/db/beacon.test.ts packages/beacon-node/test/unit/chain/archiveStore/blockArchiver.test.ts packages/beacon-node/test/unit/db/dataColumnStore.test.ts packages/beacon-node/test/unit/db/flatFileStore/flatFileStoreUpgrade.test.ts
pnpm --config.verify-deps-before-run=false lint
pnpm --config.verify-deps-before-run=false check-types
git diff --check
```

- DB build: exit 0, `green-db-build.log`.
- Targeted tests: exit 0, 39 passed, no failures/skips, four files, `green-tests-final.log` (initial green also retained in `green-tests.log`). Counts: beacon 6, archiver 12, data-column store 8, flat-file upgrade 13.
- Full lint: exit 0, 1886 files, no fixes, `green-lint-final.log` (initial green also retained in `green-lint.log`).
- Full check-types: exit 0, 17 workspace projects plus 15 utility type tests, `green-types-fixed.log`.
- `git diff --check`: exit 0.

Prune coverage uses real LevelDB compaction passthrough, exact encoded boundaries, completed-deletion and call-order checks, including 1024 legacy columns across multiple delete batches. It preserves hot blocks, archived blobs/columns and flat files. A pre-deleted bucket still compacts; controlled deferred completion verifies startup awaits compaction without a timing threshold. A real BeaconDb archiver case confirms canonical flat columns remain readable after blocks migrate. Existing cold fallback, range-serving and noncanonical cleanup tests remain unchanged.

No dependency or validation blockers remain. Review and publication are left to the parent session.
