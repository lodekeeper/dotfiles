#!/usr/bin/env bash
# check-github-access.sh — fast pre-flight guard for GitHub-dependent crons.
#
# Usage: check-github-access.sh [--max-age-minutes N] [--state-file path]
#
# Exit codes:
#   0 — GitHub accessible
#   2 — GitHub suspended/inaccessible, or API rate-limited (safe to skip GH work)
#   1 — unexpected error
#
# Caches the access-check result for --max-age-minutes (default: 10) to avoid
# hammering the API when multiple crons run close together. A rate-limit verdict
# is transient (NOT a suspension) and is cached only until the core limit resets.
set -euo pipefail

MAX_AGE_MINUTES=10
STATE_FILE="${WORKSPACE:-$HOME/.openclaw/workspace}/tmp/github-access-state.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-age-minutes) MAX_AGE_MINUTES="$2"; shift 2 ;;
    --state-file)      STATE_FILE="$2";      shift 2 ;;
    -h|--help)
      echo "Usage: check-github-access.sh [--max-age-minutes N] [--state-file path]"
      echo "Exits 0 if GitHub is accessible, 2 if suspended/inaccessible/rate-limited."
      exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

mkdir -p "$(dirname "$STATE_FILE")"

_age_ok() {
  [[ -f "$STATE_FILE" ]] || return 1
  local checked_at
  checked_at=$(python3 -c "
import json, sys, time
try:
    d = json.loads(open('$STATE_FILE').read())
    print(int(d.get('checked_at_epoch', 0)))
except Exception:
    print(0)
" 2>/dev/null) || return 1
  local now
  now=$(date -u +%s)
  local age_min=$(( (now - checked_at) / 60 ))
  [[ "$age_min" -lt "$MAX_AGE_MINUTES" ]]
}

_cached_status() {
  python3 -c "
import json
try:
    d = json.loads(open('$STATE_FILE').read())
    print(d.get('status','unknown'))
except Exception:
    print('unknown')
" 2>/dev/null || echo "unknown"
}

_cached_until_epoch() {
  python3 -c "
import json
try:
    d = json.loads(open('$STATE_FILE').read())
    print(int(d.get('until_epoch', 0)))
except Exception:
    print(0)
" 2>/dev/null || echo 0
}

_write_state() {
  local status="$1" until_epoch="${2:-}"
  python3 - "$STATE_FILE" "$status" "$until_epoch" << 'PY'
import json, sys, time
path, status, until_epoch = sys.argv[1], sys.argv[2], sys.argv[3]
state = {"status": status, "checked_at_epoch": int(time.time())}
if until_epoch:
    state["until_epoch"] = int(until_epoch)
with open(path, 'w') as f:
    json.dump(state, f, indent=2)
    f.write("\n")
PY
}

# A cached rate-limit verdict is valid until its recorded reset time (not the
# MAX_AGE window), so recovery is noticed promptly and we stop poking the API
# while it is refusing us.
if [[ "$(_cached_status)" == "rate_limited" ]]; then
  cached_until=$(_cached_until_epoch)
  if [[ "$(date -u +%s)" -lt "$cached_until" ]]; then
    echo "GITHUB_ACCESS: rate-limited until $(date -u -d "@$cached_until" +%H:%M:%SZ) — skip GH-dependent work (transient, NOT suspended; cached)"
    exit 2
  fi
fi

if _age_ok; then
  status=$(_cached_status)
  if [[ "$status" == "ok" ]]; then
    echo "GITHUB_ACCESS: ok (cached)"
    exit 0
  elif [[ "$status" == "suspended" ]]; then
    echo "GITHUB_ACCESS: suspended — skip GH-dependent work (cached)"
    exit 2
  fi
fi

set +e
response=$(gh api user --jq '.login' 2>&1)
gh_exit=$?
set -e

if [[ "$gh_exit" -eq 0 && -n "$response" && "$response" != *"suspended"* ]]; then
  _write_state "ok"
  echo "GITHUB_ACCESS: ok (login: $response)"
  exit 0
fi

# An "API rate limit exceeded" 403 is transient budget exhaustion, NOT a suspension.
# Caching it as "suspended" mislabels the state for every guarded cron and keeps them
# skipping for the whole MAX_AGE window, past the actual reset. Still exit 2 (skipping
# GH work is right while limited), but cache only until the core limit resets. The
# rate_limit endpoint is not counted against the limit, so it is safe to query now.
if echo "$response" | grep -qi "rate limit"; then
  now_epoch=$(date -u +%s)
  until_epoch=$(( now_epoch + 60 ))  # secondary limit / reset race / unreadable: re-probe soon
  limits=$(gh api rate_limit --jq '"\(.resources.core.remaining) \(.resources.core.reset)"' 2>/dev/null || true)
  read -r remaining reset_epoch <<< "$limits" || true
  if [[ "${remaining:-}" == "0" && "${reset_epoch:-}" =~ ^[0-9]+$ ]]; then
    # Primary budget exhausted: wait for the reset (+2s slack), re-probing within MAX_AGE.
    until_epoch=$(( reset_epoch + 2 ))
    cap_epoch=$(( now_epoch + MAX_AGE_MINUTES * 60 ))
    if [[ "$until_epoch" -gt "$cap_epoch" ]]; then until_epoch=$cap_epoch; fi
  fi
  _write_state "rate_limited" "$until_epoch"
  echo "GITHUB_ACCESS: rate-limited until $(date -u -d "@$until_epoch" +%H:%M:%SZ) — skip GH-dependent work (transient, NOT suspended)"
  exit 2
fi

if echo "$response" | grep -qi "suspend\|403\|blocked"; then
  _write_state "suspended"
  echo "GITHUB_ACCESS: suspended — skip GH-dependent work"
  exit 2
fi

# Unexpected error — don't cache; let caller decide
echo "GITHUB_ACCESS: check failed (gh exit $gh_exit): $response" >&2
exit 1
