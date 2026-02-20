# Lodestar EPBS Upgrade Plan: alpha.1 → alpha.2

## Overview
Lodestar is currently on `v1.7.0-alpha.1`. Need to upgrade to `v1.7.0-alpha.2`.

## Risk Level: MEDIUM-HIGH ⚠️
- SSZ wire format changes affect builder/relay coordination
- Attestation domain fix is consensus-critical
- Several validation logic changes

## Spec Changes (alpha.1 → alpha.2)

### 1. blob_kzg_commitments Location Change 🔴 HIGH IMPACT
**Before:** In `ExecutionPayloadEnvelope`
**After:** In `ExecutionPayloadBid`

**Files to change:**
- `@lodestar/types` — SSZ containers
- `chain/validation/executionPayloadEnvelope.ts` — Remove commitments verification there
- `chain/validation/executionPayloadBid.ts` — Add commitments verification here
- `util/dataColumns.ts` — Update sidecar construction

### 2. MIN_BUILDER_WITHDRAWABILITY_DELAY Reduced 🟡 MEDIUM IMPACT
**Before:** 4096 epochs (~18 days)
**After:** 64 epochs (~6.8 hours)

**Files to change:**
- `@lodestar/params` — Update constant

### 3. Builder Activation Logic 🟡 MEDIUM IMPACT
**Before:** Active immediately when deposit processed
**After:** Active after deposit_epoch is finalized

**Files to change:**
- `state-transition/src/util/gloas.ts` — Update `isActiveBuilder` logic

### 4. DataColumnSidecar kzg_commitments Removed 🔴 HIGH IMPACT
**Before:** `sidecar.kzg_commitments` exists
**After:** Commitments come from bid via block lookup

**Files to change:**
- `@lodestar/types` — SSZ container update
- `chain/validation/dataColumnSidecar.ts` — Update validation logic
- `util/dataColumns.ts` — Update sidecar construction/verification
- `network/` — Gossip validation changes

### 5. verify_data_column_sidecar Signature Change 🟡 MEDIUM IMPACT
**Before:** `verify_data_column_sidecar(sidecar)`
**After:** `verify_data_column_sidecar(sidecar, kzg_commitments)`

### 6. add_builder_to_registry Signature Change 🟢 LOW IMPACT
**Before:** `add_builder_to_registry(state, pubkey, credentials, amount)`
**After:** `add_builder_to_registry(state, pubkey, credentials, amount, slot)`

**Files to change:**
- `state-transition/src/block/processDepositRequest.ts`

### 7. is_data_available Modified 🟡 MEDIUM IMPACT
**Before:** Sidecars retrieved with commitments inside
**After:** Commitments retrieved separately via `retrieve_column_sidecars_and_kzg_commitments`

### 8. onboard_builders_from_pending_deposits 🟢 LOW IMPACT
**New function** for fork transition

**Files to change:**
- `state-transition/src/slot/upgradeStateToGloas.ts`

### 9. Attestation Domain Fix (PR #4836) 🔴 CRITICAL
**Before:** `get_domain(state, DOMAIN_PTC_ATTESTER, None)`
**After:** `get_domain(state, DOMAIN_PTC_ATTESTER, compute_epoch_at_slot(attestation.data.slot))`

**Files to change:**
- `state-transition/src/block/processPayloadAttestation.ts`

### 10. Withdrawals Space Reservation (PR #4832) 🔴 CRITICAL  
**Before:** `len(all_withdrawals) == withdrawals_limit`
**After:** `len(all_withdrawals) >= withdrawals_limit` + assertions

**Files to change:**
- `state-transition/src/block/processWithdrawals.ts`

### 11. prepare_execution_payload Update (PR #4841) 🟡 MEDIUM
**Change:** Use `state.latest_block_hash` instead of execution payload header

**Files to change:**
- Validator client payload preparation

### 12. EIP-8025 Execution Proof Awareness (PR #4877/#4828) 🟡 MEDIUM
**New:** Metadata/ENR updates for execution proofs

**Files to change:**
- `network/metadata.ts`
- `network/discv5/` ENR handling

### 9. Withdrawals Limit Assert 🟢 LOW IMPACT
**Added:** `assert len(prior_withdrawals) <= withdrawals_limit` in withdrawal processing

## Implementation Order

