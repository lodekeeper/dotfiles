# Deneb — Beacon Chain & Data Availability

*Studied: 2026-02-18*

## Overview

Deneb is the consensus-layer companion to the execution-layer Cancun upgrade. It introduces:

1. **EIP-4844** (Proto-Danksharding): Blob transactions with KZG commitments — the biggest change
2. **EIP-4788**: Beacon block root in the EVM (parent beacon block root passed to execution engine)
3. **EIP-7044**: Perpetually valid signed voluntary exits (fixed to `CAPELLA_FORK_VERSION`)
4. **EIP-7045**: Increased attestation inclusion window (full next epoch for target)
5. **EIP-7514**: Max epoch churn limit for validator activations

## EIP-4844: Proto-Danksharding (Blob Sidecars)

### Key Concept
Blobs are large data payloads (~128KB each, up to 6 per block) attached to blocks but transmitted **separately** as "sidecars". This is the foundation for future data availability sampling (DAS/PeerDAS).

### New Types
- `Blob` = `ByteVector[BYTES_PER_FIELD_ELEMENT * FIELD_ELEMENTS_PER_BLOB]` (131,072 bytes = 128KB)
- `KZGCommitment`, `KZGProof` = `Bytes48` (BLS G1 points)
- `VersionedHash` = `Bytes32` (commitment hash with version prefix `0x01`)
- `BlobSidecar` = `{index, blob, kzgCommitment, kzgProof, signedBlockHeader, kzgCommitmentInclusionProof}`
- `BlobIdentifier` = `{blockRoot, index}` (for req/resp by-root requests)

### Constants
| Name | Value | Notes |
|------|-------|-------|
| `MAX_BLOB_COMMITMENTS_PER_BLOCK` | 4096 | Theoretical max (upgrade-independent) |
| `MAX_BLOBS_PER_BLOCK` | 6 | Practical limit (Deneb) |
| `BLOB_SIDECAR_SUBNET_COUNT` | 6 | One subnet per blob index |
| `KZG_COMMITMENT_INCLUSION_PROOF_DEPTH` | 17 | Merkle proof depth |
| `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` | 4096 | ~18 days blob retention |
| `MAX_REQUEST_BLOCKS_DENEB` | 128 | Reduced from previous 1024 |

### Beacon Block Changes
- `BeaconBlockBody` gains `blobKzgCommitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]`
- `ExecutionPayload` gains `blobGasUsed: uint64`, `excessBlobGas: uint64`
- `ExecutionPayloadHeader` gains same two fields
- `BeaconState.latestExecutionPayloadHeader` type updated accordingly

### Block Processing (`process_execution_payload`)
1. Validate `len(blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK`
2. Compute `versioned_hashes` from commitments via `kzg_commitment_to_versioned_hash`
3. Pass both `versioned_hashes` AND `parent_beacon_block_root` to `verify_and_notify_new_payload`
4. Engine validates: no empty transactions, valid block hash (with beacon root), valid versioned hashes, valid payload

### Fork Choice (`is_data_available`)
- **Critical gate**: Block MUST NOT be considered valid until all blobs are available
- `on_block` calls `is_data_available(block_root, blob_kzg_commitments)` before state transition
- Implementation: retrieve all blobs+proofs, verify via `verify_blob_kzg_proof_batch`
- Blocks previously validated as available remain available even after blob pruning

### Versioned Hash Computation
```
kzg_commitment_to_versioned_hash(commitment) = VERSIONED_HASH_VERSION_KZG || sha256(commitment)[1:]
```
First byte is `0x01`, remaining 31 bytes from SHA-256 hash.

### Lodestar Implementation

**Types** (`packages/types/src/deneb/sszTypes.ts`):
- All spec types faithfully implemented using `@chainsafe/ssz`
- `Blob` = `ByteVectorType(BYTES_PER_FIELD_ELEMENT * FIELD_ELEMENTS_PER_BLOB)`
- Additional types: `BlobsBundle`, `BlockContents`, `SignedBlockContents` (for validator API)
- `BlindedBeaconBlock` with `blobKzgCommitments` for builder API

