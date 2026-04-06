#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

# Source nvm for qmd
source ~/.nvm/nvm.sh
nvm use 22 2>/dev/null

LOG_DIR="memory"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/memory-cycle-$(date -u +%F).log"

{
  echo "[$(date -u +%FT%TZ)] Starting nightly memory cycle"

  echo "Step 1: consolidate recent daily notes -> bank state/views (LLM auto)"
  # Scan last 7 days to catch any missed consolidation runs
  python3 scripts/memory/consolidate_from_daily.py --limit 7 --mode auto --apply

  echo "Step 2: regenerate entity pages from state"
  python3 scripts/memory/generate_entity_pages.py

  echo "Step 3: rebuild local SQLite FTS index"
  python3 scripts/memory/rebuild_index.py

  echo "Step 4: update QMD collections (skip embeddings on CPU)"
  qmd update 2>&1 || true
  # qmd embed disabled: CPU-only fallback causes 9+ min hangs
  # Re-enable when CUDA or GPU acceleration available

  echo "Step 5: prune old cycle logs (keep last 14 days)"
  find "$LOG_DIR" -name "memory-cycle-*.log" -mtime +14 -delete 2>/dev/null || true

  echo "[$(date -u +%FT%TZ)] Nightly memory cycle complete"
} >> "$LOG_FILE" 2>&1

echo "Wrote $LOG_FILE"
