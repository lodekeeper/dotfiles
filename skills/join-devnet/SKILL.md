---
name: join-devnet
description: Join an existing Ethereum devnet (ethpandaops or custom) with a local Lodestar beacon node using engineMock. Use for syncing, debugging, testing serving/sync changes, or monitoring devnet activity without running an execution client.
---

# Join Devnet

Run a local Lodestar beacon node against a live Ethereum devnet using `--execution.engineMock`. No execution client needed — useful for testing CL changes, sync behavior, req/resp serving, and debugging.

## Quick Start

```bash
# Run from a BUILT ~/lodestar (worktrees have no node_modules). ~/lodestar is usually parked on an
# unrelated branch — confirm branch + SHA are what you mean to test (don't blindly checkout):
git -C ~/lodestar rev-parse --abbrev-ref HEAD && git -C ~/lodestar log --oneline -1
cd ~/lodestar
S=~/.openclaw/workspace/skills/join-devnet/scripts/run-devnet-beacon.sh
DEVNET=glamsterdam-devnet-8   # required — pick a live one: panda devnets

# Basic — default ports; artifacts/data/logs go to ~/devnet-runs/$DEVNET (outside the repo)
bash $S --devnet $DEVNET

# With supernode (all custody columns — needed for PeerDAS/post-Fulu)
bash $S --devnet $DEVNET --supernode

# Custom ports (for multi-node setups)
bash $S --devnet $DEVNET --port 9201 --rest-port 9701 --data-dir ~/devnet-runs/node-b/beacon-data --log-dir ~/devnet-runs/node-b

# Preview command without executing
bash $S --devnet $DEVNET --dry-run
```

## Script Location

The script lives in this skill: `~/.openclaw/workspace/skills/join-devnet/scripts/run-devnet-beacon.sh`. Run it with `bash` from the root of a built Lodestar checkout — it calls `packages/cli/bin/lodestar.js` relative to the CWD and refuses to start without `packages/cli/lib`. Don't copy it into a worktree (no `node_modules`/`lib` there). `~/lodestar/scripts/run-devnet-beacon.sh` is an old untracked copy — never `git add` it.

## How It Works

1. **Auto-downloads artifacts** from `https://config.<devnet>.ethpandaops.io/` if missing:
   - `config.yaml` — chain parameters
   - `genesis.ssz` — genesis state
   - `bootstrap_nodes.txt` — bootnode ENRs
2. **Starts Lodestar** with `--execution.engineMock` (no EL needed)
3. **Connects to devnet** via bootnodes + discovery
4. **Syncs from genesis** (or from checkpoint if you add `--checkpointSyncUrl`)
5. **Detaches with `setsid`** (survives session teardown) and **writes a PID file** for easy cleanup

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--devnet NAME` | **required** | Devnet name (matches ethpandaops URL pattern; pick via `panda devnets`) |
| `--artifacts DIR` | `~/devnet-runs/$DEVNET/artifacts` | Path to config/genesis/bootnodes |
| `--data-dir DIR` | `~/devnet-runs/$DEVNET/beacon-data` | Beacon chain database |
| `--log-dir DIR` | `~/devnet-runs/$DEVNET` | Log files directory |
| `--port PORT` | `9200` | libp2p TCP port |
| `--rest-port PORT` | `9700` | REST API port |
| `--supernode` | off | Enable all custody columns (needed for post-Fulu batches) |
| `--log-level LEVEL` | `info` | Console log level |
| `--extra-flags "..."` | none | Additional lodestar flags |
| `--dry-run` | off | Print command without running |

## Multi-Node Setup

Run two nodes on the same machine (e.g., for e2e serve+sync testing):

```bash
# Node A — syncs from devnet, serves data
bash $S --devnet $DEVNET --supernode --port 9200 --rest-port 9700 \
  --data-dir ~/devnet-runs/e2e/node-a/beacon-data --log-dir ~/devnet-runs/e2e/node-a

# Wait for Node A to sync...
# Get Node A's peer ID:
A_PEER=$(curl -s http://127.0.0.1:9700/eth/v1/node/identity | jq -r '.data.peer_id')

# Node B — syncs exclusively from Node A
bash $S --devnet $DEVNET --port 9201 --rest-port 9701 \
  --data-dir ~/devnet-runs/e2e/node-b/beacon-data --log-dir ~/devnet-runs/e2e/node-b \
  --extra-flags "--discv5=false --directPeers /ip4/127.0.0.1/tcp/9200/p2p/$A_PEER --targetPeers 1"
```

> **Note:** Strict direct-peer mode may hit an mplex stream-handshake bug (`Too many messages for missing streams`; Lodestar uses only mplex). Use mixed-peer discovery instead for reliable testing. See [#8999](https://github.com/ChainSafe/lodestar/issues/8999) (still open).

## Monitoring

```bash
# Sync progress
curl -s http://127.0.0.1:9700/eth/v1/node/syncing | jq

# Peer count
curl -s http://127.0.0.1:9700/eth/v1/node/peer_count | jq

# Node identity (peer ID, ENR)
curl -s http://127.0.0.1:9700/eth/v1/node/identity | jq

# Follow logs
tail -f ~/devnet-runs/$DEVNET/run.out

# Stop
kill $(cat ~/devnet-runs/$DEVNET/beacon.pid)
```

## Downloading Artifacts Manually

If auto-download fails (private devnet, auth required):

```bash
DEVNET=glamsterdam-devnet-8
A=~/devnet-runs/$DEVNET/artifacts
mkdir -p $A
curl -sL https://config.${DEVNET}.ethpandaops.io/cl/config.yaml > $A/config.yaml
curl -sL https://config.${DEVNET}.ethpandaops.io/cl/genesis.ssz > $A/genesis.ssz
curl -sL https://config.${DEVNET}.ethpandaops.io/cl/bootstrap_nodes.txt > $A/bootstrap_nodes.txt
```

## Common Issues

| Problem | Fix |
|---------|-----|
| `EADDRINUSE` on port | Another node on same port. Use `lsof -iTCP:<port> -sTCP:LISTEN` to find it, kill it, or use different `--port` |
| `headState does not exist` on restart | Stale data dir from different branch. Delete `--data-dir` and restart |
| `Too many messages for missing streams` | mplex bug in small peer sets (#8999). Use normal discovery, not `--directPeers` isolation |
| No peers found | Check `bootstrap_nodes.txt` exists and the devnet is still listed in `panda devnets` |
| `protocol selection failed` for envelope requests | Remote peer doesn't support `execution_payload_envelopes_by_range` (not on ePBS fork) |

## Devnet Explorer

Dora (`https://dora.<devnet-name>.ethpandaops.io/`), config and service endpoints: see `../devnet-debug/references/network-metadata.md`; quick health snapshot: `../devnet-debug/scripts/net-health.sh <devnet-name>`.
