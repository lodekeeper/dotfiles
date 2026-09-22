# Review Findings - reviewer-architect - 10143-forkchoice

Reviewer: reviewer-architect
Reviewed commit: 2dd55c424ead1fe4df36c5feb04e814b19f10ad0
Generated at: 2026-09-22 03:32 UTC

Scope: local uncommitted diff for PR #10143 follow-up, listed files only.

## Findings

### 1. Fork-choice now depends on a state-transition metric contract

Path: packages/fork-choice/src/forkChoice/forkChoice.ts:10,71-74,186,868-872; packages/state-transition/src/stateView/interface.ts:54,149; packages/state-transition/src/stateView/nativeBeaconStateView.ts:547

The diff imports `BeaconStateTransitionMetrics` into `@lodestar/fork-choice` and widens the `ForkChoice` constructor from `ForkChoiceMetrics | null` to a hybrid `ForkChoiceMetrics & Pick<BeaconStateTransitionMetrics, "progressiveBalancesMismatches">`. That makes fork-choice aware of a state-transition-specific counter and relies on beacon-node's composite `Metrics` object to satisfy the constructor. It also pushes an observability side effect into `IBeaconStateView.computeUnrealizedCheckpoints`, where the native implementation accepts but ignores the new parameter.

This is a package-boundary and abstraction mismatch. Fork-choice should consume state views and fork-choice metrics, not own the shape of state-transition instrumentation. Prefer keeping `ForkChoiceMetrics` as the constructor surface and routing the progressive-balance mismatch reporter through a state-transition-owned, narrow hook used by `computeUnrealizedCheckpoints`, so fork-choice remains unaware of the state-transition metric bundle.

### 2. The fork-choice spec runner boots full beacon-node metrics for one state-transition assertion

Path: packages/beacon-node/test/spec/utils/forkChoiceTestRunner.ts:69-70,103,159,758-761

The runner now calls `createMetrics(defaultMetricsOptions, anchorState.genesisTime)`, passes the full beacon-node metrics object into `BeaconChain`, and closes it after asserting `progressiveBalancesMismatches` stayed zero. Architecturally the spec vector only needs a single state-transition counter, but this wires the fork-choice spec runner to the full beacon-node metrics stack and reinforces the cross-package coupling above.

Prefer a narrow fixture: a local metrics register plus `@lodestar/state-transition` metrics, or a minimal counter object, injected through the state-transition path that computes unrealized checkpoints. That keeps the test focused on the state-transition drift signal without making fork-choice depend on beacon-node's composite metrics shape.
