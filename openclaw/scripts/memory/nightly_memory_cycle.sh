#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

# Source nvm for qmd
source ~/.nvm/nvm.sh
nvm use 22 2>/dev/null
# `nvm use 22` prepends v22.23.3 (no qmd), so PATH would fall through to the v24-built
# qmd (ABI mismatch / Node 24 teardown SIGABRT). ~/.local/bin/qmd pins qmd to its
# working Node 22.22.0 install; put it first.
export PATH="$HOME/.local/bin:$PATH"

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

  echo "Step 4: update QMD collections"
  qmd update 2>&1 || true

  # Embeddings run in a detached worker: the embed phase alone exceeds the cron's 900s timeout
  # (details in nightly_embed_phase.sh). fd 200 holds this cycle's lock, so close it for the worker;
  # it waits for this script to exit, then takes the lock itself. The worker logs Step 4b and the
  # final "Nightly memory cycle complete" line (check_cron_health.py keys off that exact line).
  # bank/facts.md is kept out of the memory-bank collection (`**/!(facts).md` in
  # ~/.config/qmd/index.yml); its facts stay searchable via query_index.py, backed by state.json.
  echo "Step 4 (embeddings): handed to detached scripts/memory/nightly_embed_phase.sh; it logs Step 4b and the final completion line below"
  setsid nohup scripts/memory/nightly_embed_phase.sh 200>&- </dev/null >> "$LOG_FILE" 2>&1 &

  echo "Step 5: prune old cycle logs (keep last 14 days)"
  find "$LOG_DIR" -name "memory-cycle-*.log" -mtime +14 -delete 2>/dev/null || true

  echo "[$(date -u +%FT%TZ)] Nightly memory cycle steps 1-5 done; embeddings continue in the detached worker"
} >> "$LOG_FILE" 2>&1

echo "Wrote $LOG_FILE"
