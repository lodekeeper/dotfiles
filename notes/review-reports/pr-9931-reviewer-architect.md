Reviewer: reviewer-architect
Reviewed commit: 1d2380582c

# PR #9931 — feat(builder): observe beacon node blocks

## Verdict

**Fit to merge — design is sound.** Clean package layering, spec-correct bid
extraction, genuinely forward-compatible fork gating (heze-tested), defense-in-depth
version checks, and an excellent test suite (562 lines). One should-fix: the observer
is a long-lived network service with **no metrics wired and no metrics constructor
param**, diverging from its sibling `BuilderStatusTracker`. Everything else is nits or
deferred-by-design items the PR already discloses.

---

## Findings (ranked)

### 🟡 1. Observability gap — no metrics, and no constructor seam to add them later
`packages/builder/src/services/blockObserver.ts:41-50` (ctor), wired at
`packages/builder/src/builder.ts:97`.

`new BlockObserver(config, logger, api)` takes **no `metrics` argument**, whereas the
sibling long-lived service does: `new BuilderStatusTracker(api, logger, index, opts.metrics)`
(`builder.ts:96`), and `BuilderStatusTracker` sets gauges (`builderStatusTracker.ts:40-41`).

This is exactly the wemeetagain pattern: a service that (a) holds an SSE subscription,
(b) fetches one block per slot with up to 5 retries, (c) drops roots on terminal failure,
(d) can see the stream close unexpectedly — and none of that is countable. Operators get
only ad-hoc log lines; an unexpected stream close (`blockObserver.ts:82`) error-logs once
and then observation is silently dead (no reconnect, disclosed as deferred) with nothing to
alert on.

The PR body says "no metrics in this PR," which is a reasonable staging call for the
*registration*, but the **constructor signature** should still accept `metrics: Metrics | null`
now so wiring counters later isn't a breaking-change churn on every call site (and stays
symmetric with `BuilderStatusTracker`). Suggested minimal counters when they land: blocks
observed, retrieval failures (by terminal reason), dedup drops, retry attempts, stream
closes/reconnects.

**Suggestion:** thread `metrics: Metrics | null` through the ctor now (pass `opts.metrics`
from `builder.ts:97`); defer the actual gauge/counter set if desired.

### 🟡 2. Incremental-staging: per-slot fetch with zero registered consumers
`runOnBlock` (`blockObserver.ts:56-58`) has **no non-test caller** anywhere in the repo,
yet `blockObserver.start()` runs unconditionally from the `Builder` ctor (`builder.ts:60`).
Post-Gloas, every slot does `getBlockV2`-by-root + deserialize + `Promise.all([])`
(no-op) whose only output is a debug log (`blockObserver.ts:179-187`).

Mitigating facts (why this is acceptable, not a blocker):
- Pre-Gloas it short-circuits *before* any network call (`blockObserver.ts:107-110`), so on
  today's networks the cost is ~nil.
- The "winning bid per slot" debug log is legitimate operator diagnostics, so this is not
  pure fetch-and-discard — it's a plausible standalone deliverable for API-02.

If the intent is *not* to pay for a fetch just to log, gate it cheaply: at the top of
`processBlockEvent`, `if (this.fns.length === 0) return;` **before** touching
`seenBlockRoots` (so an idle observer consumes nothing and stays correct once a consumer
registers pre-`start`, per the doc-comment contract at `blockObserver.ts:52-55`). Either
way, call it out; I'd keep the log + gate the fetch, or accept as-is if the log is the
deliverable.

### 🟢 3. `executionOptimistic` sourced from the SSE event, not the fetch meta
`blockObserver.ts:97,173`. The value is taken from the `block` event; `getBlockV2` also
returns `executionOptimistic` (and `finalized`) in its meta
(`ExecutionOptimisticFinalizedAndVersionMeta`, `block.ts:87`). The fetch-time meta is the
more authoritative "is this block optimistic now" and would let you surface `finalized`
too. Minor; the event value is a defensible choice. Consider preferring `response.meta()`
for consistency with `version`, which *is* taken from meta.

