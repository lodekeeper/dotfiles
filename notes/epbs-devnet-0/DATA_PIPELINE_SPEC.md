# EPBS Data Pipeline Redesign Spec

## Problem

Current PR #8941 has hacky workarounds:
1. **Deferred envelope queue** — retries envelope import when block hasn't arrived yet
2. **VC attestation retries** — masks BN-side optimistic rejection (now removed)
3. **Complex fork-choice reconciliation** — PENDING/FULL variant pointer patching

These exist because the pipeline doesn't cleanly separate block and envelope concerns.

## Target Architecture (per Nico's review on PR #8940)

### Two Separate Caches

```
SeenBlockInputCache[blockRoot]         → BlockInputPayloadBid     (block + bid, immediately complete)
SeenPayloadEnvelopeCache[blockRoot]    → PayloadEnvelopeInput     (envelope + columns, created from bid)
```

### Key Principles

1. **Block input lifecycle unchanged** — same as pre-data (PreDeneb). Block arrives, immediately complete, import proceeds.
2. **Envelope is a separate pipeline** — not part of block input at all.
3. **Bid is the anchor** — `PayloadEnvelopeInput` is created from the bid (extracted from the block) because:
   - Envelope gossip validation needs the bid (builder index, block hash)
   - Data column gossip validation needs kzg commitments from the bid
   - Therefore, bid must exist before either can be processed
4. **No deferred queues needed** — if envelope arrives before block, it fails gossip validation (no bid to validate against). This is correct behavior — just drop it and let the next gossip cycle handle it.

### Naming Conventions (Nico feedback)

- Avoid "epbs" everywhere — use spec terminology
- `PayloadStatus.PendingEnvelope` instead of `PayloadStatus.PENDING`
- `BlockInputPayloadBid` for the block input class
- `DAType.PayloadBid` instead of `DAType.Epbs`
- `DataAvailabilityStatus.NotRequired` or `BlockOnly` instead of `Epbs`

## Detailed Design

### 1. BlockInputPayloadBid (block pipeline)

```typescript
// In blockInput.ts
export class BlockInputPayloadBid extends AbstractBlockInput<ForkPostGloas, null> {
  type = DAType.PayloadBid as const;
  
  static createFromBlock(props: AddBlock<ForkPostGloas> & CreateBlockInputMeta): BlockInputPayloadBid {
    // Immediately complete — no DA requirements for the beacon block itself
    // The bid is embedded in the block body
  }
}
```

- Created in `SeenBlockInput.getBlockInput()` when `isForkPostGloas(forkName)`
- Immediately has `hasAllData: true` — no waiting
- Import proceeds through normal block pipeline
- Fork-choice creates node with `ExecutionStatus.Syncing` and `PayloadStatus.PendingEnvelope`

### 2. PayloadEnvelopeInput (envelope pipeline)

```typescript
// New file: packages/beacon-node/src/chain/blocks/payloadEnvelopeInput.ts
export class PayloadEnvelopeInput {
  blockRoot: RootHex;
  bid: gloas.ExecutionPayloadBid;  // from the beacon block
  envelope: gloas.ExecutionPayloadEnvelope | null;
  // Future: data columns when PeerDAS applies to post-Gloas
  
  static createFromBid(blockRoot: RootHex, bid: gloas.ExecutionPayloadBid): PayloadEnvelopeInput {
    // Created right after block gossip validation succeeds
    // Envelope starts as null, filled when envelope gossip arrives
  }
  
  addEnvelope(envelope: gloas.ExecutionPayloadEnvelope): void {
    // Called when envelope passes gossip validation
    // Triggers engine_newPayloadV5 + fork-choice update
  }
}
```

### 3. SeenPayloadEnvelopeCache

