#!/usr/bin/env bash
# Preflight: report panda auth state and make sure the containerized panda-server
# can read its credential file.
#
# Token *refresh* is handled by panda-server itself (panda >= 0.35 seeds a refresh
# token on login). Do NOT drive the unattended browser re-auth — disabled per
# nflaig 2026-06-19 ("panda server should handle the token refresh now"). The old
# scripts/panda/panda-reauth (Camoufox/GitHub-cookie device flow) is no longer
# called from here.
set -euo pipefail
CREDDIR="$HOME/.config/panda/credentials"

# panda-server runs in a container as a different uid but shares group 'docker'.
# A token refresh can leave the credential file 0600, which the container then
# cannot read -> "datasource refresh failed: permission denied" -> 0 datasources
# (datasources=null). Restore group-read so the server can read it. Idempotent.
chmod -f 640 "$CREDDIR"/*.json 2>/dev/null || true

if panda auth status 2>/dev/null | grep -q 'Status: Authenticated'; then
  panda auth status 2>/dev/null | grep -E 'Status|Expires'
  exit 0
fi

# Not authenticated: panda-server is responsible for refreshing. Do not browser
# re-auth. If datasources stay null, a human runs `panda auth login` once.
echo "panda: NOT authenticated. panda-server handles refresh; if datasources stay null run 'panda auth login' (do NOT use scripts/panda/panda-reauth)." >&2
exit 1
