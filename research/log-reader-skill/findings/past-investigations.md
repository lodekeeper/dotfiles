# Past Investigation Analysis — Log Reading Patterns

**Date:** 2026-03-21
**Author:** Lodekeeper (subagent: log-research-past-investigations)
**Purpose:** Extract log-access patterns and lessons from real investigations to inform log reader skill design.

---

## Overview

Seven distinct investigations were analyzed, drawn from:
- `memory/2026-03-20.md`, `memory/2026-03-17.md`, `memory/2026-03-14.md`
- `notes/memory-leak-8969-feat1-super-2026-03-10.md`
- `notes/epbs-devnet-0/TRACKER.md` and `RESEARCH.md`
- `notes/epbs-state-restart/TRACKER.md`
- `notes/epbs-withdrawals-regression/TRACKER.md`
- `notes/epbs-envelope-reqresp-investigation.md`
- `notes/fork-choice-metrics-report.md`
- `notes/v8-ptr-compress-metrics-latest.md`
- `MEMORY.md` (lessons section)

---

## Investigation 1: Sync Aggregate Bug — Bad Participation in Small Devnets (Issue #8294)

**Date:** 2026-03-20
**Type:** Protocol bug (gossip deduplication + pool indexing)

### What was being investigated?
Blocks produced by Lodestar in small devnets (64 validators) consistently showed ~64% sync aggregate participation instead of 100%. Issue traced to two independent gossip-layer bugs.

### How were logs accessed?
1. **Loki** — Queried `lodestar_oppool_sync_contribution_and_proof_pool_get_aggregate_returns_empty_total` metric via Grafana/Loki. Narrowed to `feat2` group (only non-zero instances). Retrieved 9 specific log events from last 7 days.
2. **Prometheus via Grafana** — Queried metric counters to confirm which node groups were affected.
3. **Kurtosis service logs** — Spun up 4-node local devnet (`kurtosis run`), observed `512/512` vs `328/512` participation counts per block in node output.
4. **Python simulation** — Modeled the statistical distribution of both bugs across 10,000 trials before deploying any containers.

### What worked?
- **Loki pattern A/B classification**: Breaking down 9 log events into "empty pool" vs "root mismatch" immediately clarified that two different failure modes existed. Without this classification, the investigation might have chased only one.
- **Prometheus metric drilling**: `lodestar_oppool_sync_*_returns_empty_total` being zero on mainnet/holesky but non-zero on `feat2` immediately scoped the investigation to PeerDAS/Hoodi behavior.
- **Kurtosis rapid reproduction**: 4-node devnet reproduced the exact participation number (64.1% vs issue-reported 63.87%) within one run — confirming the bug was deterministic.
- **Simulation before Kurtosis**: Mathematical modeling correctly predicted participation percentages before any containers were deployed, saving multiple iteration cycles.
- **Context log correlation**: In Loki, reading context logs around the exact problem slot (2643619) revealed `recvToValLatency=23.6s` and `expectedColumns=128`, pointing to PeerDAS backpressure as Pattern A's root cause.

