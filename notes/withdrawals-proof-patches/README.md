# Gloas withdrawals higher-level proof patches

These two patches preserve the current local-only `produceBlockV3` proof artifacts from `~/lodestar-gloas-withdrawals`.

## Scope

This patch stack is a **branch-selection proof**, not a full stale-field provenance proof.

What it proves:
- in the forced Gloas empty-parent case, the higher-level `produceBlockBody()` -> `notifyForkchoiceUpdate(...)` path selects `getPayloadExpectedWithdrawals()` instead of `getExpectedWithdrawals()`

What it does **not** fully prove yet:
- real-Gloas stale-field provenance end-to-end, because the test still uses an Electra-backed `BeaconStateView` with minimal Gloas-only overrides and mocks the two withdrawals accessors

## Patch files

1. `0001-test-cover-Gloas-empty-parent-withdrawals-branch-in-.patch`
   - commit: `45649c5c4f`
   - message: `test: cover Gloas empty-parent withdrawals branch in produceBlockV3`
2. `0002-test-cover-gloas-empty-parent-withdrawals-branch.patch`
   - commit: `52404aff3f`
   - message: `test: cover gloas empty-parent withdrawals branch`
   - purpose: wording-tightening / honest narrower claim

## Apply later

From a fresh Lodestar branch/worktree:

```bash
git am /home/openclaw/.openclaw/workspace/notes/withdrawals-proof-patches/*.patch
```

Or cherry-pick by hash if the original worktree/branch still exists:

```bash
git cherry-pick 45649c5c4f 52404aff3f
```

## Validation command

```bash
pnpm lint -- packages/beacon-node/test/unit/api/impl/validator/produceBlockV3.test.ts
pnpm test:unit packages/beacon-node/test/unit/api/impl/validator/produceBlockV3.test.ts
```

Expected current result when these patches were packaged:
- lint: clean
- unit: `26/26` passing
