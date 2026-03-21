#!/usr/bin/env bash
# start-epbs-devnet.sh — Cold-start an EPBS devnet-0 Lodestar beacon node in <5 minutes
#
# This is the "just make it work" wrapper. Handles:
#   1. Worktree existence / branch checkout
#   2. Dependencies (pnpm install)
#   3. Build (pnpm build)
#   4. Artifact download
#   5. Node startup with engineMock
#
# Usage:
#   ./scripts/devnet/start-epbs-devnet.sh [OPTIONS]
#
# Options:
#   --devnet NAME         Devnet name (default: epbs-devnet-0)
#   --branch BRANCH       Git branch (default: epbs-devnet-0)
#   --worktree DIR        Worktree path (default: ~/lodestar-<devnet>)
#   --port PORT           libp2p port (default: 9200)
#   --rest-port PORT      REST API port (default: 9700)
#   --supernode           Enable all custody columns
#   --rebuild             Force rebuild even if packages/cli/bin exists
#   --skip-build          Skip build (useful if already built)
#   --extra-flags "..."   Additional lodestar flags
#   --dry-run             Print commands without executing
#   --clean               Wipe data dir and start fresh
#   -h, --help            Show this help
#
# Requires: git, node (v24+), pnpm, curl
# Environment: source ~/.nvm/nvm.sh && nvm use 24

set -euo pipefail

# --- Config ---
MAIN_REPO="$HOME/lodestar"
DEVNET="epbs-devnet-0"
BRANCH="epbs-devnet-0"
WORKTREE=""
PORT=9200
REST_PORT=9700
SUPERNODE=false
REBUILD=false
SKIP_BUILD=false
EXTRA_FLAGS=""
DRY_RUN=false
CLEAN=false

# --- Parse args ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --devnet)       DEVNET="$2"; shift 2 ;;
    --branch)       BRANCH="$2"; shift 2 ;;
    --worktree)     WORKTREE="$2"; shift 2 ;;
    --port)         PORT="$2"; shift 2 ;;
    --rest-port)    REST_PORT="$2"; shift 2 ;;
    --supernode)    SUPERNODE=true; shift ;;
    --rebuild)      REBUILD=true; shift ;;
    --skip-build)   SKIP_BUILD=true; shift ;;
    --extra-flags)  EXTRA_FLAGS="$2"; shift 2 ;;
    --dry-run)      DRY_RUN=true; shift ;;
    --clean)        CLEAN=true; shift ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
      exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

WORKTREE="${WORKTREE:-$HOME/lodestar-$DEVNET}"
ARTIFACTS="$WORKTREE/devnet-artifacts/$DEVNET"
DATA_DIR="$WORKTREE/runs/$DEVNET/beacon-data"
LOG_DIR="$WORKTREE/runs/$DEVNET"
BEACON_SCRIPT="$WORKTREE/scripts/run-devnet-beacon.sh"
SKILL_SCRIPT="$HOME/.openclaw/workspace/skills/join-devnet/scripts/run-devnet-beacon.sh"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

# --- Step 0: Node.js ---
if command -v nvm &>/dev/null; then
  nvm use 24 2>/dev/null || true
elif [[ -f "$HOME/.nvm/nvm.sh" ]]; then
  # shellcheck source=/dev/null
  source "$HOME/.nvm/nvm.sh"
  nvm use 24 2>/dev/null || true
fi

if ! command -v node &>/dev/null; then
  echo "ERROR: node not found. Install Node.js 24+ first." >&2
  exit 1
fi

NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
if (( NODE_VER < 22 )); then
  echo "WARNING: Node.js v$NODE_VER detected. v24+ recommended for Lodestar." >&2
fi

# --- Step 1: Worktree ---
if [[ ! -d "$WORKTREE/.git" ]] && [[ ! -f "$WORKTREE/.git" ]]; then
  log "Creating worktree at $WORKTREE on branch $BRANCH..."
  if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY RUN] git -C $MAIN_REPO worktree add $WORKTREE $BRANCH"
  else
    cd "$MAIN_REPO"
    git fetch origin "$BRANCH" 2>/dev/null || true
    if git rev-parse --verify "$BRANCH" &>/dev/null; then
      git worktree add "$WORKTREE" "$BRANCH"
    elif git rev-parse --verify "origin/$BRANCH" &>/dev/null; then
      git worktree add "$WORKTREE" -b "$BRANCH" "origin/$BRANCH"
    else
      echo "ERROR: Branch '$BRANCH' not found locally or on origin." >&2
      exit 1
    fi
  fi
