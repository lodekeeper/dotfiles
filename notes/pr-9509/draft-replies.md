# Draft replies for PR #9509 (pending advisor sanity-check)

## A) Inline in-thread reply to Codex P2 (comment id 3412586222, importBlock.ts:291)

Good catch — the concern is directionally valid. Traced it:

- `importBlock` runs **once per block** during range sync (`blocks/index.ts` loops `await importBlock.call(...)` per slot), and this PR moves the prune from `prepareNextSlot` into that per-import path, wrapped in `callInNextEventLoop` (which is just `setTimeout(cb, 0)` — no coalescing).
- `pruneBelowParent` → `getAllAncestorBlocks` → `protoArray.getAllAncestorNodes` walks `while (node.parent !== undefined)` back to the previous-finalized boundary and **eagerly materializes the full ancestor array** each call.
- During non-finality the finalized boundary is frozen, so the unfinalized depth grows 1→N as blocks import → aggregate Σk = **O(N²)** node visits + allocations. And on exactly the EMPTY branch this PR targets, those ancestors fail the `payloadStatus === FULL && hasComputedAllData()` guard, so the walk evicts nothing — pure overhead that re-scans the same already-processed prefix every import.

Magnitude: for a few epochs of non-finality (N≈100–300) it's tens of thousands of cheap ops — negligible. It only bites for *prolonged* non-finality (thousands of unfinalized blocks), which is the scenario class this PR is built for, so I think it's worth bounding rather than leaving.

Minimal bounded fix: switch to the existing lazy `iterateAncestorBlocks` generator and stop early via a `lastPrunedSlot` cursor, so each import scans only the newly-eligible portion (aggregate O(N)).

One correctness nuance if you go the cursor route: an ancestor that was EMPTY when first walked can transition to FULL later (payload revealed mid-sync); a hard `lastPrunedSlot` stop would skip evicting it via this path. `pruneFinalized` is the backstop (clears everything below finalized on the next `forkChoiceFinalized`), so the retained set stays bounded by the non-finality window — but if you'd rather not lean on that, an evict-on-FULL-transition hook is the precise (larger) alternative. Non-blocking from my side; fine as a follow-up if you want to keep this PR scoped to the correctness fix.

## B) Issue comment replying to twoeths (ack + overall review)

@twoeths reviewed — this is the right shape and it directly fixes the #9489 unsafety we flagged (insert-time `pruneToMaxSize` evicting inputs before their envelopes/columns were consumed).

What I checked:
- ✅ **Eviction guard is now safe.** Only evicting on `payloadStatus === FULL && input.hasComputedAllData()` matches the `writeDataColumnsToDb` gate, so we never drop an input whose columns are still being gathered. Keeping EMPTY/PENDING ancestors is what avoids the devnet-5 "Missing PayloadEnvelopeInput for known block" regression (#9475). 👍
- ✅ **Moving the prune `prepareNextSlot` → `importBlock` is the key correctness change.** `prepareNextSlot` effectively doesn't run during deep range sync, so the cache wasn't bounded mid-sync — which is exactly when it grew. Pruning per-import fixes that.
- ✅ **Tests** cover positive eviction (FULL+computed below parent) plus both retention cases (not-yet-FULL, not-computed) and the parent-slot edge. Good coverage.
- ⚠️ **One perf item:** Codex's P2 on the per-import ancestor walk is valid for the prolonged-non-finality case (O(N²) aggregate, evicts nothing on the EMPTY branch it re-scans). Details + a bounded-walk suggestion in the inline thread — non-blocking IMO, fine as a follow-up.
- Carry-over from the #9489 thread: this fixes the *syncing* OOM path; the original no-import / no-fork-choice-progression shape from #9073 stays a separate follow-up since the prune is now import-driven.

LGTM on the correctness fix.
