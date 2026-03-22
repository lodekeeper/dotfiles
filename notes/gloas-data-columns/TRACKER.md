# Gloas Data Columns — Implementation Tracker

## Status: Phase 1 → Phase 2 transition — Starting Implementation
**Created:** 2026-03-22
**Source:** Nico, DM
**Priority:** 🔴 High
**Branch:** `feat/gloas-data-columns` (worktree at `~/lodestar-gloas-data-columns`)
**Base:** `unstable`
**Spec:** `/tmp/spec-gloas-data-columns.md`

## Phase 1: Research & Design ✅
- [x] Scanned all TODO GLOAS (55 found)
- [x] Read PR #8938 diff
- [x] Read Gloas consensus-specs (p2p, beacon-chain, fork-choice, validator)
- [x] Reviewed existing Fulu data column implementation
- [x] Reviewed Gloas SSZ types (DataColumnSidecar, PayloadEnvelopeInput)
- [x] Gap analysis → spec document written
- [x] gpt-advisor architecture review (xhigh thinking)
- [x] Spec refined with reviewer feedback

### Key Architecture Decisions (from gpt-advisor review)
1. **Separate validation functions** — `validateGossipGloasDataColumnSidecar` (not branching in existing)
2. **Block lookup via `chain.getBlockByRoot()`** — not just seenBlockInputCache
3. **Deferred sidecar queue** — columns arriving before block must be queued with peer tracking
4. **Two distinct queues** — sidecar validation queue ≠ payload import completeness
5. **All 3-object arrival orders** — block/sidecar/envelope can arrive in any order
6. **Fork-aware ReqResp types** — response types must use fork context

## Phase 2: Implementation — Core Types & Helpers
- [ ] New error codes (BLOCK_UNKNOWN, SLOT_MISMATCH)
- [ ] `verifyGloasDataColumnSidecar(sidecar, kzgCommitments)` helper
- [ ] Normalized helpers: `getDataColumnSlot()`, `getDataColumnBlockRoot()`
- [ ] Shared `validateSidecarAgainstCommitments()` helper

## Phase 3: Implementation — Deferred Queue & Gossip
- [ ] `DeferredDataColumnQueue` — keyed by (beaconBlockRoot, index), tracks peers
- [ ] Drain queue on block import → validate, re-broadcast / downscore
- [ ] `validateGossipGloasDataColumnSidecar` — separate function
- [ ] Fork-branched gossip handler (deserialization + routing)
- [ ] PayloadEnvelopeInput column integration in gossip handler
- [ ] Column arrival → check PayloadEnvelopeInput → trigger processing

## Phase 4: Implementation — ReqResp & Recovery
- [ ] Fork-aware ReqResp response types for DataColumnsByRoot/ByRange
- [ ] Gloas column recovery variant
- [ ] Update ColumnReconstructionTracker for Gloas
- [ ] SSZ fast-path helpers update (sszBytes.ts)

## Phase 5: Implementation — Integration & API
- [ ] Beacon API Gloas data column serving
- [ ] SSE event schema updates for Gloas columns
- [ ] validateBlockDataColumnSidecars Gloas variant
- [ ] Resolve remaining TODO GLOAS items related to data columns

## Phase 6: Quality Gate
- [ ] pnpm build passes
- [ ] pnpm lint passes
- [ ] pnpm check-types passes
- [ ] Self-review full diff
- [ ] Sub-agent review (lodestar-review skill)
- [ ] Fix all issues

## Phase 7: Push
- [ ] Push to lodekeeper/lodestar fork
- [ ] DO NOT open PR
- [ ] Report completion to Nico
