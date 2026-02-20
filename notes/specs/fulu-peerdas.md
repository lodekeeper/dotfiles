# Fulu/PeerDAS Consensus Specs — Study Notes

*Studied: 2026-02-18*
*Spec files: `specs/fulu/das-core.md`, `specs/fulu/beacon-chain.md`, `specs/fulu/fork-choice.md`, `specs/fulu/p2p-interface.md`, `specs/fulu/validator.md`, `specs/fulu/polynomial-commitments-sampling.md`*
*Lodestar: `packages/beacon-node/src/util/dataColumns.ts`, `packages/beacon-node/src/chain/`, `packages/beacon-node/src/network/`*

---

## Overview

Fulu is the next consensus fork (after Electra). It bundles **3 EIPs**:

1. **EIP-7594**: PeerDAS — Peer Data Availability Sampling
2. **EIP-7917**: Deterministic proposer lookahead
3. **EIP-7892**: Blob Parameter Only Hardforks (BPO forks)

PeerDAS is the headline feature — replacing per-blob distribution with a column-based data availability sampling scheme, enabling higher blob throughput without requiring every node to download every blob.

---

## EIP-7594: PeerDAS — Data Availability Sampling

### Core Concept
Instead of distributing full blobs, blob data is encoded into an **extended matrix** (rows × columns) using 1D erasure coding. Each blob becomes a row; columns are distributed across the network. Any 50%+ of columns can reconstruct the full data.

### Key Parameters
| Parameter | Value | Notes |
|-----------|-------|-------|
| `NUMBER_OF_COLUMNS` | 128 | Fixed: equals `CELLS_PER_EXT_BLOB` |
| `NUMBER_OF_CUSTODY_GROUPS` | 128 | Groups of columns that nodes custody together |
| `CUSTODY_REQUIREMENT` | 4 | Minimum groups for regular nodes |
| `VALIDATOR_CUSTODY_REQUIREMENT` | 8 | Minimum groups for validator nodes |
| `SAMPLES_PER_SLOT` | 8 | Minimum samples per slot |
| `BALANCE_PER_ADDITIONAL_CUSTODY_GROUP` | 32 ETH | Extra custody per 32 ETH of validator balance |
| `DATA_COLUMN_SIDECAR_SUBNET_COUNT` | 128 | One subnet per column |
| `MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` | 4096 | ~18 days retention |

### Data Structures

**`DataColumnSidecar`** — A vertical slice through all blobs:
```
DataColumnSidecar {
  index: ColumnIndex           // Which column (0-127)
  column: List[Cell, MAX]      // One cell per blob
  kzg_commitments: List[KZGCommitment, MAX]
  kzg_proofs: List[KZGProof, MAX]
  signed_block_header: SignedBeaconBlockHeader
  kzg_commitments_inclusion_proof: Vector[Bytes32, 4]
}
```

**`MatrixEntry`** — Single cell in the matrix:
```
MatrixEntry {
  cell: Cell
  kzg_proof: KZGProof
  column_index: ColumnIndex
  row_index: RowIndex
}
```

### Custody System

1. **Deterministic assignment**: `get_custody_groups(node_id, count)` — hash-based, public, reproducible
2. **Column-to-group mapping**: `compute_columns_for_custody_group(group)` — `columns_per_group = 128/128 = 1` currently (1:1 mapping)
3. **Validator scaling**: Validators custody more based on total effective balance:
   - `count = total_balance / 32 ETH`, clamped to `[VALIDATOR_CUSTODY_REQUIREMENT, NUMBER_OF_CUSTODY_GROUPS]`
   - Nodes with ≥4096 ETH combined validator balance → **supernode** (custody all 128 groups)

### Sampling
At each slot, nodes sample `max(SAMPLES_PER_SLOT, custody_group_count)` groups. Sampling succeeds if all selected columns are retrieved. Custody groups are a subset of sampled groups.

### Reconstruction
- If ≥50% columns obtained → SHOULD reconstruct full matrix via `recover_matrix`
- After reconstruction: MUST expose new columns as if received via gossip
- If subscribed to reconstructed column's subnet → MUST publish to mesh
- MAY delete non-custodied columns after publishing

### Lodestar Implementation — `CustodyConfig` class
Well-designed class in `util/dataColumns.ts`:
- Tracks `targetCustodyGroupCount`, `custodyColumns`, `sampledColumns`, `sampledSubnets`
- `custodyColumnsIndex: Uint8Array` — O(1) lookup for "is this column custodied?"
- `updateTargetCustodyGroupCount()` — dynamic adjustment
- `getValidatorsCustodyRequirement()` — spec-compliant balance-based calculation

