# Phase0 — Beacon Chain State Transition Notes

**Spec:** `consensus-specs/specs/phase0/beacon-chain.md`  
**Status:** Read ✅  
**Date:** 2026-02-16

## Overview

The foundational specification — defines the complete beacon chain state machine including types, state transition, epoch processing, block processing, genesis, and all helper functions. Everything in later forks builds on this.

## Core Architecture

### State Transition Flow
```
state_transition(state, signed_block):
  1. process_slots(state, block.slot)     → advance slot-by-slot, run epoch processing
  2. verify_block_signature(state, block)  → BLS verify proposer signature
  3. process_block(state, block)           → apply block operations
  4. verify state_root matches            → post-state integrity check
```

### Slot Processing (`process_slot`)
Each slot:
1. Cache state root in `state.state_roots[slot % 8192]`
2. Fill in `latest_block_header.state_root` if it's zero (it's intentionally left blank during block processing to avoid circular dependency)
3. Cache block root in `state.block_roots[slot % 8192]`

**Key insight:** The `latest_block_header.state_root` trick — during `process_block_header`, the state root is set to `Bytes32()` (zeros) because the state root isn't known until after processing. It gets filled in at the *next* slot's `process_slot`. This avoids the circular dependency of "state root depends on block header, which contains state root."

### Epoch Processing (`process_epoch`)
Runs at the boundary of each epoch (when `(slot + 1) % SLOTS_PER_EPOCH == 0`):
1. Justification & finalization (Casper FFG)
2. Rewards & penalties
3. Registry updates (activations, ejections)
4. Slashings
5. Eth1 data votes reset
6. Effective balance updates (with hysteresis)
7. Slashings vector reset
8. RANDAO mixes rotation
9. Historical roots accumulation
10. Participation records rotation

## Key Data Structures

### `Validator`
```
pubkey, withdrawal_credentials, effective_balance,
slashed, activation_eligibility_epoch, activation_epoch,
exit_epoch, withdrawable_epoch
```
- `effective_balance` ≤ `MAX_EFFECTIVE_BALANCE` (32 ETH), updated with hysteresis
- Lifecycle: deposit → eligible → activated → (optionally slashed) → exited → withdrawable

### `BeaconState`
Core state fields:
- **Chain metadata:** genesis_time, genesis_validators_root, slot, fork
- **Block/state history:** block_roots, state_roots (circular buffers of 8192)
- **Eth1:** eth1_data, eth1_data_votes, eth1_deposit_index
- **Validators:** validators list, balances list
- **Randomness:** randao_mixes (circular buffer of 65536 epochs)
- **Slashings:** slashings vector (8192 epochs)
- **Attestations:** previous/current_epoch_attestations (PendingAttestation lists)
- **Finality:** justification_bits, previous/current_justified_checkpoint, finalized_checkpoint

## Committee & Proposer Selection

### Shuffling (`compute_shuffled_index`)
- Swap-or-not algorithm (90 rounds)
- Based on the paper by Viet Tung Hoang & Phillip Rogaway
- Produces a permutation of validator indices that's efficient to compute for individual indices

### Committee Formation (`compute_committee`)
- Divides shuffled validator set into committees
- Committee count per slot = `max(1, min(64, active_validators / 32 / 128))`
- Target committee size of 128 validators
- Each slot has potentially up to 64 committees

### Proposer Selection (`compute_proposer_index`)
- Weighted random selection proportional to effective balance
- Uses rejection sampling: candidate chosen from shuffled indices, accepted with probability `effective_balance / MAX_EFFECTIVE_BALANCE`
- Ensures higher-balance validators have proportionally higher chance of proposal

## Justification & Finalization (Casper FFG)

### Justification
- Track via `justification_bits` (4-bit vector, most recent epochs)
- Epoch justified if ≥ 2/3 of total active balance attested to its target
- Both previous and current epoch attestations considered

### Finalization Rules (4 patterns)
1. Epochs N-3, N-2, N-1 justified, N-3 using N-1 as source → finalize N-3
2. Epochs N-2, N-1 justified, N-2 using N-1 as source → finalize N-2
3. Epochs N-2, N-1, N justified, N-2 using N as source → finalize N-2
4. Epochs N-1, N justified, N-1 using N as source → finalize N-1

**Note:** The 2/3 threshold check uses integer math: `target_balance * 3 >= total_balance * 2`

## Rewards & Penalties

### Base Reward
```
base_reward = effective_balance * 64 / sqrt(total_active_balance) / 4
```
- `BASE_REWARD_FACTOR = 64`, `BASE_REWARDS_PER_EPOCH = 4`
- Scales with individual balance, inversely with sqrt of total stake

### Four Components
1. **Source** — correct source checkpoint vote
2. **Target** — correct target checkpoint vote
3. **Head** — correct head block vote
4. **Inclusion delay** — proposer reward + attester reward inversely proportional to delay

### Normal Operation
- Reward = `base_reward * attesting_balance / total_balance` for each component
- This means rewards scale with participation rate — higher participation → higher individual rewards

### Inactivity Leak
- Triggered when `finality_delay > 4` epochs
- Non-participating validators get quadratically increasing penalty: `effective_balance * finality_delay / INACTIVITY_PENALTY_QUOTIENT`
- Participating validators get full base reward (neutral)
- Purpose: force finality by draining inactive validators until active set has 2/3 supermajority

## Slashing

