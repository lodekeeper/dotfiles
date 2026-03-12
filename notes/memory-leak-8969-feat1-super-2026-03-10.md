# Memory leak RCA — feat1-super network thread (2026-03-10)

## Scope
- Host: `feat1-super` (`devops@65.109.29.221 -p 3022`)
- Target: network worker old-space growth
- Method: live metrics + network-thread heap snapshots + retainer analysis

## Data collected
### Metrics
- `network_worker_nodejs_heap_space_size_used_bytes{space="old"}` showed multi-day growth on `feat1-super`.
- Handles/resources were not tracking old-space growth proportionally.

### Heap snapshots (network thread)
Captured on host via:
`POST /eth/v1/lodestar/write_heapdump?thread=network&dirpath=/tmp`

Files:
- `/tmp/network_thread_2026-03-10T14:03:29.032Z.heapsnapshot`
- `/tmp/network_thread_2026-03-10T14:05:19.648Z.heapsnapshot`
- `/tmp/network_thread_2026-03-10T14:52:45.922Z.heapsnapshot`

Local copies in:
- `~/.openclaw/workspace/tmp/feat1-super-heap/`

## Key heap signals
- Persistent growth in:
  - `object::WeakRef`
  - `hidden::system / WeakCell`
  - `object::Listener`
  - `object::Timeout` / `object::AbortSignal`
- Retainer/edge pattern heavily featured abort-composition internals (`sourceSignalRef`, `composedSignalRef`).

## Root cause
A missing cleanup in `@libp2p/utils` repeating task timeout path:

- File: `@libp2p/utils/src/repeating-task.ts` (+ dist JS)
- Behavior before fix:
  - For each loop iteration with `options.timeout`, code created `anySignal([...])`
  - Did **not** call `signal.clear()` after task completion
  - In long-running loops, abort listeners accumulated on long-lived signals while process stayed running

This matches the observed heap profile (WeakRef/WeakCell/listener growth and timeout/abort churn).

## Fix implemented
Branch: `~/lodestar-libp2p-hotfixes` (`test/libp2p-hotfixes-3392-3394`)

Commit:
- `bf0349f339` — `fix(libp2p-utils): clear repeatingTask timeout signals`

Changes:
- `patches/@libp2p__utils@7.0.11.patch`
  - add `signal?.clear()` in `repeating-task` `.finally()`
  - keep previous `adaptive-timeout cleanUp` fix
- `pnpm-lock.yaml`
  - updated patch hash for `@libp2p/utils@7.0.11`

## Validation (targeted harness)
Synthetic loop test instrumenting `AbortSignal.add/removeEventListener`:

### Before fix (feat1-super host code)
- Mid-run (~120ms): `add=220, remove=0` (accumulating)
- After `stop()`: listeners cleaned (`remove=220`)

### After fix (patched branch)
- Mid-run (~120ms): `add=216, remove=216` (no accumulation while running)
- After `stop()`: remains balanced

Conclusion: fix eliminates steady-state listener accumulation in repeating tasks.

## Next ops step
Deploy patched branch/build to feat1-super and monitor old-space slope for several hours to verify regression is gone under real traffic.

## Overnight corroboration checkpoint (2026-03-11 04:03 UTC)
- Collector (`silent-monitor-super-2026-03-10-night.log`) remained live through post-3h trigger window.
- Backlog decision state moved to `SUSTAINED_RUNAWAY_CONFIRMED` at 04:01 UTC (two consecutive ≥30m post-3h windows above +15MB/h).
- Evidence preserved for morning handoff:
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-10-night-2026-03-11T04-03Z-checkpoint.log`
  - `tmp/feat1-super-heap/postfix-verify/morning-handoff-2026-03-11T04-03Z.md`
- Mean-reversion downgrade gate still pending until first full ≥1h post-trigger window is available.
- Additional corroboration addendum captured at 04:11 UTC:
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-10-night-2026-03-11T04-11Z-checkpoint.log`
  - `tmp/feat1-super-heap/postfix-verify/morning-handoff-2026-03-11T04-11Z-addendum.md`
