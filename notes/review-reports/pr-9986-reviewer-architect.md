Reviewer: reviewer-architect
Reviewed commit: 0defe10a6788efe3f580eb31394523faac23cd0f

## Architectural Findings

- [Medium] `packages/beacon-node/test/spec/presets/sanity.test.ts:67` moves the consensus `state_transition` slot precondition into one beacon-node spec runner instead of the state-transition abstraction. The spec path is `state_transition -> process_slots`, and `process_slots` asserts `state.slot < slot`; Lodestar's `stateTransition()` still accepts `state.slot === block.slot` because production regen can hand it a state already dialed to the block slot. That production optimization is legitimate, but using the same `stateTransition` API for both exact spec transitions and "process block against a pre-dialed state" leaves the spec precondition enforced only by selected callers. Future block-style spec runners or direct users of `@lodestar/state-transition` can still get non-spec behavior for same-slot prestates. Architecturally, this should be a named split or mode in state-transition, for example a strict spec-transition entrypoint for spec tests and a separate pre-dialed block-transition path for beacon-node import, rather than a beacon-node-only test shim.

## Notes

- `packages/state-transition/src/block/processWithdrawals.ts` does not look like a test-only concern leaking into production. The new throws are pure, have no logging/network side effects, and match the consensus spec's raw `state.builders[builder_index]` / `state.validators[validator_index]` access before modulo advancement.
- `packages/spec-test-util/src/single.ts` is already Vitest-based (`describe`, `it`, `expect`, `vi`), so `expect.unreachable` is appropriately placed in the shared spec-test runner to make `shouldError` semantics real.
- The `verifyStateRoot: true` change in the sanity runner aligns the harness with state-transition post-state checking and does not create a package-boundary concern.
