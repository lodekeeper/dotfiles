# V8 Pointer Compression — 40h Checkpoint (feat4 vs unstable)

**Timestamp:** 2026-02-28 09:48 UTC
**Previous checkpoint:** 2026-02-28 03:48 UTC (34h)

## Status: Pointer Compression OFF — Steady-State Health Check

feat4 nodes were redeployed without pointer compression ~19.8h ago.
Both groups running standard V8. No experiment active.

## Process Uptime

| Node Type | feat4 beacon | unstable beacon |
|-----------|-------------|-----------------|
| solo | ~19.8h | ~407.8h (17.0d) |
| semi | ~19.8h | ~57.8h (2.4d) |
| super | ~19.8h | ~57.8h |
| sas | ~19.8h | ~57.8h |
| mainnet-super | ~19.8h | ~57.8h |

## RSS Memory (GB) — Beacon process

| Node Type | feat4 (19.8h) | unstable | Δ | vs 34h checkpoint |
|-----------|--------------|----------|---|-------------------|
| solo | 6.64 | 7.48 | -11% | Was -9% |
| semi | 7.17 | 6.30 | +14% | Was +10% |
| super | 8.37 | 7.29 | +15% | Was +16% |
| sas | 10.36 | 8.65 | +20% | Was +8% |
| mainnet-super | 9.93 | 8.24 | +21% | Was +18% |

**Analysis:** feat4 RSS continues growing with uptime. feat4-sas increased from
9.29→10.36 GB (+1.07 GB in 6h) — largest growth. Solo still negative due to unstable-solo
being 17 days old. mainnet-super feat4 RSS is approaching 10 GB but within normal range
for a mainnet supernode at 20h uptime.

## V8 Heap Used (GB) — Beacon process

| Node Type | feat4 (19.8h) | unstable | Δ | vs 34h checkpoint |
|-----------|--------------|----------|---|-------------------|
| solo | 2.51 | 2.40 | +5% | Was +3% |
| semi | 2.37 | 2.35 | +1% | Was +2% |
| super | 2.38 | 2.35 | +1% | Was +3% |
| sas | 2.50 | 2.49 | +0% | Was +6% |
| mainnet-super | 3.66 | 3.52 | +4% | Was +2% |

**Analysis:** V8 heap used within ±5% across all node types — noise level.
Confirms pointer compression remains OFF. No heap leaks detected.

## V8 Heap Total (allocated, GB)

| Node Type | feat4 | unstable | Δ |
|-----------|-------|----------|---|
| solo | 2.66 | 2.59 | +3% |
| semi | 2.56 | 2.56 | 0% |
| super | 2.61 | 2.54 | +3% |
| sas | 2.70 | 2.59 | +4% |
| mainnet-super | 3.97 | 3.83 | +4% |

**Note:** feat4-mainnet-super heap total stable at 3.97 GB (same as 34h checkpoint).
If pointer compression were re-enabled, this would be right at the 4 GB cage limit.

## External Memory (GB)

| Node Type | feat4 | unstable |
|-----------|-------|----------|
| solo | 0.39 | 0.37 |
| semi | 0.40 | 0.35 |
| super | 0.44 | 0.41 |
| sas | 0.45 | 0.61 |
| mainnet-super | 0.64 | 0.59 |

unstable-sas external memory (0.61 GB) still higher than feat4-sas (0.45 GB) — age-related.

## Peer Count

| Node Type | feat4 | unstable |
|-----------|-------|----------|
| solo | 201 | 202 |
| semi | 201 | 200 |
| super | 200 | 203 |
| sas | 98 ⚠️ | **4** ❌ |
| mainnet-super | 210 | 204 |
| arm64 | — | 200 |

### ❌ unstable-sas STILL DEGRADED — 10.5h unsynced

**unstable-sas has 4 peers and is UNSYNCED (status=0).**
This was flagged at 03:48 UTC (34h checkpoint) with 2 peers.

12h peer history:
- 21:49 UTC: 104 peers → declining from earlier levels
- 23:19 UTC: **Drop to 2 peers** — hasn't recovered since
- 23:49-09:49 UTC: Stuck at 0-7 peers for **~10.5 hours**
- Node has been unsynced the entire time (sync_status=0)

This is NOT recovering on its own. Likely needs a restart.

### ⚠️ feat4-sas PEER VOLATILITY — NEW