```typescript
// New file or extend seenCache
export class SeenPayloadEnvelopeCache {
  private cache: Map<RootHex, PayloadEnvelopeInput>;
  
  getOrCreate(blockRoot: RootHex, bid: gloas.ExecutionPayloadBid): PayloadEnvelopeInput {
    // Called from block gossip handler after block import succeeds
  }
  
  get(blockRoot: RootHex): PayloadEnvelopeInput | undefined {
    // Called from envelope gossip handler to find the bid for validation
  }
  
  onFinalized(finalizedEpoch: Epoch): void {
    // Prune entries for finalized blocks
  }
}
```

### 4. Gossip Handler Flow

#### Block arrives (gossip_beacon_block):
```
1. validateGossipBlock(block)
2. Extract bid from block body
3. seenPayloadEnvelopeCache.getOrCreate(blockRoot, bid)  // BEFORE processBlock!
4. Consume orphan envelope if present in orphan cache
5. seenBlockInput.getBlockInput(block) → BlockInputPayloadBid (immediately complete)
6. chain.processBlock(blockInput)  // normal import, creates FC node
```

**CRITICAL**: Step 3 must happen BEFORE step 6. If envelope arrives between
block gossip validation and processBlock, the envelope handler needs to find
the bid in the cache. Creating the cache entry early closes this race window.

#### Envelope arrives (gossip_execution_payload_envelope):
```
1. Look up bid: seenPayloadEnvelopeCache.get(blockRoot)
2. If no bid → IGNORE (not REJECT!) + store in bounded orphan cache
   - gossipsub does NOT re-broadcast; REJECT would lose the envelope permanently
   - REJECT also penalizes honest peers for benign ordering skew
3. validateGossipEnvelope(envelope, bid)  // builder index, block hash, etc.
4. Assert envelope.payload.blockHash === bid.blockHash  // equality check, not update!
   - Mismatch → treat as invalid/equivocation, do not import
5. chain.importEnvelope(envelope)  // single place for EL + FC update:
   a. engine_newPayloadV5(envelope.payload) → handle VALID/INVALID/SYNCING/ACCEPTED
   b. If VALID: update FC status PendingEnvelope → Full
   c. If INVALID: update FC status → Invalid, propagate
   d. If SYNCING/ACCEPTED: keep PendingEnvelope, re-check on EL notification
   e. Send FCU with execution block hash
```

### 5. Fork-Choice Changes

- Block import creates node with:
  - `executionStatus: ExecutionStatus.Syncing`
  - `payloadStatus: PayloadStatus.PendingEnvelope`
  - `executionPayloadBlockHash: bid.blockHash` (immutable — same as envelope hash by spec)
- Envelope arrival updates node:
  - `executionStatus: ExecutionStatus.Valid` (after newPayload returns VALID)
  - `payloadStatus: PayloadStatus.Full`
  - `executionPayloadBlockHash` stays the same (equality-checked, not updated)
- **No PENDING/FULL variant split** — single node, status updates in place
- **No reconcilePendingDescendant needed** — no dual variants to reconcile
- **In-place status transition MUST trigger**: best-descendant/head viability recomputation
  including ancestor/descendant effects (call `updateBestDescendant` path after status change)

#### Duplicate/conflicting envelopes
- If a second envelope arrives for the same blockRoot:
  - If already `Full` → IGNORE (duplicate)
  - If different payload hash from bid → REJECT (equivocation)

#### EL return codes
- `VALID` → PendingEnvelope → Full
- `INVALID` → PendingEnvelope → Invalid (propagate to descendants)
- `SYNCING` / `ACCEPTED` → keep PendingEnvelope, await async EL notification
- Error → log + keep PendingEnvelope, retry on next FCU cycle

### 6. BN API Changes

- `produceAttestationData`: Skip `notOnOptimisticBlockRoot` for post-Gloas (already done)
  - Rationale: blocks are naturally PendingEnvelope until envelope arrives, validators vote on beacon block
- `notOnOptimisticBlockRoot`: Add Gloas awareness — PendingEnvelope is expected, not an error

### 7. What Gets Removed

