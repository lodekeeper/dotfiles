# Altair Beacon Chain — Study Notes

**Spec:** `consensus-specs/specs/altair/beacon-chain.md`
**Lodestar impl:** `packages/state-transition/src/`
**Date:** 2026-02-16

## Overview

Altair is the first beacon chain upgrade (after Phase 0). Three main features:
1. **Sync committees** — 512-validator rotating committees to support light clients
2. **Incentive accounting reforms** — replaced `PendingAttestation` lists with per-validator participation flags (uint8 bitfield)
3. **Penalty parameter updates** — moved toward maximally punitive values

## Key Changes from Phase 0

### 1. Participation Flags (replaces PendingAttestations)

**Spec:** Three participation flags per validator:
- `TIMELY_SOURCE_FLAG_INDEX = 0` (weight: 14/64)
- `TIMELY_TARGET_FLAG_INDEX = 1` (weight: 26/64)
- `TIMELY_HEAD_FLAG_INDEX = 2` (weight: 14/64)

Plus sync committee weight (2/64) and proposer weight (8/64) = 64/64 total.

**Lodestar:** `state.currentEpochParticipation` / `state.previousEpochParticipation` — uses `setBitwiseOR: true` option for efficient flag updates. Flags stored as uint8 per validator.

**Implementation note:** `processAttestationsAltair.ts` handles this. Uses bitwise operations (`~flags & flagsAttestation`) to detect newly-set flags — efficient.

### 2. Timeliness Requirements

- Source: `inclusion_delay <= sqrt(SLOTS_PER_EPOCH)` (= 5 slots)
- Target: `inclusion_delay <= SLOTS_PER_EPOCH` (= 32 slots)
- Head: `inclusion_delay == 1` (must be included next slot)

**Lodestar:** `getAttestationParticipationStatus()` — cross-referenced, matches spec exactly. `SLOTS_PER_EPOCH_SQRT` pre-computed.

### 3. Sync Committee

**Spec:** 512 validators selected per period (256 epochs ≈ 27 hours). Members sign the previous slot's block root each slot.

**Selection:** Weighted random sampling — validators with higher effective balance more likely to be selected (like proposer selection).

**Lodestar impl:**
- `processSyncAggregate()` in `block/processSyncCommittee.ts`
- `processSyncCommitteeUpdates()` in `epoch/processSyncCommitteeUpdates.ts`
- Uses `SyncCommitteeCache` for indexed committee access
- Signature verification uses `block.parentRoot` instead of `get_block_root_at_slot(state, previous_slot)` — equivalent on skipped slots since state block roots just copy the latest block

**Key optimization:** Spec has 3 branches based on participation (all, >50%, <50%) for aggregate key computation. Lodestar skips this subtraction optimization and just aggregates participant keys directly via `intersectValues`.

### 4. Rewards/Penalties Overhaul

**Spec functions:**
- `get_flag_index_deltas()` — loops per flag (3 calls)
- `get_inactivity_penalty_deltas()` — separate inactivity loop

**Lodestar:** `getRewardsAndPenaltiesAltair()` — **single pass** through all validators, computes all flag rewards + inactivity penalties at once. Uses `rewardPenaltyItemCache` keyed by effective balance increment to avoid redundant math. Very efficient.

**Inactivity leak:** During leak, participants get 0 rewards (not penalized), non-participants get penalized proportionally to their `inactivityScore * effectiveBalance`.

### 5. Inactivity Scores (New)

**Spec:** Per-validator `inactivity_scores` array:
- Active + target attester: decrease by 1
- Active + non-target: increase by `INACTIVITY_SCORE_BIAS` (4)
- Not in leak: decrease by `INACTIVITY_SCORE_RECOVERY_RATE` (16)

**Lodestar:** `processInactivityUpdates()` — matches spec. Uses a reusable `inactivityScoresArr` array (pre-allocated, never GC'd). Only writes to tree when score actually changes.

### 6. Slashing Changes

- `MIN_SLASHING_PENALTY_QUOTIENT_ALTAIR = 64` (down from 128 in Phase 0)
- `PROPORTIONAL_SLASHING_MULTIPLIER_ALTAIR = 2` (up from 1)
- Proposer reward now: `whistleblower_reward * PROPOSER_WEIGHT / WEIGHT_DENOMINATOR` (= 8/64 = 12.5%)

### 7. Epoch Processing Order

```
process_justification_and_finalization  [Modified - uses flags]
process_inactivity_updates              [New]
process_rewards_and_penalties           [Modified - flag-based]
process_registry_updates
process_slashings                       [Modified constants]
process_eth1_data_reset
process_effective_balance_updates
process_slashings_reset
process_randao_mixes_reset
process_historical_roots_update
process_participation_flag_updates      [New - rotate current→previous]
process_sync_committee_updates          [New - every 256 epochs]
```

## Lodestar Implementation Quality

### Strengths
- **Single-pass rewards:** Combines 4 spec functions into 1 loop — major perf win
- **Bitwise participation:** Efficient flag operations with `setBitwiseOR`
- **Progressive target balances:** Tracks cumulative target balances as attestations arrive (avoids recomputing at epoch boundary)
- **Reusable arrays:** `inactivityScoresArr`, `rewards`, `penalties` — zero GC pressure
- **`rewardPenaltyItemCache`:** Since effective balance is always a multiple of 1 ETH, there are only ~32 possible values — cache hit rate is very high

### Deviation from spec (intentional)
- `processSyncAggregate` uses `block.parentRoot` instead of `get_block_root_at_slot(state, previous_slot)` — documented, equivalent, enables batch verification
- Attestation processing merges multiple spec functions into one for performance
- Gloas-specific extensions already mixed into Altair attestation code (forward-compatible design)

## Spec Tests
- Altair tests run via the same spec test framework in `test/spec/presets/`
- Operations, epoch processing, fork choice, rewards, sanity tests all cover Altair
- Fork transition tests (Phase0 → Altair) in `transition.test.ts`

## Issues Found
None — the implementation is clean and spec-compliant. The performance optimizations (single-pass rewards, progressive target balances, bitwise participation) are well-documented and don't change semantics.
