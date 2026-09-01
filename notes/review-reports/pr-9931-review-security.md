Reviewer: review-security
Reviewed commit: 1d2380582c

# PR #9931 — feat(builder): observe beacon node blocks — Security & Supply-Chain Review

## Verdict

- **Malicious / supply-chain risk: NO.** The diff is clean. No new dependencies, no
  suspicious hosts, no `eval`/`Function`, no base64/hex blobs, no env/secret access, no
  filesystem writes, no telemetry, no obfuscation, and no hidden build/CI/config changes.
- **🔴 DoS / security blockers: NO.** One 🟡 resource-exhaustion design gap worth
  addressing, plus two 🟢 defense-in-depth notes. None block merge.

## Scope reviewed

Full diff `git diff origin/unstable...HEAD` (base d79d81f994, head 1d2380582c). 5 files,
+850/-2. Every changed line reviewed including tests and `apiStub.ts`.

- `packages/builder/src/builder.ts` (M) — wires `BlockObserver` into `BuilderModules`,
  constructs it, starts it after the clock with the shared abort signal.
- `packages/builder/src/services/blockObserver.ts` (A, 226 LOC) — core.
- `packages/builder/test/unit/builder.test.ts` (A)
- `packages/builder/test/unit/services/blockObserver.test.ts` (A, 562 LOC)
- `packages/builder/test/unit/utils/apiStub.ts` (M, +4) — adds `getBlockV2` +
  `events.eventstream` vi.fn() stubs. Benign.

## 1. Supply-chain / malicious-code assessment — CLEAN

- **Imports (blockObserver.ts:1-5):** every symbol is from an existing `@lodestar/*`
  package. Verified each is a real, pre-existing export (not fabricated):
  - `@lodestar/utils`: `retry` (retry.ts:37), `pruneSetToMax` (map.ts:88),
    `TimeoutError` (errors.ts:54), `isErrorAborted` (errors.ts:63),
    `isFetchError` (fetch.ts:18), `toRootHex`, `Logger`.
  - `@lodestar/params`: `isForkPostGloas` (forkName.ts:128), `ForkPostGloas`,
    `BUILDER_INDEX_SELF_BUILD` (index.ts:371, = Infinity).
  - `@lodestar/types`: `isGloasBeaconBlock` (typeguards.ts:111), `SignedBeaconBlock`,
    `RootHex`, `Slot`, `ssz`.
  - `@lodestar/api`: `ApiClient`, `ApiError`, `routes` — `getBlockV2` (block.ts:82),
    `eventstream` (events.ts:269), `EventType.block` (events.ts:96).
- **Network calls:** only `this.api.beacon.getBlockV2(...)` and
  `this.api.events.eventstream(...)`. Both go through the injected `ApiClient`, i.e. the
  operator's own configured beacon node. No hard-coded hosts, URLs, or IPs. No new
  inbound listener, no libp2p, no external peers.
- **No hidden changes:** `git diff --name-status` shows only the 5 files above. No
  `package.json`, lockfile, `.github/`, tsconfig, `.npmrc`, Dockerfile, or shell script
  touched. (A filename grep appears to "match" lock/config — false positive on the
  substring "lock" inside "b**lock**Observer".)
- **No dynamic code / encoding / secret access:** none present. Test helper `rootBytes`
  builds deterministic 32-byte fill arrays — not a payload.

## 2. Findings

### 🟡 F1 — Fire-and-forget event handling has no concurrency bound or slot-proximity gate
`blockObserver.ts:73` (`void this.processBlockEvent(event.message, signal)`), dispatch
loop `blockObserver.ts:95-217`, retry `112-141`.

**Mechanism.** The SSE `block` topic is driven entirely by the beacon node. `onEvent`
fires `processBlockEvent` as `void` with no semaphore, queue cap, or backpressure. The
`seenBlockRoots` dedup (`162-168`) is applied synchronously before the first `await`, so
duplicate roots are correctly collapsed to one in-flight fetch (good). **But each
*distinct* post-Gloas root spawns an independent `getBlockV2` retry chain of up to 6
requests** (`retries: 5` + initial; `retryDelay` is a *fixed* 200 ms — confirmed in
utils/retry.ts, not exponential). There is also **no check that the event slot is near
the current clock** — any slot the local config maps to a post-Gloas fork is processed.

**Failure scenario.** A compromised, buggy, or overloaded BN (or a duplicating proxy, or
a reconnect that replays a large history) that emits many *distinct* block roots in a
burst causes:
- unbounded concurrent in-flight `getBlockV2` promise chains + retained closures /
  `ObservedBlock` refs in the builder process (memory + socket/FD pressure), and
- up to 6× amplified request load back onto the same BN.

