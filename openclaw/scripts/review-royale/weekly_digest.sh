#!/usr/bin/env bash
# Review Royale Weekly Digest - generates digest text from the API
# Called by OpenClaw cron, output is used by the cron agent to post to Discord

set -euo pipefail

API_BASE="${REVIEW_ROYALE_API:-http://localhost:3456}"

# Fetch weekly leaderboard for both repos
lodestar_lb=$(curl -sf "${API_BASE}/api/repos/ChainSafe/lodestar/leaderboard?period=week&limit=10" 2>/dev/null || echo "[]")
lodestar_z_lb=$(curl -sf "${API_BASE}/api/repos/ChainSafe/lodestar-z/leaderboard?period=week&limit=5" 2>/dev/null || echo "[]")

# Check if we have any data
lodestar_count=$(echo "$lodestar_lb" | jq 'length')
lodestar_z_count=$(echo "$lodestar_z_lb" | jq 'length')

if [ "$lodestar_count" = "0" ] && [ "$lodestar_z_count" = "0" ]; then
  echo "NO_DATA"
  exit 0
fi

echo "=== WEEKLY DIGEST DATA ==="
echo ""
echo "## Lodestar Weekly Leaderboard (top 10)"
echo "$lodestar_lb" | jq -r '.[] | "\(.rank). \(.user.login) — \(.score) XP (\(.stats.reviews_given) reviews, \(.stats.comments_written) comments)"'
echo ""
echo "## Lodestar-z Weekly Leaderboard (top 5)"
echo "$lodestar_z_lb" | jq -r '.[] | "\(.rank). \(.user.login) — \(.score) XP (\(.stats.reviews_given) reviews)"'
echo ""

# Global stats
echo "## Stats"
echo "Lodestar reviewers this week: $lodestar_count"
total_xp=$(echo "$lodestar_lb" | jq '[.[].score] | add // 0')
total_reviews=$(echo "$lodestar_lb" | jq '[.[].stats.reviews_given] | add // 0')
total_comments=$(echo "$lodestar_lb" | jq '[.[].stats.comments_written] | add // 0')
echo "Total XP: $total_xp"
echo "Total reviews: $total_reviews"  
echo "Total comments: $total_comments"

# Champion
champion=$(echo "$lodestar_lb" | jq -r '.[0].user.login // "nobody"')
champion_xp=$(echo "$lodestar_lb" | jq -r '.[0].score // 0')
echo "Champion: $champion ($champion_xp XP)"
