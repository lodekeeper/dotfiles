# Review Findings — review-wisdom — 10263

Reviewer: review-wisdom
Reviewed commit: 2e9ac55d6dde395fceed1d4778f7939458471923
Generated at: 2026-10-05 09:05 UTC

## Summary

This is a well-scoped, readable optimization. `IndexedBuilderState` is small, the lazy re-check of reuse candidates is easy to follow, and the call site in `applyParentExecutionPayload` only builds the index when it's needed. No correctness concerns are in scope for this reviewer. The six findings below cover documenting the cache's lifetime invariant, keeping the class to one responsibility, naming, and test readability. They are 1× 🟡 and 5× 🟢.

---

### 1. 🟡 Document the lifetime invariant that keeps the index valid

- **File:Line** — `packages/state-transition/src/block/indexedBuilderState.ts:9-12`
- **Anchor** — `* This is to make sure we loop through builders once per block processing.`
- **Principle** — Comments should record non-obvious invariants, not motivation alone.
- **Current** — The docstring says why the class exists (one loop per block) and that it can't be used across blocks/slots. It doesn't say what keeps the snapshot correct *within* its lifetime. The design relies on two unstated rules:
  1. A builder's pubkey only changes through `addBuilderToRegistry` on this instance. That method is the only place that updates `indexByPubkey`.
  2. No builder becomes reusable while the instance is alive. Candidates are only ever removed, by the lazy `canReuseBuilder` re-check, never added. Today this holds because the instance is discarded before `processWithdrawals` sweeps balances to 0. The exit path writes to raw `state` through `initiateBuilderExit`, which is safe only because it moves `withdrawableEpoch` forward.
- **Suggested** — Replace the docstring with the invariant, for example:
  ```ts
  /**
   * Block-scoped pubkey->index map and ascending reuse candidates for state.builders, built in one pass.
   * Valid only while (a) builder pubkeys change exclusively via addBuilderToRegistry() and
   * (b) no builder becomes newly reusable (candidates are re-checked lazily but never added).
   */
  ```
- **Why** — This cache sits on a consensus-critical path. Someone who later adds a builder-mutating request type, reorders `applyParentExecutionPayload`, or reuses the instance elsewhere needs these rules to stay correct. "Cannot use across blocks/slots" alone doesn't tell them.

---

### 2. 🟢 Keep `IndexedBuilderState` to one job: index lookup and slot allocation

- **File:Line** — `packages/state-transition/src/block/indexedBuilderState.ts:36`
- **Anchor** — `topUp(index: BuilderIndex, amount: number): void {`
- **Principle** — Single responsibility; code that mirrors the spec should read in spec order.
- **Current** — `topUp` never reads or updates `indexByPubkey` or the candidate list. It is the `else` branch of `process_builder_deposit_request`, moved into the index class mainly to reuse `this.currentEpoch`. As a result:
  - `processBuilderDepositRequest.ts` no longer mirrors the spec function that `specrefs/functions.yml` maps to it. Half of `process_builder_deposit_request` now lives in another file.
  - Ownership of writes is inconsistent. Deposit top-ups go through the class, but exit requests write through `initiateBuilderExit(state, builderIndex)` on the raw state. There is no rule for which writes belong to the class.
- **Suggested** — Leave the class responsible only for what has to touch the index (`findBuilderIndexByPubkey`, `addBuilderToRegistry`). Move the top-up back inline:
  ```ts
  // processBuilderDepositRequest.ts
  const builder = state.builders.get(builderIndex);
  if (builder.withdrawableEpoch !== FAR_FUTURE_EPOCH && builder.balance === 0) {
    builder.withdrawableEpoch = computeEpochAtSlot(state.slot) + state.config.MIN_BUILDER_WITHDRAWABILITY_DELAY;
  }
  builder.balance += amount;
  ```
  The existing "Top-ups can invalidate initial candidates" re-check in `findReusableBuilderIndex` already covers the interaction.
- **Why** — A narrow class makes the invariant in finding 1 easy to state and audit. Spec-mirroring functions that read top to bottom like the spec are easier to diff against future spec releases.

---

### 3. 🟢 Clarify the names of the candidate list and its cursor

- **File:Line** — `packages/state-transition/src/block/indexedBuilderState.ts:16-17, 63`
- **Anchor** — `const index = this.reusableIndiceCandidates[this.nextCandidateIndex++];`
- **Principle** — Meaningful names; avoid one word meaning two things in the same expression.
- **Current** — `reusableIndiceCandidates` uses "Indice", which isn't a word (the singular of "indices" is "index"). `nextCandidateIndex` is a position in that array, but it reads like a `BuilderIndex`. Line 63 then assigns a real `BuilderIndex` to a local called `index`, so "index" means two different things in one statement.
- **Suggested** —
  ```ts
  private readonly reusableIndexCandidates: BuilderIndex[] = [];
  private candidateCursor = 0;
  ...
  const index = this.reusableIndexCandidates[this.candidateCursor++];
  ```
