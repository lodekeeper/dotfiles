# PR #10261 — Style Enforcer Review (review-linter)

Reviewer: review-linter
Reviewed commit: 6d790d2845a530be1b96bac0eb5fa8a66b784b67

PR: ChainSafe/lodestar#10261 "fix: honor group validator statuses when filtering by ids"
Scope: style / convention consistency only (naming, comments, types, assertion messages, pattern consistency). Functional and architectural concerns are out of scope for this reviewer.

Line numbers below are **new-file (PR head) line numbers**, taken from `git show refs/review/pr-10261:<path>`.

## Mechanical checks (done, no findings)

- `biome format` run via stdin on the three new/rewritten files (`validatorStatus.ts`, `validatorStatus.test.ts`, `getStateValidators.test.ts`): output identical to the PR content, so formatting is clean. CI has not run lint, so this was checked locally.
- Double quotes, `.js` relative-import extensions, named exports only, no `any`, no underscore-prefixed private fields. All consistent.
- Named-specifier ordering in the changed imports (`ValidatorIndex, getBuilderStatus, getValidatorStatus, ssz, statusMatches`) matches Biome's lexicographic order.
- No logging, metrics or new error-throwing code is added, so those conventions don't apply. `statusMatches` can still reach the pre-existing generic `throw new Error(...)` in `mapToGeneralStatus`, but that code is untouched.
- The `(await api.getX(...)) as {data: ...}` cast in the new test is an established pattern (`getBlockHeaders.test.ts`, `beacon.test.ts`, `config.test.ts`). Not flagged.

## Findings

### 1. 🟡 should-fix — Single-use public helper that duplicates an existing inline pattern
**File:Line** — `packages/types/src/utils/validatorStatus.ts:95-98` (call site `packages/beacon-node/src/api/impl/beacon/state/index.ts:103`)

**Convention** — `AGENTS.md` ("Style learnings from reviews"): *"Prefer inline logic over single-use helper functions for simple checks"* and *"Match existing patterns in the file you're modifying."* The identical predicate already exists inline in `packages/state-transition/src/stateView/beaconStateView.ts:650`:
```ts
if (statuses.has(validatorStatus) || statuses.has(mapToGeneralStatus(validatorStatus))) {
```

**Deviation**
- The PR adds a one-line helper with exactly one production caller (`index.ts:103`) rather than inlining the check next to `getValidatorStatus(...)`.
- `validatorStatus.ts` is re-exported via `export * from "./utils/validatorStatus.js"` (`packages/types/src/index.ts`), so `statusMatches` becomes a permanent public export of `@lodestar/types` that is used in one place.
- Two implementations of the same predicate now exist in two packages (Set-based in state-transition, array-based in types) and can drift. The PR does not reuse the new helper in `getValidatorsByStatus`.
- A `ValidatorStatus`-only helper in `@lodestar/types` also isn't where this kind of API-filter logic usually lives. The sibling filter helpers (`filterStateValidatorsByStatus`, `getStateValidatorIndex`, `toValidatorResponse`) are in `packages/beacon-node/src/api/impl/beacon/state/utils.ts`.

**Suggestion** — Pick one:
- (a) Inline at `index.ts:103`: `statuses.includes(status) || statuses.includes(mapToGeneralStatus(status))`. Import `mapToGeneralStatus`, which is already exported. Drop the helper and its 34-line test block.
- (b) Keep a helper, but put it in `beacon-node/src/api/impl/beacon/state/utils.ts` next to `filterStateValidatorsByStatus`, so it doesn't widen the `@lodestar/types` public surface.

Do not add a second copy of the logic without consolidating the first.

### 2. 🟡 should-fix — New filter type is not used by the helper; `readonly string[]` bypasses it
**File:Line** — `packages/types/src/utils/validatorStatus.ts:96` and `packages/api/src/beacon/routes/beacon/state.ts:48`

