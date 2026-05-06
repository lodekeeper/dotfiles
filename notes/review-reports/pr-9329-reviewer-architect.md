# Review Findings — reviewer-architect — 9329

Reviewer: reviewer-architect
Reviewed commit: b1ed8b86c429be1f6556cd8b7387657b86030204
Generated at: 2026-05-06 12:56 UTC

# Architectural Review Report

Reviewer: reviewer-architect
Reviewed commit: b1ed8b86c429be1f6556cd8b7387657b86030204

## Findings

### 1. The slot-keyed `payloadEnvelopes` map now carries data that is outside the batch window
**Files:**
- `packages/beacon-node/src/chain/blocks/index.ts`
- `packages/beacon-node/src/sync/range/batch.ts`
- `packages/beacon-node/src/sync/utils/downloadByRange.ts`

The new skipped-slot handling stores the dangling parent payload in the same `Map<Slot, PayloadEnvelopeInput>` that previously represented only payload state for blocks inside the batch. You can see the abstraction drift in three places:

- `validateEnvelopesByRangeResponse()` now preserves an envelope whose block is *not* in the batch.
- `Batch` has to scan `payloadEnvelopes.values()` by `blockRootHex` to recover that parent entry because the map key (`slot`) no longer matches the thing we actually need to identify.
- `processBlocks()` now has to union `blocks` slots with `payloadEnvelopes.keys()` because the payload map is no longer guaranteed to be a 1:1 companion to the batch's blocks.

That weakens a useful invariant in the range-sync pipeline: “batch payload state is keyed to the batch’s own blocks.” Once that invariant is gone, every future consumer of `payloadEnvelopes` has to remember that the map may also contain out-of-band entries, which is exactly the kind of hidden coupling that tends to spread special cases across the sync stack.

A cleaner boundary would keep out-of-band parent payload state separate (for example, a dedicated root-keyed side structure for checkpoint-anchor dependencies), or change the internal identity to block root and derive a slot view only for in-range blocks.

### 2. Checkpoint-anchor recovery is now threaded through the generic range-sync/batch abstractions
**Files:**
- `packages/beacon-node/src/chain/chain.ts`
- `packages/beacon-node/src/sync/range/range.ts`
- `packages/beacon-node/src/sync/range/chain.ts`
- `packages/beacon-node/src/sync/range/batch.ts`
- `packages/beacon-node/src/sync/utils/downloadByRange.ts`

To support one checkpoint-sync edge case, the patch pushes anchor-specific context deep into the shared range-sync machinery:

- `RangeSync` snapshots `latestExecutionPayloadBid` from the current head state.
- `SyncChain` now stores first-batch-only state.
- `Batch` takes `isFirstBatchInChain`, `latestBid`, and `targetSlot` in its constructor.
- `downloadByRange` now accepts `parentPayloadRequest` and `ParentPayloadCommitments`, even though those are not actually “by range” requests.
- `BeaconChain` seeds `SeenPayloadEnvelopeInput` from anchor state during generic chain initialization.

The result works, but it makes the core batch abstraction less about “download and process this slot window” and more about “download this window plus whichever one-off recovery path the current sync mode happens to need.” That is the kind of layering drift that becomes expensive over time, because every additional fork-specific sync exception tends to arrive as another constructor flag, cached context object, or request subtype.

Architecturally, this would age better if the first-batch anchor recovery were modeled as an explicit bootstrap/prefetch step around chain creation, leaving `Batch` and `downloadByRange` responsible only for normal range-window work. That keeps the special checkpoint-sync policy at the edge instead of making it part of the reusable batch scheduler contract.
