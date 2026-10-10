# Lodestar `notifyNewPayload` timing: why the metric dropped in v1.50.0-rc.0, and what it was measuring

Notes by [@lodekeeper](https://github.com/lodekeeper), 2026-10-10.

**Code read at:**
- v1.45.0 `6051fa333`
- v1.49.0 `b1dee246f`
- v1.50.0-rc.0 `78b217eea`

**Data:** Lodestar's Prometheus on Hoodi nodes paired with geth `1.17.8-stable`. Geth has no SSZ engine API, so every engine call in these windows went over JSON-RPC: 6,212 of 6,212 in 6 h, per `engineApiRequests{transport}`.

## TL;DR

- After upgrading to v1.50.0-rc.0, the mean `notifyNewPayload` roundtrip on a Hoodi beta node dropped from about 281 ms to about 182 ms (median 305 → 161 ms).
- **The request did not get faster.** The timer now starts later.
  - Since [#10204](https://github.com/ChainSafe/lodestar/pull/10204), engine calls first go through `await this.getTransport()`, which yields.
  - So `requestTime.startTimer()` now runs *after* the synchronous state transition (STF) that is started in the same tick.
  - Before, the timer started *before* the STF.
- **The request body reaches the socket after the STF in both versions.** That is [#10188](https://github.com/ChainSafe/lodestar/issues/10188), which is still open.
  - The EL sits idle while we run the STF.
  - The old metric included that wait; the new one hides it.
- **Import latency did not improve.** Gossip block received → processed was 440 → 447 ms on the same node, and 445 → 454 ms on a v1.49 control node.
- **StereumLabs' 181–208 ms caller-side gap** ([report](https://docs.stereumlabs.com/blog/where-the-slot-goes-six-instruments)) is the same effect measured on v1.45.0. It comes mostly from the STF running between timer start and the request reaching the socket, not from JSON encoding.

---

## 1. The observation

A Hoodi beta node was upgraded from v1.49.0 to v1.50.0-rc.0 at 2026-10-09 21:59:55 UTC.

Before: 10-09 18:00–21:55. After: 10-09 22:40 – 10-10 06:00.

| Metric | v1.49.0 | v1.50.0-rc.0 |
|---|---|---|
| Lodestar `notifyNewPayload` roundtrip, mean (`execution_engine_http_client_request_time_seconds`) | 281 ms | 182 ms |
| same, median (histogram) | 305 ms | 161 ms |
| same, p90 | 479 ms | 463 ms |
| geth `engine_newPayloadV4` handler (`rpc_duration_engine_newPayloadV4_success`, decaying summary) | ~112 ms | ~104 ms |
| geth `chain_execution` p50 | 104 ms | 104 ms |
| geth `chain_inserts` p50 | 115 ms | 116 ms |
| Lodestar gossip block STF mean (`gossip_block_state_transition_time`) | 85 ms | 87 ms |
| Lodestar `stfn_process_block_seconds` mean | 68 ms | 70 ms |
| Lodestar block processor job time mean | 227.6 ms | 227.4 ms |
| `notifyNewPayload` calls/min | 4.49 | 4.47 |

Notes on the table:
- Geth was already on 1.17.8 since 10-09 00:00, so the EL did not change in this window.
- The EL's own handler time is flat, our STF is flat, and the total block job time is flat. Only the caller-side roundtrip moved.
- The median dropped about 145 ms while p90 barely moved. The p90 is dominated by blocks where the EL itself is slow.

**Gossip block received → processed, mean** (before: 10-08 00:00 – 10-09 21:55; after: 10-09 23:00 – 10-10 14:00):

| Node (Hoodi) | Version change | Before | After |
|---|---|---|---|
| beta node A (the one above) | 1.49.0 → rc.0 | 440.5 ms | 446.8 ms |
| beta node B | 1.49.0 → rc.0 | 394.5 ms | 375.2 ms |
| beta node C | 1.49.0 → rc.0 | 556.3 ms | 527.9 ms* |
| stable node (control) | 1.49.0, unchanged | 445.2 ms | 454.4 ms |

\* Node C also restarted into a different GC regime (Scavenge pause rate 0.70% → 0.52%). On these "subscribe all subnets" nodes that regime flips from restart to restart regardless of commit, so its delta isn't attributable to code.

If newPayload were now reaching the EL before the STF, received → processed should drop by about the STF time (~85 ms) for blocks where the EL is the last import prerequisite. It doesn't.

---

## 2. Why the timer moved

`verifyBlocksInEpoch` starts payload verification first. In the same synchronous run, it then calls `verifyBlocksStateTransitionOnly`, which runs the STF before its first `await` ([verifyBlock.ts L104](https://github.com/ChainSafe/lodestar/blob/78b217eeaa678ebf92641f397545928865c233c1/packages/beacon-node/src/chain/blocks/verifyBlock.ts#L104), [L179-L186](https://github.com/ChainSafe/lodestar/blob/78b217eeaa678ebf92641f397545928865c233c1/packages/beacon-node/src/chain/blocks/verifyBlock.ts#L179-L186)):

```ts
] = await Promise.all([
  verifyExecutionPayloadsPromise,   // already started above
  daAvailabilityPromise,
  // Run state transition only
  // TODO: Ensure it yields to allow flushing to workers and engine API
  verifyBlocksStateTransitionOnly(...)   // stateTransition() runs synchronously, first await is after it
```

What matters is how far the newPayload call gets *synchronously* before the STF takes the main thread.

### v1.45.0 / v1.49.0: the timer starts before the STF

The call chain is synchronous all the way down to the timer:

```
notifyNewPayload()
→ rpcFetchQueue.push()          # noYieldIfOneItem: true → runJob() called synchronously
→ jobQueueProcessor
→ fetchWithRetries → retry → fetchJson
→ fetchJsonOneUrl
→ requestTime.startTimer()      # timer starts here, still in the same tick
→ fetch()                       # body is written on a later event-loop turn
```

Code refs at v1.49.0:
- [http.ts L167-L170](https://github.com/ChainSafe/lodestar/blob/b1dee246fe68fc5f0242fa91ad41a2a8a88ef4f3/packages/beacon-node/src/execution/engine/http.ts#L167-L170): the queue is created with `noYieldIfOneItem: true`.
- [http.ts L277](https://github.com/ChainSafe/lodestar/blob/b1dee246fe68fc5f0242fa91ad41a2a8a88ef4f3/packages/beacon-node/src/execution/engine/http.ts#L277): `rpcFetchQueue.push(engineRequest)`.
- [itemQueue.ts L69](https://github.com/ChainSafe/lodestar/blob/b1dee246fe68fc5f0242fa91ad41a2a8a88ef4f3/packages/beacon-node/src/util/queue/itemQueue.ts#L69): `if (this.jobs.length === 1 && this.opts.noYieldIfOneItem) void this.runJob()`.
- [jsonRpcHttpClient.ts L249](https://github.com/ChainSafe/lodestar/blob/b1dee246fe68fc5f0242fa91ad41a2a8a88ef4f3/packages/beacon-node/src/execution/engine/jsonRpcHttpClient.ts#L249): `const timer = this.metrics?.requestTime.startTimer({routeId})`.

v1.45.0 has the same path (`noYieldIfOneItem: true` at [http.ts L167](https://github.com/ChainSafe/lodestar/blob/6051fa3335c3dadf3f99292a8fe345ccd69121f7/packages/beacon-node/src/execution/engine/http.ts#L167), timer at [jsonRpcHttpClient.ts L249](https://github.com/ChainSafe/lodestar/blob/6051fa3335c3dadf3f99292a8fe345ccd69121f7/packages/beacon-node/src/execution/engine/jsonRpcHttpClient.ts#L249)).

**What happens next:** the timer is running, `fetch()` has been called, and the STF runs synchronously. The request body only reaches the socket after the STF returns and the event loop turns. The measured roundtrip therefore covers:
- the STF and any other synchronous work in that tick;
- the request write;
- the EL's processing;
- waiting for the main thread to pick up the response.

### v1.50.0-rc.0: the timer starts after the STF

[#10204](https://github.com/ChainSafe/lodestar/pull/10204) (SSZ engine API over REST, merged 2026-10-09) puts every call behind a transport selector:

```
notifyNewPayload()
→ enqueue()                       # same JobItemQueue, noYieldIfOneItem: true → job() called synchronously
→ withTransport()
→ await this.getTransport()       # yields here; in "auto" mode with one URL this awaits probeRestSupport()
   ... the STF runs on the main thread ...
→ (microtask, after the STF) jsonRpc.newPayload() → serializeExecutionPayload → fetchWithRetries
→ requestTime.startTimer()        # timer starts here
→ fetch()
```

Code refs at v1.50.0-rc.0:
- [http.ts L164-L168](https://github.com/ChainSafe/lodestar/blob/78b217eeaa678ebf92641f397545928865c233c1/packages/beacon-node/src/execution/engine/http.ts#L164-L168): queue.
- [http.ts L244-L246](https://github.com/ChainSafe/lodestar/blob/78b217eeaa678ebf92641f397545928865c233c1/packages/beacon-node/src/execution/engine/http.ts#L244-L246): `enqueue(() => withTransport(...))`.
- [http.ts L435-L441](https://github.com/ChainSafe/lodestar/blob/78b217eeaa678ebf92641f397545928865c233c1/packages/beacon-node/src/execution/engine/http.ts#L435-L441): `const transport = await this.getTransport(fork, blobsRevision)`.
- [http.ts L478-L482](https://github.com/ChainSafe/lodestar/blob/78b217eeaa678ebf92641f397545928865c233c1/packages/beacon-node/src/execution/engine/http.ts#L478-L482): `await this.probeRestSupport(this.rest)`.
- [jsonRpcTransport.ts L55](https://github.com/ChainSafe/lodestar/blob/78b217eeaa678ebf92641f397545928865c233c1/packages/beacon-node/src/execution/engine/jsonRpcTransport.ts#L55): payload serialization now happens inside the job.
- [jsonRpcHttpClient.ts L250](https://github.com/ChainSafe/lodestar/blob/78b217eeaa678ebf92641f397545928865c233c1/packages/beacon-node/src/execution/engine/jsonRpcHttpClient.ts#L250): timer.

**Consequences:**
- The timer starts after the STF, so the metric now reads closer to EL time plus transport and response pickup.
- The request still reaches the socket after the STF. If anything it now also *starts* (serialize + `fetch()`) after the STF rather than before.
- The about 145 ms that left the median is roughly the synchronous STF tick (STF mean about 85 ms, plus whatever else ran before the event loop turned).

---

## 3. #10188 is not fixed

[#10188](https://github.com/ChainSafe/lodestar/issues/10188) (wemeetagain, 2026-09-26, open, no linked PR) measured this directly on 4 Hoodi nodes and 1 mainnet node:
- The newPayload body was on the wire before the STF started in **0%** of blocks.
- It was written 73–83 ms after the STF started, i.e. right when the STF finished.
- The EL was the last import prerequisite for 33–52% of blocks on Hoodi and 92% in one mainnet window. For those blocks the EL's idle time adds directly to import latency.

On `unstable` (`b726a05a4`, 2026-10-09) the `// TODO: Ensure it yields to allow flushing to workers and engine API` is still above the STF call, and the STF still runs before its first `await`. rc.0 changed what the metric measures, not when the request is sent.

**Options listed in the issue:**
- write the body without yielding to arbitrary queued work;
- send newPayload once gossip validation accepts the block;
- move the STF off the main thread. wemeetagain is planning "native STF in a promise".

---

## 4. The StereumLabs caller-side gap

[Where the slot goes: six instruments, calibrated](https://docs.stereumlabs.com/blog/where-the-slot-goes-six-instruments) (StereumLabs, 6 CL × 6 EL on identical 12-core bare-metal hosts, mirrored validator traffic) compared each CL's engine timer with the EL's own server-side handler timer over the same calls.

**Their method:**
- **Lodestar side:** v1.45.0, window 2026-08-07 → 08-10, mean of `lodestar_execution_engine_http_client_request_time_seconds{routeId="notifyNewPayload"}` from `_sum`/`_count`.
- **EL side:** the handler timers of Ethrex, Besu, Nethermind and Erigon, each with a `_sum`/`_count`. Geth was excluded because it only exports a decaying summary.
- **Gap = CL mean − EL mean.** Call counts matched within one call per pairing.

**Their result:**

| EL | EL handler | Lodestar | Gap |
|---|---|---|---|
| Ethrex | 164.8 ms | 372.6 ms | ~208 ms |
| Besu | 270.8 ms | 466.9 ms | ~196 ms |
| Nethermind | 363.4 ms | 557.7 ms | ~194 ms |
| Erigon | 397.8 ms | 579.1 ms | ~181 ms |

For comparison, the same gap on other CLs: Lighthouse 6–34 ms, Grandine 7–32 ms, Prysm 10–43 ms, Nimbus 19–50 ms.

**What they ruled out, and what they guessed:**
- Ruled out: queue wait (0.33 ms), reading the response (0.14 ms), and the SSZ transport (unused).
- Guessed, without claiming it: JSON encoding of the block body, because the gap "scales with request size". In practice that is newPayload versus forkchoiceUpdated: Lodestar's fcU gap is 31–42 ms against Lighthouse's 4–6 ms.

**Our reading:**
- **On v1.45.0 the timer started before the synchronous STF** (§2), so most of the gap is the STF tick, not encoding.
- **Our own Hoodi numbers line up with theirs.**
  - On v1.49.0, Lodestar 305 ms vs geth's handler ~112 ms is a gap of about 190 ms, inside their 181–208 ms band.
  - On rc.0, where the timer starts after the STF, it is 161 vs ~104 ms, about 57 ms.
  - Medians vs geth's summary aren't strictly comparable to their means, but the size matches.
- **The remaining ~57 ms** is still caller-side main-thread time: serialization, `fetch` setup, and response pickup when the main thread is busy. It hasn't been broken down yet.
- **The fcU gap is probably the same effect** (hypothesis, not verified). `importBlock` fires fcU without awaiting it and keeps doing synchronous work afterwards. So the timer measures how busy the main thread is after the call more than the size of the request.

The underlying cost they found is real. It is #10188 (the EL idle during our STF), plus main-thread contention on the response path. It just isn't serialization.

---

## 5. Suggested follow-ups

1. **Fix #10188.** Get the newPayload body on the wire before or in parallel with the STF.
2. **Add a "call → request written" timer** (or "call → first byte sent"), so that we keep seeing the STF penalty that the old metric showed by accident. Ideally also a "response received → handler resumed" timer for main-thread pickup.
3. **Note the semantic change in the rc.0 release notes and dashboards.** `notifyNewPayload` roundtrips from ≤ v1.49 and ≥ v1.50 are not comparable. Pre-v1.50 numbers include the STF.
