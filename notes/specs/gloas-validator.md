# Gloas/EPBS — Validator Spec Notes

**Spec:** `consensus-specs/specs/gloas/validator.md`  
**Status:** Read ✅ | Cross-referenced with Lodestar ✅  
**Date:** 2026-02-16

## Overview

The Gloas validator spec defines changes to "honest validator" behavior for ePBS. The major themes are:

1. **Shifted timing deadlines** — All attestation/sync duties use new basis-point constants
2. **PTC (Payload Timeliness Committee)** — New duty for selected attesters to vote on payload presence
3. **Proposer Preferences** — New gossip mechanism for proposers to advertise fee_recipient/gas_limit
4. **Block proposal refactored** — Proposers select builder bids instead of building payloads themselves; DataColumnSidecar broadcasting moves to builders
5. **Attestation `data.index` repurposed** — Signals payload status (EMPTY/FULL) rather than committee index

## Time Parameters

All deadlines are now in basis points (1/10000th) of `SLOT_DURATION_MS`:

| Parameter | Value | % of Slot | Notes |
|-----------|-------|-----------|-------|
| `ATTESTATION_DUE_BPS_GLOAS` | 2500 | 25% | Earlier than pre-Gloas (was 33%) |
| `AGGREGATE_DUE_BPS_GLOAS` | 5000 | 50% | |
| `SYNC_MESSAGE_DUE_BPS_GLOAS` | 2500 | 25% | Matches attestation |
| `CONTRIBUTION_DUE_BPS_GLOAS` | 5000 | 50% | Matches aggregate |
| `PAYLOAD_ATTESTATION_DUE_BPS` | 7500 | 75% | **New** — PTC deadline |

**Key insight:** Attestation deadline moved earlier (25% vs ~33%) to give more room for the ePBS two-phase slot structure: beacon block → payload → PTC vote.

**Slot timeline (12s slot):**
```
0s          3s          6s          9s          12s
|           |           |           |           |
Block prop  Att due     Agg due     PTC due     Slot end
            (25%)       (50%)       (75%)
```

## PTC Assignment

New `get_ptc_assignment(state, epoch, validator_index)`:
- Returns the slot (if any) where the validator is a PTC member in the given epoch
- Stable within current + next epoch only
- Called at epoch start to prepare for next epoch's duties
- Iterates `SLOTS_PER_EPOCH` slots calling `get_ptc(state, slot)` and checking membership

### Lodestar Implementation
- `epochCache.getPayloadTimelinessCommittee(slot)` — pre-computed in `EpochCache`
- Stored as `payloadTimelinessCommittees: Uint32Array[]` indexed by `slot % SLOTS_PER_EPOCH`
- Only available for the cached epoch (throws if wrong epoch)
- **⚠️ NOT YET in validator client** — No PTC duty scheduling in `packages/validator/`

## Attestation Changes

The `attestation.data.index` field is **repurposed** to signal payload status:

- If `block.slot == current_slot` → always `data.index = 0`
  - Rationale: at current slot, payload may not have arrived yet
- Otherwise, check fork-choice payload status:
  - `data.index = 0` → payload is `EMPTY` (not present in canonical chain)
  - `data.index = 1` → payload is `FULL` (present in canonical chain)

**This is a fundamental change** — pre-Gloas, `data.index` was the committee index. ePBS reuses this field as a binary payload-present signal, which is critical for the fork-choice's understanding of chain quality.

## Block Proposal

Major restructuring — proposers no longer build execution payloads directly.

### 1. ProposerPreferences (new)

At each epoch start, proposers MAY broadcast `SignedProposerPreferences` for their upcoming proposal slots:
- Contains: `proposal_slot`, `validator_index`, `fee_recipient`, `gas_limit`
- Gossip topic: `proposer_preferences`
- Uses `DOMAIN_PROPOSER_PREFERENCES` for signing
- Obtained via `get_upcoming_proposal_slots(state, validator_index)` which reads from `state.proposer_lookahead`

**Purpose:** Allows builders to prepare execution payloads matching the proposer's preferences before the slot arrives.

### 2. Execution Payload Bid Selection

Instead of calling the execution engine, proposers:
1. Listen to `execution_payload_bid` gossip topic
2. Verify bid constraints:
   - Valid builder signature (or `G2_POINT_AT_INFINITY` for self-builds)
   - `BUILDER_INDEX_SELF_BUILD` for self-build, with `bid.value = 0`
   - Builder can cover `bid.value`
   - `bid.slot` matches proposal slot
   - `bid.parent_block_hash` == `state.latest_block_hash`
   - `bid.parent_block_root` == `block.parent_root`
3. Select one bid → set `body.signed_execution_payload_bid`

**Self-build option:** Proposers can still build their own payload by setting `builder_index = BUILDER_INDEX_SELF_BUILD`, signature to infinity point, and value to 0.

### 3. Payload Attestations in Block

Proposers include up to `MAX_PAYLOAD_ATTESTATIONS` aggregated payload attestations:
- From `payload_attestation_message` gossip topic
- `data.beacon_block_root` must match `block.parent_root`
- Parent slot must be exactly `block_slot - 1`
- Must aggregate all attestations with same data into single `PayloadAttestation`
- Aggregation bits use PTC committee positions from `get_ptc(state, block_slot - 1)`

