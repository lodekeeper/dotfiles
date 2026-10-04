#!/usr/bin/env bash
set -euo pipefail

# Nudge a Telegram topic session. Kept for existing callers (github-notifications
# cron prompt), now a thin wrapper around route-topic-nudge.sh.
#
# OpenClaw 2026.9.8 rejects the old route (agent-exec `openclaw gateway call
# sessions.send` "would lose inter-session attribution"), so this no longer
# calls sessions.send. route-topic-nudge.sh writes the body to a file, wakes the
# topic session via the inbound webhook when that is enabled, and otherwise
# posts a short visible notice in the topic.
#
# Usage:
#   nudge-topic-session.sh <sessionKey> "<message>"
#   printf "<message>" | nudge-topic-session.sh <sessionKey>
#
# Exit codes:
#   0  - topic session woken, or visible notice posted in the topic
#   2  - bad invocation
#   4  - routing failed (no wake, no visible notice)

ROUTE="$(dirname "$(readlink -f "$0")")/route-topic-nudge.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '3,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

if [[ $# -lt 1 ]]; then
  echo "usage: nudge-topic-session.sh <sessionKey> \"<message>\"" >&2
  exit 2
fi

SESSION_KEY="$1"
shift

if [[ $# -gt 0 ]]; then
  MESSAGE="$*"
else
  if [[ -t 0 ]]; then
    echo "usage: nudge-topic-session.sh <sessionKey> \"<message>\"" >&2
    exit 2
  fi
  MESSAGE="$(cat)"
fi

if [[ -z "${MESSAGE//[$'\t\r\n ']/}" ]]; then
  echo "nudge-topic-session: refusing to send an empty message" >&2
  exit 2
fi

SUMMARY="$(printf '%s\n' "$MESSAGE" | sed -n '/[^[:space:]]/{p;q}' | cut -c1-300)"

set +e
printf '%s' "$MESSAGE" | "$ROUTE" --summary "$SUMMARY" "$SESSION_KEY"
RC=$?
set -e

case "$RC" in
  0|10) exit 0 ;;
  2) exit 2 ;;
  *) exit 4 ;;
esac