- First full ≥1h post-trigger gate (05:01 UTC) indicated sustained mean reversion and triggered state downgrade back to `STILL_NOISY`:
  - `tmp/feat1-super-heap/postfix-verify/post-trigger-1h-gate-2026-03-11T05-01Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-10-night-2026-03-11T05-01Z-checkpoint.log`
- Post-gate corroboration checkpoint (05:24 UTC) shows early upward pressure but remains below re-escalation threshold:
  - `tmp/feat1-super-heap/postfix-verify/post-gate-corroboration-2026-03-11T05-24Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-10-night-2026-03-11T05-24Z-checkpoint.log`
- First full post-gate >=30m window (05:31 UTC) is positive and now a re-escalation candidate, pending consecutive confirmation:
  - `tmp/feat1-super-heap/postfix-verify/post-gate-window1-2026-03-11T05-31Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T05-31Z-checkpoint.log`
- Second consecutive >=30m decision window (06:02 UTC) did not confirm a sustained upward regime; classification remains `STILL_NOISY`:
  - `tmp/feat1-super-heap/postfix-verify/post-gate-window2-decision-2026-03-11T06-02Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T06-02Z-checkpoint.log`
- Follow-up corroboration at 06:12 UTC remained short-window/noise-only and did not meet re-escalation criteria:
  - `tmp/feat1-super-heap/postfix-verify/post-gate-corroboration-2026-03-11T06-12Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T06-12Z-checkpoint.log`
- First fresh post-06:02 >=30m window at 06:40 UTC is a qualifying up-window (+33.87MB/h), but classification remains `STILL_NOISY` pending consecutive confirmation:
  - `tmp/feat1-super-heap/postfix-verify/post-gate-fresh-window1-2026-03-11T06-32Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T06-40Z-checkpoint.log`
- Second fresh >=30m confirmation window at 07:10 UTC also exceeded threshold (+90.46MB/h), satisfying consecutive-window criteria and re-escalating state to `SUSTAINED_RUNAWAY_CONFIRMED`:
  - `tmp/feat1-super-heap/postfix-verify/post-gate-fresh-window2-decision-2026-03-11T07-02Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T07-10Z-checkpoint.log`
- Re-escalated-state checkpoint at 07:20 UTC shows a short-window dip, but downgrade gate remains pending until full >=1h window from re-escalation anchor:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-corroboration-2026-03-11T07-20Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T07-20Z-checkpoint.log`
- First full >=1h post-re-escalation gate (08:08 UTC decision sample) **did not** satisfy downgrade criteria; state remains `SUSTAINED_RUNAWAY_CONFIRMED`:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-1h-gate-decision-2026-03-11T08-02Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T08-02Z-checkpoint.log`
- Operational note: collector stream had a gap after `07:57:37Z`; restarted collector session (`ember-cedar`) and resumed samples (`08:08:44Z`) before evaluating the gate.
- Follow-up corroboration at 08:19 UTC showed short-window upward bounce (no decision-state change):
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-corroboration-2026-03-11T08-19Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T08-19Z-checkpoint.log`
- Next full >=1h post-decision gate (09:09 UTC decision sample) also stayed in re-escalated state:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-1h-gate-decision-2026-03-11T09-08Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T09-08Z-checkpoint.log`
  - reason: endpoint old-space slope was negative, but robust median drift was positive (`+11.841MB`), so sustained sharp mean-reversion downgrade gate failed.
