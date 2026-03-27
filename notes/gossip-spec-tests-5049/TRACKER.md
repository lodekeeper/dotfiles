# Gossip spec tests #5049 — Tracker

Last updated: 2026-03-27 10:50 UTC

## Goal
Validate Justin's new bellatrix/capella sync-committee gossip validation vectors from consensus-specs PR #5049 against Lodestar, using `nflaig/sync-committee-gossip-spec-tests` as the base, and determine whether failures (if any) are caused by Lodestar, the local harness, or the vectors.

## Phase Plan
- [x] Task captured in BACKLOG.md
- [x] Set up worktree / fetch vectors
- [x] Run bellatrix/capella vectors
- [x] Triage failures into vector vs harness vs Lodestar
- [~] Report results to Nico in topic #1456

## Completed Work
- Backlog entry created for topic #1456.
- Spawned `gpt-advisor` consult for likely harness pitfalls and triage criteria.
- Used worktree `~/lodestar-sync-committee-gossip-tests` on `feat/sync-committee-gossip-spec-tests` (`nflaig/sync-committee-gossip-spec-tests` base).
- Downloaded Justin's zips from consensus-specs PRs:
  - #5047 bellatrix: `https://github.com/user-attachments/files/26291481/reftests.zip`
  - #5049 capella: `https://github.com/user-attachments/files/26294429/reftests.zip`
- Built Lodestar locally and staged the vector zips under temporary spec-test directories.
- Ran bellatrix networking vectors (minimal + mainnet): 84/86 pass on mainnet, 83/85 pass on minimal; only 2 failures in each preset.
- Bellatrix failing cases are both harness-state issues, not clear Lodestar bugs:
  - `gossip_beacon_block__ignore_parent_consensus_failed_execution_known`
  - `gossip_beacon_block__ignore_parent_execution_verified_invalid`
  The vectors encode parent `payload_status` / failed-known-parent state, but current Lodestar harness does not model that metadata when constructing forkchoice state.
- Added local-only harness support for `gossip_bls_to_execution_change` so capella vectors could run.
- Ran capella BLS-to-execution-change vectors (minimal + mainnet): 5/7 pass in both presets.
- Capella failures split cleanly:
  - `gossip_bls_to_execution_change__ignore_pre_capella` = harness bug. Case `config.yaml` sets `CAPELLA_FORK_EPOCH: 1`, but current Lodestar harness uses `getConfig(fork)` and ignores per-case `config.yaml`, so it treats the message as post-Capella and returns `valid`.
  - `gossip_bls_to_execution_change__reject_not_bls_credentials` = vector bug in consensus-specs PR #5049. In Justin's test, `yield "state", state` happens before mutating the validator withdrawal credentials, so the serialized `state.ssz_snappy` still has BLS credentials while the message/meta expect non-BLS credentials.
- No confirmed Lodestar protocol bug found yet from these later-fork vectors.

## Next Immediate Steps
1. Report the split to Nico: bellatrix = harness limitation; capella = one harness limitation + one vector bug.
2. If needed, turn the local harness adjustments into a clean Lodestar patch so the cases can be rerun end-to-end.
3. Optionally reply upstream (through Nico) with the precise capella vector bug details from `test_gossip_bls_to_execution_change__reject_not_bls_credentials`.

## Interop/Validation Target
- Bellatrix + Capella sync-committee gossip validation vectors from consensus-specs PR #5049.

## Spec Compliance Artifacts
- N/A (test/vector validation task, not a protocol implementation change yet)