### Lodestar Implementation — `recoverDataColumnSidecars()`
- Only attempts recovery if `NUMBER_OF_COLUMNS/2 ≤ columns < NUMBER_OF_COLUMNS`
- Caps input to exactly 50% to minimize compute
- Uses `dataColumnMatrixRecovery()` from `util/blobs.ts` (async, KZG-based)
- After recovery: emits `ChainEvent.publishDataColumns` for network distribution
- Handles late resolution (gossip/getBlobsV2 completing during recovery)

---

## EIP-7917: Deterministic Proposer Lookahead

### Problem
Before Fulu, proposer selection was computed on-demand and could change with state updates. Pre-confirmation protocols need stable proposer knowledge.

### Solution
New `proposer_lookahead` field in `BeaconState`:
```
proposer_lookahead: Vector[ValidatorIndex, (MIN_SEED_LOOKAHEAD + 1) * SLOTS_PER_EPOCH]
```
With `MIN_SEED_LOOKAHEAD = 1`, this is `2 * 32 = 64` slots — current epoch + next epoch.

### Changes
1. **`get_beacon_proposer_index`** simplified: just reads `state.proposer_lookahead[slot % SLOTS_PER_EPOCH]`
2. **`process_proposer_lookahead`** added to epoch processing: shifts out current epoch, computes next+1 epoch's proposers
3. **`compute_proposer_indices`** / **`get_beacon_proposer_indices`**: batch computation helpers

### Impact
- Proposer index becomes deterministic at epoch boundaries
- No more per-slot computation of proposer selection
- Enables reliable pre-confirmation commitments

---

## EIP-7892: Blob Parameter Only Hardforks (BPO)

### Problem
Changing blob limits requires a full fork. This creates friction for blob throughput tuning.

### Solution
**Blob schedule** — a configuration list of `(epoch, max_blobs_per_block)` pairs that can update blob limits without changing the fork version.

```python
BLOB_SCHEDULE = [
  {"EPOCH": 412672, "MAX_BLOBS_PER_BLOCK": 15},
  {"EPOCH": 419072, "MAX_BLOBS_PER_BLOCK": 21},
]
```

### Key Changes
1. **`get_blob_parameters(epoch)`**: Returns active blob params for given epoch
2. **`compute_fork_digest`**: Modified to XOR base digest with hash of blob parameters — BPO changes create new fork digests without changing fork version
3. **`process_execution_payload`**: Blob limit checked via `get_blob_parameters()` instead of hardcoded constant
4. **ENR `nfd` field**: "Next fork digest" — enables peers to detect upcoming BPO fork divergence

### Mainnet Schedule
- Epoch 412672 (Dec 9, 2025): 15 blobs
- Epoch 419072 (Jan 7, 2026): 21 blobs

---

## P2P Changes

### Gossip
- **`blob_sidecar_{subnet_id}`** — DEPRECATED in Fulu
- **`data_column_sidecar_{subnet_id}`** — NEW: 128 subnets, one per column
  - Full validation: structural checks, KZG proofs, inclusion proofs, proposer signature
  - Anti-equivocation: first valid sidecar per `(slot, proposer, column)` wins
- **`beacon_block`**: Blob limit checked via `get_blob_parameters()`

### Req/Resp
- **`BlobSidecarsByRange/Root v1`** — DEPRECATED (transition period: serve pre-Fulu slots)
- **`DataColumnSidecarsByRange v1`** — NEW: Request columns by slot range
  - Request includes `columns: List[ColumnIndex, 128]` — request specific columns
  - Response ordered by `(slot, column_index)`
- **`DataColumnSidecarsByRoot v1`** — NEW: Request columns by block root
  - Uses `DataColumnsByRootIdentifier { block_root, columns: List[ColumnIndex, 128] }`
- **`Status v2`** — NEW field: `earliest_available_slot` (advertise data availability range)
- **`GetMetaData v3`** — NEW field: `custody_group_count`

### Distributed Blob Publishing
Honest nodes SHOULD query `engine_getBlobsV2` on seeing a valid block/column on gossip. If ALL blobs retrieved, convert to columns and import. This helps with late publishers.

### ENR Updates
- **`cgc`** field: Custody group count (uint64)
- **`nfd`** field: Next fork digest (Bytes4) — for BPO fork detection
- **`eth2` field**: `next_fork_epoch` covers both regular and BPO forks

---

## Fork Choice Changes

