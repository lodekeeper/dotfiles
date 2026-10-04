#!/usr/bin/env bash
# Preflight: report panda auth state.
#
# Token *refresh* is handled by panda-server itself (panda >= 0.35 seeds a refresh
# token on login). Do NOT drive the unattended browser re-auth — disabled per
# nflaig 2026-06-19 ("panda server should handle the token refresh now"). The old
# scripts/panda/panda-reauth (Camoufox/GitHub-cookie device flow) is no longer
# called from here.
#
# No credential chmod: panda-server runs as the same uid (openclaw), so the
# 0600 credential file is readable (verified 2026-10-04: docker top panda-server
# -> openclaw, creds 0600, datasources load).
set -euo pipefail

if panda auth status 2>/dev/null | grep -q 'Status: Authenticated'; then
  panda auth status 2>/dev/null | grep -E 'Status|Expires'
  exit 0
fi

# Not authenticated: panda-server is responsible for refreshing. Do not browser
# re-auth. If datasources stay null, a human runs `panda auth login` once.
echo "panda: NOT authenticated. panda-server handles refresh; if datasources stay null run 'panda auth login' (do NOT use scripts/panda/panda-reauth)." >&2
exit 1