### What failed or was inefficient?
- Initial investigation (Issue #7299) was later redirected (Issue #8294) — two separate issues with similar symptoms. Having a single unified Loki query that distinguished "empty pool" vs "root mismatch" upfront would have saved time.
- The "message pool merge" fix was implemented, Kurtosis-validated, and then stripped — extra work because the fix wasn't needed once both gossip bugs were resolved. Simulation should have been run earlier to predict this outcome.

### Most useful log patterns?
- **Named metric counter with non-zero filter**: `returns_empty_total > 0` immediately identifies affected groups.
- **Context window around error event**: Reading ±5 log lines around the anomalous slot revealed the actual delay chain (PeerDAS column processing backlog → head stuck → missed gossip).
- **Timing correlations**: `recvToValLatency=23.6s` was the single most diagnostic field — it explained the entire Pattern A failure chain.
- **Participation ratio per block**: Simple `bits_set / total_bits` from Kurtosis output was a reliable, observable invariant.

---

## Investigation 2: Memory Leak — feat1-super Network Thread (2026-03-10 to 03-12)

**Date:** 2026-03-10 to 2026-03-12
**Type:** Memory leak (native/V8 heap growth in network worker thread)

### What was being investigated?
`network_worker_nodejs_heap_space_size_used_bytes{space="old"}` showing multi-day linear growth on `feat1-super`. Suspected leak in network worker (separate thread from main beacon process).

### How were logs accessed?
1. **Prometheus via Grafana** — Polled `heap_space_size_used_bytes{space="old"}` every 30 minutes with hourly gate decisions. Custom Python sampler running as background exec session, writing to `tmp/feat1-super-heap/postfix-verify/*.log`.
2. **Heap snapshots via REST API** — `POST /eth/v1/lodestar/write_heapdump?thread=network&dirpath=/tmp` to capture 3 snapshots on the live remote host. Files retrieved via `scp` to `~/.openclaw/workspace/tmp/feat1-super-heap/`.
3. **Local repro** — Ran a synthetic instrumented loop with `AbortSignal.add/removeEventListener` tracking to validate the fix without requiring production traffic.
4. **Retainer chain analysis** — Parsed heap snapshots with custom tooling to extract constructor counts, retainer chains, and edge patterns (`retainers-WeakRef.txt`, `chains-AbortSignal.txt`, etc.)

### What worked?
- **Prometheus slope as primary signal**: Measuring `old` space MB/h slope per hourly gate was the only reliable way to distinguish real leaks from GC noise. Point-in-time values were unreliable.
- **Consecutive-window confirmation gate**: Requiring 2+ consecutive positive-slope windows before escalating prevented false positives from GC pause oscillation. This gate design was critical.
- **Constructor-level heap diff**: Diffing heap snapshots at T0/T+20/T+40/T+60 intervals revealed `WeakRef +17252`, `WeakCell +8664` over 60 minutes as the dominant growth pattern — directly identifying `AbortSignal` composition retention.
- **Retainer chain files**: `chains-WeakRef.txt` showing `sourceSignalRef/composedSignalRef → WeakRef` fanout immediately identified the code path (`@libp2p/utils repeating-task.ts`).
- **A/B local synthetic test**: Before/after listener count comparison (`add=220, remove=0` → `add=216, remove=216`) confirmed the fix works without needing a production deploy.

### What failed or was inefficient?
- **Oscillatory signal**: The metric oscillated significantly, causing multiple false escalation/downgrade cycles over 24+ hours. A single "is it going up?" question took 15+ hourly gate decisions to answer definitively.
- **Session continuity loss**: Monitor sessions stalled mid-run at 16:06 UTC (sampler stopped), requiring manual restart and one-shot samples to close the gate window. Critical monitors should not rely on long-lived exec sessions.
- **Initial req/resp patch was insufficient**: First deployed fix (clearable signals in reqresp) showed partial improvement but didn't stop the leak. Post-deploy monitoring revealed the primary driver was elsewhere. This wasted several hours of deploy + monitor time.
- **Heap snapshot size**: Full-process snapshots were too large for the analyzer. Had to pivot to network-thread-only snapshots. Should default to thread-specific snapshots for thread-local leaks.

### Most useful log patterns?
- **`heap_space_size_used{space="old"}` slope over ≥1h window** — the single most reliable leak indicator.
- **Constructor count diff between snapshots** — `WeakRef`, `WeakCell`, `Listener`, `AbortSignal` count increases point directly at retention pattern.
- **Retainer chain signature** — `sourceSignalRef/composedSignalRef → WeakRef` fanout was unique to this leak and absent in the patched version.
- **Socket count correlation**: `sockets 208 → 21` at restart time confirmed anchor point for post-deploy measurement window.

---

## Investigation 3: EPBS Devnet-0 — Chain Stall After Slot Transition

**Date:** 2026-02-21
**Type:** Interop protocol bug (fork choice stale hash, unknown-parent sync failure)

### What was being investigated?
Lodestar+Lighthouse+Geth Kurtosis devnet stalling after slot ~49: Lodestar produced slot 33, then couldn't import Lighthouse blocks from slot 34 onward. Error: `PARENT_UNKNOWN` with `parentInForkChoice=false`.

### How were logs accessed?
1. **Kurtosis service logs** — `kurtosis service logs <enclave> <service-name> --follow` to stream live logs from individual nodes.
2. **Targeted diagnostic logging** — Added temporary `logger.warn` statements in `validateGossipBlock` and `gossipHandlers.ts` to surface `PARENT_UNKNOWN` diagnostic with specific context.
3. **Geth logs** — Observed `Ignoring beacon update to old head` in Geth execution client logs, which was the first signal pointing to stale FCU hash.
4. **Prometheus metrics** — `unknown_parent` counter increasing confirmed that unknown-parent sync was being triggered (but failing).
5. **Error message parsing** — `UnknownBlockSync processBlock failed slot=34 ... errCode=BLOCK_ERROR_BEACON_CHAIN_ERROR` with nested cause `Parent block hash ... does not match state's latest block hash` gave the exact state inconsistency.

### What worked?
- **EL (Geth) log inspection**: `Ignoring beacon update to old head` in Geth logs was the earliest signal — it appeared before Lodestar logs made the cause obvious.
- **Targeted in-code diagnostics**: Adding `PARENT_UNKNOWN diagnostic` log with `parentInForkChoice=false` in `validateGossipBlock` immediately confirmed the exact failure condition.
- **Nested error cause extraction**: The error chain `BLOCK_ERROR_BEACON_CHAIN_ERROR → Parent block hash ... does not match` was only visible when full error context was printed — truncated errors would have missed it.
- **Kurtosis multi-service observation**: Being able to stream Lodestar + Lighthouse + Geth logs simultaneously allowed correlation across the consensus/execution client boundary.
- **Soak monitor (slot 40→136)**: Running a structured soak with specific error counters confirmed zero occurrences after fix: `ISR=0/0`, `UnknownBlockSync=0/0`.

### What failed or was inefficient?
- **Multiple Kurtosis restarts**: The investigation required 6+ enclave restarts, each with a 5-10 minute rebuild+deploy cycle. More upfront logging would have reduced iterations.
- **Deferred retry workaround**: Added `scheduleDeferredEnvelopeImport` retry worker as a temporary fix, which worked but masked the root cause. A proper event-driven pipeline was needed (designed separately in `epbs-envelope-reqresp-investigation.md`).
- **Resource contention**: 3×LH + 3×LS topology failed three times with `service has Docker resources but not a container` race — had to downgrade to 2×2 lean topology. Kurtosis devnets need headroom.
- **Ephemeral log loss**: After `kurtosis enclave rm`, all container logs are gone. Key findings must be extracted and written during the investigation.

### Most useful log patterns?
- **Execution client (Geth) "Ignoring beacon update to old head"** — earliest cross-layer signal of stale FCU hash.
- **`errCode=BLOCK_ERROR_*`** — Lodestar's structured error codes for gossip block validation failures.
- **`parentInForkChoice=false`** — custom diagnostic that pinpointed the exact failure condition.
- **Nested error chain** — `BLOCK_ERROR_BEACON_CHAIN_ERROR` wrapping the actual state consistency failure.
- **Soak monitor counters** (ISR, UnknownBlockSync, publishBlock errors, payloadId=null) as acceptance criteria.

---

## Investigation 4: feat3 / blst-z Native Memory Leak (2026-03-20)

**Date:** 2026-03-20
**Type:** Native memory leak in Zig NAPI bindings

### What was being investigated?
RSS growing linearly on all feat3 nodes (blst-z PR #248) while V8 heap and external memory stayed flat. Growth rate correlated with BLS workload (custody group count), pointing to missing `napi_adjust_external_memory` calls in Zig NAPI bindings.

### How were logs accessed?
1. **Prometheus via Grafana** — Queried `process_resident_memory_bytes`, `nodejs_heap_size_used_bytes`, and `nodejs_external_memory_bytes` for feat3 vs unstable groups.
2. **Time series comparison** — 12h vs 48h RSS values to compute growth rate per node type.
3. **Metric correlation** — Cross-referenced RSS growth rate with custody group count per node.
4. **Code-level analysis** — Traced the NAPI binding code path (`blst.zig:Signature_ctor`) to identify missing `napi_adjust_external_memory` calls.

### What worked?
- **Three-metric combination (RSS + V8 heap + external memory)**: V8 heap flat while RSS grows linearly immediately ruled out JS-layer leaks and pointed to native allocations.
- **Growth rate per workload group**: Comparing `semi` (64 custody, 42 MB/h) vs `super` (128, 75 MB/h) vs `sas` (validator+128, 223 MB/h) confirmed leak was per-BLS-operation.
- **Baseline comparison (unstable group)**: `unstable-semi` oscillating with no trend was the critical control — it ruled out the application code and pointed to the zig bindings.

### What failed or was inefficient?
- Unstable nodes had restarted ~12h ago vs feat3's 55h uptime, making direct RSS comparisons misleading. Uptime normalization was necessary.
- `unstable-sas` was stalled (sync_status=0) during analysis, making it an invalid comparison target.

### Most useful log patterns?
- **RSS trend over time** (slope, not absolute value).
- **V8 heap flat + RSS growing = native leak** — two-metric pattern is a reliable diagnostic shortcut.
- **Growth rate per workload dimension** — BLS sigs/slot × 192 bytes predicted actual MB/h within noise bounds.

---

## Investigation 5: EPBS State Restart Crash (2026-03-07)

**Date:** 2026-03-07
**Type:** Node crash on restart (`headState does not exist`)

### What was being investigated?
Lodestar crashed on restart in EPBS (Gloas) devnet with `headState does not exist` error. Also: finalized API returning wrong state bytes vs checkpoint-sync endpoint.

### How were logs accessed?
1. **Live devnet logs** — Checkpoint sync + restart cycle on local Kurtosis devnet connected to `checkpoint-sync.epbs-devnet-0.ethpandaops.io`.
2. **API response comparison** — `curl` the finalized state endpoint and compare bytes with checkpoint endpoint response.
3. **Code path tracing** — Read `chain.ts` and `forkChoice/index.ts` to trace anchor state construction logic.

### What worked?
- **Direct checkpoint sync URL as ground truth**: Comparing local API output against the public checkpoint URL gave an immediate binary pass/fail signal.
- **Targeted regression tests**: After fix, wrote targeted unit tests for fallback paths — served as both documentation and regression guards.

### What failed or was inefficient?
- The crash error (`headState does not exist`) was generic and didn't immediately indicate which code path failed. Required careful tracing of `anchorPayloadPresent` construction logic.

### Most useful log patterns?
- **Crash error message with exact field name** — `headState does not exist` pointed to state cache lookup, not fork choice or DB layer.
- **Checkpoint sync as reproducible trigger** — Using a public checkpoint URL made the bug 100% reproducible without a long-running devnet.

---

## Investigation 6: EPBS Withdrawals Regression (2026-02-24)

**Date:** 2026-02-24
**Type:** Block production mismatch (withdrawals computed from wrong parent state)

### What was being investigated?
`produceBlockV4` failing with withdrawals mismatch on `epbs-devnet-0`. EL returned a payload built with W1 (from PENDING parent state), but envelope validation compared against W2 (from FULL parent state).

### How were logs accessed?
1. **Kurtosis devnet** — 4-node 2×LH + 2×LS + assertoor (Nico's config).
2. **Error log pattern** — `produceBlockV4 error: Withdrawals mismatch` was the specific log line.
3. **Code path tracing** — Read `prepareNextSlot` → `computeNewStateRoot` → `getPayload` chain to identify the state-mismatch window.

### What worked?
- **Exact error message with field name** (`Withdrawals mismatch`) immediately pinpointed the comparison point.
- **Cache invalidation as root cause pattern**: Once the state-transition sequence was clear (`prepareNextSlot` caches payloadId from PENDING state, then FULL state changes withdrawals), the fix was obvious (bypass cache in Gloas path).

### What failed or was inefficient?
- Fix was implemented but Kurtosis strict validation left incomplete before closing the tracker.

### Most useful log patterns?
- **`produceBlockV4 error: Withdrawals mismatch`** — specific enough to immediately identify the failing code path.
- **`payloadId=null`** as a secondary signal (appeared in soak monitors for other EPBS issues).

---

## Investigation 7: Fork-Choice Latency Regression (feat1 vs stable, 2026-02-24)

**Date:** 2026-02-24
**Type:** Performance regression (fork choice timing anomaly + reorg rate spike)

### What was being investigated?
PR #8739 (EPBS fork choice) introduced a ~0.3s head-setting latency gap on all feat1 nodes, and a 5× reorg rate increase on feat1-semi specifically.

### How were logs accessed?
1. **Prometheus via Grafana** — Multi-day time series comparison (3 days) for block lifecycle timestamps, reorg counts, finalization, CPU, memory.
2. **Group comparison** — feat1 {solo, semi, super, sas, mainnet-super} vs stable counterparts.
3. **Depth analysis** — Reorg depth histogram (depth-2 vs depth-3) from Prometheus data.

### What worked?
- **Multi-metric comparison table** — Having 15+ metrics side-by-side for both groups made it immediately clear that the latency gap was specifically in the "processed → head" window.
- **Group-level breakdown** — Seeing that only feat1-semi had elevated reorgs (not super/sas) suggested a workload-size-dependent effect.
- **"Metrics That Are Fine" section** — Explicitly listing what was NOT regressed helped scope the investigation and prevent over-investigation.

### What failed or was inefficient?
- The 0.3s gap couldn't be definitively resolved without inspecting the code diff — it might have been a metric recording order change rather than real latency. Grafana alone wasn't sufficient to disambiguate.
- The reorg spike on feat1-semi required a separate follow-up investigation.

### Most useful log patterns?
- **Block lifecycle timestamps** (`received`, `processed`, `set_as_head`) — timing deltas between consecutive events exposed the latency gap.
- **Reorg count per node group** — aggregated 3-day totals with per-node breakdown immediately showed the semi-only pattern.

---

## Cross-Investigation Lessons for Log Reader Design

### 1. Log Access Hierarchy (by usefulness, most → least)

| Tier | Method | When useful |
|------|--------|-------------|
| **1** | Named metric counter (`> 0` filter) | First triage — is there a signal at all? |
| **2** | Prometheus time series (slope over ≥1h) | Memory leaks, performance regressions |
| **3** | Loki context window around event | Protocol bugs, timing failures |
| **4** | Cross-service log correlation | Interop bugs (CL + EL boundary) |
| **5** | Heap snapshot diffs | Memory leaks, object retention |
| **6** | Local repro with instrumentation | Validation after fix |

### 2. Most Diagnostic Log Fields (ranked by frequency of use)

1. **`errCode`** — Lodestar's structured block/gossip error codes immediately scope to the right subsystem
2. **Timing fields** (`recvToValLatency`, `slot`, timestamps) — correlate latency to protocol timing windows
3. **`parentInForkChoice`**, `payloadStatus` — fork choice state at error time
4. **Constructor names in heap diff** (`WeakRef`, `AbortSignal`, `Listener`) — leak type identification
5. **Participation ratios** (`328/512`, `bits_set`) — observable correctness invariants
6. **Nested error chain** — inner cause is often more diagnostic than outer wrapping error

### 3. What Log Readers Should NOT Do

- **Don't rely on point-in-time metric values for leak detection** — slope over ≥1h windows required
- **Don't truncate nested error causes** — the outer `BEACON_CHAIN_ERROR` wrapping the inner `Parent block hash mismatch` is useless without the inner message
- **Don't parse only one service's logs for interop bugs** — EL (Geth) often surfaces the signal first
- **Don't stream unfiltered Kurtosis logs** — at 12s slots with 4+ nodes, unfiltered output is ~100+ lines/minute; must filter to specific error codes or metrics
- **Don't assume a single good window means a leak is fixed** — oscillatory signals require consecutive confirmation windows

### 4. Effective Filter Patterns for Lodestar Logs

```
# Protocol bugs
"errCode=BLOCK_ERROR" OR "PARENT_UNKNOWN" OR "parentInForkChoice=false"

# Timing anomalies  
"recvToValLatency>" OR "recvToImportLatency>" OR "setHead" (with slot/time context)

# Memory leaks (Prometheus)
heap_space_size_used{space="old"} — track slope over ≥1h windows, not instant value

# Block production failures
"produceBlock.*error" OR "payloadId=null" OR "Withdrawals mismatch"

# Sync failures
"UnknownBlockSync.*failed" OR "BLOCK_ERROR_BEACON_CHAIN_ERROR"

# Network/gossip
"fastMsgId" OR "duplicate" OR "returns_empty_total" (filter to > 0)

# EPBS-specific
"Ignoring beacon update to old head" (from EL/Geth)
"PENDING" OR "FULL" OR "EMPTY" (payload status transitions)
```

### 5. Investigation Anti-Patterns (from real failures)

- **Investigating the wrong issue**: Issue #7299 was initially investigated; #8294 was the real target. Always confirm issue scope before deep-diving.
- **Deploying a fix before confirming root cause**: The req/resp clearable-signal fix (Investigation 2) was deployed before confirming it addressed the primary driver — several hours of deploy+monitor wasted.
- **Single-session long-running monitors**: Monitor sessions stalled, causing data gaps. Background collectors need liveness checks and restart logic.
- **Ephemeral Kurtosis logs**: No raw log preservation after `kurtosis enclave rm`. Key findings must be extracted and written during the investigation.
- **Sub-agent reviewer false positives**: Reviewers flagged files not in the diff — always cross-check findings against `git diff --name-only` before acting.

### 6. Kurtosis-Specific Log Access Patterns

```bash
# Stream logs from one service
kurtosis service logs <enclave> <service-name> --follow

# Get all service names in enclave
kurtosis enclave inspect <enclave>

# Filter for specific error pattern
kurtosis service logs <enclave> lodestar-1 --follow 2>&1 | grep "errCode=BLOCK_ERROR"

# Soak monitor: count specific errors over time
for i in $(seq 1 20); do
  echo "Sample $i: $(date -u +%H:%M:%S)"
  kurtosis service logs <enclave> lodestar-1 2>&1 | grep -c "ISR"
  sleep 30
done
```

### 7. Acceptance Criteria Pattern (from EPBS soak)

The most reliable post-fix validation pattern observed across investigations:
```
ISR (BLOCK_ERROR_INVALID_STATE_ROOT): 0/N samples
UnknownBlockSync processBlock failed: 0/N samples
Block production errors: 0 occurrences
payloadId=null: 0 occurrences
Finality: finalized epoch advances normally
```

Run for ≥20 samples over ≥10 minutes (or ≥100 slots) before declaring a fix valid.

### 8. Loki vs Prometheus: When to Use Each

| Signal Type | Use Loki | Use Prometheus |
|---|---|---|
| Specific error occurrence | ✅ | — |
| Timing of individual events | ✅ | — |
| Context around anomaly | ✅ | — |
| Trend/slope over time | — | ✅ |
| Memory leak detection | — | ✅ |
| Comparative group analysis | — | ✅ |
| Cross-node correlation | ✅ | ✅ |
| Error rate per unit time | — | ✅ |

---

## Summary Table

| Investigation | Type | Primary Log Source | Key Signal | Time to Root Cause |
|---|---|---|---|---|
| Sync aggregate bug (#8294) | Protocol bug | Loki + Kurtosis | `recvToValLatency=23.6s` + participation ratio | ~2h |
| feat1-super memory leak | Memory leak | Prometheus + heap snapshots | `old` space slope + constructor diff | ~24h (oscillatory) |
| EPBS devnet-0 stall | Interop bug | Kurtosis service logs | `Ignoring beacon update to old head` (EL) | ~6h + 6 restarts |
| feat3/blst-z native leak | Native memory | Prometheus | RSS slope vs V8 flat | ~1h |
| EPBS state restart crash | Crash | Live devnet + API | Crash message + checkpoint sync diff | ~2h |
| EPBS withdrawals mismatch | Block production | Kurtosis + error log | `Withdrawals mismatch` error | ~1h |
| Fork choice latency (feat1) | Performance | Prometheus multi-day | Block lifecycle timestamp delta | ~1h |
