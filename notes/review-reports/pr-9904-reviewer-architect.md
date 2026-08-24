# Review Findings — reviewer-architect — 9904

Reviewer: reviewer-architect
Reviewed commit: bb66eca801346ef46495f0248277735cc1bb0244
Generated at: 2026-08-24 10:44 UTC

Reviewer: reviewer-architect
Reviewed commit: bb66eca801346ef46495f0248277735cc1bb0244

## Findings

### [P1] Dangling-parent payload is still owned only by the capped shared cache

`cacheByRangeResponses()` protects in-batch payload inputs by copying them into the batch-local `payloadEnvelopes` map, but the dangling-parent path still falls back to `seenPayloadEnvelopeInputCache.get()` when the parent envelope arrives by root (`packages/beacon-node/src/sync/utils/downloadByRange.ts:229-244`). The first checkpoint/range-sync batch can require that parent after the initial block/envelope range download (`packages/beacon-node/src/sync/range/batch.ts:368-393`), while the parent input itself is usually the anchor-state entry inserted at chain init (`packages/beacon-node/src/chain/chain.ts:462-475`).

The new cap prunes on every payload-input insert by Map insertion order (`packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:139-147`, `packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:290-296`). With lookahead batches, the first batch can download its blocks, decide it needs the parent payload, then other batches insert enough entries to evict that older anchor entry before the parent by-root response is cached. When the parent response lands, the local batch map has no parent entry and the shared cache lookup can miss, causing the `Missing PayloadEnvelopeInput` throw on `downloadByRange.ts:241-244`.

This means the range-sync separation is only partial: active in-batch slots are protected, but the active boundary parent remains load-bearing on the capped cache. The parent `PayloadEnvelopeInput` should be promoted into the batch-owned map before issuing `parentPayloadRequest`, or otherwise protected from cap eviction for the lifetime of that batch. `getOrReload()` is not enough for checkpoint anchors because `addFromBid()` exists specifically for the case where the bid comes from state rather than a persisted full block.

### [P1] `getOrReload()` can overwrite an active payload input created while the DB read is in flight

`getOrReload()` checks the map once, records an in-flight reload, then awaits `db.block.get()` via `reloadFromDb()` (`packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:185-219`). After that await it unconditionally constructs a fresh EMPTY `PayloadEnvelopeInput` and stores it back into `payloadInputs` (`packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:229-240`). If gossip, by-root, API, or range sync calls `add()` for the same root during the DB read, `add()` will create the real shared object, potentially with envelope/columns attached, and the reload then replaces it with an empty shell.

That is an ownership race introduced by putting DB reload semantics inside the seen cache: the cache now has two writers for the same key with no merge or final compare-and-set. It can lose payload/column state and also recreate the object identity that the payload processor relies on for same-object de-duplication, which the new reload comments explicitly call out. Recheck `this.payloadInputs.get(blockRootHex)` after the awaited block load and before `set()`, returning or merging the existing object rather than replacing it. Longer term, keep the seen cache as an in-memory registry and move reload/rehydration policy into a resolver that can coordinate with sync-owned batch state.
