# Fork-Choice Metrics: feat1 vs stable (3-day window)

**Date:** 2026-02-24
**Groups:** feat1 (PR #8739 fork-choice) vs stable
**Window:** Feb 21–24 (3 days)
**Scope:** Fork-choice performance + anomalies only

## Summary: INVESTIGATE (2 items)

Overall fork-choice behavior is healthy — no finalization issues, no attestation regressions, no CPU/memory concerns. Two items warrant investigation:

### Finding 1: feat1-semi has 5x more reorgs 🟡

| Node | feat1 (3d) | stable (3d) | Delta |
|------|-----------|-------------|-------|
| solo | 47 | 32 | +47% |
| **semi** | **166** | **32** | **+419%** |
| super | 32 | 32 | 0% |
| sas | 32 | 32 | 0% |
| mainnet-super | 23 | 23 | 0% |

- **Sustained:** 47-76 reorgs/day on feat1-semi consistently over 5 days (not a transient spike)
- **Depth:** All depth-2 (143/165) or depth-3 (18/165). No deep reorgs.
- **Pattern:** Only affects semi (64 custody groups) and slightly solo. Super/SAS/mainnet-super are identical to stable.
- **Possible causes:**
  1. Fork-choice code regression that manifests more at medium custody group sizes
  2. Node-specific issue on feat1-semi (network position, hardware)
  3. Since solo is also mildly elevated (+47%), could be a subtle fork-choice regression that semi amplifies

### Finding 2: +0.3s fork-choice overhead in gossip block → head path 🟡

| Metric | feat1 | stable | Notes |
|--------|-------|--------|-------|
| Block received (from slot start) | 1.09-1.87s | 1.14-1.87s | Same |
| Block processed | 1.65-2.01s | 1.74-2.02s | Same or faster |
| **Block set as head** | **1.94-2.54s** | **1.74-2.02s** | **+0.3s gap** |

The ~0.3s gap between "processed" and "become head" is consistent across ALL feat1 nodes but absent on stable. This suggests the fork-choice PR adds ~300ms latency to the head-setting step after block processing.

- Block import time is actually slightly faster on feat1 (28-48ms vs 28-52ms)
- STFN process block time is equal or faster
- The overhead is specifically in the "after processing, before head" window

**Note:** Could be a metric recording order change rather than actual latency — the code may now emit the "processed" event before an async fork-choice step that stable does synchronously.

## Metrics That Are Fine ✅

| Metric | feat1 | stable | Verdict |
|--------|-------|--------|---------|
| Sync status | All synced | All synced | ✅ |
| Finalization | Normal | Normal | ✅ |
| Epoch transition time | 0.65-0.93s | 0.68-0.99s | ✅ Faster |
| STFN process block | 67-82ms | 66-102ms | ✅ Same/faster |
| Block import time | 28-48ms | 28-52ms | ✅ Same/faster |
| Gossip validate time | ~1.1ms | ~1.1ms | ✅ |
| Attestation head slot drift | 0.183-0.189 | 0.183-0.187 | ✅ |
| CPU usage | 0.47-3.14 cores | 0.53-3.19 cores | ✅ Lower |
| Event loop lag P99 | 10-38ms | 10-59ms | ✅ Same/better |
| RSS memory | 5.7-10.9 GB | 7.1-8.2 GB | ✅ Mixed (uptime) |
| Peer count | 137-202 | 199-208 | ✅ (sas low: 137) |
| Block process errors | 0-133 | 0-133 | ✅ Same |
| Set head after cutoff | 166-590 | 168-573 | ✅ Same |

## Recommendation

**Not a blocker**, but worth investigating:
1. Check if feat1-semi's reorg spike correlates with any known network events
2. Verify the 0.3s head-setting overhead is real latency vs metric timing change — could inspect the `importBlock` code path diff for new async steps between processing and head setting
3. Consider restarting feat1-semi to rule out node-specific state
