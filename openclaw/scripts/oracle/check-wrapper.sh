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
COOKIE_FILE=""

SYNTAX_RESULT="pending"
HELP_RESULT="pending"
REJECT_RESULT="pending"
UNKNOWN_ARG_RESULT="pending"
DRY_RUN_RESULT="pending"
RENDER_ALIAS_RESULT="pending"
COPY_MARKDOWN_RESULT="pending"
RECOVERY_HELPERS_RESULT="pending"
MALFORMED_JSON_RESULT="pending"
NON_OBJECT_JSON_RESULT="pending"
INVALID_STATUS_JSON_RESULT="pending"
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
- API-only / native-browser flags are rejected clearly
- unknown args are rejected clearly
- dry-run / render / preview guard behavior works
- recovery helpers render the expected dry-run / install behavior

Optional live checks (--live):
- auth/pro smoke test
- browser-style prompt run
- multi-file --file compatibility

Usage:
  scripts/oracle/check-wrapper.sh [--live] [--cookie-file <path>] [--verbose] [--json]
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
    "$FINAL_STATUS" "$FINAL_MESSAGE" "$LIVE" "$COOKIE_FILE" \
    "$SYNTAX_RESULT" "$HELP_RESULT" "$REJECT_RESULT" "$UNKNOWN_ARG_RESULT" "$DRY_RUN_RESULT" "$RENDER_ALIAS_RESULT" "$COPY_MARKDOWN_RESULT" "$RECOVERY_HELPERS_RESULT" "$MALFORMED_JSON_RESULT" "$NON_OBJECT_JSON_RESULT" "$INVALID_STATUS_JSON_RESULT" "$AUTH_RESULT" "$SMOKE_RESULT"