- **Why** — The cursor/candidate split is the core of the lazy-reuse algorithm. Distinct names make the "consume each candidate at most once" logic obvious at a glance.

---

### 4. 🟢 `createBuilderView` doc comment now restates the signature

- **File:Line** — `packages/state-transition/src/util/gloas.ts:254-256`
- **Anchor** — `* Build a Builder view from builder fields.`
- **Principle** — Zero comments by default; keep only rationale. Exported functions get explicit return types.
- **Current** — The PR replaced a comment that explained *why* this helper exists (both insertion paths must produce identical views) with one that repeats the function name. The function is also newly exported but still has an inferred return type.
- **Suggested** — Either drop the comment, or keep the invariant with updated references:
  ```ts
  /**
   * Single construction point for new registry entries so IndexedBuilderState.addBuilderToRegistry and
   * appendBuilderToRegistry stay byte-identical (asserted in test/unit/util/gloas.test.ts).
   */
  export function createBuilderView(...): CompositeViewDU<typeof ssz.gloas.Builder> {
  ```
- **Why** — The byte-identity invariant is what makes the scan-free fork-transition path safe. Recording it where the views are built stops a future change from adding a field to only one path. An explicit return type keeps the newly exported API stable and self-documenting.

---

### 5. 🟢 Test variable `indexedState` means something different from production code; the oracle rationale was lost

- **File:Line** — `packages/state-transition/test/unit/util/gloas.test.ts:106-111`
- **Anchor** — `const indexedState = buildGloasState(slot);`
- **Principle** — Use names consistently across production and test code; keep non-obvious test rationale.
- **Current** — In `processBuilderDepositRequest.ts` and `processBuilderExitRequest.ts`, `indexedState` is an `IndexedBuilderState`. In this test, `indexedState` is a `CachedBeaconStateGloas` and the `IndexedBuilderState` is called `indexed`. The PR also deleted the three-line comment explaining that this test treats the scan/allocate path as the oracle for `appendBuilderToRegistry`. The title still says "matches addBuilderToRegistry" with no hint that this is now a method on `IndexedBuilderState`.
- **Suggested** —
  ```ts
  // With no reusable slots at the fork, appendBuilderToRegistry must match the spec-faithful
  // IndexedBuilderState.addBuilderToRegistry byte-for-byte; the latter is the oracle.
  it("matches IndexedBuilderState.addBuilderToRegistry for append-only onboarding", () => {
    const oracleState = buildGloasState(slot);
    const appendState = buildGloasState(slot);
    const indexedState = new IndexedBuilderState(oracleState);
  ```
- **Why** — When this equivalence test fails, the reader needs to know right away which side is the reference. Matching the production variable names avoids a moment of type confusion.

---

### 6. 🟢 Make the intent of the new deposit-sequence tests explicit

- **File:Line** — `packages/state-transition/test/unit/block/processBuilderDepositRequest.test.ts:262, 297`
- **Anchor** — `it("does not consume candidates for invalid deposits and re-registers replaced pubkeys", () => {`
- **Principle** — One behaviour per test; named values over magic values; consistent test scaffolding.
- **Current** —
  - The second test checks two behaviours (the "and" in its title) in one sequence of interleaved asserts. If the first behaviour regresses, the failure for the second gets hidden.
  - Intent is carried by unexplained magic values. `signatureFirstByte: 0` means "invalid PoP". `amount: 0` makes the new builder look reusable when it isn't, because `withdrawableEpoch === FAR_FUTURE_EPOCH`. `amount: 7` marks the top-up. `new Uint8Array(48).fill(3)` is built twice inline. The existing tests in this file annotate `signatureFirstByte: 0` with a reason; the new ones don't.
  - The new top-level `describe` sits outside `describe("processBuilderDepositRequest")`, so it misses that block's `beforeEach(() => isValidBuilderDepositSignatureMock.mockClear())`. Any call-count assertion added here later would see leftover calls from earlier tests.
- **Suggested** — Nest the block under the existing `describe` (or add the same `beforeEach`). Split the second test into "invalid PoP does not consume a reuse candidate" and "a replaced pubkey re-registers at a fresh index". Name the inputs once, e.g. `const invalidPop = {signatureFirstByte: 0}` and `const secondReusablePubkey = new Uint8Array(48).fill(3)`, and add a short inline note where `amount: 0` is deliberate.
- **Why** — These sequence tests are the main guard on the subtle candidate-consumption logic. Named inputs and one behaviour per test make a future failure diagnosable without re-deriving the scenario.
