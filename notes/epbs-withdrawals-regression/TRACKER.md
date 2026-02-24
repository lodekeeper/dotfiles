# EPBS Withdrawals Regression — Tracker

Last updated: 2026-02-24 15:35 UTC

## Goal
Fix `produceBlockV4` withdrawals mismatch on `epbs-devnet-0` and pass strict Kurtosis criteria (no missed blocks, no peering issues, no unhealthy errors).

## Phase Plan
- [x] Reproduce with Nico config (4-node 2×LH + 2×LS + assertoor)
- [x] Root cause analysis in code path (`prepareExecutionPayload` cache vs FULL-parent production state)
- [x] Patch implementation
- [ ] Kurtosis strict validation (full run with assertoor through slot 34+ and post-fork stability)
- [ ] Sub-agent review (gpt-advisor + reviewer pass)
- [ ] Push branch + report to Nico

## Completed Work
- `e8d1f2bd32` — bypass payloadId cache in Gloas block production path so EL always receives fresh FCU with withdrawals computed from FULL-parent state.

## Root Cause Summary
`prepareNextSlot` prepares payload from PENDING parent state and caches payloadId (withdrawals W1).
`produceBlockWrapper` later upgrades parent to FULL; `computeNewStateRoot` computes expected withdrawals from FULL state (W2).
`getPayload` returns cached payload built with W1, but envelope validation compares against W2 -> withdrawals mismatch.

## Next Immediate Steps
1. Run Kurtosis repro with fixed image `lodestar:epbs-withdrawals-fix`
2. Verify zero `Withdrawals mismatch`, zero `produceBlockV4 error`, healthy peers/finality
3. Run sub-agent architecture sanity check on patch
4. If pass: push and report concise status to Nico

## Interop/Validation Target
- 4-node config from Nico msg 4748
- Through Gloas transition and assertoor BLS-changes + builder-deposit tests
- No missed blocks, no peering issues, no unhealthy error logs