- Following full >=1h gate (10:09 UTC decision sample) also remained re-escalated:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-1h-gate-decision-2026-03-11T10-09Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T10-09Z-checkpoint.log`
  - reason: old-space slope was mildly positive (`+1.30MB/h`), so sharp mean-reversion downgrade criterion was not met.
- Periodic corroboration at 10:37 UTC shows short-window upward pressure and no state change:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-corroboration-2026-03-11T10-37Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T10-37Z-checkpoint.log`
- Full >=1h gate at 11:09 UTC remained re-escalated with clear upward pressure:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-1h-gate-decision-2026-03-11T11-09Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T11-09Z-checkpoint.log`
  - reason: old-space slope `+38.70MB/h` and median drift `+29.384MB` (opposite of downgrade condition).
- Full >=1h gate at 12:09 UTC also remained re-escalated:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-1h-gate-decision-2026-03-11T12-09Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T12-09Z-checkpoint.log`
  - reason: endpoint slope only `-1.93MB/h` with positive median drift `+15.572MB`, so sustained sharp mean-reversion criterion failed.
- Full >=1h gate at 13:10 UTC also remained re-escalated:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-1h-gate-decision-2026-03-11T13-10Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T13-10Z-checkpoint.log`
  - reason: slope `-10.83MB/h` and median drift `-4.215MB` indicate mild reversion, but not sharp enough for downgrade threshold.
- Full >=1h gate at 14:10 UTC remained re-escalated:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-1h-gate-decision-2026-03-11T14-10Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T14-10Z-checkpoint.log`
  - reason: slope turned positive (`+5.97MB/h`), so sustained sharp mean-reversion downgrade criterion clearly failed.
- Local instrumented repro track: full-process `T0/T+20m/T+40m/T+60m` captured; analysis pivoted to network-thread-only snapshots due full-snapshot parser limits, and network-thread series now completed (`T0/T+20/T+40/T+60`).
- Network-thread constructor/retainer analysis completed on quiet-meadow series:
  - Diff artifacts: `tmp/feat1-super-heap/local-repro/network-thread/analysis/diff-T0-T20.txt`, `diff-T20-T40.txt`, `diff-T40-T60.txt`, `diff-T0-T60.txt`
  - Retainer/chains artifacts: `retainers-WeakRef.txt`, `retainers-Listener.txt`, `retainers-MplexStream.txt`, `retainers-AbortSignal.txt`, `retainers-AbortController.txt`, `chains-WeakRef.txt`, `chains-Listener.txt`, `chains-MplexStream.txt`, `chains-AbortSignal.txt`, `chains-AbortController.txt`
  - Consolidated memo: `tmp/feat1-super-heap/local-repro/network-thread/analysis/constructor-retention-analysis-2026-03-11.md`
  - Main signal: post-warmup growth is WeakRef/WeakCell-heavy (`WeakRef +17252`, `WeakCell +8664` over 60m), while Listener/MplexStream are near-flat after warmup.
  - Retainer signature: large `sourceSignalRef/composedSignalRef -> WeakRef` fanout suggests residual AbortSignal composition retention path; candidate code path is req/resp timeout composition using `AbortSignal.any` (`@lodestar/reqresp/src/request/index.ts`).
- Full >=1h gate at 15:10 UTC remained re-escalated:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-1h-gate-decision-2026-03-11T15-10Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T15-10Z-checkpoint.log`
  - reason: `old` slope only `-1.02MB/h` (median drift `-6.893MB`) — reversion exists but does not meet sustained **sharp** downgrade threshold.
- Full >=1h gate at 16:10 UTC also remained re-escalated:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-1h-gate-decision-2026-03-11T16-10Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T16-10Z-checkpoint.log`
  - note: sampler stalled after `16:06`; recovered with one-shot manual sample at `16:31` to close a valid `>=1h` window.
  - reason: `old` slope `+17.55MB/h` and median drift `+1.973MB` (no mean-reversion; runaway classification reinforced).