### 4. `prepare_execution_payload` Modified

- Uses `state.latest_block_hash` as `head_block_hash` (instead of previous payload hash)
- Only called for self-builds where the proposer is also acting as builder

### 5. DataColumnSidecars No Longer Proposer's Job

Proposers don't broadcast `DataColumnSidecar` objects anymore — this is the builder's responsibility (see builder.md).

## Payload Timeliness Attestation (PTC Duty)

PTC members must:
1. Check if they've seen a beacon block for their assigned slot → if not, don't submit
2. Create `PayloadAttestationMessage`:
   - `data.beacon_block_root` = hash of the seen beacon block
   - `data.slot` = assigned slot
   - `data.payload_present` = `True` if a `SignedExecutionPayloadEnvelope` referencing the block was seen, else `False`
   - `validator_index` = the PTC member's index
3. Sign `data` (NOT the full message with validator_index) using `DOMAIN_PTC_ATTESTER`
4. Broadcast before `PAYLOAD_ATTESTATION_DUE_BPS` (75% of slot = 9s into slot)

**Important:** PTC members don't need to fully validate the execution payload — just check that the `SignedExecutionPayloadEnvelope` passes networking-level validation (p2p-interface checks).

## Modified `get_data_column_sidecars_from_column_sidecar`

Simplified in Gloas to use `beacon_block_root` + `slot` directly instead of full block reference. This aligns with the builder-centric sidecar distribution model.

## Lodestar Implementation Status

### Implemented ✅
- **PayloadAttestationPool** (`beacon-node/src/chain/opPools/payloadAttestationPool.ts`)
  - Aggregation by block root → data root → slot
  - `getPayloadAttestationsForBlock()` — returns top attestations sorted by vote count
  - DoS protection: `MAX_PAYLOAD_ATTESTATIONS_PER_SLOT` cap
  - Pruning: retains 2 slots (`SLOTS_RETAINED = 2`)
  - TODO: Revisit SLOTS_RETAINED value and rationale

- **Payload attestation validation** (`beacon-node/src/chain/validation/payloadAttestationMessage.ts`)
  - Current slot check with gossip disparity
  - Duplicate check via `seenPayloadAttesters`
  - Block root existence in fork-choice
  - PTC membership verification via `epochCache.getPayloadTimelinessCommittee()`
  - Signature verification
  - ⚠️ TODO: Block validation pass check not fully implemented

- **Execution payload bid validation** (`beacon-node/src/chain/validation/executionPayloadBid.ts`)
  - Slot check (current or next)
  - Active builder verification
  - Execution payment zero check (interesting — spec says `bid.value` but code checks `bid.executionPayment`)
  - Duplicate bid check via `seenExecutionPayloadBids`
  - Best bid comparison (only accept higher bids)
  - Builder balance coverage check
  - Block root existence in fork-choice
  - Signature verification
  - ⚠️ TODO: ProposerPreferences validation not implemented yet
  - ⚠️ TODO: Parent block hash check not implemented yet

- **EpochCache PTC** (`state-transition/src/cache/epochCache.ts`)
  - Pre-computed `payloadTimelinessCommittees` arrays
  - `getPayloadTimelinessCommittee(slot)` with epoch bounds check
  - `getIndexedPayloadAttestation()` for attestation indexing

- **Critical params** (`validator/src/util/params.ts`)
  - All Gloas timing parameters marked as critical when fork is relevant
  - `PTC_SIZE`, `MAX_PAYLOAD_ATTESTATIONS`, builder registry params included

### NOT Implemented ❌
- **Validator client PTC duties** — No PTC assignment scheduling, no payload attestation submission
- **Validator client ProposerPreferences broadcasting** — No epoch-start preference announcements
- **Beacon API PTC endpoints** — No API routes for PTC duties/attestations
- **Attestation `data.index` payload status signaling** — Not found in validator attestation logic
- **Self-build path in block proposal** — `BUILDER_INDEX_SELF_BUILD` exists in params but validator proposer logic not updated

## Observations & Potential Issues

1. **`executionPayment` vs `value` naming discrepancy**: The bid validation code checks `bid.executionPayment !== 0` but the spec uses `bid.value` for the collateral amount. Need to verify these map to the correct SSZ fields. Could be a naming evolution between spec versions.

2. **ProposerPreferences TODO**: Both the bid validation and block proposal paths have TODO comments about ProposerPreferences. This is a significant gap — without preferences, builders can't prepare valid bids for specific proposers.

3. **Missing validator-side PTC logic**: The beacon node handles PTC validation and aggregation, but the validator client has no PTC duty scheduling. This is a major implementation gap for any validator wanting to participate in ePBS.

4. **Attestation index field change**: The shift from committee index to payload-present signal in `data.index` is a breaking change. Need to verify Lodestar's attestation creation logic handles this correctly for Gloas.

5. **`SLOTS_RETAINED = 2` with TODO**: The payload attestation pool retains only 2 slots of history. Given that PTC attestations are only valid for the current slot, this seems reasonable but the TODO suggests it needs review.

---
*Next: Cross-reference remaining Gloas impl, then move to Phase0 specs*
