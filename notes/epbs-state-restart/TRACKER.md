# EPBS state restart + finalized API parity — Tracker

Last updated: 2026-03-07 01:27 UTC

## Goal
Fix restart crash (`headState does not exist`) and make Lodestar finalized state behavior match spec/potuz (consensus post-state) + checkpoint-sync parity on epbs-devnet-0.

## Phase Plan
- [x] Phase 0: Research (code paths + potuz guidance + screenshot analysis)
- [x] Phase 1: Spec/architecture draft
- [x] Phase 2: Worktree setup from latest `epbs-devnet-0`
- [x] Phase 3: Implementation
- [x] Phase 4: Quality gate + multi-reviewer pass
- [x] Phase 5: Live-devnet validation + PR + handoff

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

## Outcome Snapshot
- PR: https://github.com/ChainSafe/lodestar/pull/9005
- Latest branch commits:
  - `8cce2b438a` — harden head-state + checkpoint fallback ordering
  - `87a6cd572b` — regression tests for fallback paths
- Validation highlights:
  - live devnet checkpoint sync + restart verified
  - finalized state API bytes parity with checkpoint endpoint verified
  - targeted unit tests for new fallback logic added and passing
- Remaining: Nico review + merge decision

## Interop/Validation Target
- Match Prysm/spec behavior (post-CL consensus state for finalized identifier)
- Checkpoint sync URL: `https://checkpoint-sync.epbs-devnet-0.ethpandaops.io/`
- Ensure sync from checkpoint works and node restart is stable
