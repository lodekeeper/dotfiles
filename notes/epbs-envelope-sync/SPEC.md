# EPBS Envelope Sync — Implementation Spec

## Problem
Lodestar's EPBS (Gloas fork) implementation is missing two critical reqresp methods needed for sync:
1. `ExecutionPayloadEnvelopesByRange v1`
2. `ExecutionPayloadEnvelopesByRoot v1`

Without these, when LS syncs Gloas blocks from another node (e.g. Lighthouse) via `beacon_blocks_by_range`, 
it gets the beacon blocks (which contain bids, not payloads) but has NO way to fetch the corresponding 
execution payload envelopes. This means LS can't process Gloas blocks during sync.

## Branch
Work on `~/lodestar-epbs-devnet-0` (worktree for `nflaig/epbs-devnet-0` branch).

## Spec Reference
From `consensus-specs/specs/gloas/p2p-interface.md`:

### ExecutionPayloadEnvelopesByRange v1
- Protocol ID: `/eth2/beacon_chain/req/execution_payload_envelopes_by_range/1/`
- Request: `(start_slot: Slot, count: uint64)` — same as BeaconBlocksByRange
- Response: `List[SignedExecutionPayloadEnvelope, MAX_REQUEST_BLOCKS_DENEB]`
- Fork digest context: `GLOAS_FORK_VERSION`
- SSZ type: `gloas.SignedExecutionPayloadEnvelope`

### ExecutionPayloadEnvelopesByRoot v1
- Protocol ID: `/eth2/beacon_chain/req/execution_payload_envelopes_by_root/1/`
- Request: `List[Root, MAX_REQUEST_PAYLOADS]` where `MAX_REQUEST_PAYLOADS = 128`
- Response: `List[SignedExecutionPayloadEnvelope, MAX_REQUEST_PAYLOADS]`
- Fork digest context: `GLOAS_FORK_VERSION`

## Implementation Tasks

### 1. Define the reqresp methods
File: `packages/beacon-node/src/network/reqresp/types.ts` (or similar)

Add new method definitions following the pattern of existing methods like `BeaconBlocksByRange`.
Need to define:
- Protocol string
- Request/response types
- SSZ encoding/decoding
- Version number

Look at how `BeaconBlocksByRange` and `BlobSidecarsByRange` are defined and follow the same pattern.

### 2. Implement the responder (server side)
When LS receives a request for envelopes:
- For ByRange: iterate slots `start_slot..start_slot+count`, fetch envelopes from DB
- For ByRoot: look up envelopes by beacon block root in DB

The envelope data should already be stored in the DB (check `packages/beacon-node/src/db/repositories/` 
for existing envelope repositories — there's already `executionPayloadEnvelope` repos from the EPBS branch).

### 3. Implement the requester (client side)  
When LS does range sync and downloads Gloas blocks, it should ALSO request envelopes:
- After `beacon_blocks_by_range` returns Gloas blocks, issue `execution_payload_envelopes_by_range` 
  for the same slot range
- Associate envelopes with their blocks (via `beacon_block_root`)
- Feed envelopes into the `pendingEnvelopes` cache so the block import pipeline can use them

### 4. Wire into sync module
File: `packages/beacon-node/src/sync/` area

The range sync module downloads batches of blocks. For Gloas batches, it needs to also download envelopes.
Either:
a. Download envelopes in the same batch (modify batch download to include envelopes)
b. Download envelopes in a parallel request after blocks arrive

Option (a) is cleaner. Follow how `data_column_sidecars_by_range` was added for PeerDAS.

## Key Files to Study (patterns to follow)
- `packages/beacon-node/src/network/reqresp/` — existing reqresp definitions
- `packages/beacon-node/src/network/reqresp/beaconBlocksMaybeBlobsByRange.ts` — how blocks+blobs are fetched together
- `packages/beacon-node/src/sync/range/` — range sync implementation
- `packages/beacon-node/src/db/repositories/executionPayloadEnvelope.ts` — DB storage
- `packages/beacon-node/src/chain/blocks/blockInput/` — how block inputs are constructed

## Testing
After implementation:
1. Build Docker image: `cd ~/lodestar-epbs-devnet-0 && docker build -t lodestar:epbs-devnet-0-latest .`
2. Run devnet with config at `/tmp/epbs-interop-updated.yaml` (LH + updated LS)
3. Verify LS can sync past Gloas fork (slot 8+)
4. Verify envelopes are fetched and blocks are processed
