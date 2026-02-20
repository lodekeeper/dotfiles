#!/bin/bash
# Update agent status file
# Usage: update-status.sh <status> [task]
# Status: idle | working | busy
STATUS="${1:-idle}"
TASK="${2:-null}"
FILE="/home/openclaw/.openclaw/workspace/memory/agent-status.json"

if [ "$TASK" = "null" ]; then
  TASK_JSON="null"
else
  TASK_JSON="\"$TASK\""
fi

cat > "$FILE" << EOF
{
  "status": "$STATUS",
  "currentTask": $TASK_JSON,
  "updatedAt": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"
}
EOF