import json, sys
status, message, live, cookie_file, syntax, help_r, reject, unknown_arg, dry_run, render_alias, copy_markdown, recovery_helpers, malformed_json, non_object_json, invalid_status_json, auth, smoke = sys.argv[1:18]
print(json.dumps({
    "status": status,
    "message": message,
    "live": live.lower() == "true",
    "cookieFile": cookie_file or None,
    "checks": {
        "shellSyntax": syntax,
        "helpOutput": help_r,
        "apiOnlyFlagRejection": reject,
        "unknownArgRejection": unknown_arg,
        "dryRun": dry_run,
        "renderAlias": render_alias,
        "copyMarkdown": copy_markdown,
        "recoveryHelpers": recovery_helpers,
        "malformedBridgeJson": malformed_json,
        "nonObjectBridgeJson": non_object_json,
        "invalidStatusBridgeJson": invalid_status_json,
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

summarize_auth_failure() {
  local json_path="$1"
  if [[ ! -s "$json_path" ]]; then
    return 1
  fi
  python3 - <<'PY' "$json_path"
import json, sys
path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
except Exception:
    sys.exit(1)

error = data.get("error")
server = ((data.get("auth") or {}).get("server") or {})
parts = []
if error:
    parts.append(error)
if server:
    state = server.get("state")
    plan = server.get("planType")
    serr = server.get("error")
    meta = []
    if state:
        meta.append(f"state={state}")
    if plan:
        meta.append(f"plan={plan}")
    if serr and serr not in (error or ""):
        meta.append(f"server_error={serr}")
    if meta:
        parts.append("(" + ", ".join(meta) + ")")
if parts:
    print(" ".join(parts))
    sys.exit(0)
sys.exit(1)
PY
}

check_verify_after_auth_refresh_dry_run() {
  local help_out="$1"
  local json_out="$2"
  run "$SCRIPT_DIR/verify-after-auth-refresh.sh" --help > "$help_out"
  grep -q -- '--cookie-source <path>' "$help_out"
  grep -q -- '--dry-run' "$help_out"
  run "$SCRIPT_DIR/verify-after-auth-refresh.sh" --dry-run --json > "$json_out"
  python3 - <<'PY' "$json_out"
import json, os, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data.get('status') == 'ok', data
assert data.get('mode') == 'dry-run', data
artifact_dir = data.get('artifactDir')
assert artifact_dir and 'refresh-verify-' in artifact_dir, data
assert not os.path.exists(artifact_dir), data
assert data.get('refreshInput') == 'no refresh input; verify existing cookie jar only', data
steps = data.get('steps') or []
assert len(steps) == 3, data
assert 'chatgpt-direct --auth-only' in steps[0], data
assert 'oracle-browser --auth-only' in steps[1], data
assert 'check-wrapper.sh --live' in steps[2], data
PY
}

check_install_chatgpt_cookies_helper() {
  local source_json="$1"
  local dest_json="$2"
  local summary_json="$3"
  cat > "$source_json" <<'EOF'
[
  {"name":"__Secure-next-auth.session-token","value":"fresh-token","domain":".chatgpt.com","path":"/","secure":true,"httpOnly":true},
  {"name":"oai-sid","value":"abc","domain":"auth.openai.com","path":"/","secure":true},
  {"name":"irrelevant","value":"drop-me","domain":"example.com","path":"/"}
]
EOF
  run python3 "$SCRIPT_DIR/install-chatgpt-cookies.py" --source "$source_json" --cookie-file "$dest_json" > "$summary_json"
  python3 - <<'PY' "$summary_json" "$dest_json"
import json, sys
summary_path, dest_path = sys.argv[1:3]
with open(summary_path) as f:
    data = json.load(f)
assert data.get('status') == 'ok', data
assert data.get('installedCookieCount') == 2, data
assert data.get('droppedNonChatgptCookies') == 1, data
assert data.get('hasSessionToken') is True, data
with open(dest_path) as f:
    cookies = json.load(f)
names = {c['name'] for c in cookies}
domains = {c['domain'] for c in cookies}
assert '__Secure-next-auth.session-token' in names, cookies
assert 'irrelevant' not in names, cookies
assert 'example.com' not in domains, cookies
PY
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
    --cookie-file)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 2; }
      COOKIE_FILE="$2"
      shift 2
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

COOKIE_ARGS=()
if [[ -n "$COOKIE_FILE" ]]; then
  COOKIE_ARGS=(--cookies "$COOKIE_FILE")
fi

log "checking shell syntax"
if run bash -n "$SCRIPT_DIR/oracle-browser-camoufox"; then
  SYNTAX_RESULT="passed"
else
  SYNTAX_RESULT="failed"
  finish_fail "shell syntax check failed"
fi

log "checking help output"
help_out="$TMP_DIR/help.txt"
if run "$WRAPPER" --help > "$help_out" \
  && grep -q 'oracle-browser-camoufox' "$help_out" \
  && grep -q -- '--files-report' "$help_out" \
  && grep -q -- '--chatgpt-url' "$help_out" \
  && grep -q -- '--browser-cookie-path <path>' "$help_out" \
  && grep -q -- '--browser-attachments' "$help_out" \
  && grep -q -- '--browser-bundle-files' "$help_out" \
  && grep -q -- '--dry-run' "$help_out" \
  && grep -q -- '--render-markdown' "$help_out" \
  && grep -q -- '--copy-markdown' "$help_out" \
  && grep -q -- '--allow-very-large-bundle' "$help_out" \
  && grep -q -- '--notify' "$help_out" \
  && grep -q -- '--heartbeat <seconds>' "$help_out" \
  && grep -q -- '--verbose-render' "$help_out" \
  && grep -q -- '--retain-hours <hours>' "$help_out" \
  && grep -q -- '--zombie-timeout <dur>' "$help_out" \
  && grep -q -- '--debug-help' "$help_out"
then
  HELP_RESULT="passed"
else
  HELP_RESULT="failed"
  finish_fail "help output check failed"
fi

log "checking API-only / native-browser flag rejection"
reject_out="$TMP_DIR/reject.txt"
remote_reject_out="$TMP_DIR/remote-reject.txt"
if "$WRAPPER" --models gpt-5.2-pro --prompt hi > "$reject_out" 2>&1; then
  REJECT_RESULT="failed"
  finish_fail "expected API-only flag rejection, but command succeeded"
fi
if ! grep -q 'API-mode functionality' "$reject_out"; then
  REJECT_RESULT="failed"
  finish_fail "API-only flag rejection message missing"
fi
if "$WRAPPER" --remote-chrome 127.0.0.1:9222 --prompt hi > "$remote_reject_out" 2>&1; then
  REJECT_RESULT="failed"
  finish_fail "expected native-browser flag rejection, but command succeeded"
fi
if grep -q 'native Chrome/CDP or remote-browser paths' "$remote_reject_out"; then
  REJECT_RESULT="passed"
else
  REJECT_RESULT="failed"
  finish_fail "native-browser flag rejection message missing"
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
if run "$WRAPPER" --prompt 'Reply with exactly DRY_RUN_OK.' --file "$ctx" --chatgpt-url https://chatgpt.com/g/example/project --dry-run json --write-output "$dry_json_written" > "$dry_json" \
  && python3 - <<'PY' "$dry_json" "$dry_json_written"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
with open(sys.argv[2]) as f:
    written = json.load(f)
assert data == written, (data, written)
assert data.get('status') == 'ok', data
assert data.get('mode') == 'dry-run', data
assert data.get('wrapperSchemaVersion') == 1, data
plan = data.get('plan', {})
assert plan.get('fileCount') == 1, data
assert plan.get('chatgptUrl') == 'https://chatgpt.com/g/example/project', data
assert plan.get('promptProvided') is True, data
assert plan.get('renderedBundleChars', 0) > 0, data
assert plan.get('finalPromptChars', 0) > 0, data
assert plan.get('requestedTimeout') is None, data
assert plan.get('effectiveTimeout') == 21600, data
assert plan.get('timeoutAutoBumped') is False, data
assert plan.get('bundleClass') == 'normal', data
assert plan.get('recommendedAction') == 'none', data
assert plan.get('bundleGuidance') in ('', None), data
assert plan.get('writeOutput') == sys.argv[2], data
assert plan.get('copyMarkdown') is False, data
PY
then
  DRY_RUN_RESULT="passed"
else
  DRY_RUN_RESULT="failed"
  finish_fail "dry-run json check failed"
fi

log "checking timeout auto-bump heuristic for large bundles"
large_ctx="$TMP_DIR/large-context.txt"
python3 - <<'PY' "$large_ctx"
import pathlib, sys
path = pathlib.Path(sys.argv[1])
path.write_text('large bundle line\n' * 1800)
PY
large_json="$TMP_DIR/large-dry-run.json"
if run "$WRAPPER" --prompt 'Reply with exactly LARGE_TIMEOUT_OK.' --file "$large_ctx" --timeout 180 --dry-run json > "$large_json" \
  && python3 - <<'PY' "$large_json"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
plan = data.get('plan', {})
assert plan.get('requestedTimeout') == 180, data
assert plan.get('effectiveTimeout') == 900, data
assert plan.get('timeoutHeuristicFloor') == 900, data
assert plan.get('timeoutAutoBumped') is True, data
assert 'auto-bumped' in (plan.get('timeoutAdjustment') or ''), data
assert plan.get('bundleClass') == 'large', data
assert plan.get('recommendedAction') == 'inspect-or-narrow', data
assert 'large rendered bundle' in (plan.get('bundleGuidance') or ''), data
assert plan.get('finalPromptChars', 0) >= 20000, data
PY
then
  :
else
  DRY_RUN_RESULT="failed"
  finish_fail "large-bundle timeout heuristic check failed"
fi

log "checking refusal guard for extremely large live bundles"
huge_ctx="$TMP_DIR/huge-context.txt"
python3 - <<'PY' "$huge_ctx"
import pathlib, sys
path = pathlib.Path(sys.argv[1])
path.write_text('huge bundle line for refusal guard path\n' * 3200)
PY
huge_guard_out="$TMP_DIR/huge-guard.txt"
if "$WRAPPER" --prompt 'Reply with exactly HUGE_BUNDLE_GUARD_OK.' --file "$huge_ctx" --timeout 180 > "$huge_guard_out" 2>&1; then
  DRY_RUN_RESULT="failed"
  finish_fail "expected extremely large bundle refusal guard, but command succeeded"
fi
if ! grep -q 'refusing live send for an extremely large rendered bundle' "$huge_guard_out"; then
  DRY_RUN_RESULT="failed"
  finish_fail "extremely large bundle refusal guard message missing"
fi

log "checking JSON refusal shape for extremely large live bundles"
huge_guard_json="$TMP_DIR/huge-guard.json"
if "$WRAPPER" --prompt 'Reply with exactly HUGE_BUNDLE_GUARD_JSON_OK.' --file "$huge_ctx" --timeout 180 --json > "$huge_guard_json" 2> "$TMP_DIR/huge-guard-json.err"; then
  DRY_RUN_RESULT="failed"
  finish_fail "expected extremely large bundle JSON refusal, but command succeeded"
fi
if python3 - <<'PY' "$huge_guard_json"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data.get('status') == 'error', data
assert data.get('wrapperSchemaVersion') == 1, data
err = data.get('error', {})
assert err.get('code') == 'very-large-bundle-refused', data
assert 'refusing live send for an extremely large rendered bundle' in (err.get('message') or ''), data
plan = data.get('plan', {})
assert plan.get('bundleClass') == 'very-large', data
assert plan.get('recommendedAction') == 'explicit-override-required', data
assert plan.get('veryLargeBundle') is True, data
assert plan.get('allowVeryLargeBundle') is False, data
assert plan.get('effectiveTimeout') == 900, data
assert plan.get('timeoutAutoBumped') is True, data
assert plan.get('finalPromptChars', 0) >= 100000, data
PY
then
  :
else
  DRY_RUN_RESULT="failed"
  finish_fail "extremely large bundle JSON refusal check failed"
fi

log "checking render alias output"
render_out="$TMP_DIR/render.txt"
render_written="$TMP_DIR/render-written.txt"
if run "$WRAPPER" --prompt 'Reply with exactly RENDER_ALIAS_OK.' --file "$ctx" --render --write-output "$render_written" > "$render_out" \
  && grep -q 'Interpret the following Oracle render bundle as plain task input.' "$render_out" \
  && cmp -s "$render_out" "$render_written"
then
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

log "checking common CLI UX/session flag compatibility"
ux_json="$TMP_DIR/ux.json"
debug_help_out="$TMP_DIR/debug-help.txt"
if run "$WRAPPER" --debug-help > "$debug_help_out" \
  && grep -q 'oracle-browser-camoufox' "$debug_help_out" \
  && run "$WRAPPER" --prompt 'Reply with exactly UX_FLAGS_OK.' --file "$ctx" --browser-cookie-path /tmp/fake-cookies.json --dry-run json --notify --no-notify-sound --heartbeat 5 --force --verbose-render --retain-hours 24 --zombie-timeout 10m --zombie-last-activity --json > "$ux_json" \
  && python3 - <<'PY' "$ux_json"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data.get('status') == 'ok', data
assert data.get('mode') == 'dry-run', data
plan = data.get('plan', {})
assert plan.get('promptProvided') is True, data
assert plan.get('fileCount') == 1, data
assert plan.get('customCookies') is True, data
PY
then
  :
else
  finish_fail "common UX/session flag compatibility check failed"
fi

log "checking recovery helper static behavior"
verify_help_out="$TMP_DIR/verify-after-auth-refresh-help.txt"
verify_dry_json="$TMP_DIR/verify-after-auth-refresh-dry-run.json"
install_source="$TMP_DIR/install-chatgpt-source.json"
install_dest="$TMP_DIR/install-chatgpt-dest.json"
install_json="$TMP_DIR/install-chatgpt.json"
if check_verify_after_auth_refresh_dry_run "$verify_help_out" "$verify_dry_json" \
  && check_install_chatgpt_cookies_helper "$install_source" "$install_dest" "$install_json"
then
  RECOVERY_HELPERS_RESULT="passed"
else
  RECOVERY_HELPERS_RESULT="failed"
  finish_fail "recovery helper static checks failed"
fi

log "checking malformed bridge JSON fallback"
malformed_bridge_stub="$TMP_DIR/malformed-bridge.sh"
cat > "$malformed_bridge_stub" <<'EOF'
#!/usr/bin/env bash
printf 'this is not json\n'
exit 17
EOF
chmod +x "$malformed_bridge_stub"
malformed_json="$TMP_DIR/malformed-bridge.json"
if ORACLE_CHATGPT_DIRECT_BIN="$malformed_bridge_stub" "$WRAPPER" --auth-only --json > "$malformed_json" 2> "$TMP_DIR/malformed-bridge.err"; then
  MALFORMED_JSON_RESULT="failed"
  finish_fail "expected malformed bridge JSON regression to fail"
fi
if python3 - <<'PY' "$malformed_json"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data.get('status') == 'error', data
assert data.get('wrapper') == 'oracle-browser-camoufox', data
assert data.get('wrapperSchemaVersion') == 1, data
err = data.get('error', {})
assert err.get('code') == 'bridge-json-invalid', data
assert err.get('bridgeExitStatus') == 17, data
assert 'did not emit valid JSON' in (err.get('message') or ''), data
assert 'this is not json' in (err.get('bridgeOutputExcerpt') or ''), data
assert err.get('bridgeOutputBytes', 0) >= len('this is not json\n'.encode()), data
plan = data.get('plan', {})
assert plan.get('authOnly') is True, data
assert plan.get('promptProvided') is False, data
assert plan.get('fileCount') == 0, data
assert plan.get('jsonOutput') is True, data
assert plan.get('bundleClass') == 'normal', data
assert plan.get('recommendedAction') == 'none', data
PY
then
  MALFORMED_JSON_RESULT="passed"
else
  MALFORMED_JSON_RESULT="failed"
  finish_fail "malformed bridge JSON fallback check failed"
fi

log "checking non-object bridge JSON fallback"
non_object_bridge_stub="$TMP_DIR/non-object-bridge.sh"
cat > "$non_object_bridge_stub" <<'EOF'
#!/usr/bin/env bash
printf '[]\n'
exit 0
EOF
chmod +x "$non_object_bridge_stub"
non_object_json="$TMP_DIR/non-object-bridge.json"
if ORACLE_CHATGPT_DIRECT_BIN="$non_object_bridge_stub" "$WRAPPER" --auth-only --json > "$non_object_json" 2> "$TMP_DIR/non-object-bridge.err"; then
  NON_OBJECT_JSON_RESULT="failed"
  finish_fail "expected non-object bridge JSON regression to fail"
fi
if python3 - <<'PY' "$non_object_json"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data.get('status') == 'error', data
assert data.get('wrapper') == 'oracle-browser-camoufox', data
assert data.get('wrapperSchemaVersion') == 1, data
err = data.get('error', {})
assert err.get('code') == 'bridge-json-shape-invalid', data
assert err.get('bridgeExitStatus') == 0, data
assert 'valid JSON but not a JSON object' in (err.get('message') or ''), data
assert '[]' in (err.get('bridgeOutputExcerpt') or ''), data
plan = data.get('plan', {})
assert plan.get('authOnly') is True, data
assert plan.get('promptProvided') is False, data
assert plan.get('fileCount') == 0, data
assert plan.get('jsonOutput') is True, data
assert plan.get('bundleClass') == 'normal', data
assert plan.get('recommendedAction') == 'none', data
PY
then
  NON_OBJECT_JSON_RESULT="passed"
else
  NON_OBJECT_JSON_RESULT="failed"
  finish_fail "non-object bridge JSON fallback check failed"
fi

log "checking invalid-status bridge JSON fallback"
invalid_status_bridge_stub="$TMP_DIR/invalid-status-bridge.sh"
cat > "$invalid_status_bridge_stub" <<'EOF'
#!/usr/bin/env bash
printf '{"foo":"bar"}\n'
exit 0
EOF
chmod +x "$invalid_status_bridge_stub"
invalid_status_json="$TMP_DIR/invalid-status-bridge.json"
if ORACLE_CHATGPT_DIRECT_BIN="$invalid_status_bridge_stub" "$WRAPPER" --auth-only --json > "$invalid_status_json" 2> "$TMP_DIR/invalid-status-bridge.err"; then
  INVALID_STATUS_JSON_RESULT="failed"
  finish_fail "expected invalid-status bridge JSON regression to fail"
fi
if python3 - <<'PY' "$invalid_status_json"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data.get('status') == 'error', data
assert data.get('wrapper') == 'oracle-browser-camoufox', data
assert data.get('wrapperSchemaVersion') == 1, data
err = data.get('error', {})
assert err.get('code') == 'bridge-json-contract-invalid', data
assert err.get('bridgeExitStatus') == 0, data
assert "without a valid top-level status" in (err.get('message') or ''), data
assert '{"foo":"bar"}' in (err.get('bridgeOutputExcerpt') or ''), data
plan = data.get('plan', {})
assert plan.get('authOnly') is True, data
assert plan.get('promptProvided') is False, data
assert plan.get('fileCount') == 0, data
assert plan.get('jsonOutput') is True, data
assert plan.get('bundleClass') == 'normal', data
assert plan.get('recommendedAction') == 'none', data
PY
then
  INVALID_STATUS_JSON_RESULT="passed"
else
  INVALID_STATUS_JSON_RESULT="failed"
  finish_fail "invalid-status bridge JSON fallback check failed"
fi

if ! $LIVE; then
  finish_ok "static checks passed (use --live for auth/browser smoke tests)"
fi

log "running live auth/pro smoke test"
auth_json="$TMP_DIR/auth.json"
if run "$WRAPPER" --auth-only --require-auth --require-pro --chatgpt-url https://chatgpt.com --browser-attachments auto --browser-bundle-files "${COOKIE_ARGS[@]}" --json > "$auth_json" \
  && python3 - <<'PY' "$auth_json"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data.get('status') == 'ok', data
assert data.get('wrapper') == 'oracle-browser-camoufox', data
assert data.get('wrapperSchemaVersion') == 1, data
plan = data.get('plan', {})
assert plan.get('authOnly') is True, data
assert plan.get('bundleClass') == 'normal', data
assert plan.get('recommendedAction') == 'none', data
assert data.get('auth', {}).get('state') == 'authenticated', data
assert data.get('auth', {}).get('server', {}).get('planType') == 'pro', data
PY
then
  AUTH_RESULT="passed"
else
  AUTH_RESULT="failed"
  python3 - <<'PY' "$auth_json" >/dev/null 2>&1 || true
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data.get('wrapper') == 'oracle-browser-camoufox', data
assert data.get('wrapperSchemaVersion') == 1, data
plan = data.get('plan', {})
assert plan.get('authOnly') is True, data
assert plan.get('bundleClass') == 'normal', data
assert plan.get('recommendedAction') == 'none', data
PY
  auth_detail="$(summarize_auth_failure "$auth_json" || true)"
  if [[ -n "$auth_detail" ]]; then
    finish_fail "live auth/pro smoke test failed: $auth_detail"
  fi
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
  "${COOKIE_ARGS[@]}" \
  --json > "$smoke_json" \
  && python3 - <<'PY' "$smoke_json"
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data.get('status') == 'ok', data
assert data.get('wrapper') == 'oracle-browser-camoufox', data
assert data.get('wrapperSchemaVersion') == 1, data
plan = data.get('plan', {})
assert plan.get('fileCount') == 2, data
assert plan.get('bundleClass') in ('normal', 'moderately-large', 'large', 'very-large'), data
assert plan.get('recommendedAction') in ('none', 'inspect-or-narrow', 'explicit-override-required'), data
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
