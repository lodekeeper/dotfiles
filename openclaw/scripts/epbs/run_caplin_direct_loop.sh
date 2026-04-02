#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/openclaw/lodestar-9148-min
RUN_DIR="$ROOT/runs/pr9156-direct-caplin-loop"
DATA_DIR="$RUN_DIR/beacon-data"
LOG_FILE="$RUN_DIR/beacon.log"
REST_PORT=10070
P2P_PORT=9670
TARGET_MULTIADDR="/ip4/46.224.62.16/tcp/4401/p2p/16Uiu2HAmRCP28eEphgbDmrS7ihqAmtBjCwLUhh8aAV2fCc5Mu85x"
CHECKPOINT_URL="https://checkpoint-sync.epbs-devnet-1.ethpandaops.io"
MISS_LIMIT=${MISS_LIMIT:-6}
SLEEP_SEC=${SLEEP_SEC:-30}

mkdir -p "$RUN_DIR"
cd "$ROOT"

attempt=0
while true; do
  attempt=$((attempt + 1))
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] launch attempt=$attempt run_dir=$RUN_DIR rest_port=$REST_PORT p2p_port=$P2P_PORT" >&2

  if lsof -iTCP:"$REST_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    lsof -iTCP:"$REST_PORT" -sTCP:LISTEN -t | xargs -r kill
    sleep 1
  fi
  if lsof -iTCP:"$P2P_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    lsof -iTCP:"$P2P_PORT" -sTCP:LISTEN -t | xargs -r kill
    sleep 1
  fi

  node --max-old-space-size=8192 packages/cli/bin/lodestar.js beacon \
    --paramsFile devnet-artifacts/epbs-devnet-1/config.yaml \
    --genesisStateFile devnet-artifacts/epbs-devnet-1/genesis.ssz \
    --dataDir "$DATA_DIR" \
    --rest --rest.port "$REST_PORT" \
    --port "$P2P_PORT" \
    --logLevel debug \
    --logFile "$LOG_FILE" --logFileLevel debug \
    --execution.engineMock --eth1=false --discv5 false \
    --targetPeers 1 --disablePeerScoring --persistNetworkIdentity \
    --directPeers "$TARGET_MULTIADDR" \
    --checkpointSyncUrl "$CHECKPOINT_URL" \
    >> "$RUN_DIR/stdout.log" 2>&1 &
  pid=$!
  echo "$pid" > "$RUN_DIR/beacon.pid"

  misses=0
  while kill -0 "$pid" 2>/dev/null; do
    peers_json=$(curl -sf "http://127.0.0.1:$REST_PORT/eth/v1/node/peers" || true)
    if [[ -n "$peers_json" ]]; then
      peers_count=$(printf '%s' "$peers_json" | jq '.data | length' 2>/dev/null || echo 0)
    else
      peers_count=0
    fi

    sync_json=$(curl -sf "http://127.0.0.1:$REST_PORT/eth/v1/node/syncing" || true)
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] pid=$pid peers=$peers_count sync=${sync_json:-null}" >&2

    if [[ "$peers_count" -gt 0 ]]; then
      misses=0
    else
      misses=$((misses + 1))
      if [[ "$misses" -ge "$MISS_LIMIT" ]]; then
        echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] restarting pid=$pid after consecutive peer misses=$misses" >&2
        kill "$pid" 2>/dev/null || true
        wait "$pid" || true
        break
      fi
    fi

    sleep "$SLEEP_SEC"
  done

  wait "$pid" || true
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] process exited pid=$pid; relaunching after 5s" >&2
  sleep 5
done
