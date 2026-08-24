# Review Findings — review-devils-advocate — 9904

Reviewer: review-devils-advocate
Reviewed commit: bb66eca801346ef46495f0248277735cc1bb0244
Generated at: 2026-08-24 10:42 UTC

Reviewer: review-devils-advocate
Reviewed commit: bb66eca801346ef46495f0248277735cc1bb0244

# PR #9904 — Devil's Advocate: "fix: bound payload envelope seen cache"

Role: challenge the premise and approach. The premise (an unbounded
`SeenPayloadEnvelopeInput` map is a real memory/DoS liability) is **sound**, and
coupling the bound with a DB-reload fallback is a reasonable way to keep the cache
non-load-bearing. `getOrReload` is independently justified (late by-root payloads for
old blocks that `pruneBelowParent`/`pruneFinalized` already dropped), the in-flight
dedup map is correct, and the test coverage is genuinely good.

Three objections to the **approach**, most-signal first. None is a claim that the PR
is broken today; each is a design gap that the "reload makes eviction safe" argument
does not actually cover.

---

## Objection 1 — The cap evicts unconditionally; every other prune path does not

`pruneBelowParent` deliberately guards eviction:

```ts
// ...and don't evict while columns are still being gathered: writeDataColumnsToDb awaits the
// same hasComputedAllData() before persisting. Such entries are pruned by a later call.
if (input?.hasComputedAllData()) {
  this.evictPayloadInput(input, "belowParent");
}
```

`pruneToMaxSize` has **no such guard** — it evicts the oldest-inserted entry regardless
of whether columns are still being gathered or `writeDataColumnsToDb` has persisted yet.
`evictPayloadInput` then `serializedCache.delete(...)`s that entry's keys.

Failure mode: an entry that is mid-column-gather (`hasComputedAllData() === false`) and
happens to be the oldest-inserted of the 96 (`MAX = (MAX_LOOK_AHEAD_EPOCHS+1)*SLOTS_PER_EPOCH
= 3*32`) when the cap fires. Its serialized-cache backing is deleted before persistence
completes; a subsequent `get()` misses and `getOrReload` rebuilds an **EMPTY** shell
("always EMPTY even when the block is actually FULL"). The in-memory columns/payload that
were about to be written are discarded, forcing re-download and potentially stalling the
block's path to FULL/DA. The reload explicitly cannot recover this — it only rebuilds the
bid shell.

Probability is low (an entry must stay mid-gather for ~96 slots while 96 newer entries
arrive), but the cap exists precisely for pathological/adversarial conditions, which is
exactly when late-column gathering and cache pressure coincide.

**Counter-proposal:** apply the same `hasComputedAllData()` skip in the cap loop (and/or
skip roots currently in `this.reloading`): if the oldest candidate isn't safe to evict,
fall through to the next candidate rather than evicting it. This keeps the cap aligned
with `pruneBelowParent`'s existing invariant and removes the only path that can drop
in-flight heavy data that is not yet in the DB.

---

## Objection 2 — Insertion order is the wrong eviction key, and it can thrash against reload

The cap evicts by **insertion order** ("the Map iterates oldest-inserted first"). The
justification is anti-thrash for a *just-reloaded* old-slot entry (set at the back, so it
survives). But insertion order does not correlate with usefulness:

- The oldest-inserted entry can be the one consumers are actively blocked on — e.g. a
  stalled block whose payload envelope hasn't been revealed yet, sitting at the front of
  the map while newer blocks stream in and push the cap. Insertion-order eviction drops
  the exact entry that is being awaited, and `getOrReload` rebuilds it EMPTY (no payload),
  so the await does not make progress from the reload.
- Reload-thrash in the other direction: under sustained by-root recovery of *scattered*
  old roots, each `getOrReload` inserts an old-slot EMPTY shell at the back and evicts a
  live-window entry at the front. That evicted live-window entry may itself then need a
  reload. The "reloaded entry survives" property only protects the entry being reloaded
  *this* call, not the working set.

The `MAX` sizing is copied from `SeenBlockInput` ("this is the same to SeenBlockInput"),
but the two caches have different populations: `SeenBlockInput` holds blocks pending
import within a look-ahead window; `SeenPayloadEnvelopeInput` additionally holds EMPTY
shells for *already-imported* blocks (anchorState seed, reload seed) whose slots can sit
far below the look-ahead window. The look-ahead-derived bound is not obviously the right
size for that mixed population.

**Counter-proposal:** evict by slot (lowest-slot, non-canonical / below-head-window first)
rather than insertion order, or exclude EMPTY reloaded/anchor shells from the cap
accounting so recovery shells can't push out live-window entries. Either removes the
thrash coupling between the cap and reload and makes "keep what's needed" the actual
policy instead of an accidental correlation.

---

## Objection 3 — "Non-load-bearing for range sync" has a gap: the dangling-parent path still hard-throws

The safety argument states range sync "reads its batch map" so the shared cache can be
freely evicted. That is true for in-batch slots (the local `payloadEnvelopes` map holds
strong refs). It is **not** true for the dangling-parent envelope, which still resolves
through the shared cache with a synchronous `.get()` and a hard throw
(`downloadByRange.ts:239`):

```ts
payloadInput = seenPayloadEnvelopeInputCache.get(toRootHex(envelope.message.beaconBlockRoot));
...
if (payloadInput === undefined) {
  throw new Error(`Missing PayloadEnvelopeInput for slot ${slot} root ...`);
}
```

`cacheByRangeResponses` is synchronous, so it cannot call `getOrReload` here. If the cap
ever evicts the parent's shell before this consumes it, the batch aborts with the exact
"Missing PayloadEnvelopeInput" failure class that #9306/#9489 were about — reintroduced
through the new cap rather than through insert-time pruning.

In practice this is protected only by an **implicit, undocumented invariant**:
`parentPayloadRequest` is first-batch-of-SyncChain only, when the cache is still nearly
empty, so the parent shell can't be the oldest-of-96 yet. That invariant is load-bearing
and nowhere asserted; a future change that makes parent-by-root fetch fire on later
batches (or that raises batch sizes) would silently break it.

**Counter-proposal:** either (a) make the parent lookup reload-capable by threading an
async `getOrReload` into this path (requires making the consumer async), or (b) pin the
dangling parent for the duration of the SyncChain (exempt it from the cap) and add an
explicit comment/assert documenting why the parent shell cannot be cap-evicted before
consumption. As written, the "cache is non-load-bearing for range sync" claim is not
fully true, and the one exception is the highest-severity historical failure mode.

---

## Verdict

Approach is fundamentally reasonable and a clear improvement over #9489's insert-time
pruning. But "reload makes eviction safe" is over-stated in three places: (1) the cap can
delete in-flight heavy data the reload can't rebuild, (2) insertion-order eviction can
drop actively-awaited entries and thrash against reload, and (3) range sync's
dangling-parent path still hard-depends on the shared cache and hard-throws. Objection 1
(add the `hasComputedAllData()` guard to the cap) is the cheapest and highest-value fix.
