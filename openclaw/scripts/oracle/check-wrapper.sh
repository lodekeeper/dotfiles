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
UNKNOWN_ARG_RESULT="pending"
DRY_RUN_RESULT="pending"
RENDER_ALIAS_RESULT="pending"
COPY_MARKDOWN_RESULT="pending"
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
    "$SYNTAX_RESULT" "$HELP_RESULT" "$REJECT_RESULT" "$UNKNOWN_ARG_RESULT" "$DRY_RUN_RESULT" "$RENDER_ALIAS_RESULT" "$COPY_MARKDOWN_RESULT" "$AUTH_RESULT" "$SMOKE_RESULT"
import json, sys
status, message, live, syntax, help_r, reject, unknown_arg, dry_run, render_alias, copy_markdown, auth, smoke = sys.argv[1:13]
print(json.dumps({
    "status": status,
    "message": message,
    "live": live.lower() == "true",
    "checks": {
        "shellSyntax": syntax,
        "helpOutput": help_r,
        "apiOnlyFlagRejection": reject,
        "unknownArgRejection": unknown_arg,
        "dryRun": dry_run,
        "renderAlias": render_alias,
        "copyMarkdown": copy_markdown,
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
if run "$WRAPPER" --help > "$help_out" && grep -q 'oracle-browser-camoufox' "$help_out" && grep -q -- '--files-report' "$help_out" && grep -q -- '--chatgpt-url' "$help_out" && grep -q -- '--browser-attachments' "$help_out" && grep -q -- '--browser-bundle-files' "$help_out" && grep -q -- '--dry-run' "$help_out" && grep -q -- '--render-markdown' "$help_out" && grep -q -- '--copy-markdown' "$help_out" && grep -q -- '--notify' "$help_out" && grep -q -- '--heartbeat <seconds>' "$help_out"; then
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

log "checking unknown argument rejection"
unknown_out="$TMP_DIR/unknown.txt"
if "$WRAPPER" --definitely-not-a-real-flag --prompt hi > "$unknown_out" 2>&1; then
  UNKNOWN_ARG_RESULT="failed"
  finish_fail "expected unknown-argument rejection, but command succeeded"
fi
if grep -q 'unrecognized or unsupported argument' "$unknown_out"; then
  UNKNOWN_ARG_RESULT="passed"
else
  UNKNOWN_ARG_RESULT="failed"
  finish_fail "unknown-argument rejection message missing"
fi

log "checking dry-run json output"
dry_json="$TMP_DIR/dry-run.json"
dry_json_written="$TMP_DIR/dry-run-written.json"
ctx="$TMP_DIR/dry-run-context.txt"
printf 'dry run context\n' > "$ctx"
if run "$WRAPPER" --prompt 'Reply with exactly DRY_RUN_OK.' --file "$ctx" --chatgpt-url https://chatgpt.com/g/example/project --dry-run json --write-output "$dry_json_written" > "$dry_json" && python3 - <<'PY' "$dry_json" "$dry_json_written"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
with open(sys.argv[2]) as f:
    written = json.load(f)
assert data == written, (data, written)
assert data.get('status') == 'ok', data
assert data.get('mode') == 'dry-run', data
plan = data.get('plan', {})
assert plan.get('fileCount') == 1, data
assert plan.get('chatgptUrl') == 'https://chatgpt.com/g/example/project', data
assert plan.get('promptProvided') is True, data
assert plan.get('renderedBundleChars', 0) > 0, data
assert plan.get('finalPromptChars', 0) > 0, data
assert plan.get('writeOutput') == sys.argv[2], data
assert plan.get('copyMarkdown') is False, data
PY
then
  DRY_RUN_RESULT="passed"
else
  DRY_RUN_RESULT="failed"
  finish_fail "dry-run json check failed"
fi

log "checking render alias output"
render_out="$TMP_DIR/render.txt"
render_written="$TMP_DIR/render-written.txt"
if run "$WRAPPER" --prompt 'Reply with exactly RENDER_ALIAS_OK.' --file "$ctx" --render --write-output "$render_written" > "$render_out" && grep -q 'Interpret the following Oracle render bundle as plain task input.' "$render_out" && cmp -s "$render_out" "$render_written"; then
  RENDER_ALIAS_RESULT="passed"
else
  RENDER_ALIAS_RESULT="failed"
  finish_fail "render alias check failed"
fi

log "checking copy-markdown guard/error behavior"
copy_guard_out="$TMP_DIR/copy-guard.txt"
if "$WRAPPER" --prompt hi --copy-markdown > "$copy_guard_out" 2>&1; then
  COPY_MARKDOWN_RESULT="failed"
  finish_fail "expected copy-markdown preview guard, but command succeeded"
fi
if grep -q 'only supported with preview/render modes' "$copy_guard_out"; then
  if command -v pbcopy >/dev/null 2>&1 || command -v wl-copy >/dev/null 2>&1 || command -v xclip >/dev/null 2>&1 || command -v xsel >/dev/null 2>&1; then
    COPY_MARKDOWN_RESULT="passed"
  else
    copy_backend_out="$TMP_DIR/copy-backend.txt"
    if "$WRAPPER" --prompt 'Reply with exactly COPY_BACKEND_OK.' --file "$ctx" --render --copy-markdown > /dev/null 2> "$copy_backend_out"; then
      COPY_MARKDOWN_RESULT="failed"
      finish_fail "expected copy-markdown backend failure on clipboard-less host, but command succeeded"
    fi
    if grep -q 'requires a clipboard backend' "$copy_backend_out"; then
      COPY_MARKDOWN_RESULT="passed"
    else
      COPY_MARKDOWN_RESULT="failed"
      finish_fail "copy-markdown backend error message missing"
    fi
  fi
else
  COPY_MARKDOWN_RESULT="failed"
  finish_fail "copy-markdown preview guard message missing"
fi

log "checking common CLI UX flag compatibility"
ux_json="$TMP_DIR/ux.json"
if run "$WRAPPER" --prompt 'Reply with exactly UX_FLAGS_OK.' --file "$ctx" --dry-run json --notify --no-notify-sound --heartbeat 5 --force --json > "$ux_json" && python3 - <<'PY' "$ux_json"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data.get('status') == 'ok', data
assert data.get('mode') == 'dry-run', data
plan = data.get('plan', {})
assert plan.get('promptProvided') is True, data
assert plan.get('fileCount') == 1, data
PY
then
  :
else
  finish_fail "common UX flag compatibility check failed"
fi

if ! $LIVE; then
  finish_ok "static checks passed (use --live for auth/browser smoke tests)"
fi

log "running live auth/pro smoke test"
auth_json="$TMP_DIR/auth.json"
if run "$WRAPPER" --auth-only --require-auth --require-pro --chatgpt-url https://chatgpt.com --browser-attachments auto --browser-bundle-files --json > "$auth_json" && python3 - <<'PY' "$auth_json"
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
