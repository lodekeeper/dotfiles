Reviewer: review-bugs
Reviewed commit: 1d2380582c

# PR #9931 "feat(builder): observe beacon node blocks" — correctness review

## Verdict

**No 🔴 blockers. No 🟡 must-fix logic bugs.** The core logic (`blockObserver.ts`) is
correct against the utilities it depends on, and the abort/retry/dedup/validation paths
all behave as the tests assert. This is an unusually well-tested PR. Findings below are
🟢 design/robustness notes, all of which fall inside the "recovery policies handled
separately" scope the code explicitly documents.

Every focus area was traced to the real definitions of `retry`, `pruneSetToMax`,
`isForkPostGloas`, `isGloasBeaconBlock`, `FetchError`, `ApiError`, `sleep`, the httpClient
abort handling, and the eventstream `onEvent`/`onClose` contract.

---

## Focus-area verification (all PASS)

**1. Seen-set marked before fetch (blockObserver.ts:104 before :112).**
Root is added to `seenBlockRoots` before retrieval. On terminal failure the root stays
"seen" until FIFO eviction, so the block is not re-fetched. This is *documented intent*
(class doc L28-33, method doc L52-55) and *asserted by tests* ("retains a root after
persistent not-found exhaustion" L187-200; "does not retry a request decoding failure"
L226-244). Accepted design, not a bug. See 🟢-1 for the consequence once consumers exist.

**2. Concurrency / dedup race — SAFE.**
`processBlockEvent` is fire-and-forget (`void`, builder path via `onEvent` L73). The dedup
gate is `seenBlockRoots.has()` (L99) + `.add()` (L104), both synchronous, before the first
`await` at L112. `onEvent` invocations are serialized by the single-threaded event loop, so
two same-root events cannot interleave between the has-check and the add. Confirmed by
"suppresses a concurrent duplicate while retrieval is in flight" (L143-158). No double-
process, no drop.

**3. Abort handling — CLEAN/SILENT on all three paths.**
- eventstream: `signal.abort` → EventSource `close` listener → `onClose` (events.ts:31-36),
  and observer's `onClose` (L78-84) logs *debug* when `signal.aborted`, error otherwise.
- retry-delay abort: `sleep(ms, signal)` rejects with `ErrorAborted` (sleep.ts:21-24) →
  propagates out of `retry` → `.catch` (L132) sees `isErrorAborted` → no log, returns null.
  Confirmed by "stops silently when aborted during a retry delay" (L246-261).
- in-flight `getBlockV2` abort: httpClient converts a user-signal abort to `ErrorAborted`
  (httpClient.ts:396-399) *before* it reaches the observer, and an internal timeout to
  `TimeoutError` (L400-401). So the observer never sees a raw FetchError "aborted".

**4. Retry classification — CORRECT (`isRetryableBlockRetrievalError` L220-226).**
- ApiError 404 / ≥500 → retry ✓; other 4xx (e.g. 400) → terminal ✓.
- `TimeoutError` → retry ✓ (this is what the httpClient throws on request timeout).
- FetchError with `type !== "input"` → retry ✓; `type === "input"` → terminal ✓.
  `"input"` is a real `FetchErrorType` (fetch.ts:22, set at fetch.ts:37-42 for URL/parse
  errors). Verified.
- Plain `Error` (decode failures) and `ErrorAborted` → terminal ✓ (neither is ApiError /
  TimeoutError / FetchError). Matches "classifies retryable retrieval errors" (L202-224).
- Note (not a bug): the `!== "input"` branch would also retry FetchError "aborted"/
  "timeout"/"unknown"/"failed", but on the `getBlockV2` path aborts arrive as `ErrorAborted`
  and timeouts as `TimeoutError`, so "aborted" never reaches this classifier in practice.

**5. Validation chain — no gap.**
Three gates before dispatch: meta version `isForkPostGloas(version)` (L148) → body shape
`isGloasBeaconBlock(block.message)` (L154) → slot match `block.message.slot === slot`
(L159). A block is dispatched only if all three agree; each mismatch is logged and dropped
(defends against beacon-node inconsistency). `isGloasBeaconBlock` checks
`signedExecutionPayloadBid !== undefined` (typeguards.ts:111-113), which is present in
gloas AND all post-Gloas forks, so a **heze** block correctly passes both `isForkPostGloas`
and `isGloasBeaconBlock` — confirmed by "preserves the exact fork-specific Heze signed bid"
(L110-127). No valid block wrongly dropped, no wrong block dispatched.

