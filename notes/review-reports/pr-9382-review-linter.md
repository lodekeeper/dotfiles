# Review Findings — review-linter — 9382

Reviewer: review-linter
Reviewed commit: 3534a7aa12cbe756a6deef878b8c1c3c59d2dc0b
Generated at: 2026-07-28 12:59 UTC

## Findings

### 1. `packages/beacon-node/src/execution/engine/sszRestClient.ts:99` — private helper uses underscore naming

**Convention:** Lodestar's current review style prefers private members without underscore prefixes (`private fetch(...)`, not `private _fetch(...)`).

**Deviation:** The new `SszRestClient` helper is named `_fetch`, and the public wrappers call `this._fetch(...)`.

**Suggestion:** Rename the helper to a descriptive non-underscore name such as `fetchRaw`, `fetchBytes`, or `request` and update the two call sites.

### 2. `packages/beacon-node/test/unit/executionEngine/httpSszRest.test.ts:253` — queue-ordering assertion relies on an arbitrary timer

**Convention:** Timing-sensitive unit tests should use deterministic gates or explicit signals where possible, especially around queues and async ordering.

**Deviation:** The serialization test sleeps for 25ms and then asserts `forkchoice:start` has not happened. On slow CI this can false-pass if a broken concurrent call simply has not reached the handler within that window, and the magic delay makes the test more brittle.

**Suggestion:** Replace the sleep with a deterministic synchronization primitive, e.g. a promise that rejects/resolves if the forkchoice handler starts before `releaseNewPayload()` is called, then assert after releasing the controlled `newPayload` gate.

## Local Checks

- `pnpm exec biome check packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts packages/beacon-node/src/execution/engine/http.ts packages/beacon-node/src/execution/engine/mock.ts packages/beacon-node/src/execution/engine/sszRestClient.ts packages/beacon-node/src/execution/engine/sszRestEncoding.ts packages/beacon-node/src/execution/engine/types.ts packages/beacon-node/test/unit/executionEngine/httpSszRest.test.ts packages/cli/src/options/beaconNodeOptions/execution.ts` passed (Node engine warning only).
- `pnpm vitest run --project unit packages/beacon-node/test/unit/executionEngine/httpSszRest.test.ts` passed (5 tests; Node engine warning only).