- Full >=1h gate at 17:31 UTC remained re-escalated:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-1h-gate-decision-2026-03-11T17-31Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T17-31Z-checkpoint.log`
  - reason: `old` slope `+14.17MB/h`, median drift `+14.825MB` (still no reversion).
- Patched req/resp clearable-signal A/B run (`good-kelp`) completed checkpoints `T0/T+20/T+40/T+60`:
  - snapshots: `tmp/feat1-super-heap/local-repro/network-thread-patched-ab1/heap-network/`
  - constructor comparison vs quiet-meadow baseline:
    - `WeakRef`: `+17252` (baseline) → `+7` (patched)
    - `WeakCell`: `+8664` (baseline) → `+7` (patched)
    - post-warmup (`T+20→T+60`): `WeakRef +10475 → -187`, `WeakCell +5019 → -187`
  - retainer comparison: baseline `sourceSignalRef/composedSignalRef` fanout signatures are absent in patched `T+60` retainers.
  - summary artifact: `tmp/feat1-super-heap/local-repro/network-thread-patched-ab1/analysis/ab1-vs-quiet-meadow-summary-2026-03-11T17-38Z.md`
- Deployment-candidate branch published for feat1 canary:
  - branch: `fix/8969-reqresp-clearable-signal`
  - commit: `c583edf543` (`fix(reqresp): clear composed response timeout signals`)
  - remote: `fork/fix/8969-reqresp-clearable-signal`
  - compare: `https://github.com/lodekeeper/lodestar/compare/unstable...fix/8969-reqresp-clearable-signal`
- Full >=1h gate at 18:34 UTC remained re-escalated:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-1h-gate-decision-2026-03-11T18-34Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T18-34Z-checkpoint.log`
  - reason: `old` slope `+5.32MB/h`, median drift `+5.319MB` (no sustained sharp mean-reversion).
- Full >=1h gate at 19:34 UTC **downgraded to STILL_NOISY**:
  - `tmp/feat1-super-heap/postfix-verify/re-escalated-1h-gate-decision-2026-03-11T19-34Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T19-34Z-checkpoint.log`
  - reason: `old` slope `-16.09MB/h`, median drift `-16.094MB` (meets sustained sharp mean-reversion downgrade criterion).
- Full >=1h corroboration gate at 20:34 UTC **re-escalated to SUSTAINED_RUNAWAY_CONFIRMED**:
  - `tmp/feat1-super-heap/postfix-verify/still-noisy-corroboration-gate-2026-03-11T20-34Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T20-34Z-checkpoint.log`
  - reason: `old` slope `+8.82MB/h`, median drift `+8.819MB` (sustained positive old-space drift returned).
- feat1 deploy confirmed live at ~20:58 UTC on `fix/8969-reqresp-clearable-signal`; immediate anchor sample at 21:00 shows hard baseline reset (`old 236.188 -> 35.267`, sockets `208 -> 21`), likely restart/reconnect effect:
  - `tmp/feat1-super-heap/postfix-verify/feat1-deploy-anchor-2026-03-11T21-00Z.md`
  - implication: use deploy-anchored gate (>=1h from 21:00) for clean post-deploy effectiveness signal.
- First clean deploy-anchored >=1h gate at 22:00 UTC reports **NOT IMPROVED**:
  - `tmp/feat1-super-heap/postfix-verify/feat1-post-deploy-gate-2026-03-11T22-00Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T22-00Z-checkpoint.log`
  - metrics: `old 35.267 -> 112.151` (`+76.884MB`, `+76.84MB/h`), sockets `21 -> 203`
  - interpretation: memory growth resumed under live rollout; req/resp patch is likely partial-path only, not primary driver.
- Deploy-anchored follow-up gate at 23:00 UTC remains **NOT IMPROVED**, but with much smaller positive drift:
  - `tmp/feat1-super-heap/postfix-verify/feat1-post-deploy-gate-2026-03-11T23-00Z.md`
  - `tmp/feat1-super-heap/postfix-verify/silent-monitor-super-2026-03-11T23-00Z-checkpoint.log`
  - metrics: `old 112.151 -> 116.030` (`+3.879MB`, `+3.88MB/h`), sockets `203 -> 200`
  - interpretation: still positive residual drift (no closure), but now near low-drift/noise boundary; needs corroboration window.
