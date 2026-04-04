#!/bin/bash
# Review Royale post-sync pipeline: categorize all new comments + recalculate XP
# Runs after each sync cycle to keep scoring up to date
set -euo pipefail

API="http://127.0.0.1:3456"
BATCH_SIZE=50
DELAY=3

echo "=== Review Royale Post-Sync Pipeline ==="

# Step 1: Check how many uncategorized comments exist
STATS=$(curl -sf "$API/api/categorize" 2>/dev/null || echo '{}')
UNCATEGORIZED=$(echo "$STATS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('uncategorized',0))" 2>/dev/null || echo "0")

if [ "$UNCATEGORIZED" = "0" ]; then
    echo "No uncategorized comments. Skipping categorization."
else
    echo "Categorizing $UNCATEGORIZED comments..."
    BATCH=0
    while true; do
        BATCH=$((BATCH + 1))
        RESULT=$(curl -sf --max-time 120 -X POST "$API/api/categorize?batch_size=$BATCH_SIZE" 2>/dev/null || echo '{"processed":0}')
        PROCESSED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('processed',0))" 2>/dev/null || echo "0")
        
        if [ "$PROCESSED" = "0" ] || [ -z "$PROCESSED" ]; then
            echo "Categorization done after $BATCH batches."
            break
        fi
        
        # Progress every 10 batches
        if [ $((BATCH % 10)) -eq 0 ]; then
            echo "  Batch $BATCH: $PROCESSED processed"
        fi
        
        sleep $DELAY
    done
fi

# Step 2: Recalculate XP
echo "Recalculating XP..."
RECALC=$(curl -sf --max-time 300 -X POST "$API/api/recalculate" 2>/dev/null || echo '{"status":"error"}')
STATUS=$(echo "$RECALC" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('status','?')}: {d.get('total_reviews',0)} reviews, {d.get('total_sessions',0)} sessions, {d.get('total_xp_awarded',0)} XP, {d.get('users_updated',0)} users\")" 2>/dev/null || echo "unknown")
echo "Recalculation: $STATUS"

echo "=== Pipeline complete ==="
