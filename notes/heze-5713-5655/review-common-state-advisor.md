# Combined common-state lookup review

Reviewed bases: #10292 ad44c7ba71e; #10293 95577761f36
Working diffs: packages/state-transition/src/util/electra.ts in both PR worktrees

Verdict: Approved. No required corrections.

Both actual diffs generalize isValidatorKnown and isPubkeyKnown to CachedBeaconStateAllForks, imported directly from ../cache/stateCache.js. util/shuffling.ts establishes this exact import pattern. All executable statements and the index type predicate are unchanged; no aliases or casts are added.

#10292 removes its now-unused Heze import from ../types.js. #10293 preserves that import for switchToCompoundingValidator and queueExcessActiveBalance, whose Electra/Gloas/Heze unions remain untouched. Thus the combined solution does not widen mutating helpers to unsupported forks. Predicate signatures and the new common-type import agree between the two worktrees. Full merge-tree validation remains the parent's gate, not a claim independently verified here.

The reply explaining the existing common type, both read-only predicates, and no runtime changes is approved. Post the lint/type/focused-test claims only after actual passes. The optional sentence "Applied the same cleanup to #10293 so the two PRs still merge cleanly" is approved only after successful full merge-tree validation. This reviewer inspected code only and did not independently execute those gates.
