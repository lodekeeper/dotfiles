# PR #9509 review — stress-test my analysis of a Codex P2 perf concern

## PR context
- PR #9509 (twoeths) "prune PayloadEnvelopeInput when syncing" — alternative to #9489 (which we flagged as unsafe: insert-time `pruneToMaxSize` could evict inputs before their envelopes/columns were consumed → "Missing PayloadEnvelopeInput for known block").
- This PR MOVES the cache prune from `prepareNextSlot.ts` into `importBlock.ts` (per-block), and tightens the eviction guard.

## The change (diff essentials)

importBlock.ts (after recomputeForkChoiceHead, ~line 291):
```ts
if (fork >= ForkSeq.gloas) {
  callInNextEventLoop(() => {
    const newHeadParent = this.forkChoice.getBlockHexDefaultStatus(newHead.parentRoot);
    if (newHeadParent) {
      this.seenPayloadEnvelopeInputCache.pruneBelowParent(newHeadParent);
    }
  });
}
```
(removed the equivalent block from prepareNextSlot.ts)

seenPayloadEnvelopeInput.ts:
```ts
pruneBelowParent(parentBlock: ProtoBlock): void {
  for (const block of this.forkChoice.getAllAncestorBlocks(parentBlock.blockRoot, parentBlock.payloadStatus)) {
    if (block.slot < parentBlock.slot && block.payloadStatus === PayloadStatus.FULL) {
      const input = this.payloadInputs.get(block.blockRoot);
      if (input?.hasComputedAllData()) {
        this.evictPayloadInput(input);
      }
    }
  }
}
```
There is also a `pruneFinalized` handler (on `forkChoiceFinalized`) that evicts ALL cache entries with `slot < finalizedSlot`.

## Verified facts (I read the source directly)
1. `importBlock` runs once per block during range sync — `blocks/index.ts` loops `await importBlock.call(this, fullyVerifiedBlock, opts)` per slot (with a TODO about batching). So per-import, not per wall-clock-slot.
2. `callInNextEventLoop(cb)` === `setTimeout(cb, 0)` — no coalescing/debounce. Each import schedules its own walk.
3. `getAllAncestorBlocks` → `protoArray.getAllAncestorNodes` walks `while (node.parent !== undefined)` back to the previous-finalized boundary, EAGERLY building a full ProtoNode[] each call.
4. There's a lazy generator alternative: `iterateAncestorBlocks` → `protoArray.iterateAncestorNodes` (yields, can break early).
5. `prepareNextSlot` is gated on being near head / synced, so it effectively does NOT run during deep range sync — that's why the old prune location failed to bound the cache mid-sync.

## Codex P2 comment (what I'm replying to)
"Avoid walking all ancestors on every import. When syncing through a long unfinalized Gloas range, this per-import prune runs once per imported block. pruneBelowParent() calls getAllAncestorBlocks(...), which walks from parent back toward finalized, so importing N unfinalized blocks does O(N²) ancestor scans in the same non-finality syncing case this change targets and can stall sync on CPU. Please throttle this or track the last pruned point so each import only scans the newly eligible portion."

## My analysis (stress-test this)
- O(N²) claim is correct in direction: non-finality => finalized boundary frozen => walk depth grows 1→N => Σk = O(N²) node visits + array allocations. In the EMPTY-branch case this PR targets, ancestors fail the `FULL && hasComputedAllData()` guard so the walk evicts nothing — pure overhead re-scanning the same prefix each import.
- Magnitude: a few epochs (N≈100–300) => tens of thousands of cheap ops, negligible. Only bites for prolonged non-finality (thousands of unfinalized blocks) — which is the scenario class this PR targets, so worth bounding.
- Proposed fix: lazy `iterateAncestorBlocks` + `lastPrunedSlot` cursor + early break => aggregate O(N).
- Caveat I plan to flag: a cursor hard-stop can skip an ancestor that was EMPTY when first walked but became FULL later (payload revealed mid-sync) — `pruneBelowParent` would no longer evict it. BUT `pruneFinalized` is the backstop (evicts below finalized on next finalization), so retained set stays bounded by the non-finality window. Alternative: evict-on-FULL-transition hook (precise, larger change).

## Questions
1. Is the O(N²) analysis correct, or is there something that bounds the walk I'm missing (e.g., proto-array variant counts, or `getBlockHexDefaultStatus` returning a status that shortens the walk)?
2. Is the cursor-fix completeness caveat (EMPTY→FULL after cursor) real, and is `pruneFinalized` a sufficient backstop in practice, or does relying on it reintroduce unbounded growth between finalizations?
3. Is there a cleaner bounded approach than the cursor? (evict-on-FULL-transition? throttle every K? prune only when head-parent slot advanced ≥ some delta?)
4. Anything in my overall verdict that's overstated or missing? Is "non-blocking / fine as follow-up" the right call for a P2 here?
