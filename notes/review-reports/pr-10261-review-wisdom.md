# PR #10261 — fix: honor group validator statuses when filtering by ids

Reviewer: review-wisdom
Reviewed commit: 6d790d2845a530be1b96bac0eb5fa8a66b784b67

Persona: wise senior engineer (readability, simplicity, maintainability). Functional correctness, security, and architecture are out of scope here.

## Summary

The behavior change is one line (`index.ts:103`), it fixes a real interop bug backed by the spec, and it touches the right place. The rest of the PR is wrapped around that line: a new public export in `@lodestar/types` with a single caller, a new API type, and ~130 lines of tests for a one-predicate change. Part of that wrapping is useful. The widened route type is required and spec-correct, and the group→member table is the first test coverage `mapToGeneralStatus` has ever had. The rest adds surface area without adding clarity. The fix itself is worth taking. The PR should be trimmed before merge.

Contributor signals: the PR is narrowly scoped (good), discloses its AI assistance, and names a concrete interop scenario (Nimbus VC v26.10.0). There is no linked issue. The second commit (`fix: correct getStateValidators test typings for CI`) is a fixup, so the first push did not type-check its own tests. The test volume and shape (a test per permutation, plus a mocked-overlay integration test that re-checks the unit-level mapping) look like unpruned agent output, not a deliberate test design.

---

## Findings

### 1. 🟡 New public helper duplicates an existing rule and has one caller
- **File:Line:** `packages/types/src/utils/validatorStatus.ts:95-98` (call site `packages/beacon-node/src/api/impl/beacon/state/index.ts:103`)
- **Principle:** DRY / single source of truth; minimal public surface
- **Current:** `statusMatches(filterStatuses, validatorStatus)` re-implements the rule that already exists in `BeaconStateView.getValidatorsByStatus`: `statuses.has(status) || statuses.has(mapToGeneralStatus(status))`. With this PR the rule exists in two TS shapes, one array-based and one Set-based, plus the native binding. The new helper is a permanent public export of `@lodestar/types`, but only one place calls it.
- **Suggested:** Pick one option.
  - **(a) Smallest change (preferred):** drop the helper and inline the fix with the already-exported `mapToGeneralStatus`:
    ```ts
    const status = getValidatorStatus(validator, currentEpoch);
    if (statuses.length && !statuses.includes(status) && !statuses.includes(mapToGeneralStatus(status))) {
      continue;
    }
    ```
  - **(b)** If a shared helper is wanted, make it the single source. Have `getValidatorsByStatus` call it too, so the "fine-grained OR group" rule lives in one place. That is a scope expansion, so it belongs in a follow-up.
- **Why:** Two copies of one rule will drift over time. For example, a future new sub-status or group would need updating in both places. A public export in `@lodestar/types` also has to be maintained once it ships. Option (a) keeps the behavior change to two lines and adds no new API.

### 2. 🟢 If the helper is kept, give it a specific name and a precise type
- **File:Line:** `packages/types/src/utils/validatorStatus.ts:96`; `packages/api/src/beacon/routes/beacon/state.ts:47-48`
- **Principle:** Meaningful names; explicit types
- **Current:** `statusMatches` sits in a module that also defines `BuilderStatus` / `getBuilderStatus`, so the name doesn't say which kind of status it matches. The argument order `(filter, status)` reads in reverse of the name. The parameter is `readonly string[]`, while the PR defines the precise union `ValidatorStatusFilter` in `@lodestar/api`, which `@lodestar/types` cannot import.
- **Suggested:** Rename it to something like `matchesValidatorStatusFilter(status, filter)`. Define `ValidatorStatusFilter = ValidatorStatus | GeneralValidatorStatus` in `@lodestar/types` next to `GeneralValidatorStatus`, and re-export it from the API routes. That follows the existing `export type {BuilderStatus, ValidatorStatus}` pattern at `state.ts:45`. Option (a) of finding 1 makes this finding moot.
- **Why:** A name that says what is being matched needs no doc comment. Defining the union beside its component types means the helper and the route type can't drift apart.