**Convention** — Explicit, specific types ("no `any`, explicit types everywhere"). Types for status vocabularies live next to their definitions in `packages/types/src/utils/validatorStatus.ts` (`ValidatorStatus`, `GeneralValidatorStatus`, `BuilderStatus`). `state.ts:46` re-exports them (`export type {BuilderStatus, ValidatorStatus};`) rather than defining parallel aliases.

**Deviation**
- The PR introduces `ValidatorStatusFilter = ValidatorStatus | GeneralValidatorStatus` in the **api** package (`state.ts:48`).
- The function that consumes that exact concept in the **types** package takes `filterStatuses: readonly string[]` (`validatorStatus.ts:96`). The new type and the helper describe the same set of strings with two different vocabularies.
- `ValidatorStatusFilter` is composed entirely of `@lodestar/types` types but is declared one package up, so the types package can't use it. That is probably why the helper fell back to `string[]`.

**Suggestion** — Declare `export type ValidatorStatusFilter = ValidatorStatus | GeneralValidatorStatus;` in `validatorStatus.ts` beside `GeneralValidatorStatus`. Re-export it from `state.ts` (as is done for `ValidatorStatus`) and type the param as `readonly ValidatorStatusFilter[]`. This also drops the `GeneralValidatorStatus` import added to `state.ts:9`.

Caveat: the neighbouring `filterStateValidatorsByStatus(statuses: string[], ...)` and `getValidatorsByStatus(statuses: Set<string>, ...)` are also loosely typed, so `string[]` is not unprecedented. It is still inconsistent with the type this PR itself introduces. If finding 1(a) is taken, this finding disappears.

### 3. 🟢 nit — Missing assertion message inside a loop
**File:Line** — `packages/beacon-node/test/unit/api/impl/beacon/state/getStateValidators.test.ts:94`

**Convention** — Test assertions in loops carry a message: `expect(x).equals(y, \`msg for ${item}\`)` (global and repo convention). The PR does this for the first assertion in the same loop (`:93`, `ids+[${group}] should include index ${id}`) and in `validatorStatus.test.ts:118`.

**Deviation** — `expect(data[0].status).toBe(expected);` inside `for (const {id, group, expected} of cases)` has no message. If one case returns the wrong status, the failure won't say which group/id it was. Line 93 only covers the length assertion.

**Suggestion** — `expect(data[0].status, \`status for ids+[${group}] index ${id}\`).toBe(expected);`

### 4. 🟢 nit — Hand-rolled literal types / casts where project types exist (tests)
**File:Line** — `getStateValidators.test.ts:81`; `packages/types/test/unit/validatorStatus.test.ts:115`

**Convention** — Reuse the canonical types (`GeneralValidatorStatus`, `ValidatorStatus`); avoid unnecessary type casts (a recurring maintainer comment per `review-patterns.md`).

**Deviation**
- `getStateValidators.test.ts:81` declares `group: "pending" | "exited" | "withdrawal"` and `expected: string` inline. This re-spells members of `GeneralValidatorStatus` and loosens `ValidatorStatus` to `string`.
- `validatorStatus.test.ts:115` iterates `Object.entries(groupMembers) as [GeneralValidatorStatus, ValidatorStatus[]][]`. The cast is needed only because `Object.entries` widens keys to `string`.

**Suggestion**
- Use `group: Exclude<GeneralValidatorStatus, "active">; expected: ValidatorStatus` in the first file.
- In the second, build `groupMembers` as an array of `[GeneralValidatorStatus, ValidatorStatus[]]` tuples (or `satisfies`) to avoid the cast.

### 5. 🟢 nit — Comments that restate code (repo default is zero comments)
**File:Line** — `packages/api/src/beacon/routes/beacon/state.ts:47`; `packages/types/src/utils/validatorStatus.ts:95`; `getStateValidators.test.ts:22`

**Convention** — `AGENTS.md` → Comments: *"The default number of comments in new code is zero"*; do not restate what the code does. `/** */` is for public API docs, `//` for implementation.