**6. Zero consumers — fine.**
`runOnBlock` is never called (builder.ts constructs `new BlockObserver(config, logger, api)`
with no consumer). `this.fns` is empty, `Promise.all([])` (L189) short-circuits. Every
post-Gloas block is fetched, validated, debug-logged, and discarded — intentional
incremental staging per the PR title. Not a bug. See 🟢-2.

Also verified: `retry` `retries: N` = N+1 attempts (retry.ts:39-40; tests expect
`{retries:2}`→3 calls, `{retries:1}`→2 calls) ✓; `pruneSetToMax` evicts oldest via
insertion-ordered `Set.keys()` (map.ts:97-104) → bounded FIFO ✓; `EventData[block]` =
`{slot, block: RootHex, executionOptimistic}` so `event.message`/`event.block` are the right
fields (events.ts:185-189, client onEvent events.ts:41) ✓; httpClient `DEFAULT_RETRIES = 0`
so no compounding with the observer's own retry ✓.

---

## 🟢 Findings (design / robustness — all within documented deferred scope)

### 🟢-1  Terminal fetch/decode failure permanently drops a bid observation (blockObserver.ts:104 / 143-145 / 206-216)
Because the root is marked seen before retrieval and stays seen on terminal failure, a
block whose `getBlockV2` fails non-retryably — most realistically a **decode failure** from
`.value()`/`.meta()` when the builder's SSZ types lag the beacon node across a fork, or a
non-retryable 4xx — is never observed. It won't re-emit (SSE doesn't replay) and is only
"reopened" after `maxSeenBlockRoots` (256) later roots evict it, by which point the event is
long gone. For a builder whose purpose is knowing whether its bid was selected, silently
missing a block's `signedExecutionPayloadBid` matters.

This is explicitly documented as out of scope ("Terminal failures remain consumed until
normal FIFO eviction; reconnect, replay, and recovery policies are handled separately",
L30-32) and there are zero consumers today, so it is **not a must-fix for this PR**. Flagging
so it is tracked before any consumer relies on complete observation. Suggested future
direction: on terminal (non-abort) failure, `seenBlockRoots.delete(blockRoot)` so a later
re-delivery / reconnect replay can retry, or add an explicit recovery path.

### 🟢-2  Observer does a `getBlockV2` round-trip per imported block with no consumer (builder.ts:60, blockObserver.ts:112)
Until a consumer is registered, each post-Gloas block triggers a full block fetch purely to
validate + debug-log + discard. That is real, continuous REST load on the beacon node for no
functional output yet. Intentional staging, but worth confirming the follow-up PR lands
before this ships to any long-running builder, or gating the fetch on `this.fns.length > 0`.

### 🟢-3  eventstream `onError` logs at error level for a self-recovering stream (blockObserver.ts:75-77)
`onError` logs `error("Failed to receive block event")` on every non-ECONNREFUSED/EAI_AGAIN
EventSource error. Per the client comment (events.ts:45-47) EventSource auto-reconnects and
`onerror` "doesn't indicate the EventSource closed", so a transient hiccup produces
error-level noise without necessarily indicating data loss. Log-level nit, not a correctness
bug. (Blocks missed during the reconnect gap are an inherent SSE limitation, also in the
"handled separately" scope.)

### 🟢-4  No resubscribe if initial `eventstream(...)` setup rejects (blockObserver.ts:86-92)
If the initial subscription promise rejects (e.g. `getEventSource()` or `new EventSource`
throws), it is logged once and the observer is permanently inert — EventSource's built-in
auto-reconnect only applies after the stream is established. Same documented deferred-scope
caveat; noting for the recovery follow-up.

---

## Tests
No test asserts wrong behavior. The suite is thorough and the assertions match the
implementation's real (and correct) semantics, including the intentional "retain root on
terminal failure" and "reopen after FIFO eviction" behaviors. The `getConfig(ForkName.gloas,
1)` pre-Gloas test (L303-310) is valid — it sets `GLOAS_FORK_EPOCH=1` so slot 0 is fulu
(config.ts:52-62).