feat4-sas showing increasing peer volatility:
- Oscillating 96-207 over last 12h (was stable 200+ before)
- Current: 98 peers (dropped from 200+ range)
- Still synced (status=3) and functional
- May be a SAS-specific networking pattern (supernode + validator + EL co-located)

## Sync Status

| Node | Status |
|------|--------|
| feat4-solo | 3 (synced) ✅ |
| feat4-semi | 3 (synced) ✅ |
| feat4-super | 3 (synced) ✅ |
| feat4-sas | 3 (synced) ✅ |
| feat4-mainnet-super | 3 (synced) ✅ |
| unstable-solo | 3 (synced) ✅ |
| unstable-semi | 3 (synced) ✅ |
| unstable-super | 3 (synced) ✅ |
| unstable-sas | **0 (unsynced)** ❌ |
| unstable-mainnet-super | 3 (synced) ✅ |
| unstable-arm64 | 3 (synced) ✅ |

## GC Pause Duration (avg 1h, ms) — Beacon process

| Node Type | GC Type | feat4 | unstable | Δ |
|-----------|---------|-------|----------|---|
| solo | major | 60.0 | 60.5 | -1% |
| solo | minor | 11.5 | 11.0 | +5% |
| semi | major | 48.3 | 45.5 | +6% |
| semi | minor | 11.5 | 11.4 | +1% |
| super | major | 45.2 | 51.9 | -13% |
| super | minor | 11.9 | 11.7 | +2% |
| sas | major | 60.0 | 54.4 | +10% |
| sas | minor | 10.0 | 3.9 | +156% ⚠️ |
| mainnet-super | major | 74.7 | 76.2 | -2% |
| mainnet-super | minor | 11.5 | 10.8 | +6% |

**sas minor GC note:** unstable-sas minor GC is very low (3.9ms) because the node
has almost no peers/work. Not a real comparison — ignore this outlier.

## Trend: 3.5h → 10h → 22h → 28h → 34h → 40h

| Category | 3.5h (ptr-comp) | 10h (ptr-comp) | 28h (no-comp) | 34h (no-comp) | 40h (no-comp) |
|----------|-----------------|-----------------|----------------|----------------|----------------|
| V8 Heap Savings | 23-28% | 24-29% | 0% (±5%) | 0% (±6%) | 0% (±5%) |
| RSS Solo Δ | -38% | -22% | -13% | -9% | -11% |
| Major GC Δ | 5-15% ↑ | 4-13% ↑ | ±17% | ±9% | ±13% |
| Minor GC Δ | 5-15% ↑ | 12-51% ↑ | ±27% | ±10% | ±6% |
| Peers | Normal | Normal | Normal | ⚠️ u-sas=2 | ❌ u-sas=4, f-sas=98 |
| Sync | All synced | All synced | All synced | ❌ u-sas=0 | ❌ u-sas=0 |

## Overall Assessment

| Category | Status |
|----------|--------|
| **Pointer Compression** | ❌ Still OFF — feat4 running standard V8 |
| **feat4 Node Health** | ⚠️ 4/5 healthy, sas peers volatile (98, still synced) |
| **unstable Node Health** | ❌ 4/5 healthy, sas DEGRADED 10.5h (0 sync, 4 peers) |
| **GC** | ✅ Normal variance (ignore sas outlier) |
| **RSS** | ⚠️ feat4-sas at 10.36 GB, growing — monitor |
| **V8 Heap** | ✅ Identical between groups (confirms no compression) |
| **mainnet-super heap** | ⚠️ 3.97 GB total — would hit 4GB cage if compression enabled |

## Conclusion

Pointer compression still OFF. The primary concern is **unstable-sas** — unsynced for
10.5 hours with 0-7 peers. This was flagged at 03:48 UTC with an "escalate at 09:48"
action item. It has not recovered and likely needs a manual restart. Not related to the
ptr-compression experiment (both groups on standard V8, and feat4-sas is synced fine).

Secondary concern: **feat4-sas** peer count is increasingly volatile (oscillating 96-207,
dipping to 98). Still synced and functional but worth watching — may indicate a SAS-specific
networking issue.

**Alerting Nico** — unstable-sas has been degraded for 10.5h with no recovery.
Not production, but the node likely needs intervention.

**Action items:**
1. ✅ Alert Nico about unstable-sas (10.5h unsynced)
2. Monitor feat4-sas peer volatility — if it drops below 50 or loses sync, escalate
3. If Nico re-enables pointer compression, next cron will detect heap delta