else
  log "Worktree exists at $WORKTREE"
fi

cd "$WORKTREE"

# --- Step 2: Dependencies ---
if [[ ! -d "node_modules" ]] || [[ "$REBUILD" == true ]]; then
  log "Installing dependencies..."
  if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY RUN] pnpm install --frozen-lockfile"
  else
    pnpm install --frozen-lockfile 2>&1 | tail -5
  fi
else
  log "Dependencies already installed"
fi

# --- Step 3: Build ---
NEED_BUILD=false
if [[ "$SKIP_BUILD" == true ]]; then
  log "Skipping build (--skip-build)"
elif [[ "$REBUILD" == true ]]; then
  NEED_BUILD=true
elif [[ ! -f "packages/cli/bin/lodestar.js" ]]; then
  NEED_BUILD=true
elif [[ ! -d "packages/beacon-node/lib" ]]; then
  NEED_BUILD=true
fi

if [[ "$NEED_BUILD" == true ]]; then
  log "Building Lodestar (this may take 2-3 minutes)..."
  if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY RUN] pnpm build"
  else
    pnpm build 2>&1 | tail -10
    log "Build complete"
  fi
else
  log "Build artifacts exist (use --rebuild to force)"
fi

# --- Step 4: Beacon script ---
if [[ ! -f "$BEACON_SCRIPT" ]]; then
  log "Copying run-devnet-beacon.sh from skill..."
  # Always copy — this is non-destructive and needed for dry-run to work
  mkdir -p "$(dirname "$BEACON_SCRIPT")"
  cp "$SKILL_SCRIPT" "$BEACON_SCRIPT"
  chmod +x "$BEACON_SCRIPT"
else
  log "Beacon script exists at $BEACON_SCRIPT"
fi

# --- Step 5: Clean if requested ---
if [[ "$CLEAN" == true ]]; then
  log "Wiping data dir: $DATA_DIR"
  if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY RUN] rm -rf $DATA_DIR"
  else
    rm -rf "$DATA_DIR"
  fi
fi

# --- Step 6: Check for existing process ---
PID_FILE="$LOG_DIR/beacon.pid"
if [[ -f "$PID_FILE" ]]; then
  OLD_PID=$(cat "$PID_FILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    log "⚠️  Beacon node already running (PID $OLD_PID)"
    log "Stop it first: kill $OLD_PID"
    echo ""
    echo "Monitor existing node:"
    echo "  curl -s http://127.0.0.1:$REST_PORT/eth/v1/node/syncing | jq"
    echo "  tail -f $LOG_DIR/run.out"
    exit 0
  else
    log "Stale PID file found, removing"
    rm -f "$PID_FILE"
  fi
fi

# --- Step 7: Start ---
BEACON_ARGS=(
  --devnet "$DEVNET"
  --artifacts "$ARTIFACTS"
  --data-dir "$DATA_DIR"
  --log-dir "$LOG_DIR"
  --port "$PORT"
  --rest-port "$REST_PORT"
  --log-level info
)

[[ "$SUPERNODE" == true ]] && BEACON_ARGS+=(--supernode)
[[ -n "$EXTRA_FLAGS" ]] && BEACON_ARGS+=(--extra-flags "$EXTRA_FLAGS")
[[ "$DRY_RUN" == true ]] && BEACON_ARGS+=(--dry-run)

log "Starting beacon node on $DEVNET..."
echo ""
bash "$BEACON_SCRIPT" "${BEACON_ARGS[@]}"

if [[ "$DRY_RUN" != true ]]; then
  echo ""
  log "✅ EPBS devnet node started!"
  echo ""
  echo "Quick checks:"
  echo "  curl -s http://127.0.0.1:$REST_PORT/eth/v1/node/syncing | jq"
  echo "  curl -s http://127.0.0.1:$REST_PORT/eth/v1/node/peer_count | jq"
  echo "  tail -f $LOG_DIR/run.out"
  echo ""
  echo "Dora explorer: https://dora.${DEVNET}.ethpandaops.io/"
  echo ""
  echo "Stop: kill \$(cat $PID_FILE)"
fi