### Phase 0: Critical Bug Fixes FIRST
**Do these before anything else — they're consensus-critical:**
1. Fix attestation domain (#4836) — `compute_epoch_at_slot(data.slot)` not `None`
2. Fix withdrawals space reservation (#4832) — `>=` not `==`, add assertions

### Phase 1: Types & Params (Foundation)
1. Update `@lodestar/params` with new constants
   - `MIN_BUILDER_WITHDRAWABILITY_DELAY`: 4096 → 64
2. Update `@lodestar/types` with modified containers:
   
   **ExecutionPayloadBid** (packages/types/src/gloas/sszTypes.ts:117-129)
   ```diff
   - blobKzgCommitmentsRoot: Root,
   + blobKzgCommitments: denebSsz.BlobKzgCommitments,
   ```
   
   **ExecutionPayloadEnvelope** (packages/types/src/gloas/sszTypes.ts:151-160)
   ```diff
     slot: Slot,
   - blobKzgCommitments: denebSsz.BlobKzgCommitments,
     stateRoot: Root,
   ```
   
   **DataColumnSidecar** (packages/types/src/gloas/sszTypes.ts)
   ```diff
     column: fuluSsz.DataColumnSidecar.fields.column,
   - kzgCommitments: fuluSsz.DataColumnSidecar.fields.kzgCommitments,
     kzgProofs: fuluSsz.DataColumnSidecar.fields.kzgProofs,
   ```

### Phase 2: State Transition
3. Update builder activation logic in `isActiveBuilder`
4. Update `add_builder_to_registry` signature
5. Add `onboard_builders_from_pending_deposits` to fork transition
6. Update withdrawal processing with new assertions

### Phase 3: Validation & Processing
7. Update `verify_data_column_sidecar` signature
8. Update `verify_data_column_sidecar_kzg_proofs` signature
9. Update bid validation (add commitments length check)
10. Update envelope validation (remove commitments check)

### Phase 4: Networking
11. Update gossip validation for data_column_sidecar
12. Update `is_data_available` to retrieve commitments separately
13. Update sidecar construction functions

### Phase 5: Tests
14. Update spec tests to v1.7.0-alpha.2
15. Run spec tests with ethspecify
16. Fix any failures

## Spec Test Status
- Current: `v1.7.0-alpha.1`
- Target: `v1.7.0-alpha.2`

## Files Likely Needing Changes (by package)

### @lodestar/params
- `src/presets/mainnet.ts`
- `src/presets/minimal.ts`

### @lodestar/types
- `src/gloas/sszTypes.ts`
- `src/gloas/types.ts`

### @lodestar/state-transition
- `src/util/gloas.ts`
- `src/block/processDepositRequest.ts`
- `src/slot/upgradeStateToGloas.ts`

### @lodestar/beacon-node
- `src/chain/validation/dataColumnSidecar.ts`
- `src/chain/validation/executionPayloadBid.ts`
- `src/chain/validation/executionPayloadEnvelope.ts`
- `src/util/dataColumns.ts`
- `src/network/gossip/handlers/index.ts`

### @lodestar/fork-choice
- Various files handling data availability

---
*Created: 2026-02-07*
*Status: In Progress*
*Branch: `lodekeeper/epbs-alpha2-upgrade`*

## Implementation Progress

### ✅ Completed
- [x] Phase 0: Critical Bug Fixes
  - [x] #4836 — Attestation domain fix (use `data.slot` not `stateSlot`)
  - [x] #4832 — Withdrawals fix (already implemented in Lodestar)
- [x] Phase 1: Types (partial)
  - [x] `ExecutionPayloadBid.blobKzgCommitments` (was root, now List)
  - [x] Remove `blobKzgCommitments` from `ExecutionPayloadEnvelope`
  - [x] Remove `kzgCommitments` from `DataColumnSidecar`
- [x] Update spec test version to v1.7.0-alpha.2
- [x] Add commitments limit check to bid processing
- [x] Update processExecutionPayloadEnvelope.ts

### 🔲 Pending
- [ ] Phase 1: Params
  - [x] `MIN_BUILDER_WITHDRAWABILITY_DELAY`: 4096 → 64 (mainnet config updated)
- [ ] Phase 2: State Transition
  - [x] Update `isActiveBuilder` for finalization requirement (already matched spec)
  - [x] Update `add_builder_to_registry` signature (+ slot param; deposit_epoch from deposit slot)
  - [x] Add `onboard_builders_from_pending_deposits` (implemented in `upgradeStateToGloas.ts`)
- [ ] Phase 3: Validation
  - [ ] Update gossip validation for Gloas data columns
- [ ] Phase 4: Networking  
  - [ ] Sidecar construction for Gloas (get commitments from bid)
  - [ ] Block input handling for Gloas
- [ ] Phase 5: Tests
  - [x] Run minimal spec tests with alpha.2 vectors (`test:spec:minimal`)
  - [x] Fix failures (builder index flag bitwise bug; fork onboarding)
  - [ ] Run mainnet spec tests (`test:spec:mainnet`)

### ⚠️ Blocked
- Several items depend on base EPBS implementation completing
- `seenGossipBlockInput.ts` has TODO "Not implemented" for Gloas
