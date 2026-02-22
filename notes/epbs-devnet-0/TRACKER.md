# EPBS Devnet-0 — Tracker

Last updated: 2026-02-21 16:30 UTC

## Goal
Implement missing code for EPBS devnet-0 in Lodestar. Must interop with Lighthouse + Geth on local Kurtosis devnet.

## Phase Plan
- [x] Phase 0: Research (Lighthouse, beacon-APIs, consensus specs, existing TODO GLOAS)
- [x] Phase 1: Spec & architecture (with gpt-advisor)
- [x] Phase A: BlockInput for Gloas (seenGossipBlockInput + types)
- [x] Phase B: Envelope import pipeline (gossip → validate → STF → EL → fork choice → DB)
- [x] Phase C: APIs & Events (all beacon-APIs PR #552 endpoints)
- [x] Phase D: Block production completion (payload attestations in block body, block production log fix)
- [x] Phase E: Validator client changes (getExecutionPayloadEnvelope already implemented)
- [x] Phase F: Quality gate (build passes, lint passes)
- [x] Phase G: Kurtosis devnet testing (Lodestar + Lighthouse + Geth)
- [x] Phase H: PR against nflaig/epbs-devnet-0 → PR #8941

## Base Branch
`nflaig/epbs-devnet-0` on ChainSafe/lodestar (commit 77e772f1b2)

## Completed Work
- ✅ Research completed and documented in `RESEARCH.md`
- ✅ Worktree created at `~/lodestar-epbs-devnet-0` from `origin/nflaig/epbs-devnet-0`
- ✅ Phase A: `seenGossipBlockInput` now imports post-Gloas blocks as `BlockInputPreData` (removed "Not implemented")
- ✅ Phase B (core wiring): Added `chain.importExecutionPayloadEnvelope()` and wired it into gossip + API publish path
- ✅ Added new SSE event types in API routes: `execution_payload_available`, `execution_payload_bid`
- ✅ Phase C: GET `/eth/v1/beacon/execution_payload_envelope/{block_id}` (from DB) + GET `/eth/v1/validator/execution_payload_envelope/{slot}/{beacon_block_root}` (from production cache)
- ✅ Phase D: Block body includes payloadAttestations from pool; logging updated for Gloas
- ✅ Phase E: Validator `getExecutionPayloadEnvelope` endpoint already implemented by Nico
- ✅ `@lodestar/api` and `@lodestar/beacon-node` builds pass
- ✅ Pushed 2 commits to fork (02ce0988bc, e2c09807dc)
- ✅ Root-caused post-Gloas stall at slot ~49: FCU used stale execution head hash from PENDING variant (`Ignoring beacon update to old head` in Geth logs)
- ✅ Implemented code fix:
  - Added `forkChoice.getHeadExecutionBlockHash()` (prefers FULL variant hash when available)
  - Patched helper to handle BOTH Gloas `PENDING` and `EMPTY` variants (EMPTY also carries parent/stale hash)
  - Switched FCU callers (`importBlock`, `prepareNextSlot`, `produceBlockBody`) to use resolved head hash
  - Added FCU push after `importExecutionPayloadEnvelope()`
- ✅ Local `pnpm build` passes
- ✅ Rebuilt Docker image `lodestar:epbs-devnet-0-local` with updated fix
- ✅ Fresh Kurtosis rerun confirms progress past prior boundary, but new stall reproduces later
- ✅ Additional fix: `protoArray.getBlockHexAndBlockHash()` now matches Gloas EMPTY/PENDING by `blockHashFromBid` (not only `executionPayloadBlockHash`)
- ✅ Kurtosis rerun impact: Lodestar now imports through slot 33 (previously stalled at 32)
- ⚠️ New observed pattern (current blocker):
  - Lodestar locally produces slot 33 and publishes envelope, then fails to import Lighthouse branch from slot 34 onward.
  - Post-slot-33 gossip blocks are dropped as `PARENT_UNKNOWN` with `parentInForkChoice=false` (diagnostic added in `validateGossipBlock`).
  - Proposer path repeatedly fails with `Parent block hash ... does not match state's latest block hash` (state still at slot-31 EL hash).
- ✅ Additional diagnostics + fixes applied:
  - Added targeted `PARENT_UNKNOWN` diagnostic logging in `packages/beacon-node/src/chain/validation/block.ts`.
  - Patched gossip handler (`packages/beacon-node/src/network/processor/gossipHandlers.ts`) to always create `blockInput` and emit `unknownParent` on `PARENT_UNKNOWN` (previously skipped when `blockInput` uninitialized).
  - Confirmed unknown-parent sync is now triggered via metrics (`unknown_parent` counter increases), but stall still persists.
- ✅ Captured concrete unknown-parent import failure with nested cause:
  - `UnknownBlockSync processBlock failed slot=34 ... errCode=BLOCK_ERROR_BEACON_CHAIN_ERROR`
  - Nested: `Parent block hash ... of bid does not match state's latest block hash ...`
  - Confirms slot-34+ imports fail for same stale `state.latestBlockHash` consistency check.
- ✅ Additional experiments completed:
  - Added deferred envelope retry worker (`scheduleDeferredEnvelopeImport`) that re-triggers `unknownBlockRoot` and retries import.
  - Relaxed `processExecutionPayloadBid` parent-hash check to accept either `state.latestBlockHash` or `state.latestExecutionPayloadBid.blockHash`.
- ✅ Latest rerun outcome after fixes:
  - Fixed deferred envelope validation for self-build (`BUILDER_INDEX_SELF_BUILD`) to avoid invalid builder-index lookup (`LeafNode has no left node`).
  - Kept deferred envelope retry worker + unknownBlockRoot retrigger in gossip handler.
  - Kept parent-hash relaxation in `processExecutionPayloadBid` (accept `latestBlockHash` OR `latestExecutionPayloadBid.blockHash`).
  - Kurtosis now progresses well past prior failure point (observed synced progression past slot 80 across LH + Lodestar validator + Lodestar observer).
  - No occurrences in latest run of:
    - `Gloas gossip block PARENT_UNKNOWN diagnostic`
    - `UnknownBlockSync processBlock failed`
    - `Failed importing deferred execution payload envelope`

## Current Phase: Pipeline Refactor
- **Task**: Replace hacky `scheduleDeferredEnvelopeImport` retry with proper separated pipeline
- **Design** (Nico comment #2836133600):
  - `SeenPayloadEnvelopeCache[blockRoot] → PayloadEnvelopeInput`
  - `PayloadEnvelopeInput.createFromBid(bid)` — only creation path
  - No retry loops — event-driven data flow
- **Status**: Phase 1 spec drafted, gpt-advisor reviewing architecture
- **Spec**: `/tmp/spec-epbs-pipeline-refactor.md`

## PR
- **PR #8941**: https://github.com/ChainSafe/lodestar/pull/8941
- Latest commits: `dfa9f0d` (remove VC retry) ← `20da48344d` (soak fix) ← `dc71710bfc` (fork-choice reconciliation)
- Opened 2026-02-21, awaiting Nico's review + pipeline refactor

## Key Files
- Research: `notes/epbs-devnet-0/RESEARCH.md`
- Spec: `/tmp/spec-epbs-devnet-0.md` (after Phase 1)

## Interop/Validation Target
- Local Kurtosis devnet: Lodestar + Lighthouse + Geth
- Blocks produced and imported successfully
- Execution payload envelopes flowing between clients
- Chain finalizing

## Update (2026-02-21 17:21 UTC)
- Refactor regression fix validated end-to-end.
- Applied patch in `processExecutionPayloadBid.ts`:
  - accept parent hash against `state.latestBlockHash` OR `state.latestExecutionPayloadBid.blockHash` to cover late-envelope sync path.
- Rebuilt no-cache image `lodestar:epbs-devnet-0-local` (`sha256:3973867cd371...`) and launched fresh enclave `a6a8891548c2`.
- Soak monitor (slot 40→136) results:
  - `BLOCK_ERROR_INVALID_STATE_ROOT`: `0/0`
  - `UnknownBlockSync processBlock failed`: `0/0`
  - `publishBlockV2 error`: `0`
  - `payloadId=null`: `0`
  - finality recovered: `finalized=2`, `current_justified=3` by slot ~131.
- Hardening follow-up applied:
  - tightened fallback guard to conditional `parentIsFull` branch in `processExecutionPayloadBid`.
  - local validation after hardening: lint + state-transition build + beacon-node check-types ✅
- Committed and pushed hardening patch: `e7078d918b`.
- Confirmation soak PASSED (enclave `d28c74923897`, commit `e7078d918b`):
  - 20 samples over 10 min (slot 41→132)
  - ISR=0/0, UnknownBlockSync=0/0, publishBlock=0, payloadId=0
  - Finality: `finalized=2` by slot ~130
- **ACCEPTANCE CRITERIA MET (6s soak runs):** zero error logs, stable peers, finalizing network.
- Nico requested one additional final pass at 12s slots with 50/50 LH/LS + debug-log verification.
- Attempted 3×LH + 3×LS topology three times; each run failed during startup with Kurtosis/Docker resource race (`service has Docker resources but not a container`).
- Switched to lean 50/50 topology for reliability: 2×LH + 2×LS, 12s slots, debug logs (`epbs-devnet-0-final-soak-12s-50-50.yaml`).
