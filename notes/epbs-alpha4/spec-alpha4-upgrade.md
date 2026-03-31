# Spec: EPBS Alpha.4 Upgrade (Gloas-only)

## Problem
Upgrade Lodestar's `epbs-devnet-0` branch from consensus-specs v1.7.0-alpha.2 to v1.7.0-alpha.4, implementing only Gloas-related changes needed for epbs-devnet-1. All spec tests must pass against the v1.7.0-alpha.4 test vectors.

## Context
- **Base branch:** `ChainSafe/lodestar:epbs-devnet-0` (currently at alpha.2)
- **Prior art:** `fork/feat/spec-alpha3-upgrade` has alpha.3 changes (specrefs, config, test skips)
- **Prior art:** PR #9047 (closed) had a `previousEpochLastSlotPtc` approach — superseded by spec's `ptc_window`

## Changes Required (alpha.3 + alpha.4 combined, Gloas-only)

### A. PTC Window — State Field (alpha.4, spec PR #4979)

**Current approach (alpha.2):** PTC committees computed on-the-fly in epochCache (`computePayloadTimelinessCommitteesForEpoch`), cached as `payloadTimelinessCommittees` / `previousPayloadTimelinessCommittees` in EpochContext. `getPayloadTimelinessCommittee(slot)` reads from epochCache.

