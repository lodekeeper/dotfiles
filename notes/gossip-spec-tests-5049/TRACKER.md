# Gossip spec tests #5049 — Tracker

Last updated: 2026-03-27 10:50 UTC

## Goal
Validate Justin's new bellatrix/capella sync-committee gossip validation vectors from consensus-specs PR #5049 against Lodestar, using `nflaig/sync-committee-gossip-spec-tests` as the base, and determine whether failures (if any) are caused by Lodestar, the local harness, or the vectors.

## Phase Plan
- [x] Task captured in BACKLOG.md
- [x] Set up worktree / fetch vectors
- [x] Run bellatrix/capella vectors
- [x] Triage failures into vector vs harness vs Lodestar
- [x] Patch Lodestar harness / minimal validator logic for later-fork gossip cases
- [~] Report results to Nico in topic #1456

## Completed Work
- Backlog entry created for topic #1456.
- Spawned `gpt-advisor` consult for likely harness pitfalls and triage criteria.
- Used worktree `~/lodestar-sync-committee-gossip-tests` on branch `fix/later-fork-gossip-harness`, based on `feat/sync-committee-gossip-spec-tests` (`nflaig/sync-committee-gossip-spec-tests` base).
- Downloaded Justin's zips from consensus-specs PRs:
  - #5033 altair: `https://github.com/user-attachments/files/26214837/reftests.zip`
  - #5047 bellatrix: `https://github.com/user-attachments/files/26291481/reftests.zip`
  - #5049 capella: `https://github.com/user-attachments/files/26294429/reftests.zip`
- Re-downloaded clean beacon-node spec tests for alpha.2, then overlaid only the fork/topic directories relevant to the Justin PRs:
  - altair `gossip_sync_committee_message`
  - altair `gossip_sync_committee_contribution_and_proof`
  - bellatrix `gossip_beacon_block`
  - capella `gossip_bls_to_execution_change`
- Patched Lodestar gossip spec harness in `packages/beacon-node/test/spec/utils/gossipValidation.ts` to:
  - load and merge per-case `config.yaml` with `getConfig(fork)` while preserving hex fork-version fields
  - support `gossip_bls_to_execution_change`
  - model failed/invalidated setup blocks using forkchoice metadata instead of plain block import
  - simulate pre-Capella topic absence by ignoring BLS-to-execution-change messages before the configured fork slot
- Patched Lodestar block validation in `packages/beacon-node/src/chain/validation/block.ts` to ignore gossip blocks whose known parent already has `ExecutionStatus.Invalid`.
- Current rerun results after harness patch:
  - **spec-minimal:** 79/80 passed, only `capella/networking/gossip_bls_to_execution_change__reject_not_bls_credentials` still failing
  - **spec-mainnet:** 80/81 passed, only `capella/networking/gossip_bls_to_execution_change__reject_not_bls_credentials` still failing
- Bellatrix is now fully green on both presets after the harness + minimal Lodestar patch.
- Altair sync-committee vectors are green on both presets.
- Remaining capella failure still looks like a **spec-vector bug** in consensus-specs PR #5049: Justin's Python test yields `state` before mutating the validator withdrawal credentials, so `state.ssz_snappy` still contains BLS credentials while the expected result assumes non-BLS credentials.

## Next Immediate Steps
1. Report the split to Nico: bellatrix = harness limitation; capella = one harness limitation + one vector bug.
2. If needed, turn the local harness adjustments into a clean Lodestar patch so the cases can be rerun end-to-end.
3. Optionally reply upstream (through Nico) with the precise capella vector bug details from `test_gossip_bls_to_execution_change__reject_not_bls_credentials`.

## Interop/Validation Target
- Bellatrix + Capella sync-committee gossip validation vectors from consensus-specs PR #5049.

## Spec Compliance Artifacts
- N/A (test/vector validation task, not a protocol implementation change yet)
