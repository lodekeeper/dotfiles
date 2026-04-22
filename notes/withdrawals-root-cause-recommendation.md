# Withdrawals mismatch root-cause recommendation

_Last updated: 2026-04-22 12:44 UTC_

## Current recommendation

Treat the leading explanation as **parent-payload-status / parent-hash semantics**, not generic `loadState()` cache contamination.

The safest minimal direction is:
1. keep the Gloas parent-hash decision keyed off `forkChoice.shouldExtendPayload(...)`
2. when extending `latestExecutionPayloadBid.blockHash`, use fresh `getExpectedWithdrawals()`
3. when building on `latestExecutionPayloadBid.parentBlockHash`, preserve stale `state.payloadExpectedWithdrawals`
4. add focused regression coverage around both hot paths that duplicate this decision

## Why this is the best current explanation

The earlier cache-poisoning theory weakened materially under direct source review:
- `TreeViewDU.clone()` cache transfer does not leave the seed and clone sharing the same top-level cache arrays afterward
- existing `loadCachedBeaconState()` tests already cover generic validator-cache reuse reasonably well
- a targeted local regression draft against `loadState()` seed-cache poisoning reportedly passes on current code
- the observed bug shape is matched more directly by recent Gloas parent-payload semantics changes than by a broad stale-cache story

The strongest current code anchor is Nico's `9fa9f08` change (`fix: use fork choice for parent payload status in block production (#9209)`), which explicitly moved Gloas block production away from `is_parent_block_full` and onto fork-choice-selected payload ancestry.

## Evidence captured so far

### Focused tests now present in `~/lodestar`
- `packages/beacon-node/test/unit/chain/produceBlock/getPayloadAttributesForSSE.test.ts`
  - proves: extending `latestExecutionPayloadBid.blockHash` uses fresh `getExpectedWithdrawals()`
  - proves: selecting `latestExecutionPayloadBid.parentBlockHash` preserves stale `payloadExpectedWithdrawals`
- `packages/beacon-node/test/unit/chain/prepareNextSlot.test.ts`
  - proves duplicated parent-hash selection logic in `prepareNextSlot`
  - `shouldExtendPayload(...) = true` -> use `latestExecutionPayloadBid.blockHash`
  - `shouldExtendPayload(...) = false` -> use `latestExecutionPayloadBid.parentBlockHash`

## What not to do first

Do **not** resurrect a broad `clone(true)` / deserialize-everything isolation patch as the first response.

That path:
- has weaker evidence now
- risks reintroducing known memory/perf regressions
- is a worse first proving experiment than the targeted semantics/unit-coverage path

## Important scoping update

The local patch at `aef726e58b` (`fix: align SSE parent root with predicted proposer head`) still looks like a **real latent bug / follow-up candidate**, but it should no longer be treated as the accepted fix for the original `#9209` withdrawals mismatch.

Live PR-thread review clarified the current maintainer intent:
- keep `parentBlockRoot: headRoot` semantics in `#9209`
- avoid changing SSE root semantics in that PR
- treat the `{prepareState: updatedPrepareState, parentBlockRoot: headRoot}` inconsistency as a **separate unstable follow-up question**

So the best current framing is:
- the narrow `updatedHeadRoot` / `parentBeaconBlockRoot` patch likely uncovered a **neighboring scheduler/SSE inconsistency**
- the original withdrawals mismatch is **still not fully explained** by that patch alone
- broad `loadState()` / cache-poisoning remains deprioritized unless a fresh reproducer points back there

## Live `#9209` thread boundary (refresh from 2026-04-21 heartbeat)

A fresh pass over the full PR comment history is useful because multiple bug candidates got mixed together in the same review window.

### What looks accepted / converged
- **Anchor / mock-EL seeding should follow `latestBlockHash`, not `latestExecutionPayloadBid.blockHash`**.
  - The early Codex suggestion to seed from `bid.blockHash` was corrected in-thread.
  - The converged explanation is that `latestBlockHash` is the invariant-correct current EL head in both cases:
    - envelope already applied -> `latestBlockHash == bid.blockHash`
    - envelope not yet applied -> `latestBlockHash == bid.parentBlockHash`
- **Cross-fork helper cleanup is a separate follow-up**, not something to force through this PR.
  - Nico pushed back on putting `latestBlockHash` behind a cross-fork base-class helper.
  - The agreed direction was a later `BeaconStateViewGloas`-style cleanup / caller-side narrowing follow-up.

### What was explicitly *not* accepted in `#9209`
- **`updatePreComputedCheckpoint(updatedHeadRoot, nextEpoch)`** was walked back.
  - After revisiting the epoch-boundary proposer-boost logic, the conclusion in-thread was that `updatedHeadRoot === headRoot` at that callsite, so the change is functionally a no-op and misleading in this PR.
- **The SSE `parentBlockRoot: fromHex(updatedHeadRoot)` change** was also kept out of `#9209`.
  - The current PR-scoping decision is to keep `parentBlockRoot: headRoot` byte-identical to unstable for now, even if the emitted `{prepareState, parentBlockRoot}` pair may represent a separate latent inconsistency worth fixing later.

### Practical implication for the investigation
When reconstructing the original withdrawals mismatch, do **not** treat every locally plausible fix from that review burst as part of the accepted root-cause story. The current safe split is:
- `latestBlockHash` anchor/mock-EL seeding = likely real/mainline direction
- `updatedHeadRoot` checkpoint/SSE tweaks = separate latent-bug bucket
- original withdrawals mismatch = still needs reproducer-backed explanation beyond the scheduler-side follow-up patch

