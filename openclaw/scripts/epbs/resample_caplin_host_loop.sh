#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/openclaw/.openclaw/workspace
WORKTREE=/home/openclaw/lodestar-9148-min
OUT="$ROOT/tmp/caplin-host-resample-loop.jsonl"
DIRECT=/ip4/46.224.62.16/tcp/4401/p2p/16Uiu2HAmRCP28eEphgbDmrS7ihqAmtBjCwLUhh8aAV2fCc5Mu85x
# Keep the short-lived resample loop away from the long-lived direct-caplin loop
# (currently living around REST 10070 / libp2p 9710) so later iterations do not
# self-poison with EADDRINUSE once the counter reaches that lane.
REST_BASE=${REST_BASE:-10200}
PORT_BASE=${PORT_BASE:-9800}
mkdir -p "$ROOT/tmp"
: >> "$OUT"
for iter in $(seq 1 48); do
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  run_dir="$WORKTREE/runs/pr9156-direct-caplin-resample-$stamp"
  rest=$((REST_BASE + iter))
  port=$((PORT_BASE + iter))
  mkdir -p "$run_dir"
  cd "$WORKTREE"
  nohup node --max-old-space-size=8192 packages/cli/bin/lodestar.js beacon \
    --paramsFile devnet-artifacts/epbs-devnet-1/config.yaml \
    --genesisStateFile devnet-artifacts/epbs-devnet-1/genesis.ssz \
    --dataDir "$run_dir/beacon-data" \
    --rest --rest.port "$rest" \
    --port "$port" \
    --logLevel debug \
    --logFile "$run_dir/beacon.log" \
    --logFileLevel debug \
    --execution.engineMock \
    --eth1=false \
    --discv5 false \
    --targetPeers 1 \
    --disablePeerScoring \
    --persistNetworkIdentity \
    --directPeers "$DIRECT" \
    --checkpointSyncUrl https://checkpoint-sync.epbs-devnet-1.ethpandaops.io \
    > "$run_dir/run.out" 2>&1 &
  pid=$!
  echo "{\"event\":\"spawn\",\"iter\":$iter,\"stamp\":\"$stamp\",\"run_dir\":\"$run_dir\",\"pid\":$pid,\"rest\":$rest,\"port\":$port}" | tee -a "$OUT"
  sleep 45
  alive=true
  if ! kill -0 "$pid" 2>/dev/null; then
    alive=false
  fi
  sync_json=$(curl -fsS "http://127.0.0.1:$rest/eth/v1/node/syncing" || echo '{}')
  peers_json=$(curl -fsS "http://127.0.0.1:$rest/eth/v1/node/peers?state=connected" || echo '{}')
  interesting=$( (grep -n "AHo4o\|5Mu85x\|Peer sync classification\|Sync peer joined\|SyncChain added\|UNDER_SSZ_MIN_SIZE\|invalid_request details\|beacon_blocks_by_range" "$run_dir/run.out" || true) | tail -n 80 | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
  startup_error=$( (grep -n "EADDRINUSE\|UnsupportedListenAddressesError\|uncaughtException" "$run_dir/run.out" || true) | tail -n 40 | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
  echo "{\"event\":\"sample\",\"iter\":$iter,\"stamp\":\"$stamp\",\"alive\":$alive,\"sync\":$sync_json,\"peers\":$peers_json,\"startup_error\":$startup_error,\"interesting\":$interesting}" | tee -a "$OUT"
  if grep -q "syncType=Advanced\|UNDER_SSZ_MIN_SIZE\|invalid_request details" "$run_dir/run.out"; then
    echo "{\"event\":\"target_hit\",\"iter\":$iter,\"stamp\":\"$stamp\",\"run_dir\":\"$run_dir\"}" | tee -a "$OUT"
    kill "$pid" || true
    wait "$pid" || true
    exit 0
  fi
  kill "$pid" || true
  wait "$pid" || true
  sleep 90
done
echo '{"event":"done","reason":"max_iters"}' | tee -a "$OUT"
