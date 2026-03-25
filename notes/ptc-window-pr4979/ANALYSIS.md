# PR #4979 Analysis — Add cached PTC window to the state

**PR:** https://github.com/ethereum/consensus-specs/pull/4979
**Author:** potuz (co-authored by jtraglia, Nico found the original issue)
**Branch:** `ptc_lookbehind` → renamed to `ptc_window` in latest commits
**Status:** Open, reopened after #4992 was deprioritized

## Problem Statement

When processing the block at slot N (first slot of a new epoch), the proposer validates payload attestations with the PTC of slot N-1. However, `get_ptc` computes committee membership using effective balances from `get_seed(state, epoch, DOMAIN_PTC_ATTESTER)`. Since the epoch boundary has been crossed, the effective balances used to compute the PTC can differ from those used when the PTC was originally assigned. This creates a mismatch — the PTC computed at slot N for slot N-1 may differ from the PTC that was computed at slot N-1 itself.

## Solution: Cached PTC Window in State

### New state field
```python
ptc_window: Vector[Vector[ValidatorIndex, PTC_SIZE], (2 + MIN_SEED_LOOKAHEAD) * SLOTS_PER_EPOCH]
```
- With `MIN_SEED_LOOKAHEAD=1`, this is `3 * 32 = 96` entries on mainnet
- Each entry is a `Vector[ValidatorIndex, PTC_SIZE]` (512 validator indices)
- **State overhead:** 96 × 512 × 8 bytes = **384 KB** (potuz called it "overkill" but pragmatic)

### Window layout (after epoch transition)
```
[0..31]   = previous epoch (for cross-epoch lookback)
[32..63]  = current epoch
[64..95]  = next epoch (lookahead via MIN_SEED_LOOKAHEAD)
```

### New/modified functions
1. **`compute_ptc(state, slot)`** — Pure computation (old `get_ptc` logic). No caching, used during initialization and epoch rotation.
2. **`get_ptc(state, slot)`** — Accessor that reads from `ptc_window`. Handles prev/curr/next epoch indexing.
3. **`process_ptc_window(state)`** — Epoch processor. Shifts window left by one epoch, fills last epoch with newly computed PTC.
4. **`initialize_ptc_window(state)`** — Fork/genesis initializer. Fills zeros for previous epoch, computes current + next.
5. **`get_ptc_assignment(state, epoch, validator_index)`** — Updated: `assert epoch <= max_epoch` where `max_epoch = current_epoch + MIN_SEED_LOOKAHEAD` (was `next_epoch = current_epoch + 1`, functionally identical for mainnet but properly parameterized).

### Files touched
| File | Change |
|------|--------|
| `specs/gloas/beacon-chain.md` | `BeaconState.ptc_window`, `compute_ptc`, `get_ptc` (refactored), `process_ptc_window`, `process_epoch` |
| `specs/gloas/fork.md` | `initialize_ptc_window`, `upgrade_to_gloas` includes `ptc_window` |
| `specs/gloas/validator.md` | `get_ptc_assignment` epoch bound updated |
| `specs/heze/beacon-chain.md` | `BeaconState.ptc_window` field carried forward |
| `specs/heze/fork.md` | `upgrade_to_heze` copies `ptc_window` |
| Tests | 6 new tests + 1 test updated |

### Timing in process_epoch
`process_ptc_window` runs LAST in `process_epoch`, after:
- `process_effective_balance_updates` (updated balances)
- `process_randao_mixes_reset` (updated mixes)

This is correct — new PTC computation sees the latest state.

## Indexing Math (verified)

### `get_ptc` indexing
```python
# Previous epoch (epoch == state_epoch - 1):
return ptc_window[slot % SLOTS_PER_EPOCH]  # indices 0..31

# Current epoch (epoch == state_epoch):
offset = (0 + 1) * SPE = 32
return ptc_window[32 + slot % SPE]  # indices 32..63

# Next epoch (epoch == state_epoch + 1):
offset = (1 + 1) * SPE = 64
return ptc_window[64 + slot % SPE]  # indices 64..95
```

### `process_ptc_window` shift
At epoch N-1's last slot:
- Before: `[prev=N-2, curr=N-1, next=N]`
- Shift left by SPE: `[curr=N-1, next=N, _]`
- Fill last: `compute_ptc` for epoch N+1
- After slot advance: `[prev=N-1, curr=N, next=N+1]` ✓

### `initialize_ptc_window` at genesis/fork
- `[zeros (prev), compute(current), compute(current+1)]` ✓

## Issues Found

### Minor: validator.md prose inconsistency
Line 52 still says:
> `get_ptc_assignment(state, epoch, validator_index)` where `epoch <= next_epoch`

But the code now uses `max_epoch = Epoch(get_current_epoch(state) + MIN_SEED_LOOKAHEAD)`.
While functionally equivalent for `MIN_SEED_LOOKAHEAD=1`, the prose should match the code parameterization. Should say `epoch <= current_epoch + MIN_SEED_LOOKAHEAD`.

### Naming: `ptc_window` → `ptc_assignments` suggested
terence suggested `ptc_window` (over `ptc_lookbehind`), jtraglia agreed. Latest commits use `ptc_window` throughout.
Nico suggested `ptc_assignments` on the spec PR (2026-03-24) — better because "window" is overloaded/implies variable size, and doesn't communicate content. "Assignments" matches existing spec vocabulary (`get_ptc_assignment`). Awaiting spec-side response.

### No issues with the core change
The indexing math, epoch boundary handling, initialization, and fork passthrough are all correct.

## Lodestar Implementation Notes

