# Review Findings - review-bugs - PR 9687

Reviewer: review-bugs
Reviewed commit: 9face9a4872302e03cd0804a7a85ad261572f43a
Generated at: 2026-08-05 09:21 UTC

## Findings

### 1. [P2] Decode `bootstrap.ssz_snappy` with `bootstrap_fork_digest`

File: `packages/beacon-node/test/spec/presets/light_client/sync.ts:207`

The new sync runner reads `meta.bootstrap_fork_digest` and computes `bootstrapFork` in `testFunction`, but `bootstrap` has already been deserialized by the static `sszTypes` entry at line 207 using the directory fork. The sync test format says the bootstrap SSZ type is determined from `bootstrap_fork_digest` and may need to be upgraded to `store_fork_version` before store initialization. A Gloas sync vector with a pre-Gloas bootstrap will fail during fixture loading, before the upgrade logic can run, so unskipping `gloas/light_client/sync` still does not exercise the cross-fork bootstrap path correctly.

Use the same raw-byte pattern as updates, or select the bootstrap SSZ type from `meta.bootstrap_fork_digest` before deserialization, then call `upgradeLightClientBootstrap` only after decoding.

## Verification

Reviewed `/tmp/pr9687.diff` and the changed-file list in `/tmp/pr9687.files`. Built the detached PR worktree at `9face9a4872302e03cd0804a7a85ad261572f43a` with `pnpm -r build`, and the new targeted unit tests passed with `pnpm vitest run --project unit packages/beacon-node/test/unit/chain/lightclient/server.test.ts packages/beacon-node/test/unit/network/reqresp/handlers/lightClientForkContext.test.ts packages/state-transition/test/unit/lightClient/upgradeLightClientStore.test.ts`.
