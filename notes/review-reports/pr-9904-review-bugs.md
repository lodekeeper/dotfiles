# Review Findings — review-bugs — 9904

Reviewer: review-bugs
Reviewed commit: bb66eca801346ef46495f0248277735cc1bb0244
Generated at: 2026-08-24 10:48 UTC

Reviewer: review-bugs
Reviewed commit: bb66eca801346ef46495f0248277735cc1bb0244

## Findings

### 1. Cap pruning can evict live block inputs before their payload envelope arrives

`SeenPayloadEnvelopeInput.add()` now calls `pruneToMaxSize()` on every insert, and `pruneToMaxSize()` evicts strictly by Map insertion order once the cache exceeds `(MAX_LOOK_AHEAD_EPOCHS + 1) * SLOTS_PER_EPOCH` (`packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:147`, `:290-297`). It does not protect current-slot or otherwise active entries that still need an execution payload envelope.

That is load-bearing for normal Gloas block import. A gossip block seeds the payload input before validation (`packages/beacon-node/src/network/processor/gossipHandlers.ts:189-201`), but the matching gossip payload envelope later does a plain `get()` and rejects the envelope with `PAYLOAD_ENVELOPE_INPUT_MISSING` if the entry was pruned (`packages/beacon-node/src/network/processor/gossipHandlers.ts:1193-1204`). The validator API path has the same plain lookup and returns 404 when publishing the envelope (`packages/beacon-node/src/api/impl/beacon/blocks/index.ts:840-845`).

Concrete failure sequence: a valid current-slot Gloas block is received or locally published, then more than 96 other Gloas payload-input shells are inserted before its envelope arrives. This can come from range/by-root sync, or from invalid gossip blocks because the gossip handler inserts before validation. The insertion-order cap evicts the live current-slot input. The subsequent execution payload envelope is ignored by gossip or rejected by the API, so the node loses the payload reveal/import path for that block.

### 2. `getOrReload()` can overwrite a populated entry created while the DB read is in flight

`getOrReload()` checks the map before starting `reloadFromDb()`, but `reloadFromDb()` awaits `db.block.get()` and then unconditionally writes a freshly reconstructed EMPTY shell back into `payloadInputs` (`packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:216-240`). There is no second map check after the await.

Any concurrent producer can call `add()` for the same root during that await, because `add()` only checks `payloadInputs` and does not look at `reloading` (`packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:130-140`). If that producer then attaches the envelope or columns to the new object, the reload completion overwrites it with an empty reconstructed shell. That drops already-received payload/data from the shared cache and can force unnecessary re-downloads or leave later plain `get()` consumers seeing an incomplete object.
