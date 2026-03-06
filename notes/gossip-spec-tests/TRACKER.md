# Gossip Validation Spec Tests — Tracker

Last updated: 2026-02-26 23:35 UTC

## Goal
All 74 gossip validation spec tests from consensus-specs PR #4902 integrated and passing in Lodestar.

## Phase Plan
- [x] Phase 0: Research (spec PR, Teku reference, Lodestar architecture)
- [x] Phase 0.5: Fixture generation (74 tests generated from PR branch)
- [~] Phase 1: Spec & architecture design (spec written, advisor reviewing)
- [ ] Phase 2: Worktree setup (~/lodestar-gossip-tests created)
- [ ] Phase 3: Implementation (Codex CLI in worktree)
- [ ] Phase 4: Quality gate (review, fix failures)
- [ ] Phase 5: Push to fork

## Completed Work
- Research notes: `notes/gossip-spec-tests/RESEARCH.md`
- Spec: `/tmp/spec-gossip-validation-tests.md`
- Task file: `~/lodestar-gossip-tests/TASK.md`
- Fixtures: generated from consensus-specs executable-networking-specs branch, copied to spec-tests dir
- Worktree: `~/lodestar-gossip-tests` on branch `feat/gossip-validation-tests`

## Key Findings
- 74 tests across 6 topics (block:12, aggregate:19, attestation:14, proposer_slashing:9, attester_slashing:12, voluntary_exit:8)
- Teku skips 7 tests (checks done outside gossip validation)
- Fork choice test runner is the closest pattern — bootstraps real BeaconChain
- Fixtures format: meta.yaml + state.ssz_snappy + message files

## Current Status (latest run)
- Typecheck: ✅
- Result: **64 passed / 10 failed** (total 74)
- Fixes applied:
  - ✅ Skip genesis block import (slot=0 → anchor state already has it)
  - ✅ Custom GossipTestClock with ms-aware gossip disparity
  - ✅ opPool insert after valid proposer_slashing/attester_slashing/voluntary_exit (seen-cache)
  - ✅ maxSkipSlots: undefined (non-spec check)
  - ✅ Map raw TypeError/Error to "reject" (e.g., validator index out of range)
- Remaining 10 failures to investigate:
  - finalized checkpoint semantics not yet wired (block/attestation/aggregate "finalized_not_ancestor" class)
  - failed-block semantics (`reject_parent_failed_validation`, `reject_block_failed_validation`) differ from Lodestar behavior
  - one attester slashing case (`reject_no_slashable_validators`) indicates missing spec check in Lodestar gossip validation
  - one block pre-import chain state issue (`reject_slot_not_higher_than_parent`) during fixture block import

## Next Immediate Steps
1. Fix bootstrap/import flow so fixture blocks import without genesis-block sanity failure
2. Implement finalized checkpoint + seen-cache seeding from fixture/meta semantics
3. Align attestation and aggregate pipeline with gossip handler context
4. Add justified skips only where Lodestar checks occur outside gossip validation
5. Re-run 74 tests, iterate to green

## Files Changed
- `packages/beacon-node/test/spec/presets/networking.test.ts` (modified)
- `packages/beacon-node/test/spec/utils/gossipValidation.ts` (new)
