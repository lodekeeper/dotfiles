# EPBS Alpha.4 Upgrade — Tracker

Last updated: 2026-03-30 20:50 UTC

## Goal
Upgrade Lodestar epbs-devnet-0 branch from consensus-specs v1.7.0-alpha.2 → v1.7.0-alpha.4 (Gloas-only changes). All spec tests must pass. Branch pushed to lodekeeper/lodestar.

## Phase Plan
- [x] Phase 1: Spec & architecture (gpt-advisor) — Option 3: state-canonical + read-through epochCache
- [x] Phase 2: Create worktree from origin/epbs-devnet-0 (at 147d35954e)
- [~] Phase 3: Implementation (Codex CLI) — PTC Window (Phase B) in progress
- [ ] Phase 3b: Alpha.3 core changes (fork choice, block validation, protoArray)
- [ ] Phase 3c: Alpha.4 proposer prefs, attestation rules, fork choice assert
- [ ] Phase 3d: Specrefs & config updates
- [ ] Phase 4: Quality gate (build, lint, spec tests)
- [ ] Phase 5: Push branch to fork

## Completed Work
- Worktree created at ~/lodestar-epbs-devnet-1 from origin/epbs-devnet-0 (147d35954e)
- Build verified clean
- gpt-advisor architecture review completed — key decisions:
  - Option 3 for PTC: state is canonical, epochCache is read-through mirror
  - processPtcWindow runs AFTER processProposerLookahead
  - genesis init needed in util/genesis.ts
  - PartialDataColumnHeader: skip unless tests require
  - compute_balance_weighted_acceptance: minimal touch

## Prior Art (reference only, do NOT cherry-pick blindly)
- `fork/feat/spec-alpha3-upgrade` — alpha.3 upgrade with specrefs, config sync fixes, ethspecify bump
- PR #9047 (closed) — cached PTCs state field (superseded by spec's ptc_window approach)

## Alpha.3 → Alpha.4 Gloas Diff Summary (from consensus-specs)
Seven commits touching `specs/gloas/`:

### 1. PTC Window (PR #4979) — LARGEST CHANGE
- New `ptc_window` field on BeaconState: `Vector[Vector[ValidatorIndex, PTC_SIZE], (2 + MIN_SEED_LOOKAHEAD) * SLOTS_PER_EPOCH]`
- New `compute_ptc(state, slot)` — extracted raw PTC computation (was inline in old `get_ptc`)
- `get_ptc(state, slot)` rewritten to read from cached `ptc_window` instead of computing on-the-fly
- New `process_ptc_window(state)` in epoch processing — shifts window, fills next epoch
- New `initialize_ptc_window(state)` in fork.md — for genesis/fork transition
- `upgrade_to_gloas` calls `initialize_ptc_window(pre)` to set the field
- validator.md: `get_ptc_assignment` epoch bound changed from `next_epoch` to `current_epoch + MIN_SEED_LOOKAHEAD`

### 2. Speed up compute_ptc (PR #5044)
- `compute_balance_weighted_selection` signature change: pre-computes `effective_balances` array outside the loop
- `compute_balance_weighted_acceptance` signature change: takes `effective_balance: Gwei` instead of `(state, index)`
- These are performance optimizations to the functions introduced in alpha.3

### 3. Allow same epoch proposer preferences (PR #5035)
- p2p-interface.md: `proposer_preferences` gossip topic now accepts current OR next epoch (was next-only)
- New IGNORE rule: `preferences.proposal_slot > state.slot` (must be future)
- `is_valid_proposal_slot` rewritten to check both current and next epoch portions of `proposer_lookahead`
- validator.md: `get_upcoming_proposal_slots` includes future slots in current epoch + all next epoch slots

### 4. Request missing payload envelopes for index-1 attestation (PR #4939)
- p2p-interface.md: New REJECT/IGNORE rules for aggregate attestations and subnet attestations with `index == 1`:
  - REJECT if index=1 but execution payload for block fails validation
  - IGNORE when index=1 but execution payload hasn't been seen yet (MAY queue, SHOULD request via ExecutionPayloadEnvelopesByRoot)

### 5. Block known check in on_payload_attestation_message (PR #5022)
- fork-choice.md: Added `assert data.beacon_block_root in store.block_states` before accessing `store.block_states[data.beacon_block_root]`

### 6. Fix block_root field in ExecutionPayloadEnvelopesByRoot (PR #5008)
- Likely a field rename fix — need to check if this affects our reqresp types

### 7. Partial data column header changes
- New `PartialDataColumnHeader` container modified for Gloas (removed signed_block_header, kzg_commitments_inclusion_proof; added slot, beacon_block_root)
- Partial message validation rules on `data_column_sidecar_{subnet_id}` — Gloas-specific changes

## Alpha.2 → Alpha.3 Changes (already in fork/feat/spec-alpha3-upgrade)
The alpha.3 work already covers the alpha.2→3 delta. Key items:
- Config/preset changes
- Specref updates
- Various function signature changes
- Test vector bump to alpha.3

## Implementation Strategy
1. Start from latest `origin/epbs-devnet-0` (currently at `147d35954e`)
2. Apply alpha.3 changes (can reference/cherry-pick from existing alpha.3 branch)
3. Apply alpha.4 changes on top
4. Bump spec test version to v1.7.0-alpha.4
5. Run full spec test suite, fix failures

## Key Files to Modify (expected)
- `packages/state-transition/src/util/gloas.ts` — compute_ptc, compute_balance_weighted_acceptance
- `packages/state-transition/src/epoch/processEpoch.ts` — add process_ptc_window
- `packages/state-transition/src/slot/upgradeStateToGloas.ts` — initialize_ptc_window
- `packages/types/src/gloas/` — BeaconState ptc_window field, PartialDataColumnHeader
- `packages/params/` — any new constants
- `packages/fork-choice/` — block_states assert
- `packages/beacon-node/src/network/processor/` — p2p validation changes
- `packages/beacon-node/src/api/` — proposer preferences validation
- `packages/beacon-node/test/spec/specTestVersioning.ts` — bump to alpha.4
- `specrefs/` — update function/container references

## Next Immediate Steps
1. Send spec to gpt-advisor for architecture review
2. Create worktree
3. Begin implementation
