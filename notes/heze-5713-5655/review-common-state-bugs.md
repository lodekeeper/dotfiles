# Common cached-state predicate bug review

Reviewer: review-bugs
Reviewed base: ad44c7ba71e (PR #10292, working one-file diff)
Reviewed base: 95577761f36 (PR #10293, working one-file diff)
Scope: packages/state-transition/src/util/electra.ts in both worktrees

No functional bugs found. Both diffs approved.

Both lookup predicates retain their original bodies and ValidatorIndex narrowing. CachedBeaconStateAllForks retains all previously accepted state types, supplies the common epochCtx cache, and exposes validators for every fork. Its direct cache/stateCache.js import references the existing exported type and uses the required ESM extension. PR #10292 removes only the unused Heze import; PR #10293 preserves it for its unchanged mutating helpers. Neither diff changes those helpers or runtime lookup behavior.
