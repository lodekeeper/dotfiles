# Review Findings — review-security — 9904

Reviewer: review-security
Reviewed commit: bb66eca801346ef46495f0248277735cc1bb0244
Generated at: 2026-08-24 10:53 UTC

Reviewer: review-security
Reviewed commit: bb66eca801346ef46495f0248277735cc1bb0244

## Findings

### 1. Invalid children can pin BlockInputSync behind a parent payload they cannot match

Location: `packages/beacon-node/src/sync/unknownBlock.ts:537-548`

`getMissingBlockDependency()` now returns `parentPayload` for any post-Gloas child whose `signedExecutionPayloadBid.parentBlockHash` is not present in fork choice, as long as the parent payload is not FULL yet. In the normal PENDING-parent case the parent block's bid hash is already available through `seenPayloadEnvelopeInputCache`; the previous code used it to drop children whose parent hash could never match. This PR removes that check.

A peer can gossip many child blocks under a known PENDING parent with arbitrary `parentBlockHash` values. They are queued in `pendingBlocks` and wait for the parent payload instead of being dropped immediately. Since `pendingBlocks` is capped and prunes older entries (`unknownBlock.ts:377-405`), this can evict legitimate recovery work and keep the node busy on blocks that are provably incompatible until the parent payload is imported. If that parent payload is withheld or delayed, the pressure persists.

Suggested fix: keep the parent bid hash check when a `PayloadEnvelopeInput` is present and return `invalidParentPayload` on mismatch. Only defer when the parent input is absent, or make this dependency check able to reload the parent input before accepting the child as blocked.

### 2. The insertion-order cap can evict live payload inputs before their envelope is consumed

Location: `packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:129-148`, `packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:290-296`

Every `add()` now immediately calls `pruneToMaxSize()`, which evicts the oldest insertion without checking whether that input is active, current-slot, PENDING, has an in-flight payload import, or still has envelope/column data that has not been consumed. The gossip block path seeds this cache before validation (`gossipHandlers.ts:193-201`), so a burst of more than 96 distinct post-Gloas block roots can push out an honest current block's `PayloadEnvelopeInput` before its execution payload envelope or columns arrive.

The downstream envelope paths still require a cache hit. Gossip uses `get()` and turns a miss into `PAYLOAD_ENVELOPE_INPUT_MISSING` (`gossipHandlers.ts:1196-1203`), and the API publish path returns 404 (`api/impl/beacon/blocks/index.ts:840-845`). Those paths do not reload or reattach the input. A peer burst can therefore make a valid envelope be ignored, or make local envelope publish fail, preventing the block from becoming FULL and affecting payload availability voting for that slot.

Suggested fix: do not run this cap on optimistic, pre-validation inserts, or make the cap skip roots that are active in fork choice, current or recent slots, PENDING without FULL payload, queued for processing, or holding unpersisted envelope/column data. The envelope/API paths also need a safe reload or reattach path if the shared cache is allowed to evict their input.

### 3. `getOrReload()` can overwrite an input created while the DB read is in flight

Location: `packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:216-240`

`getOrReload()` checks `payloadInputs` once, awaits `db.block.get()`, then blindly writes a newly reconstructed empty shell back into the map. If any other path calls `add()` for the same root while the DB read is pending, that path can create the canonical in-memory object and attach an envelope or columns to it. When the reload resumes, line 240 replaces that object with the empty reload object.

That loses the cache state for future `get()` callers and recreates the duplicate-object problem the new `reloading` map is trying to avoid: `PayloadEnvelopeProcessor` dedups imports by `PayloadEnvelopeInput` object identity, so reload-vs-add races can still produce two objects for one root and drive repeated payload processing or downloads.

Suggested fix: after every await and immediately before `payloadInputs.set()`, recheck the map and return the existing input if one appeared. If both objects can contain data, merge rather than replace.

## Tests

Not run. Review only.
