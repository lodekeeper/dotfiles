#!/bin/bash
# Review Royale MANUAL one-time refresh (crons stay paused).
# Incremental backfill of both tracked repos + categorize + recalculate.
# Params rationale:
#   - NO skip_existing: it skips the ENTIRE PR if already in DB (backfill.rs:148),
#     which would MISS new reviews on pre-existing PRs. We want those.
#   - NO force: avoids resetting last_synced_at into a full 365-day re-backfill.
#   - Incremental window = PRs updated since last_synced_at; reviews dedupe on insert.
# Does NOT run the Discord-posting crons (weekly_digest.sh / check_achievements.sh) — data only.
set -uo pipefail
API="http://127.0.0.1:3456"
PIPE="$(dirname "$0")/post_sync_pipeline.sh"

echo "START $(date -u +%FT%TZ)"
for repo in ChainSafe/lodestar ChainSafe/lodestar-z; do
  echo "=== backfill $repo ==="
  curl -s --max-time 900 -X POST "$API/api/backfill/$repo" || echo "!! $repo backfill request failed"
  echo
done
echo "=== post-sync pipeline (categorize + recalculate) ==="
bash "$PIPE" || echo "!! pipeline failed"
echo "END $(date -u +%FT%TZ)"