**Deviation**
- `state.ts:47` `/** Fine-grained or Beacon API group status used as a request filter */` restates `ValidatorStatus | GeneralValidatorStatus` under the name `ValidatorStatusFilter`.
- `validatorStatus.ts:95` `/** Match fine-grained validator status against Beacon API filter statuses (incl. group statuses). */` restates `statusMatches(filterStatuses, validatorStatus)`. This one is the weakest case: it is a public export, and the neighbouring `getValidatorStatus` and `getBuilderStatus` have JSDoc.
- `getStateValidators.test.ts:22` `// Validators are active_ongoing (activationEpoch 0, exitEpoch FAR_FUTURE)` describes fixture contents that the first test already asserts (`expect(data[0].status).toBe("active_ongoing")`).

**Suggestion**
- Drop `state.ts:47` and test `:22`.
- At `state.ts:47`, a link to the beacon-APIs spec section (the `oneOf: [ValidatorStatus, enum[active|pending|exited|withdrawal]]` definition) would be the one non-obvious piece of information worth recording, if any comment is kept.
- Keep or drop `validatorStatus.ts:95` depending on the outcome of finding 1.

### 6. 🟢 nit — Predicate name is unqualified and not verb-prefixed
**File:Line** — `packages/types/src/utils/validatorStatus.ts:96`

**Convention** — Boolean predicates in `@lodestar/types` use an `is*` prefix (`typeguards.ts`: `isDenebBlockContents`, `isElectraAttestation`, ...). The sibling functions in this file are verb-first and name the thing: `getValidatorStatus`, `getBuilderStatus`, `mapToGeneralStatus`.

**Deviation** — `statusMatches` has no verb, and `status` is ambiguous in a file that also defines `BuilderStatus` and `getBuilderStatus`. The convention here is soft (no existing `matches*` predicate to compare against), hence a nit.

**Suggestion** — If the helper is kept (see 1), rename to something like `matchesValidatorStatusFilter(filter, status)` or `isValidatorStatusMatch`.

## Considered, not flagged

- Test file placement, and describe titles (`"getStateValidators status filtering with ids"` vs siblings `"api - beacon - <fn>"` / `"beacon state api utils"`). Siblings in the same directory are already inconsistent, so this isn't a clear contradiction.
- `vi.spyOn(state, "getValidator").mockImplementation(...)` with overlay merging, instead of building a state through `generateCachedAltairState(opts)`. This is a test-design question (readability), not a convention violation.
- `validatorStatus.test.ts:107-142` re-encodes the `mapToGeneralStatus` switch as a `groupMembers` table. This is a maintenance-cost / test-value concern rather than style, but it is relevant to the verdict: 34 + 97 test lines guard a one-line behavioural change.
- The `ValidatorStatusFilter` type widening at `state.ts:198/200/215/217` is consistent across GET query and POST body, and is correctly re-exported from `routes/beacon/index.ts:30`.

## Overall

The production diff is small and stylistically mostly clean: formatting, naming casing, imports and exports are all in line with Lodestar. The deviations are about pattern consistency, not correctness. The helper adds public API surface and a second copy of a predicate that already exists inline (1), its type vocabulary is split across two packages (2), and there are a few minor test/comment nits (3-6). Nothing here is a blocker on its own. Per the review mandate, note that CI (lint/types/tests) has not run for this external PR, so the Biome result above is local only and `check-types` was not verified.

**Verdict: MERGE AFTER CHANGES** — (1) bug is real and spec-valid and the fix is tiny, but the new `@lodestar/types` export should be inlined or relocated to avoid a single-use public helper that duplicates `beaconStateView.ts:650`; (2) `ValidatorStatusFilter`/helper typing should be unified (or the helper removed); (3) CI has not run (lint/types/tests unverified), and the minor test nits (loop assertion message, restated comments) should be tidied.
