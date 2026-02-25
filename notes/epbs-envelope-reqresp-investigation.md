# Investigation: ExecutionPayloadEnvelopesByRoot ReqResp

**Date:** 2026-02-24
**Source:** Nico (PR #8947 review + PR #8949 comment)
**Branch:** `epbs-devnet-0`

## Problem

Currently, execution payload envelopes in Lodestar only arrive via gossip (`execution_payload` topic). During UnknownBlockSync catch-up, nodes that missed gossip have no way to recover envelopes — they rely on `chain.pendingEnvelopes` (gossip cache) which is ephemeral and slot-limited.

This means:
1. Nodes syncing via reqresp (blocks-by-root/range) never get envelopes
2. Blocks that extend FULL parent path can't verify state root without the parent envelope
3. The current workaround (gossip subscription during SyncingHead/Stalled in PR #8949) is fragile and not spec-compliant

## Spec Reference

The Gloas P2P spec defines two new reqresp methods:

### ExecutionPayloadEnvelopesByRoot v1
- **Protocol ID:** `/eth2/beacon_chain/req/execution_payload_envelopes_by_root/1/`
- **Request:** `List[Root, MAX_REQUEST_PAYLOADS]` (block roots)
- **Response:** `List[SignedExecutionPayloadEnvelope, MAX_REQUEST_PAYLOADS]`
- **Purpose:** Recover envelopes by beacon block root (primary use: unknown block sync)

### ExecutionPayloadEnvelopesByRange v1
- **Protocol ID:** `/eth2/beacon_chain/req/execution_payload_envelopes_by_range/1/`
- **Request:** `{start_slot: Slot, count: uint64}`
- **Response:** `List[SignedExecutionPayloadEnvelope, MAX_REQUEST_BLOCKS_DENEB]`
- **Purpose:** Range sync (parallel to BeaconBlocksByRange)

## Current State

- `MAX_REQUEST_PAYLOADS = 128` ✅ (already in config)
- `SignedExecutionPayloadEnvelope` SSZ type ✅ (already defined in `@lodestar/types`)
- `db.executionPayloadEnvelope` ✅ (hot DB, keyed by beaconBlockRoot)
- `db.executionPayloadEnvelopeArchive` ✅ (cold DB, keyed by slot)
- `chain.importExecutionPayloadEnvelope()` ✅ (import logic exists)
- **Missing:** ReqResp protocol definition, handler, sender, integration with unknownBlock

## Implementation Scope

### Phase 1: ExecutionPayloadEnvelopesByRoot (Priority — fixes REGEN issue)

1. **`packages/beacon-node/src/network/reqresp/types.ts`**
   - Add `ExecutionPayloadEnvelopesByRoot` to `ReqRespMethod` enum
   - Add request/response body type mappings

2. **`packages/beacon-node/src/network/reqresp/protocols.ts`**
   - Add `ExecutionPayloadEnvelopesByRoot` protocol definition (similar to `BlobSidecarsByRoot`)

3. **`packages/beacon-node/src/network/reqresp/handlers/executionPayloadEnvelopesByRoot.ts`** (new)
   - Server-side handler: lookup envelopes from `db.executionPayloadEnvelope` by block root
   - Similar pattern to `blobSidecarsByRoot.ts`

4. **`packages/beacon-node/src/network/reqresp/ReqRespBeaconNode.ts`**
   - Register protocol + handler for Gloas fork
   - Add `sendExecutionPayloadEnvelopesByRoot` method

5. **`packages/beacon-node/src/network/interface.ts`**
   - Add `sendExecutionPayloadEnvelopesByRoot` to `INetwork` interface

6. **`packages/beacon-node/src/network/network.ts`**
   - Implement `sendExecutionPayloadEnvelopesByRoot`

7. **`packages/beacon-node/src/sync/unknownBlock.ts`** (key change)
   - In `processBlock()` after block import: if no pending envelope and fork is Gloas, request envelope via reqresp
   - Integrate with download retry logic

8. **`packages/beacon-node/src/sync/utils/downloadByRoot.ts`** (optional)
   - Extend `downloadByRoot` to also fetch envelope for Gloas blocks

### Phase 2: ExecutionPayloadEnvelopesByRange (Lower priority — range sync)

- Similar to BeaconBlocksByRange but for envelopes
- Needed for full range sync support but not critical for devnet-0

## Pattern Reference

The closest existing analog is `DataColumnSidecarsByRoot`:
- Same request format (`List[Root]` vs `List[{Root, columns}]`)
- Same fork-gated activation pattern
- Same handler pattern (lookup from DB, respond with available items)

## Complexity Estimate

- **Phase 1 (ByRoot):** Medium — ~8 files, ~300 lines. Follows established patterns.
- **Phase 2 (ByRange):** Medium — additional ~5 files, ~200 lines.

## Dependencies

- No spec changes needed — Gloas P2P spec already defines both protocols
- No type changes needed — SSZ types already exist
- DB repositories already exist for storing/retrieving envelopes

## Impact

This would:
1. **Eliminate the REGEN_ERROR issue** — syncing nodes can fetch envelopes via reqresp, no gossip dependency
2. **Remove the need for gossip subscription workaround** (PR #8949 on `epbs-devnet-0`)
3. **Enable proper range sync** for EPBS (Phase 2)
4. **Align with spec** — these are mandatory P2P methods for Gloas
