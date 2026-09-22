# Review Findings — review-devils-advocate — 10143-forkchoice

Reviewer: review-devils-advocate
Reviewed commit: 2dd55c424ead1fe4df36c5feb04e814b19f10ad0
Generated at: 2026-09-22 03:32 UTC

Reviewer: review-devils-advocate
Reviewed commit: 2dd55c424ead1fe4df36c5feb04e814b19f10ad0

Scope: local uncommitted diff only, limited to the requested files.

## Findings

### 1. The new metric plumbing does not actually observe the fork-choice unrealized-checkpoint path it is meant to validate

`ForkChoice.onBlock()` now passes `progressiveBalancesMismatches` into `state.computeUnrealizedCheckpoints()` (`packages/fork-choice/src/forkChoice/forkChoice.ts:868`). But `computeUnrealizedCheckpoints()` only forwards that metric to `beforeProcessEpoch()` in the phase0 branch (`packages/state-transition/src/epoch/computeUnrealizedCheckpoints.ts:25-30`), while `beforeProcessEpoch()` only increments the progressive-balance mismatch counter for Altair and later (`packages/state-transition/src/cache/epochTransitionCache.ts:466-475`). For Altair+ fork-choice unrealized checkpoints, the function uses `state.epochCtx.previousTargetUnslashedBalanceIncrements` / `currentTargetUnslashedBalanceIncrements` directly and never recomputes or checks them.

That means the end-of-vector assertion can stay green even if the specific fork-choice unrealized-checkpoint computation is using drifted progressive balances. It may catch mismatches from normal state transition processing, but not the premise twoeths asked about.

Counter-proposal: remove the metric threading and add an explicit test-only/state-transition helper that validates the Altair+ `epochCtx` progressive balances against a recomputation before `weighJustificationAndFinalization()` uses them. Call that helper from the fork-choice spec runner around block import, or from a test-only wrapper of `computeUnrealizedCheckpoints()`. If this needs production observability too, make the Altair+ branch in `computeUnrealizedCheckpoints()` perform the same validation when a narrow test/metrics hook is supplied.

### 2. This turns a pure state-view/fork-choice API into a metrics-aware production contract for a spec-test assertion

The patch changes `IBeaconStateView.computeUnrealizedCheckpoints()` to accept state-transition metrics (`packages/state-transition/src/stateView/interface.ts:149`), threads that through `BeaconStateView`, adds an ignored `_metrics` parameter to `NativeBeaconStateView`, and widens `ForkChoice.metrics` into a hybrid fork-choice/state-transition type (`packages/fork-choice/src/forkChoice/forkChoice.ts:71-74`). That is a hidden maintenance cost: every state-view implementation now carries a metric parameter that is not part of the consensus operation, and fork-choice now knows about one state-transition metric solely to satisfy this spec runner.

Counter-proposal: keep `computeUnrealizedCheckpoints()` pure and leave `ForkChoiceMetrics` as fork-choice metrics only. Put the invariant in one of two narrower places: a test helper that inspects a `CachedBeaconStateAllForks`/`BeaconStateView` and asserts progressive balances are consistent, or a state-transition-level validation hook/callback owned by the epoch cache code. The fork-choice runner can call that helper without changing the production state-view interface.

### 3. Creating full beacon-node metrics per fork-choice spec vector is too broad for one counter

`forkChoiceTestRunner` now calls `createMetrics(defaultMetricsOptions, anchorState.genesisTime)` for every vector (`packages/beacon-node/test/spec/utils/forkChoiceTestRunner.ts:103`) and passes the full object into `BeaconChain` (`packages/beacon-node/test/spec/utils/forkChoiceTestRunner.ts:159`). `createMetrics()` registers beacon, fork-choice, Lodestar, and state-transition metrics, installs a process-level `unhandledRejection` listener, and starts Node.js default/GC metric collection. That is a lot of global instrumentation for a single progressive-balance assertion in a spec runner that previously ran with `metrics: null`.

Counter-proposal: use the existing lightweight spec-test metrics pattern from `createSpecTestMetrics()` and pass only the needed counter to the code that validates progressive balances. If the runner truly needs fork-choice metrics as well, build a tiny test metrics object from `getForkChoiceMetrics(register)` plus `getMetrics(register).progressiveBalancesMismatches`, without enabling Lodestar/node process metrics or changing the whole `BeaconChain` run to metrics-enabled.
