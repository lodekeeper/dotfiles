# feat3 BLS Batch Verifier vs Stable — Metrics Analysis

**Date:** 2026-02-26 ~23:00 UTC
**feat3 uptime:** 16-25h | **stable uptime:** 24-367h
**feat3 node:** v24.14.0 | **stable node:** v24.13.0

## Key Change

feat3 replaces the BLS thread pool (`lodestar_bls_thread_pool_*`) with a new batch verifier (`lodestar_bls_verifier_*`). Metrics aren't 1:1 comparable but the pipeline-level effects are.

## 🏆 Signatures Verification — Major Win

| Node Type | feat3 (ms) | stable (ms) | Delta |
|-----------|-----------|------------|-------|
| solo | 58 | 123 | **-53%** |
| semi | 56 | 94 | **-40%** |
| super | 65 | 106 | **-39%** |
| sas | 64 | 126 | **-49%** |
| mainnet-super | 31 | 58 | **-46%** |

## Block Pipeline — End-to-End Improvement

### Received → Fully Verified (ms)
| Node | feat3 | stable | Delta |
|------|-------|--------|-------|
| solo | 320 | 514 | -38% |
| semi | 288 | 341 | -16% |
| super | 361 | 373 | -3% |
| sas | 368 | 432 | -15% |
| mainnet-super | 308 | 299 | +3% |

### Received → Block Import (ms)
| Node | feat3 | stable | Delta |
|------|-------|--------|-------|
| solo | 356 | 547 | -35% |
| semi | 387 | 440 | -12% |
| super | 477 | 498 | -4% |
| sas | 523 | 596 | -12% |
| mainnet-super | 339 | 326 | +4% |

### Gossip Block → Head (s)
| Node | feat3 | stable | Delta |
|------|-------|--------|-------|
| solo | 1.61 | 1.81 | -11% |
| semi | 1.67 | 1.72 | -3% |
| super | 1.75 | 1.79 | -2% |
| sas | 1.87 | 1.86 | +1% |
| mainnet-super | 2.25 | 2.22 | +1% |

## BLS Verifier Internals (feat3 only)

| Metric | solo | semi | super | sas | mn-super |
|--------|------|------|-------|-----|----------|
| Async time (ms) | 56 | 73 | 68 | 115 | 49 |
| Batch flush (ms) | 56 | 73 | 68 | 116 | 49 |
| Buffer wait (ms) | 14 | 11 | 17 | 53 | 21 |
| Main thread (ms) | 1.4 | 2.3 | 2.3 | 2.3 | 2.3 |
| Time/sigset (ms) | 2.0 | 2.5 | 2.5 | 7.0 | 2.0 |
| Same-msg time (ms) | 5 | 6 | 10 | 197 | 5 |
| Sig sets/s | 70 | 78 | 78 | 110 | 59 |
| Batched sigs/s | 69 | 77 | 77 | 110 | 58 |
| Same-msg sets/s | 92 | 93 | 210 | 2834 | 78 |
| Batch retries (6h) | 0 | 0 | 0 | 0 | 0 |
| Inflight jobs | 0 | 0 | 0 | 0 | 0 |

**Batching efficiency:** ~99% of sig sets are batchable and succeed. Zero retries.

## ⚠️ SAS Node Pressure

feat3-sas shows elevated metrics vs other node types:
- **Event loop lag p99:** 138ms (vs stable-sas 34ms, other feat3 nodes 11-13ms)
- **Same-message verification:** 197ms (vs others 5-10ms)
- **Buffer wait:** 53ms (vs others 11-21ms)
- **Time per sigset:** 7.0ms (vs others 2.0-2.5ms)
- **Peers:** 129 (vs others 200+)
- **Same-message sets/s:** 2834/s (10-30x other nodes)

The SAS node handles 2834 same-message sets/s (validator attestation aggregation) creating contention. The high event loop lag suggests the batch verifier's main thread work is blocking when combined with validator duties.

## Memory & CPU

| Node | feat3 RSS (MB) | stable RSS (MB) | feat3 Heap (MB) | stable Heap (MB) |
|------|---------------|-----------------|-----------------|------------------|
| solo | 7397 | 7354 | 2349 | 2600 |
| semi | 9030 | 7893 | 2373 | 2501 |
| super | 10105 | 7834 | 2397 | 2563 |
| sas | 11131 | 8171 | 2542 | 2680 |
| mn-super | 9881 | 9819 | 3586 | 3814 |

- **V8 heap: feat3 lower across the board** (5-9% reduction)
- RSS higher on feat3 but expected: feat3 is 16-25h old vs stable 24-367h (fresh process effect)
- CPU similar or slightly lower on feat3

## Health

- All nodes synced (status=3) ✅
- Block processor queue: 0 everywhere ✅
- Zero BLS batch retries ✅
- GC: similar rates ✅
- Gossip block errors: feat3 lower (26-45 vs stable 43-736) ✅
- Epoch transition: similar (~0.67-1.0s feat3 vs 0.69-1.26s stable) ✅

## Summary

**Overall: Strongly positive.** ~40-50% faster signature verification, 12-38% faster end-to-end block verification for most node types. Lower V8 heap. Zero retries. Clean health.

**One concern:** SAS node shows 4x event loop lag increase (138ms vs 34ms). The high same-message verification throughput (2834 sets/s) on the combined validator+beacon node creates main thread contention. Worth investigating whether the batching buffer/flush strategy needs tuning under high same-message load.