### 3. 🟡 Beacon-node test re-checks unit-level mapping by mocking an implementation detail
- **File:Line:** `packages/beacon-node/test/unit/api/impl/beacon/state/getStateValidators.test.ts:68-96`
- **Principle:** Testability / tests at the right level; maintenance cost
- **Current:** The pending/exited/withdrawal case spies on `state.getValidator` and overlays partial validator fields. That ties the test to the impl fetching validators through `state.getValidator` specifically. It then checks the group→sub-status mapping, which the `@lodestar/types` unit test (`validatorStatus.test.ts:107-121`) already covers exhaustively. The overlay also sets defaults that change nothing (`slashed: false`, line 72). The case union is hand-written (`"pending" | "exited" | "withdrawal"`, `expected: string`, line 81) when `GeneralValidatorStatus` / `ValidatorStatus` exist.
- **Suggested:** Delete this case. The integration test only needs to prove the ids path is wired to group matching. Lines 35-45 (group `active` → included) and 58-66 (group `pending` → excluded) already do that. Keep the mapping exhaustiveness in the pure unit test.
- **Why:** If someone later refactors the impl to read validators differently, for example by batching through `getAllValidators()`, this test breaks even though the behavior is unchanged. Integration tests should pin the integration and unit tests should pin the logic. Duplicating across both levels costs maintenance and adds no confidence.

### 4. 🟢 Repeated call-and-cast boilerplate in the beacon-node test
- **File:Line:** `packages/beacon-node/test/unit/api/impl/beacon/state/getStateValidators.test.ts:36-40, 48-52, 59-63, 88-92`
- **Principle:** DRY in tests
- **Current:** Every case repeats `(await api.getStateValidators({stateId: "head", validatorIds: [...], statuses: [...]})) as {data: routes.beacon.ValidatorResponse[]}`. The cast itself follows existing precedent (`getBlockHeaders.test.ts`).
- **Suggested:** Add a local helper inside the `describe`, e.g.:
  ```ts
  async function getValidators(
    validatorIds: routes.beacon.ValidatorId[],
    statuses: routes.beacon.ValidatorStatusFilter[]
  ): Promise<routes.beacon.ValidatorResponse[]> {
    const {data} = (await api.getStateValidators({stateId: "head", validatorIds, statuses})) as {
      data: routes.beacon.ValidatorResponse[];
    };
    return data;
  }
  ```
- **Why:** Each test then reads as input → expectation. That roughly halves the file and puts the cast in one place.

### 5. 🟢 Types-package tests: retarget the useful part, drop the narration
- **File:Line:** `packages/types/test/unit/validatorStatus.test.ts:107-139` (esp. line 123)
- **Principle:** Tests describe behavior, not change history; test the unit that owns the logic
- **Current:** The group→members table (108-121) is the most valuable part of the PR's tests, because `mapToGeneralStatus` had no tests on `unstable`. It is attached to `statusMatches`, though, and the other three cases mostly re-test `Array.prototype.includes`. The test name "fine-grained statuses **still** match exactly" (123) narrates the diff.
- **Suggested:** If finding 1(a) is adopted, keep the table as a `describe("mapToGeneralStatus")` test, e.g. `expect(mapToGeneralStatus(member)).toBe(group)`, and drop the rest. If the helper is kept, rename line 123 to describe behavior without "still", e.g. "fine-grained status filter requires exact match".
- **Why:** Tests outlive the PR that added them. Names that refer to the change make no sense once the diff is gone. The mapping logic belongs in `mapToGeneralStatus`, so that is where its tests should live.

---

## Not flagged (deliberately)
- The `ValidatorStatusFilter` widening on GET `query.status` / POST `body.statuses` is required: without it, the inline fix in finding 1(a) doesn't type-check. It also makes the client-side types match the beacon-APIs `oneOf`. Keep it.
- The JSDoc on `ValidatorStatusFilter` (`state.ts:47`) states intent ("used as a request filter") and doesn't just restate the code, so it's fine.
- The fixture comment at `getStateValidators.test.ts:22` documents a non-obvious fixture invariant, so it's fine.

---

**Verdict: MERGE AFTER CHANGES.** (1) The core fix is real, spec-backed, and one line, so it is worth owning. (2) Inline it with `mapToGeneralStatus` instead of adding a single-caller public `@lodestar/types` export that duplicates the rule in `getValidatorsByStatus`. (3) Trim the tests: drop the `getValidator`-overlay integration case and move the group table onto `mapToGeneralStatus`.
