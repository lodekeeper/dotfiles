#!/usr/bin/env bash
# run-devnet-beacon.sh — Start a Lodestar beacon node on an ethpandaops devnet with engineMock
#
# Usage (run from the root of a BUILT Lodestar checkout, e.g. ~/lodestar):
#   bash ~/.openclaw/workspace/skills/join-devnet/scripts/run-devnet-beacon.sh --devnet <name> [OPTIONS]
#
# Examples:
#   run-devnet-beacon.sh --devnet glamsterdam-devnet-8                         # default ports
#   run-devnet-beacon.sh --devnet glamsterdam-devnet-8 --supernode             # with all custody columns
#   run-devnet-beacon.sh --devnet glamsterdam-devnet-8 --port 9300 --rest-port 9800
#   run-devnet-beacon.sh --devnet glamsterdam-devnet-8 --dry-run               # print command only
#
# --devnet is required: pick a live one with `panda devnets`.
# Artifacts/data/logs default to ~/devnet-runs/<devnet>/ (outside the repo, so they never land in a commit).
# Artifacts are auto-downloaded if missing.

set -euo pipefail

DEVNET=""
ARTIFACTS=""
DATA_DIR=""
LOG_DIR=""
PORT=9200
REST_PORT=9700
SUPERNODE=false
LOG_LEVEL=info
EXTRA_FLAGS=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --devnet)       DEVNET="$2"; shift 2 ;;
    --artifacts)    ARTIFACTS="$2"; shift 2 ;;
    --data-dir)     DATA_DIR="$2"; shift 2 ;;
    --log-dir)      LOG_DIR="$2"; shift 2 ;;
    --port)         PORT="$2"; shift 2 ;;
    --rest-port)    REST_PORT="$2"; shift 2 ;;
    --supernode)    SUPERNODE=true; shift ;;
    --log-level)    LOG_LEVEL="$2"; shift 2 ;;
    --extra-flags)  EXTRA_FLAGS="$2"; shift 2 ;;
    --dry-run)      DRY_RUN=true; shift ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
      exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

if [[ -z "$DEVNET" ]]; then
  echo "ERROR: --devnet <name> is required (pick a live one: panda devnets)" >&2
  exit 1
fi

ARTIFACTS="${ARTIFACTS:-$HOME/devnet-runs/$DEVNET/artifacts}"
DATA_DIR="${DATA_DIR:-$HOME/devnet-runs/$DEVNET/beacon-data}"
LOG_DIR="${LOG_DIR:-$HOME/devnet-runs/$DEVNET}"

# Auto-download artifacts if missing
if [[ ! -f "$ARTIFACTS/config.yaml" ]] || [[ ! -f "$ARTIFACTS/genesis.ssz" ]]; then
  echo "Downloading artifacts for $DEVNET..."
  mkdir -p "$ARTIFACTS"
  BASE="https://config.${DEVNET}.ethpandaops.io"
  curl -sfL "$BASE/cl/config.yaml" -o "$ARTIFACTS/config.yaml" || { echo "ERROR: failed to download config.yaml from $BASE"; exit 1; }
  curl -sfL "$BASE/cl/genesis.ssz" -o "$ARTIFACTS/genesis.ssz" || { echo "ERROR: failed to download genesis.ssz from $BASE"; exit 1; }
  curl -sfL "$BASE/cl/bootstrap_nodes.txt" -o "$ARTIFACTS/bootstrap_nodes.txt" 2>/dev/null || echo "(no bootstrap_nodes.txt)"
  curl -sfL "$BASE/api/v1/nodes/inventory" -o "$ARTIFACTS/inventory.json" 2>/dev/null || true
  echo "Artifacts saved to $ARTIFACTS/"
fi

BOOTNODES=""
if [[ -f "$ARTIFACTS/bootstrap_nodes.txt" ]]; then
  BOOTNODES=$(tr '\n' ',' < "$ARTIFACTS/bootstrap_nodes.txt" | sed 's/,$//')
fi

mkdir -p "$DATA_DIR" "$LOG_DIR"

CMD=(
  node --max-old-space-size=8192
  packages/cli/bin/lodestar.js beacon
  --paramsFile "$ARTIFACTS/config.yaml"
  --genesisStateFile "$ARTIFACTS/genesis.ssz"
  --dataDir "$DATA_DIR"
  --rest --rest.port "$REST_PORT"
  --port "$PORT"
  --logLevel "$LOG_LEVEL"
  --logFile "$LOG_DIR/beacon.log"
  --logFileLevel debug
  --execution.engineMock
  --network.connectToDiscv5Bootnodes
  --disablePeerScoring
  --persistNetworkIdentity
)

[[ -n "$BOOTNODES" ]] && CMD+=(--bootnodes "$BOOTNODES")
[[ "$SUPERNODE" == true ]] && CMD+=(--supernode)
# shellcheck disable=SC2206
[[ -n "$EXTRA_FLAGS" ]] && CMD+=($EXTRA_FLAGS)

echo "=== Lodestar Beacon Node ==="
echo "Devnet:    $DEVNET"
echo "Artifacts: $ARTIFACTS"
echo "Data:      $DATA_DIR"
echo "Logs:      $LOG_DIR/beacon.log"
echo "Ports:     libp2p=$PORT rest=$REST_PORT"
echo "Supernode: $SUPERNODE"
echo ""

if [[ "$DRY_RUN" == true ]]; then
  echo "[DRY RUN] ${CMD[*]}"
  exit 0
fi

if [[ ! -f packages/cli/bin/lodestar.js || ! -d packages/cli/lib ]]; then
  echo "ERROR: run from the root of a built Lodestar checkout (no packages/cli/lib in $PWD)" >&2
  exit 1
fi

echo "Starting... (PID file: $LOG_DIR/beacon.pid)"
# setsid + disown: fully detached, so a long sync survives session teardown (nohup does not)
setsid "${CMD[@]}" < /dev/null > "$LOG_DIR/run.out" 2>&1 &
PID=$!
disown
echo "$PID" > "$LOG_DIR/beacon.pid"
sleep 3
if ! kill -0 "$PID" 2>/dev/null; then
  echo "ERROR: beacon exited right after start — tail of $LOG_DIR/run.out:" >&2
  tail -20 "$LOG_DIR/run.out" >&2
  exit 1
fi
echo "Started with PID $PID"
echo ""
echo "Monitor:"
echo "  tail -f $LOG_DIR/run.out"
echo "  curl -s http://127.0.0.1:$REST_PORT/eth/v1/node/syncing | jq"
echo ""
echo "Stop:"
echo "  kill \$(cat $LOG_DIR/beacon.pid)"
