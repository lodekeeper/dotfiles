#!/usr/bin/env bash
set -euo pipefail

API_BASE="${REVIEW_ROYALE_API:-http://127.0.0.1:3456}"
BATCH_SIZE="${BATCH_SIZE:-50}"
MAX_BATCHES="${MAX_BATCHES:-200}"
SLEEP_SECS="${SLEEP_SECS:-2}"
RETRY_SECS="${RETRY_SECS:-10}"

progress() {
  cd ~/review-royale
  docker compose exec -T rr-postgres psql -U postgres -d review_royale -At -F $'\t' \
    -c "SELECT COUNT(*)::text, COUNT(*) FILTER (WHERE category IS NOT NULL)::text FROM review_comments;"
}

read -r total categorized < <(progress)
echo "Starting categorization loop: categorized=${categorized}/${total}"

for i in $(seq 1 "$MAX_BATCHES"); do
  response=$(curl -fsS -X POST "${API_BASE}/api/categorize?batch_size=${BATCH_SIZE}" 2>/tmp/review-royale-categorize.err || true)
  if [[ -z "${response}" ]]; then
    err=$(cat /tmp/review-royale-categorize.err 2>/dev/null || true)
    echo "Batch ${i}: request failed: ${err:-unknown error}. Retrying in ${RETRY_SECS}s"
    sleep "$RETRY_SECS"
    continue
  fi

  processed=$(echo "$response" | jq -r '.processed // 0' 2>/dev/null || echo 0)
  errors=$(echo "$response" | jq -r '.errors // 0' 2>/dev/null || echo 0)

  if [[ "$processed" == "0" ]]; then
    read -r total categorized < <(progress)
    echo "Batch ${i}: no new items processed. Current ${categorized}/${total}. Stopping."
    break
  fi

  if (( i % 10 == 0 )); then
    read -r total categorized < <(progress)
    echo "Batch ${i}: processed=${processed} errors=${errors} total_progress=${categorized}/${total}"
  fi

  sleep "$SLEEP_SECS"
done

read -r total categorized < <(progress)
echo "Done: ${categorized}/${total} categorized"
