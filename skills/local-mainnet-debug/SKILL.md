---
name: local-mainnet-debug
description: Debug Lodestar beacon node issues by running a local mainnet node with checkpoint sync and engineMock. Use for investigating networking bugs, peer discovery issues, identify failures, metrics anomalies, or any behavior that needs real-world peer interactions without a full execution client.
---

# Local Mainnet Debugging

Run a local Lodestar beacon node against mainnet peers using checkpoint sync and engineMock to reproduce and debug networking, peer discovery, and protocol-level issues in a real-world environment.

## Quick Start

```bash
# ~/lodestar is usually on an unrelated branch; worktrees can't run Lodestar (no node_modules/lib).
# Verify branch + SHA + a built lib first (don't blindly checkout):
git -C ~/lodestar rev-parse --abbrev-ref HEAD && git -C ~/lodestar log --oneline -1
ls ~/lodestar/packages/cli/lib/index.js && cd ~/lodestar

# Basic run — connects to mainnet peers, no EL needed
./lodestar beacon \
  --network mainnet \
  --rest false \
  --metrics \
  --execution.engineMock \
  --port 19771 \
  --logLevel debug \
  --checkpointSyncUrl https://beaconstate-mainnet.chainsafe.io \
  --forceCheckpointSync

# Time-boxed run (e.g., 2 minutes)
timeout 120 ./lodestar beacon \
  --network mainnet \
  --rest false \
  --metrics \
  --execution.engineMock \
  --port 19771 \
  --logLevel debug \
  --checkpointSyncUrl https://beaconstate-mainnet.chainsafe.io \
  --forceCheckpointSync
```

## Key Parameters

| Parameter | Purpose | Notes |
|-----------|---------|-------|
| `--network mainnet` | Connect to real mainnet peers | Use `hoodi` (or `sepolia`) for testnet — `holesky` is no longer accepted |
| `--execution.engineMock` | Skip EL requirement | Node won't validate execution payloads |
| `--rest false` | Disable REST API | Reduces noise, avoids port conflicts |
| `--metrics` | Enable Prometheus metrics | Scrape at `http://localhost:8008/metrics` |
| `--port 19771` | Custom P2P port | Avoid conflicts with other instances |
| `--logLevel debug` | Verbose logging | Use `trace` for maximum detail |
| `--checkpointSyncUrl` | Checkpoint sync endpoint | `https://beaconstate-mainnet.chainsafe.io` for mainnet |
| `--forceCheckpointSync` | Force checkpoint sync even if DB exists | Clean start each run |

## Catch-Up Repro Depth Guard

For sync-depth or OOM repros, validate the checkpoint is far enough behind head before launching the node. A latest-finalized checkpoint is usually too shallow for catch-up backlog investigations.

```bash
# Direct slot check. For a 1000-epoch repro, checkpoint must be at least 32000 slots behind head.
~/.openclaw/workspace/scripts/debug/check-catchup-depth.sh \
  --head-slot 14415648 \
  --checkpoint-slot 14383648 \
  --min-epochs 1000

# Beacon API-assisted check. Fetches head from --beacon-url and finalized checkpoint from --checkpoint-sync-url.
~/.openclaw/workspace/scripts/debug/check-catchup-depth.sh \
  --beacon-url http://127.0.0.1:5052 \
  --checkpoint-sync-url https://beaconstate-mainnet.chainsafe.io \
  --min-epochs 1000
```

Exit `2` means the checkpoint is too shallow or ahead of head; get an older state SSZ for `--checkpointState` before starting the repro. Public checkpoint endpoints only serve recent finalized state (HTTP 500 for old slots), so an old `/eth/v2/debug/beacon/states/<slot>` needs a real archive node. Probe a source cheaply before planning around it:

```bash
curl -s -o /dev/null -w "%{http_code}\n" --max-time 20 -r 0-1023 \
  -H "Accept: application/octet-stream" "$URL/eth/v2/debug/beacon/states/<slot>"   # 200 = available, 500 = not stored
```

## Metrics Scraping

```bash
# One-shot metric grab
curl -s http://localhost:8008/metrics | grep <pattern>

# Periodic sampling (every 30s)
while true; do
  echo "=== $(date -u +%H:%M:%S) ==="
  curl -s http://localhost:8008/metrics | grep -E 'lodestar_peers_by_client|peer_count'
  sleep 30
done

# Key metrics for peer debugging
curl -s http://localhost:8008/metrics | grep -E \
  'lodestar_peers_by_client|libp2p_identify|peer_count|connected_peers'
```

## Incident Bundle Preflight

Before starting a longer incident bundle or devnet triage run, validate that the helper scripts, output path, and telemetry prerequisites are usable. Use `--require-grafana` when a partial bundle without Grafana logs/metrics would not answer the question.

```bash
eval "$(grep '^export GRAFANA' ~/.bashrc)"   # GRAFANA_TOKEN (plain `source ~/.bashrc` early-returns)
# --node/--peer = ChainSafe Grafana `instance` names (substring match), e.g. beta-mainnet-super
~/.openclaw/workspace/scripts/debug/build-incident-bundle.sh \
  --node beta-mainnet-super \
  --peer unstable-mainnet-super \
  --window 1h \
  --require-grafana \
  --check-only
```

Exit non-zero means fix the missing token/tooling/output path before collecting data. Omit `--require-grafana` only when a local/process-only bundle is intentionally sufficient.

## Debugging Techniques

