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