### 🟢 4. `processBlockEvent` public + whole-value cast
`blockObserver.ts:95` is `public` (invoked internally via `void this.processBlockEvent`),
likely for testing — tests actually drive it through the captured `onEvent`, so it could be
`private`. And `blockObserver.ts:168` casts the whole `SignedBeaconBlock` via `as` after
`isGloasBeaconBlock(block.message)` narrows only `block.message`. Both are safe; flagging as
tidy-ups only.

---

## Affirmations (focus areas the design gets right)

**Package boundary / layering — clean.** Imports are strictly downward: `@lodestar/api`,
`@lodestar/config`, `@lodestar/params`, `@lodestar/types`, `@lodestar/utils`
(`blockObserver.ts:1-5`). No beacon-node-internal reach-in, no upward import. `ObservedBlock`
+ `BlockObserver` sit in `packages/builder/src/services/` next to `builderStatusTracker.ts`
and follow the same service shape (ctor deps, `start(signal)`, fire-and-forget, abort via
the shared `AbortController`, `logger.info/debug/error` idioms). Good fit.

**ePBS/Gloas correctness — right field, right authority, sound defense-in-depth.**
- `signedExecutionPayloadBid` (`blockObserver.ts:169`) is the correct field to answer "was my
  bid selected": it's the canonical bid the block committed to; `message.builderIndex`
  distinguishes self-build (`BUILDER_INDEX_SELF_BUILD`, exercised by the "self-build sentinel"
  test) from an external builder win.
- Treating `response.meta().version` as fork authority (`blockObserver.ts:147-151`) is correct:
  the API client deserializes by `Eth-Consensus-Version`, so meta.version *is* the type of the
  decoded block. Using `getForkName(slot)` (`blockObserver.ts:107`) only as a cheap pre-filter
  to skip a network call is fine.
- Skipping pre-Gloas by **local** config is safe despite a "possibly-different node": `init()`
  calls `assertEqualParams(opts.config, specRes.value())` (`builder.ts:76`), so builder and node
  share an identical fork schedule. Worth stating in a comment, but correct.
- The triple check (meta postGloas + `isGloasBeaconBlock` body guard + slot match,
  `blockObserver.ts:147-166`) is appropriate belt-and-suspenders; under `assertEqualParams` the
  "unsupported fork version" branch is effectively unreachable but harmless.

**Forward-compatibility — genuinely good, not rot-prone.** `ForkPostGloas` = `Exclude<ForkName,
ForkPreGloas>` (`forkName.ts:118`) *includes* heze and every future fork; `isForkPostGloas`
returns true for them (`forkName.ts:128`); `isGloasBeaconBlock` narrows to `BeaconBlock<
ForkPostGloas>` via `signedExecutionPayloadBid !== undefined`, which heze also carries
(`heze/sszTypes.ts:75`). The four logged bid fields (`builderIndex/value/blockHash/
parentBlockHash`) exist in gloas and survive heze's progressive extension, and the `signedBid`
union type means a future field rename fails at compile — the desirable outcome. The suite even
asserts a **heze** block with `inclusionListBits` flows through. The only codename coupling is
the pre-existing helper name `isGloasBeaconBlock` (types package, out of scope) and accurate
"post-Gloas" log strings that won't rot.

**API choice — right, stable surface; retry justified.** `block` SSE (fires on successful
`on_block` import, `events.ts:95`) + `getBlockV2`-by-root is the correct minimal way to learn
selection without libp2p; `head`/`block_gossip` would be wrong (gossip = pre-import, head =
fork-choice not import). `getBlockV2` is long-stable and returns versioned meta. The bounded
404/5xx retry (`blockObserver.ts:220-226`, `assertOk` throws `ApiError` with `.status`, verified)
is cheap read-after-write insurance and correctly excludes non-retryable `input`/4xx/decode/abort
errors.

**Tests — excellent.** Covers subscribe-only-to-block, non-block ignore, dedup (sequential +
in-flight concurrent), 404/5xx retry + exhaustion-retains-root, retryable classification, decode
failures (request/meta/value), abort-during-delay, pre-Gloas skip, meta pre-Gloas, body/meta
mismatch, slot mismatch, bounded-set eviction re-open, self-build sentinel, stream failure +
unexpected-close, concurrent callback dispatch + failure isolation, shared abort signal. Sibling
`builder.test.ts` asserts start ordering + abort-on-close.
