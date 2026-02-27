# 6-Second Slots (EIP-7782) — Research Notes

## Overview
- **EIP:** [EIP-7782](https://eips.ethereum.org/EIPS/eip-7782) — Reduce Block Latency
- **Authors:** Ben Adams, Dankrad Feist, Maria Inês Silva, Paul Harris (Teku)
- **Spec PR:** [ethereum/consensus-specs#4484](https://github.com/ethereum/consensus-specs/pull/4484)
- **Eth R&D Channel:** `shorter-slot-times` (13 days of logs in archive)
- **Status:** Draft, targeting Glamsterdam upgrade

## What Changes
1. **Slot time:** 12s → 6s
2. **Slot timing (BPS):** New attestation/aggregate/sync deadlines for 6s slots
3. **Blob schedule:** MAX_BLOBS_PER_BLOCK halved to 3 (maintain constant throughput/time)
4. **Churn limits:** Halved (maintain time-proportional rates)
5. **Sync committee period:** Doubled (512 epochs, maintain ~27 hours)
6. **Base reward factor:** `BASE_REWARD_FACTOR_EIP7782 = 32` (halved from 64?)
7. **Fork-choice time calculation:** Dual-rate slot calculation (12s pre-fork, 6s post-fork)
8. **Gas limit:** Halved on first post-fork block
9. **New fork:** EIP7782_FORK_VERSION, EIP7782_FORK_EPOCH

## Spec Changes (from PR #4484)
- **Files changed:** configs/mainnet.yaml, configs/minimal.yaml, specs/_features/eip7782/beacon-chain.md
- **Key functions modified:**
  - `get_balance_churn_limit()` — uses `MIN_PER_EPOCH_CHURN_LIMIT_EIP7782`
  - `get_activation_exit_churn_limit()` — uses `MAX_PER_EPOCH_ACTIVATION_EXIT_CHURN_LIMIT_EIP7782`
  - `get_sync_committee_period()` — uses `EPOCHS_PER_SYNC_COMMITTEE_PERIOD_EIP7782`
  - `get_base_reward_per_increment()` — uses `BASE_REWARD_FACTOR_EIP7782`
  - All timing functions (attestation_due, aggregate_due, sync_message_due, etc.)
  - Fork choice `compute_slot_at_time` — handles transition from 12s to 6s

## Config Parameters (EIP-7782 specific)
```
SLOT_DURATION_MS_EIP7782: 6000
ATTESTATION_DUE_BPS_EIP7782: 5000  (50% = 3000ms)
AGGREGRATE_DUE_BPS_EIP7782: 7500   (75% = 4500ms)
SYNC_MESSAGE_DUE_BPS_EIP7782: 3333 (~33% = 2000ms)
CONTRIBUTION_DUE_BPS_EIP7782: 6667 (~67% = 4000ms)
PROPOSER_REORG_CUTOFF_BPS_EIP7782: 1667 (~17% = 1000ms)
PAYLOAD_ATTESTATION_DUE_BPS_EIP7782: 7500 (75% = 4500ms)
VIEW_FREEZE_CUTOFF_BPS_EIP7782: 7500 (75% = 4500ms)
INCLUSION_LIST_SUBMISSION_DUE_BPS_EIP7782: 6667 (~67% = 4000ms)
PROPOSER_INCLUSION_LIST_CUTOFF_BPS_EIP7782: 9167 (~92% = 5500ms)
EPOCHS_PER_SYNC_COMMITTEE_PERIOD_EIP7782: 512
MIN_PER_EPOCH_CHURN_LIMIT_EIP7782: 64000000000
MAX_PER_EPOCH_ACTIVATION_EXIT_CHURN_LIMIT_EIP7782: 128000000000
BASE_REWARD_FACTOR_EIP7782: 32
BLOB_SCHEDULE: [{EPOCH: EIP7782_FORK_EPOCH, MAX_BLOBS_PER_BLOCK: 3}]
```

## Focil Branch Reference (ChainSafe/lodestar `focil`)
- 115 files changed, 2535 insertions
- Pattern for adding new fork: EIP7805 between Fulu and Gloas
- Key files to study:
  - `packages/params/src/forkName.ts` — ForkName enum
  - `packages/config/src/chainConfig/types.ts` — config types
  - `packages/config/src/chainConfig/configs/mainnet.ts` — fork version/epoch
  - `packages/config/src/forkConfig/index.ts` — ForkInfo, fork ordering
  - `packages/state-transition/src/slot/` — state upgrade function

## Eth R&D Discord (shorter-slot-times channel)
- 13 files (2025-06-27 to 2025-09-04)
- Key discussions:
  - terencechain: attestation arrival timing analysis (mainnet)
  - barnabemonnot: block/attestation propagation analysis
  - potuz: MEV implications of faster slots
  - misilva73: attestation timing analysis for 6s: https://ethresear.ch/t/an-analysis-of-attestation-timings-in-a-6-s-slot/23016
  - Discussion on delayed execution (EIP-7886) as prerequisite
  - julianma_: PR #3510 (slot subdivision spec)

## Prysm PoC
- No separate branch found. Per eth-rnd archive (2025-07-29), terencechain says:
  "right now, I can run prysm at 3s slot time on kurtosis with a single parameter change"
- Prysm's approach: just change SECONDS_PER_SLOT in config, client handles it
- This is the "PoC" Nico referenced — not a dedicated branch

## Key Research Links
- terencechain attestation arrival timing: https://hackmd.io/@tchain/att-arrival-timing
- misilva73 attestation analysis for 6s: https://ethresear.ch/t/an-analysis-of-attestation-timings-in-a-6-s-slot/23016
- Slot subdivision spec PR: https://github.com/ethereum/consensus-specs/pull/3510

## Implementation Scope for Lodestar
1. **New fork definition** (EIP7782) — follow focil pattern
2. **Config:** Add all EIP7782 parameters
3. **Clock:** Handle 6s slot duration post-fork
4. **Fork choice:** `compute_slot_at_time` dual-rate calculation
5. **State transition:** Churn limits, sync committee period, base rewards
6. **Timing:** All BPS-based deadlines
7. **Blob schedule:** MAX_BLOBS_PER_BLOCK = 3
8. **Validator client:** Updated duties timing
9. **Network:** Gossip timing adjustments
10. **Kurtosis config:** Custom fork activation

## ⚠️ Key Insight from Nico (2026-02-27 00:51 UTC)
**The hard problem is NOT running at 6s slots — that already works today by setting SECONDS_PER_SLOT=6.**
**The hard problem is changing the slot duration AT RUNTIME at the fork boundary.**

This means:
1. **All timers** (slot tick, epoch tick, scheduled events) must be adjusted mid-run
2. **Cache TTLs** — anything expiring based on "N slots" or "N epochs" implicitly assumes 12s
3. **Hard-coded 12s assumptions** — full codebase audit needed
4. **BPS timing functions** — must switch at fork epoch
5. **`compute_slot_at_time`** — piecewise calculation (12s pre-fork, 6s post-fork)

**Approach:** Systematic audit of all time-dependent code paths in Lodestar.

## Decisions
- **Fork ordering:** EIP-7782 on top of FULU (NOT after Gloas). Nico confirmed (msg 5675).
  - Fork chain: phase0 → altair → bellatrix → capella → deneb → electra → fulu → eip7782
  - Same slot as eip7805 in focil branch pattern

## Open Questions
- What about EL changes (gas limit halving)?
- Full list of hard-coded timing assumptions in the codebase? (audit started: TIMING-AUDIT.md)
