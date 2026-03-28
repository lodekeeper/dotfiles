# PTC Caching Spec — Research Phase 1

## The Problem (consensus-specs#4979)

**Found by Nico (@nflaig).** When processing a block at slot 32 (first slot of epoch 1), payload attestations from slot 31 (last slot of epoch 0) are validated. The PTC for slot 31 is computed via `get_ptc(state, 31)` which uses `compute_balance_weighted_selection`. This function depends on validators' **effective balances**, which change during `process_effective_balance_updates` at the epoch boundary.

**Result:** `get_ptc(state, 31)` called at slot 31 (gossip) may return a different committee than `get_ptc(state, 31)` called at slot 32 (block processing). Attestations that were valid during gossip become invalid during block processing (or vice versa).

**Why only the epoch boundary?** Within an epoch, effective balances don't change, so `compute_balance_weighted_selection` is deterministic for any given slot. The problem only manifests when `data.slot` is in epoch N but `state.slot` is in epoch N+1.

**Why only the last slot?** `process_payload_attestation` asserts `data.slot + 1 == state.slot`. So we only ever validate attestations from the immediately previous slot. The cross-epoch case only happens when `state.slot` is the first slot of an epoch (e.g., slot 32) and `data.slot` is the last slot of the previous epoch (e.g., slot 31).

## Existing Proposals

### PR #4979 — Full Epoch Lookbehind (potuz, CLOSED)

**State change:** `ptc_lookbehind: Vector[Vector[ValidatorIndex, PTC_SIZE], 2 * SLOTS_PER_EPOCH]`
- Size: 2 × 32 × 512 × 8 = **262,144 bytes (~256KB)** per state

**Mechanism:**
- `process_ptc_lookbehind` at end of `process_epoch`: shifts current epoch PTCs → previous, computes new epoch's PTCs
- `get_ptc` reads from cache for prev/current epoch, computes on-demand for next epoch
- `initialize_ptc_lookbehind` at fork/genesis

**Preserves:** `get_ptc_assignment` (validator duties API for current + next epoch)

**Pros:** Single computation point (epoch boundary), no `process_slots` modification, full epoch coverage
**Cons:** 256KB state overhead per state

**Closed** in favor of #4992.

### PR #4992 — Per-Slot Rotation (potuz/jtraglia, OPEN)

**State change:** `previous_ptc: Vector[ValidatorIndex, PTC_SIZE]` + `current_ptc: Vector[ValidatorIndex, PTC_SIZE]`
- Size: 2 × 512 × 8 = **8,192 bytes (~8KB)** per state

**Mechanism:**
- Per-slot rotation in `process_slots`: `previous_ptc = current_ptc; current_ptc = compute_ptc(state)`
- `get_ptc` asserts `slot == state.slot or slot + 1 == state.slot`
- `compute_ptc(state)` only works for current slot (uses `state.slot`)

**Removes:** `get_ptc_assignment` entirely — validators can only check current slot
**Modifies:** `process_slots` (hot path) with PTC computation every slot

**Pros:** Small state (8KB), simple rotation logic
**Cons:**
- Per-slot computation in `process_slots` (hot path)
- Removes validator duties lookahead (`get_ptc_assignment`)
- Per-slot state churn (SSZ tree modifications every slot)
- potuz himself expressed doubt about this version (2026-03-13)

### Lodestar Implementation (PR #9047 + PR #12)

