---
name: join-devnet
description: Join an existing Ethereum devnet (ethpandaops or custom) with a local Lodestar beacon node using engineMock. Use for syncing, debugging, testing serving/sync changes, or monitoring devnet activity without running an execution client.
---

# Join Devnet

Run a local Lodestar beacon node against a live Ethereum devnet using `--execution.engineMock`. No execution client needed — useful for testing CL changes, sync behavior, req/resp serving, and debugging.

## Quick Start

```bash
cd ~/lodestar-epbs-devnet-0  # or whichever worktree has your branch

# Basic — join epbs-devnet-0 with default ports
./scripts/run-devnet-beacon.sh

# With supernode (all custody columns — needed for PeerDAS/post-Fulu)
./scripts/run-devnet-beacon.sh --supernode

# Different devnet
./scripts/run-devnet-beacon.sh --devnet epbs-devnet-1

# Custom ports (for multi-node setups)
./scripts/run-devnet-beacon.sh --port 9201 --rest-port 9701 --data-dir runs/node-b/beacon-data --log-dir runs/node-b

# Preview command without executing
./scripts/run-devnet-beacon.sh --dry-run
```

## Script Location

The script lives at `scripts/run-devnet-beacon.sh` in the Lodestar worktree. Copy it to any worktree that needs it.

A reference copy is also at: `~/.openclaw/workspace/skills/join-devnet/scripts/run-devnet-beacon.sh`

## How It Works

1. **Auto-downloads artifacts** from `https://config.<devnet>.ethpandaops.io/` if missing:
   - `config.yaml` — chain parameters
   - `genesis.ssz` — genesis state
   - `bootstrap_nodes.txt` — bootnode ENRs
2. **Starts Lodestar** with `--execution.engineMock --eth1=false` (no EL needed)
3. **Connects to devnet** via bootnodes + discovery
4. **Syncs from genesis** (or from checkpoint if you add `--checkpointSyncUrl`)
5. **Writes PID file** for easy cleanup

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--devnet NAME` | `epbs-devnet-0` | Devnet name (matches ethpandaops URL pattern) |
| `--artifacts DIR` | `devnet-artifacts/$DEVNET` | Path to config/genesis/bootnodes |
| `--data-dir DIR` | `runs/$DEVNET/beacon-data` | Beacon chain database |
| `--log-dir DIR` | `runs/$DEVNET` | Log files directory |
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
./scripts/run-devnet-beacon.sh --supernode --port 9200 --rest-port 9700 \
  --data-dir runs/e2e/node-a/beacon-data --log-dir runs/e2e/node-a

# Wait for Node A to sync...
# Get Node A's peer ID:
A_PEER=$(curl -s http://127.0.0.1:9700/eth/v1/node/identity | jq -r '.data.peer_id')

# Node B — syncs exclusively from Node A
./scripts/run-devnet-beacon.sh --port 9201 --rest-port 9701 \
  --data-dir runs/e2e/node-b/beacon-data --log-dir runs/e2e/node-b \
  --extra-flags "--discv5=false --directPeers /ip4/127.0.0.1/tcp/9200/p2p/$A_PEER --targetPeers 1"
```

> **Note:** Strict direct-peer mode may hit a yamux stream-handshake bug (`Too many messages for missing streams`). Use mixed-peer discovery instead for reliable testing. See [#8999](https://github.com/ChainSafe/lodestar/issues/8999).

## Monitoring

```bash
# Sync progress
curl -s http://127.0.0.1:9700/eth/v1/node/syncing | jq

# Peer count
curl -s http://127.0.0.1:9700/eth/v1/node/peer_count | jq

# Node identity (peer ID, ENR)
curl -s http://127.0.0.1:9700/eth/v1/node/identity | jq

# Follow logs
tail -f runs/epbs-devnet-0/run.out

# Stop
kill $(cat runs/epbs-devnet-0/beacon.pid)
```

## Downloading Artifacts Manually

If auto-download fails (private devnet, auth required):

```bash
DEVNET=epbs-devnet-0
mkdir -p devnet-artifacts/$DEVNET
curl -sL https://config.${DEVNET}.ethpandaops.io/cl/config.yaml > devnet-artifacts/$DEVNET/config.yaml
curl -sL https://config.${DEVNET}.ethpandaops.io/cl/genesis.ssz > devnet-artifacts/$DEVNET/genesis.ssz
curl -sL https://config.${DEVNET}.ethpandaops.io/cl/bootstrap_nodes.txt > devnet-artifacts/$DEVNET/bootstrap_nodes.txt
```

## Common Issues

| Problem | Fix |
|---------|-----|
| `EADDRINUSE` on port | Another node on same port. Use `lsof -iTCP:<port> -sTCP:LISTEN` to find it, kill it, or use different `--port` |
| `headState does not exist` on restart | Stale data dir from different branch. Delete `--data-dir` and restart |
| `Too many messages for missing streams` | yamux bug in small peer sets. Use normal discovery, not `--directPeers` isolation |
| No peers found | Check `bootstrap_nodes.txt` exists and devnet is still running |
| `protocol selection failed` for envelope requests | Remote peer doesn't support `execution_payload_envelopes_by_range` (not on ePBS fork) |

## Devnet Explorer

Most ethpandaops devnets have a Dora explorer:
```
https://dora.<devnet-name>.ethpandaops.io/
```


## Self-Maintenance

If any commands, file paths, URLs, or configurations in this skill are outdated or no longer work, update this SKILL.md with the correct information after completing your current task. Skills should stay accurate and self-healing — fix what you find broken.
