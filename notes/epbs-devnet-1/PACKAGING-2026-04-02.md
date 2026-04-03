# PR #9148 packaging options — 2026-04-02

## Current repo state
- Branch: `fix/epbs-devnet1-checkpoint-follow-head-min`
- Base: `origin/epbs-devnet-1`
- **Committed diff vs base:** only `packages/beacon-node/src/sync/unknownBlock.ts`
  - resolve missing parent envelope on `PRESTATE_MISSING`
  - gate envelope fetch on explicit `FULL` absence check
- **Uncommitted experiments:**
  - **A)** classification tweak in `remoteSyncType.ts` + caller plumbing + regression test
  - **B)** `beacon_blocks_by_range` V1 fallback experiment post-Altair
  - **C)** req/resp invalid-request instrumentation

## Evidence summary
- Earlier `discovery11` live sample showed a genuine **Advanced** erigon/caplin peer.
- With the classification-only patch, Lodestar entered finalized range sync instead of staying in the fully-synced path.
- That same run then hit a **separate downstream req/resp failure**: outgoing `beacon_blocks_by_range` V2 `INVALID_REQUEST: SSZ_SNAPPY_ERROR_UNDER_SSZ_MIN_SIZE`.
- Later direct-host repros degraded from `AHo4o/Behind` to repeated **peerless/refused** windows, so the live repro path is currently unstable.

## Packaging options

### Option 1 — absolute safest
Ship **only** the committed `unknownBlock.ts` fix.

**Pros**
- smallest and cleanest diff
- directly tied to a concrete Lodestar-side recovery bug
- easiest to describe honestly
- no risk of over-claiming end-to-end fix

**Cons**
- leaves out the validated classification improvement from the earlier Advanced-caplin sample
- PR must be framed narrowly (missing-parent-FULL / `PRESTATE_MISSING` recovery only)

### Option 2 — still fairly minimal, but broader
Ship committed `unknownBlock.ts` fix **plus A**, trimmed to:
- `getPeerSyncType(..., currentSlot)` logic change
- regression test
- **drop temporary debug log**

**Pros**
- includes the only experimental behavior change with direct live evidence that it fixes a real local decision bug
- aligns better with the user-facing goal of checkpoint sync + follow-head

**Cons**
- broader behavioral change than option 1
- current live repro window is gone, so the downstream path cannot be revalidated right now
- PR description must explicitly say the separate req/resp `UNDER_SSZ_MIN_SIZE` failure is **not** fixed here

## Explicitly keep out for now
- **B)** V1-first / post-Altair V1 fallback
- **C)** invalid-request debug instrumentation
- any claim of full end-to-end live-devnet resolution

## Honest PR wording constraints
Do **not** claim:
- full epbs-devnet-1 sync is fixed end-to-end
- Caplin interop is fully solved
- the root cause was definitively version fallback / classification alone
- the outgoing `UNDER_SSZ_MIN_SIZE` failure is addressed by this PR
