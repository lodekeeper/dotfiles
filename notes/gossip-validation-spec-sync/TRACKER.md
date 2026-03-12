# Gossip validation spec sync — Tracker

Last updated: 2026-03-12 22:42 UTC

## Goal
Make Lodestar pass the unreleased phase0 executable gossip validation reftests from consensus-specs PR #4902, then push the fix branch to `lodekeeper/lodestar`.

## Phase Plan
- [x] Scope clarified with Nico
- [x] Initial task spec written
- [x] Fresh Lodestar worktree from `origin/unstable`
- [x] Generate unreleased phase0 gossip reftests from `~/consensus-specs`
- [x] Run Lodestar gossip spec tests against generated fixtures
- [x] Fix harness and validation code
- [x] Quality gate: gossip spec tests green
- [x] Quality gate: `pnpm lint`
- [x] Quality gate: `pnpm check-types`
- [x] Reviewer pass
- [x] Commit + push branch to fork

## Completed Work
- Created worktree: `~/lodestar-gossip-validation` on `feat/gossip-validation-spec-sync`
- Generated unreleased phase0 gossip reftests from consensus-specs PR #4902 (`make test k=gossip reftests=true fork=phase0`)
- Confirmed current released fixtures are missing phase0 networking coverage needed for this validation
- Added networking-only opt-in reftest override in `networking.test.ts` via `LODESTAR_NETWORKING_REFTESTS_DIR`
- Fixed pre-Deneb attestation old-boundary handling in `verifyPropagationSlotRange`
- Added regression unit tests for exact old-boundary / just-past-boundary behavior

## Validation Results
- `LODESTAR_NETWORKING_REFTESTS_DIR=~/consensus-specs/reftests SPEC_FILTER_FORK=phase0 pnpm exec vitest run packages/beacon-node/test/spec/presets/networking.test.ts --project spec-minimal --project spec-mainnet`
  - ✅ 155/155 passed
- `pnpm exec vitest run packages/beacon-node/test/unit/chain/validation/attestation/validateAttestation.test.ts packages/beacon-node/test/unit/chain/validation/aggregateAndProof.test.ts --project unit-minimal --project unit`
  - ✅ 31 passed, 1 skipped
- `pnpm lint`
  - ✅ passed (1 unrelated existing warning in `packages/light-client/test/unit/webEsmBundle.browser.test.ts`)
- `pnpm check-types`
  - ✅ passed

## Current Focus
1. Review the diff with sub-agent(s).
2. Commit with clear repro context.
3. Push branch to `lodekeeper/lodestar`.
4. Report branch + commands back in topic #1456.
