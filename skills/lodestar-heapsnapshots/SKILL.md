---
name: lodestar-heapsnapshots
description: Capture and analyze Lodestar heap snapshots (main/network/discv5 workers) via the lodestar REST write_heapdump endpoint. Use for memory leak investigations on running beacon nodes.
---

# Lodestar Heap Snapshots

Use this for live memory leak debugging on running Lodestar nodes.

## 1) Preconditions
- You can SSH to the host running Lodestar.
- Lodestar REST API is reachable locally on that host (often `127.0.0.1:<api-port>`).
- You know where snapshots can be written (`/tmp` is safest).

Quick port discovery (if unknown):
```bash
# Common in Lodestar infra
grep -n "rest.port\|rest.address" /home/devops/beacon/rcconfig.yml
```

Quick API sanity check:
```bash
curl -sS -m 5 http://127.0.0.1:9596/eth/v1/node/health -w "\nHTTP:%{http_code}\n"
```

## 2) Capture snapshots
Use the Lodestar endpoint from the host:

```bash
curl -sS -m 1200 -X POST \
  "http://127.0.0.1:9596/eth/v1/lodestar/write_heapdump?thread=network&dirpath=/tmp"
```

Parameters:
- `thread`: `main` | `network` | `discv5`
- `dirpath`: output directory on host filesystem

Response shape:
```json
{"data":{"filepath":"/tmp/network_thread_2026-03-10T14:52:45.922Z.heapsnapshot"}}
```

Notes:
- If you get `{"code":500,"message":"Already writing heapdump"}`, wait and retry.
- Large heaps can take minutes.

## 3) Copy snapshots locally
```bash
scp -P <ssh-port> user@host:/tmp/network_thread_*.heapsnapshot ./tmp/
```

Take at least 2 snapshots separated by meaningful runtime (e.g. 10–60 min).

## 4) Fast diff (type/count/self-size)
Use the local helper (if present):

```bash
node --max-old-space-size=24576 /home/openclaw/lodestar-debug-8969/analyze-heap.mjs \
  <older.heapsnapshot> <newer.heapsnapshot>
```

If snapshots are too large for Node parser, use Python fallback to aggregate by `(type,name)` and diff counts/self-size.

## 5) Retainer-oriented checks
For leak triage, prioritize growth in:
- `WeakRef`, `WeakCell`, `Listener`, `Timeout`, `AbortSignal`
- protocol stream/connection objects
- large maps/sets keyed by peer/topic/message IDs

Then map these to concrete code paths (timeouts, listeners, per-iteration allocations, caches without pruning).

## 6) Verify fix behavior
After patching:
1. Reproduce under similar load.
2. Re-capture snapshots.
3. Confirm suspect classes no longer grow unbounded.
4. Cross-check Prometheus trend (`network_worker_nodejs_heap_space_size_used_bytes{space="old"}`).

## 7) Warm-up rule for post-deploy verdicts (important)
Do **not** conclude immediately after restart.

Use this sequence:
1. Confirm restart took effect (`process_start_time_seconds` changed).
2. Wait **1–2h warm-up** for peer convergence (e.g. around normal peer counts).
3. Only then evaluate old-space slope vs pre-fix baseline.

During warm-up, temporary rises in heap/handles/sockets are expected.

## 8) Useful metrics to track with snapshots
- `network_worker_nodejs_heap_space_size_used_bytes{space="old"}`
- `network_worker_nodejs_heap_size_used_bytes`
- `network_worker_nodejs_external_memory_bytes`
- `network_worker_nodejs_active_handles{type="Socket"}`
- `network_worker_process_start_time_seconds`

If doing fleet validation, track all relevant instances in parallel and compare post-warm-up slopes.

## 9) Artifact packaging for GitHub sharing
Large `.heapsnapshot` files are usually too big for direct issue upload.

Use compressed assets + checksums:
```bash
zstd -T0 -10 -f snapshot.heapsnapshot -o snapshot.heapsnapshot.zst
sha256sum *.zst > SHA256SUMS.txt
```

Prefer attaching to a release (or other blob storage), then link from the issue comment.

## 10) Final verdict template (issue comment)
Use this after the warm-up window and slope check:

```md
### Post-deploy memory-leak verdict (`<env>`, `<time-window>`)

- **Deploy/version:** `<branch or commit>`
- **Warm-up window observed:** `<start> → <end>`
- **Primary metric:** `network_worker_nodejs_heap_space_size_used_bytes{space="old"}`

#### Result
- **Verdict:** ✅ Fixed / ⚠️ Inconclusive / ❌ Not fixed
- **Observed slope vs pre-fix baseline:** `<summary with numbers>`
- **Handles/external-memory behavior:** `<stable or growing, key values>`

#### Evidence
- Metrics log/artifact: `<link/path>`
- Heap snapshots (if taken): `<link/path>`
- Checksum file (if shared): `<link/path>`

#### Next action
- `<if fixed: keep monitoring + upstream patch>`
- `<if not fixed: capture new snapshots + iterate patch>`
```

## Lodestar endpoint location
- Endpoint wiring is in `packages/api/src/beacon/routes/lodestar.ts`.
- Handler uses `writeHeapdump` and supports thread selection.
