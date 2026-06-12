#!/usr/bin/env bash
# check-github-access.sh — fast pre-flight guard for GitHub-dependent crons.
#
# Usage: check-github-access.sh [--max-age-minutes N] [--state-file path]
#
# Exit codes:
#   0 — GitHub accessible
#   2 — GitHub suspended/inaccessible (safe to skip GH work)
#   1 — unexpected error
#
# Caches the access-check result for --max-age-minutes (default: 10) to avoid
# hammering the API when multiple crons run close together.
set -euo pipefail

MAX_AGE_MINUTES=10
STATE_FILE="${WORKSPACE:-$HOME/.openclaw/workspace}/tmp/github-access-state.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-age-minutes) MAX_AGE_MINUTES="$2"; shift 2 ;;
    --state-file)      STATE_FILE="$2";      shift 2 ;;
    -h|--help)
      echo "Usage: check-github-access.sh [--max-age-minutes N] [--state-file path]"
      echo "Exits 0 if GitHub is accessible, 2 if suspended/inaccessible."
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

_write_state() {
  local status="$1"
  python3 - "$STATE_FILE" "$status" << 'PY'
import json, sys, time
path, status = sys.argv[1], sys.argv[2]
with open(path, 'w') as f:
    json.dump({"status": status, "checked_at_epoch": int(time.time())}, f, indent=2)
    f.write("\n")
PY
}

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

if echo "$response" | grep -qi "suspend\|403\|blocked"; then
  _write_state "suspended"
  echo "GITHUB_ACCESS: suspended — skip GH-dependent work"
  exit 2
fi

# Unexpected error — don't cache; let caller decide
echo "GITHUB_ACCESS: check failed (gh exit $gh_exit): $response" >&2
exit 1