### 1. Instrument libp2p Internals (Monkeypatching)

For deep protocol debugging, add temporary instrumentation to the libp2p deps. They aren't in the root `node_modules` — they hang off `packages/beacon-node/node_modules/` (pnpm symlinks into `node_modules/.pnpm/`):

```bash
ls packages/beacon-node/node_modules/@libp2p/   # find the file to patch

# Key files for identify debugging (Lodestar uses only mplex — no yamux):
# - packages/beacon-node/node_modules/@libp2p/identify/dist/src/identify.js
# - packages/beacon-node/node_modules/@libp2p/mplex/dist/src/mplex.js (mplex streams)
```

**Important:** pnpm hard-links these files to the shared store (`~/.local/share/pnpm/store/v11`; `identify.js` has ~31 links), so editing in place changes every checkout that shares it. Save the original and break the hardlink before editing; restore from the saved copy before committing or running validation. `git checkout` can't restore (node_modules is untracked), and never run `pnpm install`.

```bash
f=packages/beacon-node/node_modules/@libp2p/identify/dist/src/identify.js
cp "$f" "$f.orig" && cp "$f" "$f.new" && mv "$f.new" "$f"   # backup + private copy
stat -c %h "$f"     # must print 1 before you edit
# ...patch "$f", run...
mv "$f.orig" "$f"   # restore
```

### 2. A/B Testing with Code Changes

When testing a hypothesis:

1. **Control run:** Baseline with current code, capture metrics
2. **Test run:** Apply change, capture metrics
3. **Compare:** Same duration, same metric sampling

```bash
# Control: capture baseline (2 min)
timeout 120 ./lodestar beacon [flags] 2>&1 | tee /tmp/control.log &
# Sample metrics during run
for i in $(seq 1 4); do sleep 30; curl -s http://localhost:8008/metrics > /tmp/control-$i.metrics; done

# Test: apply change, repeat
timeout 120 ./lodestar beacon [flags] 2>&1 | tee /tmp/test.log &
for i in $(seq 1 4); do sleep 30; curl -s http://localhost:8008/metrics > /tmp/test-$i.metrics; done

# Compare
diff <(grep pattern /tmp/control-4.metrics) <(grep pattern /tmp/test-4.metrics)
```

### 3. Log Analysis

```bash
# Count specific errors
grep -c "Error setting agentVersion" /tmp/run.log

# Track identify success/failure over time
grep -E "identify (success|error|timeout)" /tmp/run.log | head -50

# Extract peer connection events
grep -E "peer:(connect|disconnect|identify)" /tmp/run.log
```

### 4. Stream-Level Debugging

For protocol stream issues (identify, ping, metadata):

```bash
# Add console.log to stream handlers in node_modules (break the hardlink first — see §1)
# Key locations:
# - @libp2p/identify: identify.js → _identify() method
# - Stream open/close: @libp2p/mplex stream.js
# - Protocol negotiation: @libp2p/multistream-select

# Trace stream lifecycle:
# 1. Stream opened (protocol, direction, connection ID)
# 2. MSS negotiation (success/failure)  
# 3. Data read/write (first frame timing)
# 4. Stream close (who closed, when)
```

## Common Issues & Root Causes

### Unknown Peers (identify failures)

**Symptoms:** High ratio of "Unknown" in `lodestar_peers_by_client` metric.

Past root cause (2026-02 metrics-listener race, fixed upstream by js-libp2p#3378): `references/history.md`.

**Diagnostic approach:**
1. Check `lodestar_peers_by_client` for Unknown ratio
2. Enable debug logs, grep for "Error setting agentVersion"  
3. Instrument identify stream to check `remoteWriteStatus` before `pb.read()`
4. A/B test: disable `trackProtocolStream` entirely → if Unknown drops to 0, it's the metrics race

### Checkpoint Sync Failures

```bash
# Try alternative checkpoint sync endpoints
--checkpointSyncUrl https://beaconstate-mainnet.chainsafe.io
--checkpointSyncUrl https://mainnet-checkpoint-sync.stakely.io
--checkpointSyncUrl https://sync-mainnet.beaconcha.in
```

### Port Conflicts

```bash
# Check if port is in use
lsof -i :19771
lsof -i :8008

# Use different ports
--port 19772 --metrics.port 8009
```

## Cleanup

```bash
# Remove data directory after testing
rm -rf ~/.local/share/lodestar/mainnet

# Or use a custom datadir for isolation
--dataDir /tmp/lodestar-debug
```

## Tips

- **Short runs are fine.** 60-120 seconds is enough to connect to 15-30 peers and observe identify behavior.
- **engineMock mocks only the EL.** Execution payloads aren't verified (with an unknown parent payload they import optimistically), but every block still runs the full consensus state transition. This is fine for networking/peer debugging.
- **Custom port avoids conflicts** with any production nodes on the same machine.
- **Always use `--forceCheckpointSync`** to ensure a clean start. Stale DB state can mask issues.
- **Metrics lag behind logs.** After stopping the node, the last metrics scrape reflects final state. Periodic sampling during the run gives time-series data.
- **Debug builds not needed.** The standard `pnpm build` output is sufficient; libp2p debug info comes from log level and instrumentation.

---

## Self-Maintenance

If any commands, file paths, URLs, or configurations in this skill are outdated or no longer work, update this SKILL.md with the correct information after completing your current task. Skills should stay accurate and self-healing — fix what you find broken.
