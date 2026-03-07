---
name: local-mainnet-debug
description: Debug Lodestar beacon node issues by running a local mainnet node with checkpoint sync and engineMock. Use for investigating networking bugs, peer discovery issues, identify failures, metrics anomalies, or any behavior that needs real-world peer interactions without a full execution client.
---

# Local Mainnet Debugging

Run a local Lodestar beacon node against mainnet peers using checkpoint sync and engineMock to reproduce and debug networking, peer discovery, and protocol-level issues in a real-world environment.

## Quick Start

```bash
cd ~/lodestar  # or worktree directory

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
| `--network mainnet` | Connect to real mainnet peers | Use `holesky` for testnet |
| `--execution.engineMock` | Skip EL requirement | Node won't validate execution payloads |
| `--rest false` | Disable REST API | Reduces noise, avoids port conflicts |
| `--metrics` | Enable Prometheus metrics | Scrape at `http://localhost:8008/metrics` |
| `--port 19771` | Custom P2P port | Avoid conflicts with other instances |
| `--logLevel debug` | Verbose logging | Use `trace` for maximum detail |
| `--checkpointSyncUrl` | Checkpoint sync endpoint | `https://beaconstate-mainnet.chainsafe.io` for mainnet |
| `--forceCheckpointSync` | Force checkpoint sync even if DB exists | Clean start each run |

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

## Debugging Techniques

### 1. Instrument libp2p Internals (Monkeypatching)

For deep protocol debugging, add temporary instrumentation to `node_modules`:

```bash
# Find the file to patch
find node_modules -path '*libp2p*identify*' -name '*.js' | head -20

# Key files for identify debugging:
# - node_modules/@libp2p/identify/dist/src/identify.js
# - node_modules/@chainsafe/libp2p-yamux/dist/src/stream.js (yamux streams)
# - node_modules/@libp2p/mplex/dist/src/mplex.js (mplex streams)
```

**Important:** Always remove monkeypatches before committing or running validation. Use `git checkout node_modules/` or `pnpm install` to restore.

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
# Add console.log to stream handlers in node_modules
# Key locations:
# - @libp2p/identify: identify.js → _identify() method
# - Stream open/close: yamux or mplex stream.js
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

**Root cause found (2026-02-25):** `@libp2p/prometheus-metrics` `trackProtocolStream()` attaches a `message` event listener that races with identify's `pb.read()` for the first data frame. The metrics listener can consume the identify response before the identify handler reads it.

**Fix:** Skip `trackProtocolStream` for `/ipfs/id/1.0.0` protocol. See PR #8958.

**Upstream fix:** `libp2p/js-libp2p#3378` — byteStream should check its own readBuffer before returning null.

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
- **engineMock means no execution validation.** The node will sync headers but won't validate blocks. This is fine for networking/peer debugging.
- **Custom port avoids conflicts** with any production nodes on the same machine.
- **Always use `--forceCheckpointSync`** to ensure a clean start. Stale DB state can mask issues.
- **Metrics lag behind logs.** After stopping the node, the last metrics scrape reflects final state. Periodic sampling during the run gives time-series data.
- **Debug builds not needed.** The standard `pnpm build` output is sufficient; libp2p debug info comes from log level and instrumentation.

---

## Self-Maintenance

If any commands, file paths, URLs, or configurations in this skill are outdated or no longer work, update this SKILL.md with the correct information after completing your current task. Skills should stay accurate and self-healing — fix what you find broken.

