# EPBS state restart + finalized API parity — Tracker

Last updated: 2026-03-06 23:44 UTC

## Goal
Fix restart crash (`headState does not exist`) and make Lodestar finalized state behavior match spec/potuz (consensus post-state) + checkpoint-sync parity on epbs-devnet-0.

## Phase Plan
- [x] Phase 0: Research (code paths + potuz guidance + screenshot analysis)
- [x] Phase 1: Spec/architecture draft
- [x] Phase 2: Worktree setup from latest `epbs-devnet-0`
- [~] Phase 3: Implementation
- [ ] Phase 4: Quality gate + multi-reviewer pass
- [ ] Phase 5: Live-devnet validation, PR, and handoff

## Completed Work
- Worktree: `~/lodestar-epbs-state-restart` from `origin/epbs-devnet-0` (`be0b39f6b7`)
- Implemented initial fixes:
  - `packages/beacon-node/src/chain/chain.ts`
    - use `isParentBlockFull()` to set `anchorPayloadPresent`
    - store anchor state in checkpoint cache with correct payload variant
  - `packages/beacon-node/src/chain/forkChoice/index.ts`
    - replace Gloas anchor `payloadStatus: PENDING` with derived FULL/EMPTY via `isParentBlockFull()`
    - replace fragile post-gloas check with `config.getForkSeq(slot) >= ForkSeq.gloas`
- Local checks pass:
  - `pnpm check-types` ✅
  - `pnpm lint` ✅ (pre-existing warning elsewhere)
  - `pnpm build` ✅

## Next Immediate Steps
1. Run live devnet checkpoint-sync start with bootnodes and this branch build
2. Verify no restart crash (`headState does not exist`) after process restart
3. Compare `/eth/v2/debug/beacon/states/finalized` output vs checkpoint sync endpoint (octet-stream bytes + decoded fields)
4. If mismatch remains, trace API state lookup path and patch explicitly
5. Run reviewer pass (gpt-advisor + codex-reviewer/gemini-reviewer) before PR

## Interop/Validation Target
- Match Prysm/spec behavior (post-CL consensus state for finalized identifier)
- Checkpoint sync URL: `https://checkpoint-sync.epbs-devnet-0.ethpandaops.io/`
- Ensure sync from checkpoint works and node restart is stable
