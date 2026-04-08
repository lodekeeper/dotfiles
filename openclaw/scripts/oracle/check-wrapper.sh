#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER="$SCRIPT_DIR/oracle-browser"
TMP_DIR="${TMPDIR:-/tmp}/oracle-wrapper-check-$$"
mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT

LIVE=false
VERBOSE=false
JSON_OUT=false

SYNTAX_RESULT="pending"
HELP_RESULT="pending"
REJECT_RESULT="pending"
AUTH_RESULT="skipped"
SMOKE_RESULT="skipped"
FINAL_STATUS="error"
FINAL_MESSAGE="not started"

usage() {
  cat <<'EOF'
check-wrapper.sh

Verify the local Oracle browser wrapper.

Default checks:
- shell syntax for oracle-browser-camoufox
- help output renders
- API-only flags are rejected with a clear error

Optional live checks (--live):
- auth/pro smoke test
- browser-style prompt run
- multi-file --file compatibility

Usage:
  scripts/oracle/check-wrapper.sh [--live] [--verbose] [--json]
EOF
}

log() {
  printf '[check-wrapper] %s\n' "$*" >&2
}

run() {
  if $VERBOSE; then
    log "RUN: $*"
  fi
  "$@"
}

emit_json() {
  python3 - <<'PY' \
    "$FINAL_STATUS" "$FINAL_MESSAGE" "$LIVE" \
    "$SYNTAX_RESULT" "$HELP_RESULT" "$REJECT_RESULT" "$AUTH_RESULT" "$SMOKE_RESULT"
import json, sys
status, message, live, syntax, help_r, reject, auth, smoke = sys.argv[1:9]
print(json.dumps({
    "status": status,
    "message": message,
    "live": live.lower() == "true",
    "checks": {
        "shellSyntax": syntax,
        "helpOutput": help_r,
        "apiOnlyFlagRejection": reject,
        "authSmoke": auth,
        "browserSmoke": smoke,
    },
}, indent=2))
PY
}

finish_ok() {
  FINAL_STATUS="ok"
  FINAL_MESSAGE="$1"
  if $JSON_OUT; then
    emit_json
  fi
  exit 0
}

finish_fail() {
  FINAL_STATUS="error"
  FINAL_MESSAGE="$1"
  if $JSON_OUT; then
    emit_json
  fi
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --live)
      LIVE=true
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    --json)
      JSON_OUT=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

log "checking shell syntax"
if run bash -n "$SCRIPT_DIR/oracle-browser-camoufox"; then
  SYNTAX_RESULT="passed"
else
  SYNTAX_RESULT="failed"
  finish_fail "shell syntax check failed"
fi

log "checking help output"
help_out="$TMP_DIR/help.txt"
if run "$WRAPPER" --help > "$help_out" && grep -q 'oracle-browser-camoufox' "$help_out" && grep -q -- '--files-report' "$help_out"; then
  HELP_RESULT="passed"
else
  HELP_RESULT="failed"
  finish_fail "help output check failed"
fi

log "checking API-only flag rejection"
reject_out="$TMP_DIR/reject.txt"
if "$WRAPPER" --models gpt-5.2-pro --prompt hi > "$reject_out" 2>&1; then
  REJECT_RESULT="failed"
  finish_fail "expected API-only flag rejection, but command succeeded"
fi
if grep -q 'API-mode functionality' "$reject_out"; then
  REJECT_RESULT="passed"
else
  REJECT_RESULT="failed"
  finish_fail "API-only flag rejection message missing"
fi

if ! $LIVE; then
  finish_ok "static checks passed (use --live for auth/browser smoke tests)"
fi

log "running live auth/pro smoke test"
auth_json="$TMP_DIR/auth.json"
if run "$WRAPPER" --auth-only --require-auth --require-pro --json > "$auth_json" && python3 - <<'PY' "$auth_json"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data.get('status') == 'ok', data
assert data.get('auth', {}).get('state') == 'authenticated', data
assert data.get('auth', {}).get('server', {}).get('planType') == 'pro', data
PY
then
  AUTH_RESULT="passed"
else
  AUTH_RESULT="failed"
  finish_fail "live auth/pro smoke test failed"
fi

log "running live multi-file browser-style smoke test"
ctx1="$TMP_DIR/context-a.txt"
ctx2="$TMP_DIR/context-b.txt"
printf 'wrapper smoke test context A\n' > "$ctx1"
printf 'wrapper smoke test context B\n' > "$ctx2"
smoke_json="$TMP_DIR/smoke.json"
if run "$WRAPPER" \
  --engine browser \
  --wait \
  --prompt 'Reply with exactly ORACLE_WRAPPER_CHECK_OK and nothing else.' \
  --file "$ctx1" "$ctx2" \
  --model gpt-5.2-pro \
  --timeout 120 \
  --json > "$smoke_json" && python3 - <<'PY' "$smoke_json"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data.get('status') == 'ok', data
text = data.get('text', '').strip().rstrip('.')
assert text == 'ORACLE_WRAPPER_CHECK_OK', data
PY
then
  SMOKE_RESULT="passed"
else
  SMOKE_RESULT="failed"
  finish_fail "live browser-style smoke test failed"
fi

finish_ok "all checks passed"
