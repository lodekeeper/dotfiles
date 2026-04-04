#!/bin/bash
# Check for unnotified Review Royale achievements and output them as JSON
# Used by OpenClaw cron to post to Discord

set -euo pipefail

RESULT=$(docker exec review-royale-rr-postgres-1 psql -U postgres -d review_royale -t -A -c "
SELECT json_agg(row_to_json(t))
FROM (
  SELECT u.login, a.emoji, a.name as achievement_name, a.description, ua.unlocked_at
  FROM user_achievements ua
  JOIN users u ON u.id = ua.user_id
  JOIN achievements a ON a.id = ua.achievement_id
  WHERE ua.notified_at IS NULL
  ORDER BY ua.unlocked_at DESC
  LIMIT 10
) t;" 2>/dev/null)

if [ -z "$RESULT" ] || [ "$RESULT" = "" ] || [ "$RESULT" = "null" ]; then
    echo "NO_PENDING"
    exit 0
fi

COUNT=$(echo "$RESULT" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
if [ "$COUNT" = "0" ]; then
    echo "NO_PENDING"
    exit 0
fi

echo "$RESULT" | python3 -c "
import sys, json
from collections import defaultdict

achievements = json.load(sys.stdin)
# Group by user
by_user = defaultdict(list)
for a in achievements:
    by_user[a['login']].append(a)

lines = []
lines.append('🏆 **New Achievements Unlocked!**')
lines.append('')

for user, achs in by_user.items():
    for a in achs:
        emoji = a.get('emoji', '🏆')
        name = a.get('achievement_name', 'Unknown')
        desc = a.get('description', '')
        lines.append(f'{emoji} **{user}** earned **{name}**! _{desc}_')

print('\n'.join(lines))
"

# Mark as notified
docker exec review-royale-rr-postgres-1 psql -U postgres -d review_royale -c "
UPDATE user_achievements SET notified_at = now() WHERE notified_at IS NULL;" >/dev/null 2>&1
