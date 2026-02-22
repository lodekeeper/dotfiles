# EPBS Devnet-0 — Research Notes

## Base Branch
- `nflaig/epbs-devnet-0` on ChainSafe/lodestar
- Contains: unstable + PR #8931 (fork choice fixes) + PR #8868 (state cache) + PR #8739 (epbs fork choice) + build fix
- 65 files changed, ~3,061 insertions vs unstable

## What's Already Done in Lodestar
1. **State transition** — `processExecutionPayloadEnvelope`, `processBuilderPendingPayments`, etc.
2. **Fork choice** — ePBS-specific proto-array with PayloadStatus.PENDING/FULL/EMPTY/WITHHELD
3. **State cache** — ePBS state caching for persistent checkpoints
4. **SSZ Types** — All Gloas types defined (packages/types/src/gloas/)
5. **Gossip topics** — Registered for execution_payload, execution_payload_bid, payload_attestation_message
6. **Gossip validation** — Basic validation for all 3 gossip types
7. **Op pools** — executionPayloadBidPool, payloadAttestationPool
8. **Block production** — Basic produceBlockBody with ePBS bid (self-build only)
9. **Execution payload envelope repos** — DB storage for envelopes
10. **Seen caches** — seenGossipBlockInput, seenExecutionPayloadBids

## What's Missing (from TODO GLOAS analysis + Lighthouse comparison)

### 🔴 CRITICAL: Block/Envelope Import Pipeline
The biggest gap. Currently the gossip handler for `execution_payload` just validates and stops:
```
// TODO GLOAS: Handle valid envelope. Need an import flow that calls processExecutionPayloadEnvelope and fork choice
```

**Need to implement:**
1. **Envelope import flow** — After gossip validation:
   - Load state snapshot for the block (state at block's state_root)
   - Run `processExecutionPayloadEnvelope` state transition
   - Notify execution layer (newPayload)
   - Update fork choice: `on_execution_payload` (change payload status from PENDING → FULL)
   - Store envelope in DB
   - Emit `execution_payload_available` SSE event
2. **BlockInput for Gloas** — Currently throws "Not implemented" in seenGossipBlockInput
   - Nico suggests: BlockInput for gloas = BlockInputPreData (import beacon block immediately)
   - Separate ExecutionPayloadInput for envelope + data columns
3. **API endpoint for publishing envelope** — POST /eth/v1/beacon/execution_payload_envelope
   - Currently has TODO stubs

### 🟡 APIs and Events (beacon-APIs PR #552)
1. **`execution_payload_available` EVENT** — Emit after successful envelope import
2. **`execution_payload_bid` EVENT** — Emit when bid received via gossip or API
3. **GET /eth/v1/validator/execution_payload_bid/{slot}/{builder_index}** — Return bid from pool/cache
4. **GET /eth/v1/beacon/execution_payload_envelope/{block_id}** — Return stored envelope
5. **POST /eth/v1/beacon/execution_payload_bid** — Submit bid to pool + gossip
6. **POST /eth/v1/beacon/execution_payload_envelope** — Import + publish envelope

### 🟡 Gossip Handler Wiring
1. **execution_payload handler** — Needs full import flow (see above)
2. **block handler** — Needs to NOT process execution payload inline for post-gloas blocks
3. **DataColumnSidecar handler** — `// TODO GLOAS: handle gloas.DataColumnSidecar` (NOT needed for devnet-0)

### 🟡 Block Production Completion
1. **Pending payload envelope cache** — Store unsigned envelope after block production
   - Lighthouse: `pending_payload_envelopes` cache
   - Needed for GET /eth/v1/validator/execution_payload_envelope/{slot}/{builder_index}
2. **produceBlockBody** — Need to get payload attestations from pool (TODO at line 281)
3. **Execution payload handling in produceBlockBody** — Revisit after fork choice (TODO at line 719)

### 🟡 Validator Client Changes
1. **Block service** — After publishing beacon block, fetch+sign+publish execution payload envelope
   - Flow: produce block → publish block → sleep → fetch envelope → sign → publish envelope
2. **Block duties** — Re-evaluate timing (TODO at line 15)

### 🟢 Validation Improvements (can be deferred)
1. **executionPayloadBid validation** — Missing proposer preference checks (NOT needed per Nico)
2. **block validation** — Missing execution payload parent check (line 156)
3. **executionPayloadEnvelope validation** — Queuing for later if block not yet imported (line 38, 70)
4. **payloadAttestationMessage validation** — Similar queuing issue (line 72)

### 🟢 Sync (Partial)
- **ExecutionPayloadEnvelopesByRoot** — Likely needed for unknown block/payload sync
- **Long range sync** — NOT needed

## NOT in Scope (per Nico)
- Data column sidecar handling (no blobs on devnet)
- PTC (payload timeliness committee) — produce empty PTC blocks
- Builder bids handling — all blocks self-built
- Proposer preferences — no external builders
- Long range sync
- builder.md spec

## Lighthouse Architecture Reference
### Envelope Verification Pipeline
```
SignedExecutionPayloadEnvelope
  → GossipVerifiedEnvelope (gossip validation + signature check)
    → ExecutionPendingEnvelope (state transition + EL notification started)
      → ExecutedEnvelope (EL confirmed)
        → AvailableExecutedEnvelope (data available)
          → import into fork choice + DB
```

### Key Lighthouse Files
- `beacon_chain/src/payload_envelope_verification/mod.rs` — Types + load_snapshot
- `beacon_chain/src/payload_envelope_verification/gossip_verified_envelope.rs` — Gossip validation
- `beacon_chain/src/payload_envelope_verification/import.rs` — Import flow
- `beacon_chain/src/block_production/gloas.rs` — Block production (863 lines)
- `beacon_chain/src/pending_payload_envelopes.rs` — Cache for VC fetch
- `http_api/src/beacon/execution_payload_envelope.rs` — REST endpoints
- `http_api/src/validator/execution_payload_envelope.rs` — VC endpoint
- `validator_services/src/block_service.rs` — VC block+envelope publishing

### Lighthouse Block Production Flow
1. `produce_partial_beacon_block_gloas` — Atts, slashings, exits, payload attestations
2. `produce_execution_payload_bid` — Get payload from EL, create bid
3. `complete_partial_beacon_block_gloas` — Combine into block with bid, run STF, store pending envelope
4. VC: publish block → sleep 4s → fetch envelope → sign → publish envelope

### Lighthouse Envelope Import Flow
1. Gossip/API receives SignedExecutionPayloadEnvelope
2. `verify_envelope_for_gossip` — Check block known, slot, builder index, block hash, signature
3. Publish to network (re-gossip)
4. `into_execution_pending_envelope` — Load state, run processExecutionPayloadEnvelope, notify EL
5. `import_execution_payload_envelope` — Update fork choice (on_execution_payload), store in DB
6. Emit execution_payload_available event

## Kurtosis Config Needed
- Need to find/create config with Lodestar + Lighthouse + Geth
- Lighthouse epbs-devnet-0 docker image needed
- Geth with ePBS support (check ethpandaops)