From current PR #8941:
- [ ] `scheduleDeferredEnvelopeImport()` and retry worker
- [ ] `BLOCK_ROOT_UNKNOWN` error handling in envelope gossip (replaced by cache lookup)
- [ ] `reconcilePendingDescendant()` in protoArray
- [ ] `propagateDescendantUpdateToAncestors()` 
- [ ] PENDING/FULL variant split in fork-choice (single node with status field)
- [ ] `getHeadExecutionBlockHash()` helper (no longer needed without variants)
- [ ] VC retry wrappers (already removed)

### 8. What Stays

- Notifier execution payload info display (improved logging is good)
- BN-side skip of optimistic check for post-Gloas attestation data
- Engine API V5 handling for post-Gloas payloads
- Self-build envelope validation bypass for `BUILDER_INDEX_SELF_BUILD`

## PayloadEnvelopeInput State Machine

```
AwaitingEnvelope  →  Complete  →  Processed
  (created from bid)    (envelope attached)   (after newPayload + FC update)
```

- `AwaitingEnvelope`: created from bid, envelope is null
- `Complete`: envelope attached and validated against bid
- `Processed`: engine_newPayloadV5 returned, FC status updated to Full

## Edge Cases

1. **Envelope arrives before block**: 
   - IGNORE (not REJECT!) + store in **bounded orphan cache** (`orphanEnvelopeByRoot`, TTL ~1-2 epochs, size-limited)
   - gossipsub does NOT guarantee re-broadcast — REJECT would lose the envelope permanently
   - REJECT also penalizes honest peers for benign ordering skew
   - On bid creation (block gossip handler step 3-4), consume orphan if present and validate/attach
   - No background retries, no looping logic — just a one-shot check
   - Fallback: envelope req-resp sync by block root if orphan cache misses too

2. **Block arrives but envelope never comes**: Fork-choice node stays at `PendingEnvelope`. Head selection naturally prefers validated blocks. The chain moves forward when the next slot's block arrives. Add soft timeout metric (`pending > N slots`) for observability.

3. **Reorg during bid→envelope window**: Cache keys are by `blockRoot` (not head), so reorg-safe. Continue accepting envelope for non-canonical but unfinalized branches. Prune at finalization.

4. **Self-built blocks**: Proposer builds the payload themselves. The envelope is available immediately (no gossip wait). Import both block and envelope in the same flow.

## Cache Lifecycle & DOS Protection

- `SeenPayloadEnvelopeCache`: prune on finalization (`onFinalized`), also slot-based TTL (~2 epochs)
- `orphanEnvelopeByRoot`: bounded size (e.g., 64 entries), TTL ~2 epochs, FIFO eviction
- Non-canonical branches: keep entries until finalization prune (reorg-safe)
- Envelope for already-pruned/orphaned block: IGNORE silently

## Test Matrix

Must cover all arrival orders:
1. Block then envelope (happy path)
2. Envelope then block (orphan cache path)
3. Block only, no envelope (PendingEnvelope stays)
4. Duplicate envelope (IGNORE)
5. Conflicting envelope hash (REJECT as equivocation)
6. EL returns SYNCING then later VALID (async notification)
7. EL returns INVALID (propagate to descendants)
8. Reorg during bid→envelope window
9. Self-built block (immediate envelope)

## Migration Plan (Priority Order)

1. **Create `PayloadEnvelopeInput` and `SeenPayloadEnvelopeCache`** — new files
2. **Update block gossip handler** — use `BlockInputPayloadBid`, populate envelope cache from bid
3. **Update envelope gossip handler** — look up bid from cache, validate, import
4. **Simplify fork-choice** — single node status instead of PENDING/FULL variants, remove reconciliation
5. **Remove deferred envelope infrastructure** — queue, retry worker, BLOCK_ROOT_UNKNOWN handling
6. **Update naming** — PayloadBid, PendingEnvelope, etc.
7. **Test on Kurtosis** — verify devnet with Lighthouse + Geth
