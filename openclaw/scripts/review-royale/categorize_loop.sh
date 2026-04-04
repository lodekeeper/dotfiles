#!/usr/bin/env bash
# Single-threaded AI categorization loop for Review Royale
# Processes uncategorized comments in batches of 50 with proper error handling
set -euo pipefail

API_BASE="${REVIEW_ROYALE_API:-http://127.0.0.1:3456}"
BATCH_SIZE=50
DELAY_BETWEEN_BATCHES=5  # seconds
MAX_RETRIES=3
RETRY_DELAY=30  # seconds

echo "Starting categorization loop: API=$API_BASE batch=$BATCH_SIZE delay=${DELAY_BETWEEN_BATCHES}s"

# Get initial count
total=$(curl -sf "${API_BASE}/api/repos" | jq 'length' 2>/dev/null || echo "?")
echo "Repos tracked: $total"

batch_num=0
consecutive_errors=0

while true; do
  batch_num=$((batch_num + 1))
  
  result=$(curl -sf --max-time 120 -X POST "${API_BASE}/api/categorize?batch_size=${BATCH_SIZE}" 2>&1) || {
    consecutive_errors=$((consecutive_errors + 1))
    echo "Batch $batch_num: HTTP error (consecutive: $consecutive_errors)"
    if [ $consecutive_errors -ge $MAX_RETRIES ]; then
      echo "Too many consecutive errors ($consecutive_errors). Stopping."
      exit 1
    fi
    echo "Retrying in ${RETRY_DELAY}s..."
    sleep $RETRY_DELAY
    continue
  }
  
  processed=$(echo "$result" | jq -r '.processed // 0' 2>/dev/null)
  errors=$(echo "$result" | jq -r '.errors // 0' 2>/dev/null)
  
  if [ "$processed" = "0" ] || [ -z "$processed" ]; then
    echo "Batch $batch_num: no more uncategorized comments. Done!"
    break
  fi
  
  consecutive_errors=0  # Reset on success
  
  if [ $((batch_num % 10)) -eq 0 ]; then
    echo "Batch $batch_num: processed=$processed errors=$errors (est. ~$((batch_num * BATCH_SIZE + 1150)) categorized)"
  fi
  
  sleep $DELAY_BETWEEN_BATCHES
done

echo "=== Categorization complete ==="
