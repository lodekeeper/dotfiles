# PeerDAS (Fulu Fork) — Learning Notes

## Overview
PeerDAS = **Peer** Data Availability **S**ampling. Enables scaling Ethereum's blob throughput by distributing data across the network without requiring every node to download every blob.

## Key Concepts

### Data Matrix
- Blobs are extended using 1D erasure coding
- Matrix: rows = blobs (up to MAX_BLOBS_PER_BLOCK), columns = 128 cells per blob
- Each cell has a KZG proof for verification

### Custody Groups
- **128 custody groups** total
- Each group maps to specific columns via `compute_columns_for_custody_group`
- Nodes MUST custody at least **4 groups** (CUSTODY_REQUIREMENT)
- Selection is deterministic based on node_id via `get_custody_groups`

### Column Sampling
- Each slot: nodes sample `max(8, custody_group_count)` groups
- Sampling succeeds if all selected columns are retrieved
- Columns distributed via gossipsub subnets

### Reconstruction
- With **50%+ columns**, full matrix can be recovered (`recover_matrix`)
- After reconstruction, nodes MUST share recovered columns (cross-seeding)
- Random delay before reconstruction to reduce CPU spikes

## Important Types
- `DataColumnSidecar`: Contains column cells, KZG proofs, and block header
- `MatrixEntry`: Single cell with proof and position indices
- `CustodyIndex`, `ColumnIndex`, `RowIndex`: Type aliases for positions

## Key Parameters
| Parameter | Value | Description |
|-----------|-------|-------------|
| NUMBER_OF_COLUMNS | 128 | Columns per blob extension |
| NUMBER_OF_CUSTODY_GROUPS | 128 | Total custody groups |
| CUSTODY_REQUIREMENT | 4 | Min groups per node |
| SAMPLES_PER_SLOT | 8 | Min samples per slot |

## Cryptography (polynomial-commitments-sampling.md)

### Cells
- Smallest verifiable unit: **64 field elements** = 2048 bytes
- CELLS_PER_EXT_BLOB = 128 (matches NUMBER_OF_COLUMNS)
- Each cell is an evaluation of the blob polynomial over a coset

### Key Operations
1. **compute_cells_and_kzg_proofs(blob)** → Generate all 128 cells + proofs
2. **verify_cell_kzg_proof_batch(...)** → Batch verify cells belong to commitments
3. **recover_cells_and_kzg_proofs(...)** → Reconstruct full blob from 50%+ cells

### Why 50% is the Magic Threshold
Reed-Solomon is an **MDS (Maximum Distance Separable) code**.

Given:
- Original blob = **k** field elements (FIELD_ELEMENTS_PER_BLOB)
- Extended blob = **n = 2k** elements (2x extension factor)
- Data interpreted as polynomial f(x) of **degree < k**

**Key property:** Any **k distinct evaluations** uniquely determine f(x) via Lagrange interpolation.

Therefore:
- Minimum cells needed = k = n/2 = **50%**
- Can tolerate up to k missing cells (50% erasure tolerance)

**General formula:** For extension factor c, need 1/c of cells (c=2 → 50%)

### Recovery Algorithm
- Uses FFT-based Reed-Solomon erasure decoding
- Runs in O(n log n) with FK20 optimization
- Steps:
  1. Construct vanishing polynomial Z(x) for missing cells
  2. Compute (E*Z)(x) where E is partial evaluations
  3. Divide by Z(x) over a coset (avoid division by zero)
  4. Recover original polynomial coefficients

### Math Concepts
- **Cosets**: Shifted evaluation domains (h * G where G is roots of unity subgroup)
- **Vanishing polynomial**: Polynomial that's zero at missing cell positions
- **FFT/IFFT**: Convert between coefficient and evaluation forms
- **Lagrange interpolation**: Recover polynomial from point evaluations

## Networking (p2p-interface.md)

### Subnet Architecture
- 128 data column subnets (`DATA_COLUMN_SIDECAR_SUBNET_COUNT`)
- Column → subnet mapping: `column_index % 128` (1:1 with 128 columns)
- Nodes subscribe to subnets for their custody columns

### Discovery (ENR)
- `custody_group_count`: Advertises how many groups node custodies
- Clients MAY reject peers with < CUSTODY_REQUIREMENT groups

### Request/Response
- **DataColumnSidecarsByRange**: Bulk sync columns
- **DataColumnSidecarsByRoot**: Request specific columns by block root

### Validation Pipeline
1. `verify_data_column_sidecar`: Index bounds, length checks
2. `verify_data_column_sidecar_kzg_proofs`: Batch KZG verification
3. `verify_data_column_sidecar_inclusion_proof`: Merkle proof to block body

## Lodestar Implementation Notes

### Key Files
- `util/dataColumns.ts`: CustodyConfig, group/column calculations, recovery
- `util/blobs.ts`: `dataColumnMatrixRecovery()` — actual recovery logic
- `chain/validation/dataColumnSidecar.ts`: Gossip validation

### Recovery Flow
1. Check if 50%+ columns available
2. For each blob row: `kzg.asyncRecoverCellsAndKzgProofs(cellIndices, cells)`
3. Reconstruct full sidecars from recovered cells + proofs
4. Emit `ChainEvent.publishDataColumns` for cross-seeding

## Open Questions
- [ ] Deep dive: FK20 algorithm for efficient proof generation
- [ ] How does the universal verification equation work?
- [ ] What are the performance characteristics of cell verification?
- [ ] How does Lodestar handle slow/missing columns during sync?

---
*Last updated: 2026-02-07*