**Versioned Hash** (`packages/beacon-node/src/util/blobs.ts`):
- `kzgCommitmentToVersionedHash()` — uses `@chainsafe/as-sha256` digest, sets `hash[0] = VERSIONED_HASH_VERSION_KZG`
- Also contains `getBlobSidecars()` (spec's `get_blob_sidecars`) and `computePreFuluKzgCommitmentsInclusionProof()`

**Data Availability** (`packages/beacon-node/src/chain/blocks/verifyBlocksDataAvailability.ts`):
- `BLOB_AVAILABILITY_TIMEOUT = 12_000ms` (full slot time)
- Uses `IBlockInput.waitForAllData()` — blocks arrive via gossip, blobs may come separately
- Returns `DataAvailabilityStatus`: `PreData`, `OutOfRange`, or `Available`
- **Smart design**: Block input is a stateful object that can receive block and blobs independently, with promises for waiting

**Block Input System** (`packages/beacon-node/src/chain/blocks/blockInput/`):
- `DAType.PreData` (pre-Deneb), `DAType.Blobs` (Deneb), `DAType.Columns` (Fulu/PeerDAS)
- `BlockInputSource` enum tracks where data came from: gossip, api, engine, byRange, byRoot, recovery
- Block and blobs can arrive in any order; the system tracks completeness and resolves promises

**Gossip Validation** (`packages/beacon-node/src/chain/validation/blobSidecar.ts`):
- `validateGossipBlobSidecar()` — comprehensive validation matching spec exactly:
  - Index < MAX_BLOBS_PER_BLOCK (dynamic via `config.getMaxBlobsPerBlock()`)
  - Correct subnet (`computeSubnetForBlobSidecar()` — Electra changed subnet count)
  - Not from future slot (with gossip disparity)
  - After finalized slot
  - Parent block known in fork choice
  - Higher slot than parent
  - Proposer signature valid (cached via `seenBlockInputCache`)
  - Inclusion proof valid (`validateBlobSidecarInclusionProof`)
  - KZG proof valid (`validateBlobsAndBlobProofs`)
  - Expected proposer for slot
- `validateBlockBlobSidecars()` — batch validation for req/resp (KZG batch verification)
- **Performance optimization**: Proposer signature verification is cached in `seenBlockInputCache` — if the block header signature was already verified (e.g., from the block gossip), skip re-verification for blob sidecars

**Inclusion Proof** (`validateBlobSidecarInclusionProof`):
- Uses `verifyMerkleBranch` with `KZG_COMMITMENT_SUBTREE_INDEX0 + blobSidecar.index` as gindex
- Verifies `hashTreeRoot(kzgCommitment)` against `bodyRoot` in signed block header

**Req/Resp** (`packages/beacon-node/src/network/reqresp/handlers/`):
- `blobSidecarsByRange.ts`: Iterates finalized (archive DB) then unfinalized (fork choice head chain)
  - Uses binary blob storage with fixed-size sidecar serialization for efficiency
  - `iterateBlobBytesFromWrapper()` slices blobs from wrapped storage format
  - Validates request: count >= 1, startSlot >= genesis, count <= MAX_REQUEST_BLOCKS_DENEB
- `blobSidecarsByRoot.ts`: Lookup by block root + blob index

**EL Blob Retrieval** (`packages/beacon-node/src/execution/engine/http.ts`):
- `engine_getBlobsV1` for pre-Fulu, `engine_getBlobsV2` for Fulu+
- Called when receiving a valid gossip block that contains blob transactions
- Per spec: "Honest nodes SHOULD query `engine_getBlobsV1` as soon as they receive a valid gossip block that contains data"
- `MAX_VERSIONED_HASHES = 1024` — limit per request

## EIP-4788: Beacon Block Root in EVM

### Spec Change
- `NewPayloadRequest` gains `parent_beacon_block_root: Root`
- `PayloadAttributes` gains `parent_beacon_block_root: Root`
- Passed through to `is_valid_block_hash` and `notify_new_payload`
- In `process_execution_payload`: `parent_beacon_block_root = state.latest_block_header.parent_root`

### Lodestar
- `PayloadAttributes` SSZ type extends Capella with `parentBeaconBlockRoot: Root`
- Wired through execution engine API calls

## EIP-7044: Perpetually Valid Signed Voluntary Exits

### Spec Change
- `process_voluntary_exit` uses `CAPELLA_FORK_VERSION` (fixed) for computing the signing domain
- Before Deneb: domain used the fork version at the exit's epoch
- After Deneb: always Capella fork version → exits signed at Capella remain valid forever

### Lodestar (`packages/config/src/genesisConfig/index.ts`)
```typescript
getDomainForVoluntaryExit(stateSlot, messageSlot) {
  return stateSlot < chainForkConfig.DENEB_FORK_EPOCH * SLOTS_PER_EPOCH
    ? this.getDomain(stateSlot, DOMAIN_VOLUNTARY_EXIT, messageSlot)  // pre-Deneb: epoch-specific
    : this.getDomainAtFork(ForkName.capella, DOMAIN_VOLUNTARY_EXIT); // Deneb+: fixed to Capella
}
```
Clean implementation — single function that handles both pre/post Deneb.

## EIP-7045: Increased Attestation Inclusion Window

### Spec Change
- **Before Deneb**: Attestation valid for `ATTESTATION_PROPAGATION_SLOT_RANGE` (32 slots)
- **After Deneb**: Valid for the entire current epoch + previous epoch
  - Gossip: `attestation.data.slot <= current_slot` (no upper range check)
  - Gossip: epoch must be current or previous
  - `TIMELY_TARGET_FLAG` awarded regardless of `inclusion_delay` (always timely for target)

### Lodestar (`packages/state-transition/src/block/processAttestationPhase0.ts`)
```typescript
export function isTimelyTarget(fork: ForkSeq, inclusionDistance: Slot): boolean {
  if (fork >= ForkSeq.deneb) return true;  // Always timely post-Deneb
  return inclusionDistance <= SLOTS_PER_EPOCH;
}
```
- `process_attestation` removes the upper slot bound check (just `data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot`)
- Gossip validation updated to allow attestations from current/previous epoch

## EIP-7514: Max Epoch Churn Limit

### Spec Change
- New function `get_validator_activation_churn_limit(state)`:
  ```python
  return min(MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT, get_validator_churn_limit(state))
  ```
- `MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT = 8`
- Used in `process_registry_updates` to cap the activation queue
- **Motivation**: Prevent runaway validator growth that could overwhelm the network

### Lodestar (`packages/state-transition/src/util/validator.ts`)
```typescript
export function getActivationChurnLimit(config, fork, activeValidatorCount) {
  return Math.min(config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT, getChurnLimit(config, activeValidatorCount));
}
```

## Networking Changes

### New Gossip Topic: `blob_sidecar_{subnet_id}`
- 6 subnets (one per blob index in Deneb, changed in Electra)
- `subnet_id = blob_sidecar.index % BLOB_SIDECAR_SUBNET_COUNT`
- Extensive validation (14 rules) including KZG proof, inclusion proof, proposer check
- Fork digest from `compute_epoch_at_slot(blob_sidecar.signed_block_header.message.slot)`

### New Req/Resp: `BlobSidecarsByRange v1`
- Request: `{start_slot, count}`
- Response: `List[BlobSidecar, MAX_REQUEST_BLOB_SIDECARS]`
- Ordered by `(slot, index)`
- Must serve `blob_serve_range = [max(current_epoch - 4096, DENEB_FORK_EPOCH), current_epoch]`
- Clients MUST include ALL blob sidecars of each block (no partial blocks)

### New Req/Resp: `BlobSidecarsByRoot v1`
- Request: `List[BlobIdentifier, MAX_REQUEST_BLOB_SIDECARS]`
- Response: `List[BlobSidecar, MAX_REQUEST_BLOB_SIDECARS]`
- Used for recovering missing blobs

### Modified: `BeaconBlocksByRange/Root v2`
- Now includes Deneb fork digest in context
- Max request size reduced to `MAX_REQUEST_BLOCKS_DENEB = 128` (was 1024)

### Blob Retrieval via Local EL
- `engine_getBlobsV1` — retrieve blobs from local EL client
- Called as soon as valid gossip block with data is received
- Must republish blobs to gossip subnets (update anti-equivocation cache)

## Architecture Observations

### Separation of Concerns
The blob sidecar design is elegant:
1. Blocks carry only commitments (48 bytes each) — small
2. Blobs travel separately as sidecars (~128KB each) — can be pruned after ~18 days
3. KZG proofs bind blobs to commitments cryptographically
4. Inclusion proofs bind commitments to blocks via Merkle tree

This separation directly enables PeerDAS/Fulu: replace full blob retrieval with column-based DAS, same block structure.

### Lodestar's Block Input System
The `IBlockInput` abstraction is well-designed for handling the asynchronous nature of block+blob arrival:
- Block and blobs can arrive in any order
- Promise-based waiting with configurable timeout
- Source tracking (gossip vs req/resp vs engine)
- Graceful handling of DA-out-of-range (historical blocks beyond blob retention)

### Performance Considerations
- KZG verification is batched (`verify_blob_kzg_proof_batch`) for efficiency
- Proposer signature caching in `seenBlockInputCache` avoids redundant BLS verification
- Binary blob storage with fixed-size serialization for efficient DB I/O
- `BLOB_AVAILABILITY_TIMEOUT = 12s` (full slot) — generous window since unavailable block sync handles recovery

## Cross-References
- **Fork choice**: Deneb `on_block` adds `is_data_available` check before state transition
- **Fulu/PeerDAS**: Extends blob sidecars to data column sidecars; `dataColumnMatrixRecovery` in `blobs.ts`
- **Electra**: Changes `BLOB_SIDECAR_SUBNET_COUNT` (Lodestar handles via `computeSubnetForBlobSidecar`)

## Potential Issues / Notes
- The `MAX_BLOBS_PER_BLOCK` is a configuration value, not a constant — Lodestar correctly uses `config.getMaxBlobsPerBlock(epoch)` which allows per-fork blob limits
- Blob pruning after `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` means nodes that start from weak subjectivity must backfill blobs
- The 128-block request limit (down from 1024) reduces bandwidth spikes but means more req/resp rounds during sync
