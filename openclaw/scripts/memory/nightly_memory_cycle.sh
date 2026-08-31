#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

# Source nvm for qmd
source ~/.nvm/nvm.sh
nvm use 22 2>/dev/null

LOG_DIR="memory"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/memory-cycle-$(date -u +%F).log"

# Serialize overlapping invocations: a cron-harness-timeout retry can otherwise
# start while a still-running prior run is mid-QMD-embed, and both race for the
# same embedding session (confirmed data loss 2026-08-22 + 2026-08-30, see
# notes/autonomy-gaps.md). Block until any in-progress cycle finishes instead
# of racing it; lock auto-releases when this script's fd 200 closes on exit.
LOCK_FILE="/tmp/lodekeeper-nightly-memory-cycle.lock"
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
  echo "[$(date -u +%FT%TZ)] Another nightly memory cycle is already running — waiting for it to finish" >> "$LOG_FILE"
  flock 200
  echo "[$(date -u +%FT%TZ)] Lock acquired after wait — prior cycle finished, proceeding" >> "$LOG_FILE"
fi

{
  echo "[$(date -u +%FT%TZ)] Starting nightly memory cycle"

  echo "Step 1: consolidate recent daily notes -> bank state/views (LLM auto)"
  # Scan last 7 days to catch any missed consolidation runs
  python3 scripts/memory/consolidate_from_daily.py --limit 7 --mode auto --apply

  echo "Step 2: regenerate entity pages from state"
  python3 scripts/memory/generate_entity_pages.py --prune-stale-person-noise

  echo "Step 3: rebuild local SQLite FTS index"
  python3 scripts/memory/rebuild_index.py

  echo "Step 4: update QMD collections + embeddings"
  qmd update 2>&1 || true
  qmd embed 2>&1 || true

  echo "Step 5: prune old cycle logs (keep last 14 days)"
  find "$LOG_DIR" -name "memory-cycle-*.log" -mtime +14 -delete 2>/dev/null || true

  echo "[$(date -u +%FT%TZ)] Nightly memory cycle complete"
} >> "$LOG_FILE" 2>&1

echo "Wrote $LOG_FILE"
