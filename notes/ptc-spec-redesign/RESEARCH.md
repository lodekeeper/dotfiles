# PTC Spec Redesign — Research Notes

## The Problem (consensus-specs#4979)
When processing the block at slot 32, we validate payload attestations with the PTC of slot 31.
However, `get_ptc` uses `compute_balance_weighted_selection` which depends on `effectiveBalanceIncrements`.
At epoch boundary (slot 31 → slot 32), effective balances change during epoch processing.
So `get_ptc(state_at_slot_32, slot=31)` may return a DIFFERENT committee than
`get_ptc(state_at_slot_31, slot=31)` — because the effective balances changed.

This means payload attestations that were valid when cast (slot 31) might be rejected
when included in a block (slot 32) because the PTC membership changed.

**Found by Nico (@nflaig).**

## Approaches Discussed

### Approach A: Full Lookbehind (PR #4979, closed)
- Add `ptc_lookbehind: Vector[Vector[ValidatorIndex, PTC_SIZE], 2 * SLOTS_PER_EPOCH]` to state
- Caches full PTC for current + previous epoch (64 entries × PTC_SIZE)
- ~256KB added to state
- potuz says: "only 0.08% of current beacon state"
- Clean but wasteful — most entries never read

### Approach B: Two-slot Cache (PR #4992, open)
- Add `previous_ptc` and `current_ptc` to state (2 × Vector[ValidatorIndex, PTC_SIZE])
- ~8KB added to state
- Rotate every slot in `process_slots`: `previous_ptc = current_ptc; current_ptc = compute_ptc(state)`
- `get_ptc(state, slot)` reads from state instead of computing
- **Problems (per Nico):**
  - Requires per-slot rotation (state mutation every slot)
  - Modified `process_slots` function (adds complexity)
  - `get_ptc_assignment` removed (validator.md simplified but limited)
  - Only serves current/previous slot, no lookahead

### Approach C: Epoch-level computation + epochCtx cache (Lodestar PR #9047 + PR #12)
- Compute all PTCs at epoch start, cache in `epochCtx.payloadTimelinessCommittees: Uint32Array[]`
- Add `previousEpochLastSlotPtc: Uint32Array | null` to epochCtx for epoch boundary
- `getPayloadTimelinessCommittee(slot)` serves from epochCtx
- **This is an implementation-level optimization, not a spec change**
- Spec still needs to define how the PTC is determined for a given slot

## Key Insights

1. **The core issue is epoch-boundary only** — within an epoch, effective balances don't change,
   so `get_ptc(state, slot)` is deterministic regardless of which slot in that epoch the state is at.

2. **Only the last slot of the previous epoch is needed at epoch boundary** — because
   `process_payload_attestation` enforces `data.slot + 1 == state.slot`.

3. **Clients already cache all epoch PTCs** — for duties API (get_ptc_assignment).
   The spec should reflect this reality.

4. **potuz's key point**: "if clients will anyway cache them, then most likely having the
   full cache in the spec is more efficient than keeping it in an ad-hoc in-memory cache
   that needs to be in-sync with the head state"

5. **sauliusgrigaitis (Grandine)**: "why do we need such a cache in the state? Clients have
   a lot of other caches that are part of the client not specification."

6. **Nico's response**: "if you load a state you can't compute the previous PTC as you'd
   need the effective balances of the previous epoch"

## Trade-offs Matrix

| Approach | State Size | Per-slot Cost | Epoch Boundary | Duties API | Spec Complexity |
|----------|-----------|--------------|----------------|------------|-----------------|
| A (full) | +256KB | None | ✅ | ✅ | Low |
| B (2-slot) | +8KB | Rotation | ✅ | ❌ (removed) | Medium |
| C (client) | +0 | None | Client handles | Client handles | None |

## Design Constraints (from Nico)
- Minimal state changes
- Avoid per-slot state modification
- Still compute all PTCs at epoch start and cache (for duties API)
- Directionally, PR #9047 + PR #12 are close to what we want
- Must solve the checkpoint-sync problem (can't compute previous epoch PTC from loaded state)
