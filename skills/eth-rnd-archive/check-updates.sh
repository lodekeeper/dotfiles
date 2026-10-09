#!/usr/bin/env bash
# Eth R&D Archive — check for new messages in tracked channels
# Usage: bash check-updates.sh [specific-date]
# Outputs new messages as JSON to stdout

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="${ETH_RND_ARCHIVE_CONFIG:-$SCRIPT_DIR/config.json}"
STATE="${ETH_RND_ARCHIVE_STATE:-$SCRIPT_DIR/state.json}"
REPO_PATH="${ETH_RND_ARCHIVE_REPO_PATH:-$(python3 -c "import json, os; print(os.path.expanduser(json.load(open('$CONFIG')).get('repoPath', '~/ethereum-repos/eth-rnd-archive')))")}"
NOTES_PATH="$(python3 -c "import json, os; print(os.path.expanduser(json.load(open('$CONFIG')).get('notesPath', '/home/openclaw/.openclaw/workspace/memory/eth-rnd-archive-notes')))")"
SPECIFIC_DATE="${1:-}"

# Ensure notes directory exists
mkdir -p "$NOTES_PATH"

# Read tracked channels from config
CHANNELS=$(python3 -c "import json; print('\n'.join(json.load(open('$CONFIG'))['channels']))")

# Print the non-empty "parent" channel of a thread file (empty for top-level channel files)
thread_parent() {
    python3 -c "import json, sys; print(next((m.get('parent', '') for m in json.load(open(sys.argv[1])) if m.get('parent')), ''))" "$1" 2>/dev/null || true
}

# Pull latest changes (timeout 30s to prevent hanging the cron budget)
cd "$REPO_PATH"
timeout 30 git pull --quiet 2>/dev/null || true

CURRENT_COMMIT=$(git rev-parse HEAD)
LAST_COMMIT=$(python3 -c "import json; print(json.load(open('$STATE')).get('lastCommit', ''))" 2>/dev/null || echo "")

if [ -n "$SPECIFIC_DATE" ]; then
    # Check a specific date across all tracked channels
    echo "{"
    echo "  \"mode\": \"specific-date\","
    echo "  \"date\": \"$SPECIFIC_DATE\","
    echo "  \"channels\": {"
    FIRST=true
    while IFS= read -r channel; do
        FILE="$REPO_PATH/$channel/$SPECIFIC_DATE.json"
        if [ -f "$FILE" ]; then
            if [ "$FIRST" = true ]; then FIRST=false; else echo ","; fi
            MSG_COUNT=$(python3 -c "import json; print(len(json.load(open('$FILE'))))")
            echo -n "    \"$channel\": {\"file\": \"$FILE\", \"messages\": $MSG_COUNT}"
        fi
    done <<< "$CHANNELS"
    # Top-level thread dirs whose parent is a tracked channel (keyed "<channel>/<thread dir>")
    for FILE in "$REPO_PATH"/*/"$SPECIFIC_DATE.json"; do
        [ -f "$FILE" ] || continue
        DIR=$(basename "$(dirname "$FILE")")
        echo "$CHANNELS" | grep -Fqx -- "$DIR" && continue
        PARENT=$(thread_parent "$FILE")
        if [ -n "$PARENT" ] && echo "$CHANNELS" | grep -Fqx -- "$PARENT"; then
            if [ "$FIRST" = true ]; then FIRST=false; else echo ","; fi
            MSG_COUNT=$(python3 -c "import json; print(len(json.load(open('$FILE'))))")
            echo -n "    \"$PARENT/$DIR\": {\"file\": \"$FILE\", \"messages\": $MSG_COUNT}"
        fi
    done
    echo ""
    echo "  },"
    echo "  \"commit\": \"$CURRENT_COMMIT\""
    echo "}"
elif [ -z "$LAST_COMMIT" ] || [ "$LAST_COMMIT" = "$CURRENT_COMMIT" ]; then
    # First run or no changes — check today's files
    TODAY=$(date -u +%Y-%m-%d)
    echo "{"
    echo "  \"mode\": \"initial-or-no-change\","
    echo "  \"date\": \"$TODAY\","
    echo "  \"commit\": \"$CURRENT_COMMIT\","
    echo "  \"changed_files\": []"
    echo "}"
else
    # Diff mode — find changed files since last commit
    CHANGED_FILES=$(git -c core.quotePath=false diff --name-only "$LAST_COMMIT" "$CURRENT_COMMIT" 2>/dev/null || git -c core.quotePath=false diff --name-only HEAD~1 HEAD)
    
    echo "{"
    echo "  \"mode\": \"diff\","
    echo "  \"from\": \"$LAST_COMMIT\","
    echo "  \"to\": \"$CURRENT_COMMIT\","
    echo "  \"tracked_changes\": ["
    FIRST=true
    while IFS= read -r file; do
        # Extract channel name (first path component)
        CHANNEL=$(echo "$file" | cut -d'/' -f1)
        THREAD=""
        # Since ~2026-10-03 threads are written as top-level dirs (not <channel>/_threads/);
        # attribute them to their tracked channel via the messages' "parent" field.
        if ! echo "$CHANNELS" | grep -Fqx -- "$CHANNEL" && [[ "$file" == *.json ]] && [ -f "$REPO_PATH/$file" ]; then
            PARENT=$(thread_parent "$REPO_PATH/$file")
            if [ -n "$PARENT" ] && echo "$CHANNELS" | grep -Fqx -- "$PARENT"; then
                THREAD="$CHANNEL"
                CHANNEL="$PARENT"
            fi
        fi
        # Check if this channel is tracked (also match _threads subdirs)
        if echo "$CHANNELS" | grep -Fqx -- "$CHANNEL"; then
            if [[ "$file" == *.json ]] && [ -f "$REPO_PATH/$file" ]; then
                if [ "$FIRST" = true ]; then FIRST=false; else echo ","; fi
                MSG_COUNT=$(python3 -c "import json; print(len(json.load(open('$REPO_PATH/$file'))))" 2>/dev/null || echo "0")
                # messages = total in file (append-only archive); new_messages = actual delta vs
                # last-checked commit (file may pre-date LAST_COMMIT, so 0 previous is a valid case).
                # Only entries from index new_since_index onward are new — slice, don't re-read the whole file.
                PREV_COUNT=$(git show "$LAST_COMMIT:$file" 2>/dev/null | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
                NEW_COUNT=$((MSG_COUNT - PREV_COUNT))
                echo -n "    {\"channel\": \"$CHANNEL\", \"thread\": \"$THREAD\", \"file\": \"$file\", \"messages\": $MSG_COUNT, \"new_messages\": $NEW_COUNT, \"new_since_index\": $PREV_COUNT}"
            fi
        fi
    done <<< "$CHANGED_FILES"
    echo ""
    echo "  ]"
    echo "}"
fi

# Update state
python3 -c "
import json
from datetime import datetime, timezone
state = json.load(open('$STATE'))
state['lastCommit'] = '$CURRENT_COMMIT'
state['lastCheck'] = datetime.now(timezone.utc).isoformat()
json.dump(state, open('$STATE', 'w'), indent=2)
"