### State changes
- Add `ptcWindow` field to `BeaconState` SSZ container for Gloas
- Type: `Vector(Vector(ValidatorIndex, PTC_SIZE), (2 + MIN_SEED_LOOKAHEAD) * SLOTS_PER_EPOCH)`
- Must be added to state tree view and type definitions

### EpochContext / CachedBeaconState
- Currently Lodestar caches PTC in `epochCtx`. This PR makes the **canonical** PTC live in the state itself.
- `epochCtx` can still cache for O(1) lookups but must be initialized FROM `state.ptcWindow`, not computed independently.
- `createFromState` must load `ptcWindow` into epochCtx
- **Key insight:** The whole point of this PR is that `get_ptc` becomes a state accessor, not a computation. Lodestar must NOT recompute PTC — it must read from state.

### New epoch processing
- Add `processPtcWindow(state)` to `processEpoch`, LAST (after `processProposerLookahead`)
- Shift logic: slice/copy the window, compute new last epoch

### Fork upgrade
- `upgradeToGloas()` must call `initializePtcWindow(state)` to populate the field
- `upgradeToHeze()` copies `ptcWindow` from Gloas state

### Heze state
- `ptcWindow` field must be in Heze `BeaconState` container too

### Test impact
- Tests that mutate effective balances directly need to call `initializePtcWindow(state)` after mutation (like `test_process_payload_attestation_sampling_not_capped`)
- New epoch processing test for `processPtcWindow`
- New validator unit tests for `getPtcAssignment`

### Comparison with my minimal PTC caching design (lodekeeper/consensus-specs feat/minimal-ptc-caching)
| Aspect | PR #4979 (potuz) | My design |
|--------|------------------|-----------|
| State fields | 1 (`ptc_window`, 96 entries) | 1 (`previous_ptc`, 32 entries) |
| State overhead | 384 KB | 128 KB |
| Lookahead | current + next (via cache) | current only (recompute next) |
| Epoch processor | `process_ptc_window` (shift + compute) | `process_ptc_update` (just store prev) |
| Complexity | Higher (shift logic, 3-epoch window) | Lower (just prev epoch storage) |

PR #4979 is more complete (handles lookahead in-state) but uses 3x the state space. My design was minimal but would require out-of-state caching for lookahead. **PR #4979 is the one that will land — implement this.**

### Relation to PR #9047 (twoeths' review feedback)
PR #9047 was addressing the same fundamental issue (PTC computed with wrong epoch's balances). Once #4979 lands in the spec:
1. Close PR #9047 (or adapt it to implement #4979)
2. The Lodestar implementation should follow #4979's approach, not our intermediate fix

## Twoeths' Review Feedback on PR #9047 (key points for #4979 implementation)

These are implementation-level concerns from twoeths that are still relevant when implementing #4979:

1. **Use `epochCtx` cache, not state tree traversal** (2026-03-18):
   > "we can get from `state.epochCtx.payloadTimelinessCommittees[slot % SLOTS_PER_EPOCH]` to avoid traversing the state tree"
   - PR #4979 adds `ptc_window` to the state, but Lodestar should still serve lookups from `epochCtx` cache (populated from state).
   - Never traverse the SSZ state tree on the hot path.

2. **`getHeadStateAtSlot` is expensive — use epoch-level state** (2026-03-18):
   > "we can just use the state at the same epoch and query `epochCtx` from there"
   > "the reason is `getHeadStateAtSlot` is not as cheap as in the past anymore"
   - For payload attestation validation, prefer `getHeadStateAtEpoch` over `getHeadStateAtSlot`.
   - The PTC window covers the full epoch, so any state within the same epoch works.

3. **Bound `getHeadStateAtSlot` to currentSlot for DOS prevention** (2026-03-18):
   > "this method should be bound to currentSlot only to prevent a DOS attack"

4. **BLS batch verification for PTC** (2026-03-18):
   > "this ptc validation is a great candidate to validate in batch to save `computeSigningRoot()` time + `verifySignatureSetsSameMessage`"
   > "but it's too much to start with, we can explore at later devnets"
   - Future optimization, not needed for initial implementation.

5. **`previousEpochLastSlotPtc` must be initialized from state** (2026-03-18):
   - Nico confirmed: must load from state in `createFromState` for checkpoint sync/restart correctness.
   - With #4979, this becomes: load the full `ptc_window` from state into `epochCtx` in `createFromState`.

6. **Genesis-at-Gloas (`GLOAS_FORK_EPOCH=0`)** (codex-connector flagged):
   - Genesis state generator must call `initializePtcWindow` to populate the field.
   - Already handled in test helper `create_genesis_state` in the spec PR.

## Other PTC-related PRs to track

| PR | Title | Status | Relevance |
|----|-------|--------|-----------|
| #4979 | Add cached PTC window to the state (potuz) | **Open — THE ONE** | Main spec change to implement |
| #4992 | Add cached PTCs to the state (potuz) | Closed | Alternative (2 entries only, 8KB). Superseded by #4979 |
| #5020 | Add PTC lookbehind minimal state change (nflaig) | Closed | Nico's minimal alternative (4KB, `previous_epoch_last_ptc`). Superseded |
| #4843 | Variable PTC deadline (fradamt) | Open | Orthogonal — variable deadline based on payload size. Independent of caching approach |
| #4932 | Add Gloas sanity/blocks tests with payload attestation (AbolareRoheemah) | Open | Test coverage, not caching-related |
| #4882 | Add two new PTC tests (jtraglia) | Closed/merged | Already in master |
| #4719 | Clarify PTC description (jihoonsong) | Closed/merged | Documentation |
| #4713 | Add PTC subsection to validator assignment (jihoonsong) | Closed/merged | Documentation |
| #4488 | Make PTC selection balance-weighted (fradamt) | Closed/merged | Already in master (the `compute_balance_weighted_selection` approach) |