### `slash_validator`
1. Initiate exit
2. Set `slashed = True`
3. Extend `withdrawable_epoch` to `epoch + EPOCHS_PER_SLASHINGS_VECTOR` (8192 epochs ≈ 36 days)
4. Immediate penalty: `effective_balance / MIN_SLASHING_PENALTY_QUOTIENT` (1/128 of balance)
5. Proposer gets `effective_balance / 512` reward
6. Whistleblower gets `effective_balance / 512` (minus proposer cut) — in Phase0, proposer IS whistleblower

### `process_slashings` (epoch)
- Additional penalty at midpoint of slashing period (`withdrawable_epoch - EPOCHS_PER_SLASHINGS_VECTOR/2`)
- Penalty proportional to total slashed balance in the period: `penalty = effective_balance * total_slashed * PROPORTIONAL_SLASHING_MULTIPLIER / total_balance`
- `PROPORTIONAL_SLASHING_MULTIPLIER = 1` in Phase0 (later increased to 3)
- This means isolated slashings have minimal additional penalty, but correlated slashings (many validators slashed together) face severe penalties

### Slashable Conditions
- **Double vote:** same target epoch, different attestation data
- **Surround vote:** source₁ < source₂ AND target₂ < target₁ (attestation 1 "surrounds" attestation 2)

## Effective Balance Hysteresis

Effective balance only updates when actual balance differs by more than threshold:
- `HYSTERESIS_INCREMENT = EFFECTIVE_BALANCE_INCREMENT / 4` = 0.25 ETH
- Downward threshold: `0.25 * 1 = 0.25 ETH` below effective
- Upward threshold: `0.25 * 5 = 1.25 ETH` above effective

This prevents constant churn in effective balance due to small reward/penalty fluctuations.

## Block Processing

### Block Header
- Verify slot matches state, block is newer than latest, proposer index correct, parent root matches
- Proposer must not be slashed
- Cache header with zeroed state_root (filled in next slot)

### RANDAO
- Proposer signs the epoch number with `DOMAIN_RANDAO`
- Mix revealed value into `randao_mixes`: `xor(current_mix, hash(reveal))`

### Eth1 Data
- Each block votes on eth1_data
- If >50% of votes in voting period agree → update `state.eth1_data`

### Operations
- **Ordering enforced:** proposer slashings → attester slashings → attestations → deposits → voluntary exits
- **Deposits:** Must process up to `min(MAX_DEPOSITS, pending_deposits)` — can't skip deposits
- **Attestations:** Valid for `[slot + 1, slot + SLOTS_PER_EPOCH]` inclusion window
  - Must reference correct source checkpoint (current or previous justified)
  - Stored as `PendingAttestation` with inclusion delay for reward calculation

## Genesis

### `initialize_beacon_state_from_eth1`
1. Create initial state seeded with eth1 block hash
2. Process all deposits (building Merkle tree incrementally)
3. Set effective balances, activate validators with 32 ETH
4. Set `genesis_validators_root`

### Validity
- `genesis_time >= MIN_GENESIS_TIME`
- Active validators ≥ `MIN_GENESIS_ACTIVE_VALIDATOR_COUNT` (16,384)

## Domain Separation

All signatures use domain separation via `compute_signing_root(object, domain)`:
- Domain = `domain_type (4 bytes) + fork_data_root[:28]`
- Fork data root includes fork version + genesis validators root
- This prevents cross-chain and cross-fork signature replay

Domain types: `BEACON_PROPOSER (0x00)`, `BEACON_ATTESTER (0x01)`, `RANDAO (0x02)`, `DEPOSIT (0x03)`, `VOLUNTARY_EXIT (0x04)`, `SELECTION_PROOF (0x05)`, `AGGREGATE_AND_PROOF (0x06)`

**Note:** `DOMAIN_DEPOSIT (0x03)` is fork-agnostic — deposits use `compute_domain(DOMAIN_DEPOSIT)` with no fork version, since deposits must be valid across forks.

## Design Observations

1. **Circular buffers everywhere** — `block_roots`, `state_roots` (8192 slots ≈ 27h), `randao_mixes` (65536 epochs ≈ 0.8yr), `slashings` (8192 epochs ≈ 36d). Bounded memory with sufficient history.

2. **PendingAttestation in Phase0** — attestations stored as pending during the epoch, processed for rewards at epoch boundary. This changes in Altair to the more efficient participation flags approach.

3. **Validator lifecycle is epoch-grained** — activation, exit, withdrawal all happen at epoch boundaries, with various delays (1 epoch min, up to 256 epochs for withdrawability).

4. **Exit queue with churn limit** — `max(4, validator_count / 65536)` exits per epoch. At 1M validators: ~15 per epoch. Prevents mass exodus.

5. **Proposer reward bundled with inclusion delay** — faster attestation inclusion benefits both proposer and attester. Proposer gets fixed fraction of base reward; attester reward scales inversely with delay.

6. **`compute_shuffled_index` is per-index efficient** — O(SHUFFLE_ROUND_COUNT) per index, no need to shuffle entire list. Critical for looking up individual committee assignments.

## Lodestar Cross-Reference Checklist
- [ ] `state-transition/src/slot/` — slot processing
- [ ] `state-transition/src/epoch/` — epoch processing functions
- [ ] `state-transition/src/block/` — block processing
- [ ] `state-transition/src/cache/epochCache.ts` — committee caching
- [ ] `state-transition/src/util/` — helper functions (shuffling, proposer, etc.)
- [ ] Spec test coverage in `beacon-node/test/spec/`

---
*Phase0 beacon-chain complete. Next: Phase0 fork-choice, p2p, validator*
