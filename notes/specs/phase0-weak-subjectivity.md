# Phase0 — Weak Subjectivity Notes

**Spec:** `consensus-specs/specs/phase0/weak-subjectivity.md`  
**Status:** Read ✅  
**Date:** 2026-02-16

## Overview

Defines weak subjectivity protections — the mechanism ensuring that nodes syncing from scratch (or after a long offline period) can't be tricked into following a fake chain created by an attacker who temporarily controlled a large validator set.

## Core Concept

In PoS, unlike PoW, an attacker who once controlled >1/3 of validators can create a valid-looking alternate chain from any point in history (long-range attack). Weak subjectivity solves this by requiring nodes to start from a recent trusted checkpoint.

## Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| `SAFETY_DECAY` | 10 | Max % loss in FFG safety margin |
| `ETH_TO_GWEI` | 10^9 | Unit conversion |

**Safety guarantee:** Any attack exploiting the WS period has safety margin of at least `1/3 - SAFETY_DECAY/100 = 1/3 - 0.1 = ~23%`.

## Weak Subjectivity Period

The number of epochs during which a WS checkpoint remains valid. Depends on:

1. **Validator set churn** — bounded by `get_validator_churn_limit()` per epoch
2. **Balance top-ups** — bounded by `MAX_DEPOSITS * SLOTS_PER_EPOCH` per epoch
3. **Average validator balance** vs **max effective balance**

### Practical Values (SAFETY_DECAY=10)

| Avg Balance | Validator Count | WS Period (epochs) | ≈ Duration |
|------------|----------------|-------------------|-----------|
| 28 ETH | 32,768 | 504 | ~3.3 days |
| 28 ETH | 262,144 | 2,241 | ~14.8 days |
| 32 ETH | 32,768 | 665 | ~4.4 days |
| 32 ETH | 262,144+ | 3,532 | ~23.3 days |

**Key insight:** With full 32 ETH balances and large validator sets, the WS period is about 3 weeks. With lower average balances (due to penalties/partial withdrawals), the period shrinks.

### Formula Logic
Two regimes based on whether average balance `t` is close to max `T`:
- If `t` is sufficiently large relative to `T`: WS period is max of churn-based and top-up-based calculations
- If `t` is closer to `T`: simpler formula dominates

## Sync Procedure

### Input
CLI parameter: `block_root:epoch_number` (e.g., `0x8584...43d9:9544`)

### Verification
- If WS checkpoint epoch > finalized epoch: Assert block with given root appears in sync path at that epoch
- If WS checkpoint epoch ≤ finalized epoch: Assert canonical block at that epoch matches the root
- **Failure is CRITICAL** — client must exit

### Staleness Check
`is_within_weak_subjectivity_period(store, ws_state, ws_checkpoint)`:
- Compute WS period from the checkpoint state
- Verify `current_epoch ≤ ws_state_epoch + ws_period`
- If stale: checkpoint is too old, need a newer one

## Lodestar Relevance

- `--weakSubjectivityCheckpoint` CLI flag for checkpoint sync
- `--checkpointSyncUrl` for fetching state from a trusted source
- The WS period calculation should be verified in `packages/beacon-node/` or `packages/state-transition/`
- Block backfill to `MIN_EPOCHS_FOR_BLOCK_REQUESTS` is required for full compliance with p2p spec

## Design Observations

1. **Trust assumption is minimal** — only need to trust ONE checkpoint from a trusted source (block explorer, friend, official channel). After that, the protocol's own finality mechanism takes over.

2. **WS period increases with validator count** — more validators = harder to churn enough to fake a chain = longer safe period.

3. **`SAFETY_DECAY = 10` is conservative** — allows 10% degradation of the 33% safety margin, leaving 23% margin. This could be tuned for different security/usability tradeoffs.

4. **Checkpoint distribution is unsolved** — the spec acknowledges this with a placeholder section. In practice, checkpoint sync URLs (Infura, ethdo, beaconcha.in) fill this role.

---
*Phase0 complete! Next: Altair specs*
