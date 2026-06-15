Valid concern, and correct in direction. During non-finality the finalized boundary is frozen, so `getAllAncestorBlocks` walks parent→finalized with depth growing 1→N across imports → Σk = O(N²) node visits + a fresh `ProtoNode[]` allocation each import. In the empty-branch case this PR targets, those ancestors fail the `FULL && hasComputedAllData()` guard, so the walk evicts nothing — it's pure re-scan overhead over the same prefix.

Magnitude: negligible for a few epochs (N≈100–300 → tens of thousands of cheap ops). It only bites under prolonged non-finality (thousands of unfinalized blocks) — which is exactly the scenario class this change targets, so worth bounding eventually.

Concrete bounded fix: swap `getAllAncestorBlocks` for the lazy `iterateAncestorBlocks` generator and keep a `lastPrunedSlot` cursor, breaking early once the walk reaches already-pruned depth → aggregate O(N).

One correctness caveat with a pure cursor: an ancestor that was EMPTY when first walked but turns FULL later (payload revealed mid-sync) sits below the cursor and would never be re-visited by `pruneBelowParent`. `pruneFinalized` is the backstop (it evicts everything below the finalized slot on the next finalization), so the retained set stays bounded by the non-finality window even with the cursor. If you want precise eviction without leaning on finalization, an evict-on-FULL-transition hook is the alternative, but that's a larger change.

Non-blocking from my side for the immediate devnet fix — fine as a follow-up. Your call on whether to fold it in here.