The 256-entry `seenBlockRoots` bounds only the *dedup set's* memory; it does **not** bound
distinct-root throughput — roots evict FIFO out of the 256 window and can be re-fetched
(the PR's own "reopens the oldest root after bounded-set eviction" test confirms this). So
"is the 256-root set the only growth bound, and is it actually bounded?" → the set is
bounded, but it is *not* a bound on concurrency or on aggregate work over time.

**Why 🟡, not 🔴.** The only source is the operator's own configured BN — a semi-trusted
component. A compromised BN already fully controls the builder's chain view (false bids,
censorship), so exhausting the builder process is strictly *less* than what it can already
do; this vector does not expand an external attacker's reach (no new inbound surface).
Under honest operation the `block` event fires ~once per slot and the mechanism is fully
bounded (dedup + 256 cap + 6-retry cap). And no consumers are registered in this PR
(`this.fns` is empty repo-wide → `Promise.all([])` is a no-op), so dispatched work is
currently trivial.

**Mitigation (defense-in-depth, before consumers are wired in future PRs):** cap
in-flight `processBlockEvent` work with a small bounded-concurrency queue/semaphore
(drop or coalesce beyond the cap), and/or gate on slot proximity to the clock (ignore
events whose slot is far from `now`). Per-root retry is already well-bounded; the gap is
aggregate concurrency.

### 🟢 F2 — No hash-tree-root verification that the returned block matches the requested root
`blockObserver.ts:112-166`.

The observer fetches `getBlockV2({blockId: blockRoot})` and validates version
(`isForkPostGloas`), body shape (`isGloasBeaconBlock`), and `block.message.slot === slot`
before handing the **exact-reference** `signedExecutionPayloadBid` to consumers
(`169-177`). It does **not** verify `HTR(block) === blockRoot`. A dishonest BN could return
a different block (different bid) whose slot happens to match, and the consumer would pair
the requested `blockRoot` with a swapped bid. Within the "trust your own BN" model this is
acceptable (getBlockV2-by-root is defined to return that block), and no consumer acts on
the bid yet. Worth adding an HTR check as defense-in-depth once consumers make
value/economic decisions on `signedBid`.

### 🟢 F3 — Error logs may surface the beacon-node URL (possible inline credentials)
`blockObserver.ts:87-91, 133-139, 75-77`.

The three error logs pass the raw error object. For a `FetchError` the message embeds the
request URL (see test at blockObserver.test.ts:554). If an operator configured the BN
endpoint with inline basic-auth (`https://user:pass@host`), that could appear in logs.
This is pre-existing Lodestar behavior, not introduced here, and the URL is the operator's
own config — informational only. No signer keys, auth tokens, or other secrets are logged;
all bid/root/slot fields logged (`179-187`) are public chain data.

## 3. Questions from the brief — direct answers

- **Q2 unbounded concurrent getBlockV2 / memory?** Yes for *distinct* roots (F1); same-root
  duplicates are correctly collapsed. 256 set bounds dedup memory only, not concurrency.
- **Q2 retry amplification bounded?** Yes per root: 1 + 5 retries = 6 requests over ~1 s,
  fixed 200 ms delay. Under an all-404/503 BN this is 6× per distinct root — tiny under
  honest operation (~1 root/slot); the multiplier only matters combined with F1's burst.
- **Q2 `this.fns` / promise growth?** `this.fns` grows only via `runOnBlock` at setup
  (no attacker input; empty in this PR). Promise accumulation is the F1 concern.
- **Q3 validation sufficient before handing off signedBid?** Yes for shape/version/slot
  (bid access is guarded by `isGloasBeaconBlock`); missing only the HTR check (F2). A
  malformed BN response cannot crash — see Q4.
- **Q4 unhandled rejection / crash path?** None found. `start()` `.catch()`es the
  eventstream promise (86-92). `processBlockEvent` wraps its *entire* body in try/catch
  (95-216); the per-consumer `Promise.all` map each has its own try/catch (190-204), so it
  never rejects. Therefore `void`-ing it (73) is safe — no rejection can escape to crash
  the process. This is a correct fire-and-forget.
- **Q5 info leak in logs?** Only the low F3 URL note. Bids/roots/slots are public.

## 4. Positives

- Fire-and-forget is unhandled-rejection-safe (fully wrapped).
- Abort signal is threaded through eventstream, `getBlockV2`, and the retry `sleep`;
  aborted errors are silently swallowed everywhere (no shutdown log noise).
- Dedup window genuinely bounded (FIFO, 256) and applied pre-await (race-safe for
  same-root concurrency).
- Strong validation ladder before dispatch: post-Gloas version guard, body typeguard,
  and event-vs-block slot consistency.
- Retryable-error classifier is conservative (404/≥500/timeout/non-input fetch only) and
  well-tested; 4xx-input and decode errors are correctly non-retryable.
- Extensive, adversarial unit tests (562 LOC) covering duplicates, concurrency,
  exhaustion, abort-mid-delay, decode failures, fork mismatch, slot mismatch, eviction.
