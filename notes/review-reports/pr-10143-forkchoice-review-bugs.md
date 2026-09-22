# Review Findings - review-bugs - 10143-forkchoice

Reviewer: review-bugs
Reviewed commit: 2dd55c424ead1fe4df36c5feb04e814b19f10ad0
Generated at: 2026-09-22 03:38 UTC

## Findings

### P2 - Fork-choice metric plumbing is a no-op for the Altair+ unrealized checkpoint path

The follow-up passes `progressiveBalancesMismatches` from `ForkChoice.onBlock()` into `state.computeUnrealizedCheckpoints()` at `packages/fork-choice/src/forkChoice/forkChoice.ts:868`, but the only place that argument is consumed is the `ForkSeq.phase0` branch in `packages/state-transition/src/epoch/computeUnrealizedCheckpoints.ts:26-30`. The actual mismatch counter in `beforeProcessEpoch()` is guarded by `forkSeq >= ForkSeq.altair` at `packages/state-transition/src/cache/epochTransitionCache.ts:466-475`.

That means the new metric argument cannot ever increment from this call path: phase0 calls `beforeProcessEpoch()` but skips the progressive-balance check, while Altair and later never call `beforeProcessEpoch()` from `computeUnrealizedCheckpoints()` and just use the cached progressive balances directly. As a result, the fork-choice spec runner's final `lodestar_stfn_progressive_balances_mismatches_total === 0` assertion does not actually cover the reviewer-requested case where fork choice computes unrealized checkpoints using progressive balances. It will only catch mismatches that happen to be self-healed by a normal epoch transition elsewhere in the test.
