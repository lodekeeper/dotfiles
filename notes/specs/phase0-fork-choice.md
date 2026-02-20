# Phase0 — Fork Choice Notes

**Spec:** `consensus-specs/specs/phase0/fork-choice.md`  
**Status:** Read ✅  
**Date:** 2026-02-16

## Overview

Defines the LMD-GHOST fork choice algorithm — the mechanism by which nodes determine the canonical chain head. This is an event-driven system with four handlers: `on_tick`, `on_block`, `on_attestation`, `on_attester_slashing`.

## Core Algorithm: LMD-GHOST

### `get_head` — The Heart of Fork Choice
```
1. Start from justified_checkpoint.root
2. Filter block tree to only viable branches (correct justified/finalized info)
3. Greedy walk: at each fork, follow child with highest weight
4. Weight = attestation_score + proposer_boost (if applicable)
5. Ties broken by lexicographically higher root (deterministic)
```

### Weight Calculation (`get_weight`)
- **Attestation score:** Sum of effective balances of validators whose latest message (LMD vote) supports this block as ancestor
- **Proposer boost:** Additional weight (40% of committee weight) if block is ancestor of `proposer_boost_root`
- Only non-equivocating, non-slashed, active validators count

## The Store

Central data structure tracking fork choice state:

| Field | Purpose |
|-------|---------|
| `justified_checkpoint` | Starting point for LMD-GHOST |
| `finalized_checkpoint` | Blocks must be descendants of this |
| `unrealized_justified/finalized` | "Pulled up" checkpoints (ahead of on-chain realization) |
| `proposer_boost_root` | Current block receiving proposer score boost |
| `equivocating_indices` | Validators caught double-voting (votes ignored) |
| `blocks` | Block storage by root |
| `block_states` | Post-state for each block |
| `block_timeliness` | Whether block arrived before attestation deadline |
| `latest_messages` | Latest LMD vote per validator (epoch + root) |
| `unrealized_justifications` | Per-block unrealized justified checkpoint |

## Checkpoint Pull-Up (`compute_pulled_up_tip`)

**Key optimization:** When a block arrives, eagerly compute what justification/finalization *would* happen if epoch processing ran now. This prevents stalling where a block contains enough attestations to justify but the on-chain realization hasn't happened yet.

- Copy block's post-state, run `process_justification_and_finalization`
- Store result in `unrealized_justifications`
- If block is from a prior epoch, realize the checkpoints immediately

## Proposer Boost (EIP-7716 area)

**Purpose:** Prevent balancing attacks by giving the timely proposer's block extra weight.

- **Boost amount:** `PROPOSER_SCORE_BOOST = 40` (40% of one committee's weight)
- **Timely:** Block for current slot arriving before attestation deadline
- **Reset:** Cleared at each new slot (`on_tick_per_slot`)
- Only first timely block gets boost (prevents equivocation abuse)
- Proposer must match canonical chain's expected proposer

## Proposer Reorg (`get_proposer_head`)

**Optional optimization** allowing proposers to build on parent instead of head when:

1. Head arrived late (`is_head_late`)
2. Not at epoch boundary (`is_shuffling_stable`) — shuffling could change proposer
3. FFG info competitive (`is_ffg_competitive`) — reorg doesn't hurt finality
4. Chain finalizing normally (`is_finalization_ok`) — within 2 epochs
5. Proposing on time (`is_proposing_on_time`) — within 17% of slot
6. Single slot reorg only (`parent_slot_ok && current_time_ok`)
7. Head is weak (`is_head_weak`) — <20% committee weight (can be overridden by boost)
8. Parent is strong (`is_parent_strong`) — >160% committee weight (votes aren't hoarded)

**Alternative path:** If head is weak AND proposer equivocated → reorg regardless (fewer conditions).

## Block Tree Filtering (`filter_block_tree`)

Before running `get_head`, prune branches that don't agree with store's justified/finalized checkpoints:

- Leaf blocks must have:
  - Voting source at same height as store's justified, OR within 2 epochs
  - Correct finalized checkpoint block at the finalized epoch's slot
- Parent blocks kept if any child passes filter

## Event Handlers

### `on_tick`
- Catches up slot-by-slot if time falls behind
- At new slot: reset `proposer_boost_root`
- At new epoch: realize unrealized checkpoints

### `on_block`
1. Verify parent known, block not in future, descendant of finalized block
2. Run full `state_transition` to get post-state
3. Store block and state
4. Record timeliness, update proposer boost
5. Update checkpoints, compute pulled-up tip

### `on_attestation`
1. Validate: correct epoch, known block roots, LMD consistent with FFG, not from future
2. Store target checkpoint state (process slots if needed)
3. Verify indexed attestation signature
4. Update `latest_messages` for non-equivocating attesters

### `on_attester_slashing`
1. Verify slashable attestation data (double vote or surround vote)
2. Verify both indexed attestations valid
3. Add intersection of attesting indices to `equivocating_indices`

## Timing

Slot timing now uses basis points of `SLOT_DURATION_MS`:
- `ATTESTATION_DUE_BPS` — attestation deadline
- `AGGREGATE_DUE_BPS` — aggregate deadline
- `PROPOSER_REORG_CUTOFF_BPS = 1667` — ~17% of slot (~2s in 12s slot)

## Design Observations

1. **Latest-message driven (LMD):** Each validator has exactly one vote (latest message). No vote counting of historical attestations — just "where does each validator currently point?"

2. **Equivocating validators zeroed out:** Once caught via `on_attester_slashing`, their votes are permanently ignored in fork choice. This is separate from the slashing penalty in beacon state.

3. **Checkpoint states are cached:** `store.checkpoint_states` avoids recomputing epoch-boundary states. These states are needed for signature verification against the target epoch's validator set.

4. **Unrealized vs realized checkpoints:** Fork choice runs ahead of on-chain processing. Checkpoints are computed eagerly (unrealized) and promoted to realized at epoch boundaries or when blocks from prior epochs arrive.

5. **Proposer boost prevents balancing attacks:** Without it, an attacker could alternate between two chain tips by timing attestations. The 40% boost ensures the timely proposer's chain gets a clear advantage.

6. **`get_ancestor` is recursive in spec but O(chain_length):** Real implementations use proto-array or similar for O(1) ancestor lookups.

---
*Next: Phase0 p2p-interface, validator, weak-subjectivity*