## State-transition validation seam is now pinned too

The previously missing state-transition-side coverage is now present in `~/lodestar`:
- `packages/state-transition/test/unit/block/processExecutionPayloadEnvelope.test.ts`
  - proves a payload is accepted when `payload.withdrawals` matches `state.payloadExpectedWithdrawals`
  - proves the exact runtime error is thrown when the withdrawals root diverges: `Withdrawals mismatch between payload and expected withdrawals ...`

That matters because `processExecutionPayloadEnvelope()` is the pure validation seam where the mismatch is actually enforced:
- `payloadWithdrawalsRoot = hashTreeRoot(payload.withdrawals)`
- `expectedWithdrawalsRoot = state.payloadExpectedWithdrawals.hashTreeRoot()`
- mismatch => immediate throw

So the scheduler-side and state-transition-side contracts are both now directly covered in focused local tests.

## Higher-level production proof is now present too

The investigation is no longer resting only on tiny scheduler seams.

A new focused regression in:
- `packages/beacon-node/test/unit/api/impl/validator/produceBlockV3.test.ts`

now proves the higher-level production behavior directly:
- it drives the real `produceBlockBody()` path
- it forces the **Gloas empty-parent** branch
- it shows `executionEngine.notifyForkchoiceUpdate(...)` takes the **`getPayloadExpectedWithdrawals()` branch**, not the fresh `getExpectedWithdrawals()` branch, in a forced Gloas empty-parent setup

Important nuance:
- this proof currently uses a valid cached **Electra** state as the base fixture and layers the minimal Gloas-only view behavior needed for the branch under test
- that is acceptable for the proving goal here, because the target question is the production-side withdrawals-source selection at the FCU seam
- local follow-up confirmed there is currently **no reusable cached Gloas/Fulu fixture helper** in the test tree to swap in cleanly, so the Electra-base approach is not just expedient — it is the least awkward house-style option available right now
- it means the generic reusable Fulu/Gloas cached-state fixture problem is still unsolved, but it is no longer blocking the main explanatory proof

Practical consequence:
- the leading explanation is now supported at three levels, with an important scope caveat on the top layer:
  1. scheduler-side branch tests (`prepareNextSlot`, `getPayloadAttributesForSSE`)
  2. state-transition-side envelope validation tests (`processExecutionPayloadEnvelope`)
  3. a higher-level production-path regression (`produceBlockV3` / `produceBlockBody`) that currently proves **method/branch selection** at the FCU seam, but not yet full real-Gloas stale-field provenance because `getPayloadExpectedWithdrawals()` is mocked
- that still makes broad `loadState()` cache-poisoning rollback work a worse first move unless a fresh reproducer contradicts this stack

## Next good step

Current state:
- the new `produceBlockV3` regression is lint-clean, unit-green, and now checkpointed locally in `~/lodestar-gloas-withdrawals`
- the original proof commit is `45649c5c4f`, and a wording-tightening follow-up commit `52404aff3f` narrows the test name to the honest method-selection claim (`uses getPayloadExpectedWithdrawals() for Gloas empty-parent payload attributes`)
- there is currently **no live PR attachment** for these proof commits from this worktree: `feat/gloas-withdrawals` has no configured upstream here, and the historical fork PR `lodekeeper/lodestar#15` is already closed
- Codex review still stands: keep describing this as a **branch-selection proof**, not full real-Gloas stale-field provenance

If more work is needed, keep it narrow:
- preserve the focused regression tests that now pin the scheduler-side parent-hash / withdrawals-source behavior, the state-transition-side withdrawals-root validation, **and** the production-path FCU withdrawals-source handoff
- treat `aef726e58b` as a possible tiny follow-up PR, not the mainline `#9209` resolution
- package the current conclusion around the focused Electra-base `produceBlockV3` proof rather than pretending the generic Gloas cached-state fixture is already solved
- recover or rebuild the **current unstable reproducer path** for the original mismatch before making broader code changes
- if reproduction still fails after the current semantics are pinned, instrument the runtime path around the actual parent-status / ancestry inputs rather than jumping back to broad cache-isolation work
- only reopen the cache-isolation branch if a fresh runtime reproduction survives the parent-semantics explanation and the new envelope-validation + production-path coverage

## Review update (Codex CLI fallback, 2026-04-22)

A local Codex CLI review of the `produceBlockV3` diff rated it **mixed**:
- valid for proving the empty-parent branch picks `getPayloadExpectedWithdrawals()` over `getExpectedWithdrawals()`
- not strong enough to claim full real-Gloas `state.payloadExpectedWithdrawals` provenance, because the test currently mocks both methods and patches Gloas-only state accessors onto an Electra-backed `BeaconStateView`

Practical read: the test is still worth keeping as a higher-level branch-selection proof, but handoff/PR language must not oversell it. If stronger provenance proof becomes necessary, the best next improvement is a minimal real `CachedBeaconStateGloas` fixture/helper that removes the method mocks.

## Artifact status (2026-04-22 12:4X UTC)

The current higher-level proof is now preserved locally as two commits on `feat/gloas-withdrawals`:
- `45649c5c4f` — `test: cover Gloas empty-parent withdrawals branch in produceBlockV3`
- `52404aff3f` — `test: cover gloas empty-parent withdrawals branch`

These should currently be treated as **local proof artifacts**, not silently-assumed PR updates. If this evidence needs to move again, do it deliberately via a fresh branch/cherry-pick path or by reopening the line of work intentionally.