**New approach (alpha.4):** PTC committees cached directly in BeaconState as `ptc_window`. The window covers `(2 + MIN_SEED_LOOKAHEAD) * SLOTS_PER_EPOCH` slots = prev epoch + current epoch + next epoch (when MIN_SEED_LOOKAHEAD=1, that's 3 * SLOTS_PER_EPOCH entries).

**Changes needed:**

1. **Types:** Add `ptc_window` field to Gloas BeaconState SSZ container:
   - Type: `Vector[Vector[ValidatorIndex, PTC_SIZE], (2 + MIN_SEED_LOOKAHEAD) * SLOTS_PER_EPOCH]`
   - In practice with MIN_SEED_LOOKAHEAD=1: `Vector[Vector[ValidatorIndex, PTC_SIZE], 3 * SLOTS_PER_EPOCH]`

2. **New function `computePtc(state, slot)`:** Extract the raw PTC computation (currently the body of `getPayloadTimelinessCommittee` / `computePayloadTimelinessCommitteesForEpoch`). This does the seed derivation, committee concatenation, and balance-weighted selection.

3. **Rewrite `getPtc(state, slot)`:** Instead of computing, look up from `state.ptcWindow`:
   ```
   epoch = computeEpochAtSlot(slot)
   stateEpoch = getCurrentEpoch(state)
   if epoch < stateEpoch:
     assert epoch + 1 == stateEpoch
     return state.ptcWindow[slot % SLOTS_PER_EPOCH]
   assert epoch <= stateEpoch + MIN_SEED_LOOKAHEAD
   offset = (epoch - stateEpoch + 1) * SLOTS_PER_EPOCH
   return state.ptcWindow[offset + slot % SLOTS_PER_EPOCH]
   ```

4. **New `processPtcWindow(state)` in epoch processing:**
   - Shift window forward by one epoch (move entries down by SLOTS_PER_EPOCH)
   - Fill the last epoch with `computePtc(state, slot)` for next epoch + MIN_SEED_LOOKAHEAD + 1

5. **New `initializePtcWindow(state)` in fork transition:**
   - Empty previous epoch (all zeros)
   - Compute current + next epochs using `computePtc`
   - Called from `upgradeToGloas()`

6. **EpochCache migration:** The `payloadTimelinessCommittees` / `previousPayloadTimelinessCommittees` fields in epochCache may become redundant since PTC is now in state. However, for performance we might still want epochCache to cache a deserialized view. Need to think about whether we:
   - (a) Keep epochCache as a fast-access layer that reads from state, OR
   - (b) Remove epochCache PTC fields entirely and always read from state
   
   The spec says `get_ptc` reads from `state.ptc_window`, so the canonical source is the state. But for hot-path performance (gossip validation etc.), we may want to keep a pre-deserialized array in epochCache that mirrors the state. This is an implementation choice.

### B. compute_balance_weighted_acceptance Signature Change (alpha.4, PR #5044)

**Before:** `compute_balance_weighted_acceptance(state, index, seed, i)` — reads effective_balance from state inside the function.
**After:** `compute_balance_weighted_acceptance(effective_balance, seed, i)` — takes effective_balance as parameter.

Also in `compute_balance_weighted_selection`: pre-compute `effective_balances` array before the loop.

This is a performance optimization. Need to update:
- `computeBalanceWeightedAcceptance()` signature
- `computeBalanceWeightedSelection()` to pre-compute balances

### C. Same-Epoch Proposer Preferences (alpha.4, PR #5035)

**Before:** Proposer preferences gossip only accepted for next epoch.
**After:** Accepted for current epoch (future slots) AND next epoch.

Changes:
- `is_valid_proposal_slot`: check both current and next epoch in `proposer_lookahead`
- gossip validation: `proposal_slot` must be in `[current_epoch, current_epoch + 1]` and `> state.slot`
- `get_upcoming_proposal_slots`: iterate all of `proposer_lookahead`, include future slots in current epoch

### D. Index-1 Attestation Payload Validation (alpha.4, PR #4939)

New gossip validation rules for attestations with `data.index == 1`:
- REJECT if index=1 but execution payload for that block fails validation
- IGNORE if index=1 but execution payload hasn't been seen (queue for later, request via reqresp)

Applies to both aggregate attestations and subnet attestations.

### E. Fork Choice: Block Known Assert (alpha.4, PR #5022)

Add `assert data.beacon_block_root in store.block_states` at the start of `on_payload_attestation_message`, before the existing `store.block_states[data.beacon_block_root]` access.

This is a small fix — should already be implicitly handled, but needs explicit check.

### F. PartialDataColumnHeader Changes (SKIP for devnet-1 unless tests require)

Modified container for Gloas — removed `signed_block_header` and `kzg_commitments_inclusion_proof`, added `slot` and `beacon_block_root`. Plus new partial message validation rules.

**Decision:** Skip for initial pass. No meaningful consumer code exists on epbs-devnet-0 branch. Revisit only if alpha.4 test vectors fail due to missing container changes.

### G. Spec Test Version Bump

- `specTestVersioning.ts`: change from `v1.7.0-alpha.2` to `v1.7.0-alpha.4`
- Download new test vectors
- Fix any test failures

### H. Alpha.3 Changes (prerequisite, from existing branch)

The existing `fork/feat/spec-alpha3-upgrade` branch has alpha.3 changes that need to be incorporated:
- Specref updates
- Config/preset changes  
- Various other alpha.2→3 changes

## Key Design Decision: PTC Window in State vs EpochCache

The biggest architectural question is how `ptc_window` interacts with the existing epochCache PTC caching.

**Option 1: State-only (spec-pure)**
- Remove `payloadTimelinessCommittees` / `previousPayloadTimelinessCommittees` from epochCache
- All PTC lookups go through `state.ptcWindow`
- Simpler, matches spec exactly
- Potential performance concern: SSZ tree reads on hot path

**Option 2: State + epochCache mirror**
- Keep epochCache PTC arrays for hot-path reads
- Populate from state during `afterProcessEpoch` or `createEpochContext`
- `ptcWindow` in state is canonical; epochCache is a perf cache
- More code, but preserves existing fast-path performance

**Option 3: Hybrid — state stores it, epochCache provides typed accessors**
- State has `ptc_window` (for merkleization, serialization, spec compliance)
- `getPayloadTimelinessCommittee(slot)` in epochCache reads from state but caches the typed array
- Avoids double-writing but still gets perf

**Recommendation (post gpt-advisor review):** Option 3 — state-canonical + read-through epochCache mirror.
- `state.ptcWindow` is the single source of truth (spec-compliant)
- `epochCtx.getPayloadTimelinessCommittee(slot)` becomes a read-through cache hydrated from state
- Existing hot-path call sites (beaconStateView, payload attestation validation) stay unchanged
- Add standalone `getPtc(state, slot)` in `util/gloas.ts` for spec semantics (prev/current/next epoch)
- epochCache no longer independently computes PTC — it reads from state

**Critical ordering:** `processPtcWindow` must run AFTER `processProposerLookahead` and reuse `cache.nextShuffling`.

**Genesis init:** `util/genesis.ts` must also call `initializePtcWindow()` if devnet starts at Gloas genesis.

## Edge Cases
1. **Fork transition:** `initializePtcWindow` must handle the case where previous epoch PTCs can't be computed (different fork). Use zeros for previous epoch slot.
2. **Mid-epoch state loads:** States loaded mid-epoch (checkpoint sync) should have valid `ptcWindow` already — it's part of the serialized state.
3. **MIN_SEED_LOOKAHEAD:** Currently 1. The window is `(2 + 1) * SLOTS_PER_EPOCH = 3 * SLOTS_PER_EPOCH` entries. Index mapping: [0..SPE) = prev epoch, [SPE..2*SPE) = current epoch, [2*SPE..3*SPE) = next epoch.

## Test Plan
1. All consensus-spec tests pass with v1.7.0-alpha.4 vectors
2. Unit tests for `computePtc`, `getPtc`, `processPtcWindow`, `initializePtcWindow`
3. Verify proposer preferences validation accepts current epoch
4. Verify index-1 attestation validation rules

## Acceptance Criteria
- [ ] Branch based on latest `origin/epbs-devnet-0`
- [ ] All alpha.4 Gloas changes implemented
- [ ] `pnpm build` passes
- [ ] `pnpm lint` passes  
- [ ] `pnpm check-types` passes
- [ ] All spec tests pass against v1.7.0-alpha.4 vectors
- [ ] Branch pushed to lodekeeper/lodestar
