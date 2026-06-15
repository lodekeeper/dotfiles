@twoeths reviewed — this is the right direction for the devnet regression, and I'd take it over #9489.

**Why it's correct:** moving the prune out of `prepareNextSlot` (which is gated on being near-head/synced, so it effectively doesn't run during deep range sync — that's why the cache grew unbounded mid-sync) into `importBlock` per-block, after `recomputeForkChoiceHead`, means eviction is driven by actual fork-choice progression. The `pruneBelowParent` guard (`slot < parent.slot && payloadStatus === FULL && input.hasComputedAllData()`) only evicts inputs that are genuinely done, so it does not reintroduce the #9489 "Missing PayloadEnvelopeInput for known block" failure where insert-time `pruneToMaxSize` dropped entries before their envelopes/columns were consumed.

**Test coverage looks good:** positive eviction (FULL + computed below parent → evicted), plus the two retention cases (not-yet-FULL, not-computed-all-data) and the parent-slot edge.

**One non-blocking perf follow-up:** the Codex P2 about the O(N²) ancestor walk is valid in direction for prolonged non-finality — details + a concrete bounded fix in the inline thread. I'd treat it as a follow-up, not a merge blocker for the devnet fix.

**Scope caveat (carry-over from #9489):** #9509 bounds the cache via import-driven pruning, so it does *not* cover the original #9073 shape where the cache grows while *no* blocks import / no fork-choice progression. That OOM path should stay a separate follow-up rather than going back to unsafe insert-time eviction.
