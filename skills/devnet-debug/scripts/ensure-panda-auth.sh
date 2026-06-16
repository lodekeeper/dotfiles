#!/usr/bin/env bash
# Ensure panda has a valid auth token; re-auth unattended via the stored GitHub
# cookie jar if it has expired. panda issues 1h tokens with no refresh.
set -euo pipefail
WS="${PANDA_WS:-$HOME/.openclaw/workspace}"

if panda auth status 2>/dev/null | grep -q 'Status: Authenticated'; then
  panda auth status 2>/dev/null | grep -E 'Status|Expires'
  exit 0
fi

echo "panda: not authenticated -> running panda-reauth"
exec "$WS/scripts/panda/panda-reauth"
