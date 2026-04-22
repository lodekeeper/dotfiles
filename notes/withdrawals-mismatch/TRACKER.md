# withdrawals-mismatch — Tracker

Last updated: 2026-04-22 03:48 UTC

## Status: INVALIDATED (2026-04-22)
The real v1.42.0 "Withdrawal mismatch at index=0" regression is fixed by PR #9246 (loadState cache aliasing — `clone()` → `clone(true)`), approved and pending merge. Do not open follow-up PRs from this tracker.

The overnight heartbeat chain (`861864a327` → `d0139e5fda`) mis-identified the documented `stateRoot: ZERO_HASH` placeholder in `getExecutionPayloadEnvelope()` as a bug. That field is intentional scaffolding scheduled for removal under deferred-payload-processing (see TODO at `packages/beacon-node/src/api/impl/validator/index.ts:1652-1654`). The proposed fix runs counter to the planned spec direction and must not be pushed.

## Goal (historical)
Either reproduce the original withdrawals mismatch in a higher-level runtime scenario, or falsify the remaining hypothesis by showing the runtime parent-selection / payload-extension bundle stays coherent under realistic Gloas flow.

## Phase Plan
- [x] Pin envelope validation/import/API/gossip seams
- [x] Pin producer-side withdrawal-source branch
- [x] Pin direct `shouldExtendPayload()` decision table
- [x] Pin prepare-next-slot root bridge
- [x] Pin integrated producer path (`produceBlockBody.call(...)`)
- [x] Pin validator API V4 proposer-head bridge
- [x] Design runtime reproducer / instrumentation path
- [x] Implement runtime reproducer / instrumentation harness
- [x] Run and interpret reproducer
- [x] Identify source-side zero-root bug
- [x] Validate accepted local fix with deterministic acceptance e2e

## Completed Work
- `60334a4735` — payload envelope state provenance
- `af0e057a3d` — payload envelope api handoff
- `a7978190ab` — payload envelope gossip handoff
- `ca98e54aba` — payload attribute withdrawal source
- `25f10d5709` — shouldExtendPayload decision boundary
- `2a1987b1b5` — prepare-next-slot payload extension root
- `2cfb08cd88` — gloas producer withdrawal source
- `48fc407474` — gloas validator api parent source
- `861864a327` — reproduce gloas runtime payload error
- `4d30422f23` — classify gloas runtime payload error
- `8ad0f6a4cf` — capture gloas envelope state root mismatch
- `c0b2adbfef` — pin zero stateRoot in gloas envelope
- `20d044533d` — fix: use cached stateRoot in gloas envelope
- `d0139e5fda` — fix: compute envelope stateRoot from postState

## Current Conclusion
The local logic stack is heavily boxed in:
- envelope validation/import provenance looks correct
- API/gossip handoff looks correct
- producer withdrawal-source branching is intentional
- `shouldExtendPayload()` semantics are pinned
- scheduler root selection is pinned
- producer-path EL call shape is pinned
- validator API parent sourcing is pinned

Runtime work established:
- produced envelope `stateRoot` matched the mismatch `expected` root
- that root was initially zero because `getExecutionPayloadEnvelope()` hardcoded `ZERO_HASH`
- a first source-side fix to use the cached full-block state root changed the mismatch but did not solve it
- the accepted local fix is to derive the cached envelope root from the real `postState` returned by `computeNewStateRoot()`

## Accepted Local Fix
Commit: `d0139e5fda` — `fix: compute envelope stateRoot from postState`

Shape:
- extend cached post-Gloas produce result with `envelopeStateRoot`
- derive `envelopeStateRoot` from `processExecutionPayloadEnvelope(postState, signedEnvelope, {verifySignature:false, verifyStateRoot:false})`
- return that cached envelope-specific root from `getExecutionPayloadEnvelope()`

## Validation
Source-side unit:
- `packages/beacon-node/test/unit/api/impl/validator/getExecutionPayloadEnvelope.test.ts`
- passes

Deterministic acceptance e2e:
- `packages/beacon-node/test/e2e/chain/gloasEnvelopeSelfBuildImport.test.ts`
- passes

Acceptance flow:
1. produce Gloas block directly through validator API
2. import block into forkchoice
3. fetch self-build envelope
4. call `chain.processExecutionPayload(..., {validSignature:true})`
5. result: succeeds without the old state-transition mismatch

## Why this is the right fix
- the original runtime failure was a state-root mismatch on envelope import
- the produced/published envelope root was initially zero
- the zero came from validator API construction (`ZERO_HASH`)
- using the full block post-state root was still semantically wrong
- the correct source is the envelope-specific post-state reached from the real `postState` returned by full block production

## Candidate Runtime Surfaces
1. `packages/beacon-node/test/e2e/chain/proposerBoostReorg.test.ts`-style dev-node flow using `getDevBeaconNode()` + `getAndInitDevValidators()` + custom fork-choice constructor
2. `packages/beacon-node/test/sim/*` with `runEL()` + real `notifyForkchoiceUpdate()` / `getPayload()`
3. direct API-driven single-node deterministic import path (now used by `gloasEnvelopeSelfBuildImport.test.ts`)

## Next Immediate Steps
1. Decide whether to open a PR from the clean cherry-picked branch/worktree.
2. If opening a PR, summarize the root-cause chain clearly:
   - zero-root bug
   - full-block-root was insufficient
   - postState-derived envelope root is the accepted fix.
3. Optionally prune or retain superseded repro-only runtime tests depending on review preference.

## Safe PR Move Plan
Recommended minimal cherry-pick payload: commit `d0139e5fda` only.

Files in that commit:
- `packages/beacon-node/src/api/impl/validator/index.ts`
- `packages/beacon-node/src/chain/chain.ts`
- `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts`
- `packages/beacon-node/test/e2e/chain/gloasEnvelopeSelfBuildImport.test.ts`
- `packages/beacon-node/test/unit/api/impl/validator/getExecutionPayloadEnvelope.test.ts`

Rationale:
- includes the accepted production fix
- includes one focused source-side unit
- includes one deterministic acceptance e2e
- avoids dragging the whole proof stack / exploratory repro commits into the PR unless explicitly wanted

## Clean Move Result
- New worktree: `~/lodestar-gloas-envelope-state-root`
- New branch: `fix/gloas-envelope-state-root`
- Cherry-picked only: `d0139e5fda`
- Focused validation on the new branch:
  - source-side unit passed
  - deterministic acceptance e2e passed
- Result: minimal PR candidate is now real, isolated, and green

## Interop/Validation Target
- Source-side unit remains green.
- Deterministic acceptance e2e remains green.
- No drift in the previously committed runtime repro stack.

## Spec Compliance Artifacts
- N/A (debugging / implementation fix; spec-facing behavior was diagnosed through tests rather than changed in spec text here)