### `is_data_available`
Simplified: no longer takes `blob_kzg_commitments` as input. Just verifies columns can be retrieved and KZG proofs are valid:
```python
def is_data_available(beacon_block_root: Root) -> bool:
    column_sidecars = retrieve_column_sidecars(beacon_block_root)
    return all(
        verify_data_column_sidecar(cs) and verify_data_column_sidecar_kzg_proofs(cs)
        for cs in column_sidecars
    )
```

### `on_block`
Minor change: `is_data_available` call updated to new signature (no commitments param).

---

## BeaconState Changes

**1 new field**:
- `proposer_lookahead: Vector[ValidatorIndex, 64]` (EIP-7917)

---

## Validator Changes

### Custody Requirements
- Regular node: `CUSTODY_REQUIREMENT = 4` groups
- Validator node: `max(total_balance / 32 ETH, VALIDATOR_CUSTODY_REQUIREMENT=8)` groups
- Combined balance ≥ 4096 ETH → supernode (128 groups)
- SHOULD NOT decrease custody count after increase (sticky high-water mark)
- Changes persist across restarts

### Sidecar Construction
Three spec functions for building `DataColumnSidecars`:
1. `get_data_column_sidecars()` — from header + commitments + cells/proofs
2. `get_data_column_sidecars_from_block()` — from full signed block
3. `get_data_column_sidecars_from_column_sidecar()` — from any received sidecar (for distributed publishing)

### BlobsBundle
Modified: `proofs` now contains cell-level KZG proofs (`CELLS_PER_EXT_BLOB * MAX_BLOB_COMMITMENTS_PER_BLOCK`), not blob-level proofs.

---

## Polynomial Commitments & Sampling (`polynomial-commitments-sampling.md`)

Not studied in detail — delegated to `c-kzg` native library in Lodestar. Key functions:
- `compute_cells_and_kzg_proofs(blob)` → cells + proofs
- `recover_cells_and_kzg_proofs(cell_indices, cells)` → full recovery
- `verify_cell_kzg_proof_batch(commitments, indices, cells, proofs)` → batch verification

---

## Spec Compliance Assessment

### Lodestar Implementation Status
- ✅ `CustodyConfig` — deterministic custody group/column assignment
- ✅ `getCustodyGroups()` — spec-compliant hash-based selection
- ✅ `computeColumnsForCustodyGroup()` — correct column mapping
- ✅ `getValidatorsCustodyRequirement()` — balance-based scaling
- ✅ `getDataColumnSidecars()` / `getDataColumnSidecarsFromBlock()` / `getDataColumnSidecarsFromColumnSidecar()` — all three spec functions
- ✅ `recoverDataColumnSidecars()` — reconstruction with gossip cross-seeding
- ✅ `DataColumnSidecarsByRange` / `DataColumnSidecarsByRoot` req/resp handlers
- ✅ `data_column_sidecar_{subnet_id}` gossip validation
- ✅ `ColumnReconstructionTracker` — tracks reconstruction state
- ✅ Data column DB repositories (hot + archive)

### Notable Implementation Details
1. **`custodyColumnsIndex: Uint8Array`** — O(1) bitmap for column custody check (practical optimization)
2. **Reconstruction capped at 50% input** — feeds exactly `NUMBER_OF_COLUMNS/2` columns to recovery function (minimizes KZG compute while meeting spec requirement)
3. **`ChainEvent.publishDataColumns`** — event-driven cross-seeding after reconstruction
4. **`BlockInputSource.recovery`** — tracks column provenance (gossip vs getBlobsV2 vs reconstruction)
5. **Gloas extension** — `getBlobKzgCommitments()` already handles Gloas where commitments move into execution payload bid
6. **TODO in code**: Comment notes potential unit mismatch between `SAMPLES_PER_SLOT` (columns) and `CUSTODY_GROUP_COUNT` (groups) — worth investigating

### No spec compliance issues found.

---

## Architecture Notes

PeerDAS significantly changes the data availability architecture:
- **Before (Deneb/Electra)**: Every node downloads every blob sidecar (N blobs per block)
- **After (Fulu)**: Nodes download only their custodied columns (~4-8 out of 128), reconstruct if needed
- **Bandwidth reduction**: ~30x for regular nodes, proportional to custody requirements for validators
- **Trade-off**: More complex network topology, reconstruction latency, custody tracking overhead
- **Supernode requirement**: Network needs ≥1 supernode for guaranteed reconstruction — validators with ≥4096 ETH combined balance automatically become supernodes

The 128 subnets (one per column) create a much finer-grained gossip topology than the 6-9 blob subnets in Deneb/Electra. This is explicitly addressed in the FAQ: network stability depends on node count and churn rate, not subnet count.