Implements #4992's spec approach with client-side optimizations:
- State has `previousPtc` + `currentPtc` (per #4992)
- `rotatePayloadTimelinessCommittees` in `process_slots` (per #4992)
- BUT uses `epochCtx.payloadTimelinessCommittees[]` for fast lookups (all PTCs precomputed at epoch start)
- `previousEpochLastSlotPtc` in epochCtx for the boundary case

## Discussion Context (eth-rnd Discord, consensus-specs comments)

### Key participants:
- **potuz:** Authored both #4979 and #4992. Prefers #4979 (single computation point, no `process_slots` sync issues). State size "only 0.08% of current mainnet state."
- **fradamt (Francesco):** Identified that only the last slot is problematic. Open to either approach, slightly leaning toward full lookahead.
- **jtraglia:** Pushed #4992 forward, suggested named constants. Decided not to include in alpha.3 release (2026-03-13) due to lack of consensus.
- **sauliusgrigaitis (Grandine):** Questions why cache in state at all — clients have other caches not in spec.
- **nflaig (Nico):** Found the original bug. Explained that `previous_ptc` in state is needed for state loading (can't compute previous PTC without previous epoch's effective balances). Suggested ptc lookahead initially.
- **ensi321:** Prefers #4992 (balance of state size vs simplicity).

### Key insights from discussion:
1. **potuz on `process_slots` concern:** "I wouldn't be so certain [about #4992]... the PR that adds the full lookahead has a single point where this computation is carried and no synchronization with process slots that happens at time on wall clock."
2. **Nico on state loading:** "if you load a state you can't compute the previous PTC as you'd need the effective balances of the previous epoch"
3. **potuz's alternative idea:** "commit on each state to the current slot PTC... get_ptc is computed after processing the payload attestations and put into the state... PTC attesters can read from there their duties and attest"
4. **No consensus reached** — decision deferred from alpha.3 release

## Analysis: What's Actually Needed

### The invariant:
- `process_payload_attestation` asserts `data.slot + 1 == state.slot`
- So we only ever need PTC for `state.slot - 1`
- This is only a problem when crossing epoch boundaries (effective balances change)

### What CAN be recomputed from current state:
- **Current epoch PTCs:** Yes — same effective balances ✅
- **Next epoch PTCs:** Yes — same effective balances (until next epoch boundary) ✅
- **Previous epoch's last slot PTC:** **NO** — effective balances have changed ❌

### Therefore:
We need exactly **one** cached PTC in state: the PTC of the last slot of the previous epoch. Everything else can be computed on demand.

## Proposed Design: Single `previous_ptc`

### State change (minimal):
```python
class BeaconState(Container):
    ...
    # [New in Gloas:EIP7732]
    previous_ptc: Vector[ValidatorIndex, PTC_SIZE]
```
- Size: 512 × 8 = **4,096 bytes (~4KB)** per state
- Single field, no arrays, no per-slot indices

### New helper — `compute_ptc(state, slot)`:
Extracted from current `get_ptc`. Pure computation, works for any slot using state's current effective balances:
```python
def compute_ptc(state: BeaconState, slot: Slot) -> Vector[ValidatorIndex, PTC_SIZE]:
    """
    Compute the payload timeliness committee for the given ``slot``
    using the state's current effective balances.
    """
    epoch = compute_epoch_at_slot(slot)
    seed = hash(get_seed(state, epoch, DOMAIN_PTC_ATTESTER) + uint_to_bytes(slot))
    indices: List[ValidatorIndex] = []
    committees_per_slot = get_committee_count_per_slot(state, epoch)
    for i in range(committees_per_slot):
        committee = get_beacon_committee(state, slot, CommitteeIndex(i))
        indices.extend(committee)
    return compute_balance_weighted_selection(
        state, indices, seed, size=PTC_SIZE, shuffle_indices=False
    )
```

### Modified `get_ptc(state, slot)`:
Uses cached `previous_ptc` for epoch boundary, computes on demand otherwise:
```python
def get_ptc(state: BeaconState, slot: Slot) -> Vector[ValidatorIndex, PTC_SIZE]:
    """
    Get the payload timeliness committee for the given ``slot``.
    """
    epoch = compute_epoch_at_slot(slot)
    state_epoch = get_current_epoch(state)
    assert epoch <= state_epoch + 1
    if epoch == state_epoch - 1:
        assert slot % SLOTS_PER_EPOCH == SLOTS_PER_EPOCH - 1
        return state.previous_ptc
    return compute_ptc(state, slot)
```

### New epoch processing — `process_ptc_update(state)`:
Runs as **first operation** in `process_epoch`, BEFORE `process_effective_balance_updates` changes balances:
```python
def process_ptc_update(state: BeaconState) -> None:
    """
    Cache the PTC for the current slot (last slot of the ending epoch)
    before effective balance updates alter the computation.
    """
    state.previous_ptc = compute_ptc(state, Slot(state.slot))
```

### Modified `process_epoch`:
```python
def process_epoch(state: BeaconState) -> None:
    process_ptc_update(state)                    # [New in Gloas:EIP7732] — FIRST!
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)      # ← balances change here
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    process_proposer_lookahead(state)
    process_builder_pending_payments(state)
```

### Fork/genesis initialization:
```python
def initialize_previous_ptc(state: BeaconState) -> Vector[ValidatorIndex, PTC_SIZE]:
    """
    Initialize previous_ptc to zeros. At genesis/fork, there are no
    previous-epoch payload attestations to validate.
    """
    return [ValidatorIndex(0)] * PTC_SIZE
```

### `get_ptc_assignment` — UNCHANGED:
Stays exactly as-is in validator.md. Works for current and next epoch via `compute_ptc`:
```python
def get_ptc_assignment(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> Optional[Slot]:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    assert epoch <= next_epoch
    start_slot = compute_start_slot_at_epoch(epoch)
    for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH):
        if validator_index in get_ptc(state, Slot(slot)):
            return Slot(slot)
    return None
```
For `epoch == current_epoch` or `epoch == next_epoch`, `get_ptc` calls `compute_ptc` which uses current effective balances — correct for both cases.

### `process_slots` — UNCHANGED:
No per-slot rotation. No modification to this hot path.

## Comparison

| | Current spec (broken) | #4979 (closed) | #4992 (open) | **Our proposal** |
|---|---|---|---|---|
| State fields added | 0 | 1 (Vector of 64 PTCs) | 2 (prev + current PTC) | **1 (previous PTC)** |
| State overhead | 0 | ~256KB | ~8KB | **~4KB** |
| `process_slots` modified | No | No | **Yes** (per-slot) | **No** |
| `process_epoch` modified | No | Yes (end) | No | **Yes (start)** |
| Per-slot computation | No | No | **Yes** | **No** |
| `get_ptc_assignment` | ✅ Works | ✅ Works | ❌ Removed | **✅ Works** |
| Validator duties API | Full lookahead | Full lookahead | Current slot only | **Full lookahead** |
| Fork choice impact | None | None | Reorder in on_payload_attestation | **None** |
| Spec complexity | N/A | Medium | Medium | **Low** |

## Correctness Proof (Edge Cases)

### 1. Normal operation (same epoch)
- State at slot 33 (epoch 1), attestation for slot 32 (epoch 1)
- `get_ptc(state, 32)` → `compute_ptc(state, 32)` → uses epoch 1 balances ✅

### 2. Epoch boundary
- State at slot 32 (epoch 1), attestation for slot 31 (epoch 0)
- `get_ptc(state, 31)` → epoch 0 ≠ epoch 1, slot 31 % 32 == 31 ✅
- Returns `state.previous_ptc` (saved before balance updates) ✅

### 3. Multiple missed slots crossing epoch
- State advances from slot 20 to slot 100 (epochs 0-3)
- Each epoch boundary updates `previous_ptc` for that epoch's last slot
- Final `previous_ptc` = PTC for slot 95 (last slot of epoch 2, with epoch 2 balances) ✅

### 4. Genesis (slot 0)
- `previous_ptc` = zeros
- No payload attestations from slot -1, never queried ✅

### 5. Fork upgrade
- `previous_ptc` = zeros (initialized at fork)
- First epoch after fork: no cross-epoch PTC lookback needed ✅

### 6. Fork choice (`on_payload_attestation_message`)
- Uses `store.block_states[data.beacon_block_root]` where `data.slot == state.slot`
- `get_ptc(state, data.slot)` → current epoch → `compute_ptc` ✅

### 7. Gossip validation
- Only validates current slot attestations
- `get_ptc(state, current_slot)` → current epoch → `compute_ptc` ✅

## Lodestar Implementation Strategy

The Lodestar implementation would be:
1. **State type:** Only `previousPtc: Vector[ValidatorIndex, PTC_SIZE]` (remove `currentPtc`)
2. **Remove** `rotatePayloadTimelinessCommittees` from `stateTransition.ts`
3. **Epoch processing:** Save PTC at start of epoch processing (before `processEffectiveBalanceUpdates`)
4. **Keep** `epochCtx.payloadTimelinessCommittees[]` for all current-epoch lookups (performance)
5. **Keep** `epochCtx.previousEpochLastSlotPtc` for the boundary case
6. **Block processing:** Use `epochCtx` for current epoch, `state.previousPtc` (via epochCtx) for boundary
7. **`get_ptc_assignment`** works via epochCtx (already precomputed for current+next epoch)

### Key changes from current PR #9047 + #12:
- Remove `currentPtc` from SSZ state type
- Remove per-slot `rotatePayloadTimelinessCommittees` calls in `processSlotsWithTransientCache`
- Add `process_ptc_update` equivalent at start of epoch processing
- Initialize `previousPtc` to zeros at fork/genesis (instead of computing)

## Open Questions for Design Phase

1. **Placement in `process_epoch`:** First operation vs. right before `process_effective_balance_updates`? First is simpler and more robust (no risk of future spec changes reordering operations before it).

2. **Assert strictness in `get_ptc`:** Should we hard-assert that previous-epoch queries can only be for the last slot? Or return an error? The assert documents the invariant clearly.

3. **Naming:** `previous_ptc` is clear but doesn't capture the "last slot of previous epoch" semantic. Alternative: `epoch_boundary_ptc`? Stick with `previous_ptc` for consistency with `previous_epoch_attestations` pattern?

4. **Heze fork passthrough:** The `previous_ptc` field needs to be carried forward to heze (same as #4992).

---

## Phase 2 — Design Review

### Review feedback (gpt-advisor + self-analysis)

#### Q1: Correctness — confirmed with caveats

**Overall verdict: correct.** The core invariant trace is sound:
1. Block at slot 31 processed
2. `process_slots(state, 32)` called
3. At `state.slot = 31`: `(31 + 1) % 32 == 0` → `process_epoch` triggers
4. FIRST: `process_ptc_update` → `compute_ptc(state, 31)` with epoch 0 balances → stored in `previous_ptc`
5. `state.slot` increments to 32
6. Block at 32: `process_payload_attestation` → `get_ptc(state, 31)` → returns `state.previous_ptc` ✅

**Critical dependency (verified safe):** The design requires `process_epoch` to run while `state.slot = SLOTS_PER_EPOCH - 1` (last slot of epoch), not the first slot of the next epoch. The canonical spec:
```python
if (state.slot + 1) % SLOTS_PER_EPOCH == 0:
    process_epoch(state)
state.slot = Slot(state.slot + 1)
```
...triggers at `state.slot = 31`, not 32. ✅ No EPBS spec changes alter this.

**Reorgs:** Deterministic — any reorg recomputes `previous_ptc` from the new chain's state at the epoch boundary. ✅

**State replays:** Same — deterministic computation from state. ✅

#### Improvement: Tighten lower-bound assert in `get_ptc`

Current design allows `epoch == state_epoch - 2` to fall through to `compute_ptc` with wrong (current) effective balances — silently returns incorrect data. While `process_payload_attestation`'s `data.slot + 1 == state.slot` constraint prevents this in practice, it's a correctness landmine for future callers.

**Fix:** Add lower-bound assert:
```python
def get_ptc(state: BeaconState, slot: Slot) -> Vector[ValidatorIndex, PTC_SIZE]:
    epoch = compute_epoch_at_slot(slot)
    state_epoch = get_current_epoch(state)
    assert state_epoch - 1 <= epoch <= state_epoch + 1  # ← tightened
    if epoch == state_epoch - 1:
        assert slot % SLOTS_PER_EPOCH == SLOTS_PER_EPOCH - 1
        return state.previous_ptc
    return compute_ptc(state, slot)
```

**Epoch 0 edge case:** When `state_epoch = 0`, `state_epoch - 1` wraps in unsigned arithmetic (`uint64`). In Python this is `-1`, in real implementations it'd overflow to `2^64 - 1`. No slot maps to that epoch, so the previous-epoch path is never taken. Correct but implicit — worth a comment in the spec.

#### Q2: Spec ordering — FIRST placement is safe ✅

Verified each `process_epoch` step before `process_effective_balance_updates`:

| Step | Changes effective balances? | Changes committee composition? | Safe? |
|------|---|---|---|
| `process_justification_and_finalization` | No | No | ✅ |
| `process_inactivity_updates` | No (inactivity_scores only) | No | ✅ |
| `process_rewards_and_penalties` | Actual balances only, NOT effective | No | ✅ |
| `process_registry_updates` | No | Sets `activation_epoch`/`exit_epoch` to **future** epochs only (`current + 1 + MAX_SEED_LOOKAHEAD`) | ✅ |
| `process_slashings` | Actual balances only | No | ✅ |
| `process_eth1_data_reset` | No | No | ✅ |
| **`process_effective_balance_updates`** | **YES** | **YES (indirectly)** | ❌ Must be after our step |

**Conclusion:** FIRST placement is the most conservative — no step before it can affect PTC computation. Even placing it right before `process_effective_balance_updates` would be safe, but FIRST removes any ambiguity.

#### Q3: Assert strictness

The `assert slot % SLOTS_PER_EPOCH == SLOTS_PER_EPOCH - 1` for previous-epoch queries is **correctly restrictive**. The only legitimate previous-epoch PTC query is from `process_payload_attestation` (which enforces `data.slot + 1 == state.slot`), and the only cross-epoch case is the last→first slot transition. Any other previous-epoch query would silently return wrong data, so asserting is strictly better than allowing it.

#### Q4: `get_ptc_assignment` for previous epoch

The current spec's `get_ptc_assignment` allows `epoch <= next_epoch` which theoretically includes previous epochs. However:
- Validators call it for `current_epoch` or `current_epoch + 1` only (per validator.md guidance)
- For previous-epoch queries, even the current spec (without caching) gives wrong results (uses current balances for a past epoch's computation)
- Our change doesn't make this any worse — and the tightened assert would make it fail-fast rather than silently wrong

**Decision:** No concern. The `assert state_epoch - 1 <= epoch` in `get_ptc` will cause `get_ptc_assignment` to fail for `epoch < current_epoch - 1`, which is the correct behavior (those results would be wrong anyway).

For `epoch == current_epoch - 1`, `get_ptc_assignment` would iterate all 32 slots, but only the last slot (SLOTS_PER_EPOCH - 1) would pass the inner assert. If the validator happens to be in that last-slot PTC, it returns correctly. If not, it tries other slots and hits the assert. This is arguably a spec UX issue — but `get_ptc_assignment` for previous epochs was never reliably correct, so we can:
- Option A: Leave `get_ptc_assignment`'s assert as `epoch <= next_epoch` (current behavior, misleading)
- Option B: Tighten to `current_epoch <= epoch <= next_epoch` (correct, breaking change for theoretically bad callers)

**Recommendation:** Option B — tighten `get_ptc_assignment` to only allow current/next epoch:
```python
def get_ptc_assignment(state, epoch, validator_index):
    next_epoch = Epoch(get_current_epoch(state) + 1)
    assert get_current_epoch(state) <= epoch <= next_epoch  # ← tightened
    ...
```

#### Q5: END vs START placement

**END placement doesn't work.** At end of `process_epoch`, effective balances have already been updated by `process_effective_balance_updates`. Computing `compute_ptc(state, state.slot)` at this point uses the NEW balances — this gives the wrong PTC for the epoch that just ended.

A "shift" pattern (like #4979) where you pre-compute the NEXT epoch's PTCs at the END would work, but then you'd need to already HAVE the current epoch's PTCs from the previous boundary — bootstrapping the same problem. You'd need two fields or the full lookbehind array.

**Conclusion:** START placement is the only single-field approach that works. Confirmed.

#### Q6: Naming

- `previous_ptc` — simple, matches `previous_epoch_attestations` pattern, understood quickly
- `epoch_boundary_ptc` — more precise semantically, but unfamiliar pattern in the spec
- `cached_ptc` — too generic

**Recommendation:** `previous_ptc` — it's consistent with existing spec naming conventions and potuz/jtraglia already used this name in #4992 discussions.

#### Q7: "Too clever" for spec adoption?

This is the real risk. The approach requires understanding:
1. Only one slot crosses the epoch boundary (non-obvious)
2. The `process_epoch` ordering matters (placement before balance updates)
3. The assert in `get_ptc` encodes a protocol invariant

However:
- fradamt already identified "the only slot where it's a problem is the last one" — the community understands this
- The spec changes are ~20 lines total (smaller than both #4979 and #4992)
- It addresses both potuz's concern (no `process_slots` modification) and the state size concern
- It preserves `get_ptc_assignment` (which #4992 removes — a real regression for validator clients)

**Mitigation:** Add a clear NOTE in the spec explaining WHY only one PTC is cached, referencing the `data.slot + 1 == state.slot` invariant in `process_payload_attestation`. Spec clarity > cleverness opacity.

### Revised Spec Design (incorporating review feedback)

```python
# BeaconState addition
class BeaconState(Container):
    ...
    # [New in Gloas:EIP7732]
    previous_ptc: Vector[ValidatorIndex, PTC_SIZE]

# New compute helper (extracted from get_ptc)
def compute_ptc(state: BeaconState, slot: Slot) -> Vector[ValidatorIndex, PTC_SIZE]:
    """
    Compute the payload timeliness committee for the given ``slot``
    using the state's current effective balances.
    """
    epoch = compute_epoch_at_slot(slot)
    seed = hash(get_seed(state, epoch, DOMAIN_PTC_ATTESTER) + uint_to_bytes(slot))
    indices: List[ValidatorIndex] = []
    committees_per_slot = get_committee_count_per_slot(state, epoch)
    for i in range(committees_per_slot):
        committee = get_beacon_committee(state, slot, CommitteeIndex(i))
        indices.extend(committee)
    return compute_balance_weighted_selection(
        state, indices, seed, size=PTC_SIZE, shuffle_indices=False
    )

# Modified get_ptc
def get_ptc(state: BeaconState, slot: Slot) -> Vector[ValidatorIndex, PTC_SIZE]:
    """
    Get the payload timeliness committee for the given ``slot``.
    
    *Note*: For the previous epoch, only the PTC of the last slot is available
    via ``state.previous_ptc``, since that is the only cross-epoch lookup 
    required by ``process_payload_attestation`` (which enforces
    ``data.slot + 1 == state.slot``). All other PTCs are computed on demand
    from the state's current effective balances.
    """
    epoch = compute_epoch_at_slot(slot)
    state_epoch = get_current_epoch(state)
    # Note: at epoch 0, state_epoch - 1 underflows; no slot maps to that epoch
    assert state_epoch - 1 <= epoch <= state_epoch + 1
    if epoch == state_epoch - 1:
        assert slot % SLOTS_PER_EPOCH == SLOTS_PER_EPOCH - 1
        return state.previous_ptc
    return compute_ptc(state, slot)

# New epoch processing step
def process_ptc_update(state: BeaconState) -> None:
    """
    Cache the PTC for the current slot (last slot of the ending epoch)
    before effective balance updates alter the weighted selection.
    """
    state.previous_ptc = compute_ptc(state, Slot(state.slot))

# Modified process_epoch (process_ptc_update FIRST)
def process_epoch(state: BeaconState) -> None:
    process_ptc_update(state)                    # [New in Gloas:EIP7732]
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    process_proposer_lookahead(state)
    process_builder_pending_payments(state)

# Modified get_ptc_assignment (tightened assert)
def get_ptc_assignment(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> Optional[Slot]:
    """
    Returns the slot during the requested epoch in which the validator with
    index ``validator_index`` is a member of the PTC. Returns None if no
    assignment is found.
    """
    next_epoch = Epoch(get_current_epoch(state) + 1)
    assert get_current_epoch(state) <= epoch <= next_epoch  # tightened from epoch <= next_epoch

    start_slot = compute_start_slot_at_epoch(epoch)
    for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH):
        if validator_index in get_ptc(state, Slot(slot)):
            return Slot(slot)
    return None

# Fork initialization
def upgrade_to_gloas(pre):
    ...
    post = BeaconState(
        ...
        previous_ptc=[ValidatorIndex(0)] * PTC_SIZE,
    )
    ...

# Genesis initialization  
def create_genesis_state(...):
    ...
    state.previous_ptc = [ValidatorIndex(0)] * PTC_SIZE
```

### Files changed (consensus-specs):
1. `specs/gloas/beacon-chain.md` — `BeaconState`, `compute_ptc`, `get_ptc`, `process_ptc_update`, `process_epoch`
2. `specs/gloas/fork.md` — `upgrade_to_gloas` initialization
3. `specs/gloas/validator.md` — `get_ptc_assignment` assert tightening
4. `specs/heze/beacon-chain.md` — `BeaconState` field passthrough
5. `specs/heze/fork.md` — `upgrade_to_heze` passthrough
6. `tests/` — test_process_ptc_update, test_get_ptc_boundary, test_get_ptc_assignment

---

*Phase 2 complete. Design reviewed and finalized. Ready for Phase 3 (spec implementation).*
