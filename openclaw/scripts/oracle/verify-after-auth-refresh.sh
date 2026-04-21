#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/../.." && pwd)"
COOKIE_FILE="$HOME/.oracle/chatgpt-cookies.json"
ARTIFACT_ROOT="$WORKSPACE/research/oracle"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARTIFACT_DIR="$ARTIFACT_ROOT/refresh-verify-$STAMP"
VERIFIER_NAME="verify-after-auth-refresh"
VERIFIER_SCHEMA_VERSION=1

TOKEN_MODE=""
TOKEN_VALUE=""
TOKEN_FILE=""
COOKIE_SOURCE=""
JSON=false
DRY_RUN=false
FAILED_STEP=""
FAILED_DETAIL=""

usage() {
  cat <<'EOF'
verify-after-auth-refresh.sh

Run the canonical Oracle/ChatGPT auth refresh verification sequence.

By default it assumes the cookie jar is already updated and just verifies:
  1) direct Camoufox auth/pro state
  2) Oracle-style wrapper auth/pro state
  3) full wrapper live verification

Optional refresh input modes:
  --token-file <path>    Patch a fresh session token from file first
  --token <value>        Patch a fresh session token from CLI first
  --stdin                Read a fresh session token from stdin first
  --cookie-source <path> Replace the local jar from a full cookie export first (`-` = stdin)
  --cookie-file <path>   Override destination cookie jar path (default: ~/.oracle/chatgpt-cookies.json)
  --dry-run              Print the planned verification sequence without changing anything
  --json                 Emit final summary as JSON
  -h, --help             Show help

Examples:
  scripts/oracle/verify-after-auth-refresh.sh --token-file /tmp/session-token.txt
  scripts/oracle/verify-after-auth-refresh.sh --cookie-source /tmp/chatgpt-cookies.json
  cat /tmp/chatgpt-cookies.json | scripts/oracle/verify-after-auth-refresh.sh --cookie-source - --dry-run --json
  scripts/oracle/verify-after-auth-refresh.sh --dry-run --json
  scripts/oracle/verify-after-auth-refresh.sh --json
EOF
}

refresh_desc() {
  case "$TOKEN_MODE" in
    file) printf 'replace-session-token from file: %s' "$TOKEN_FILE" ;;
    value) printf 'replace-session-token from inline value' ;;
    stdin) printf 'replace-session-token from stdin' ;;
    *)
      if [[ -n "$COOKIE_SOURCE" ]]; then
        printf 'install full cookie export from: %s' "$COOKIE_SOURCE"
      else
        printf 'no refresh input; verify existing cookie jar only'
      fi
      ;;
  esac
}

summarize_failure_json() {
  local json_path="$1"
  [[ -s "$json_path" ]] || return 1
  python3 - <<'PY' "$json_path"
import json, sys
path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
except Exception:
    sys.exit(1)

parts = []
message = data.get("message")
error = data.get("error")
if isinstance(error, str) and error:
    parts.append(error)
elif isinstance(message, str) and message:
    parts.append(message)

server = ((data.get("auth") or {}).get("server") or {})
state = server.get("state")
plan = server.get("planType")
serr = server.get("error")
meta = []
if state:
    meta.append(f"state={state}")
if plan:
    meta.append(f"plan={plan}")
if serr and (not parts or serr not in parts[0]):
    meta.append(f"server_error={serr}")
if meta:
    parts.append("(" + ", ".join(meta) + ")")

if parts:
    print(" ".join(parts))
    sys.exit(0)
sys.exit(1)
PY
}

summarize_failure_stderr() {
  local stderr_path="$1"
  [[ -s "$stderr_path" ]] || return 1
  python3 - <<'PY' "$stderr_path"
import sys
path = sys.argv[1]
try:
    text = open(path, encoding="utf-8", errors="replace").read()
except Exception:
    sys.exit(1)
lines = [line.strip() for line in text.splitlines() if line.strip()]
if not lines:
    sys.exit(1)
for line in reversed(lines):
    if line.startswith("Traceback "):
        continue
    print(line)
    sys.exit(0)
sys.exit(1)
PY
}

set_failed_detail_from_artifacts() {
  local json_path="$1"
  local stderr_path="$2"
  FAILED_DETAIL="$(summarize_failure_json "$json_path" || summarize_failure_stderr "$stderr_path" || true)"
}

emit_dry_run() {
  local refresh_input
  refresh_input="$(refresh_desc)"

  if $JSON; then
    python3 - <<'PY' "$ARTIFACT_DIR" "$COOKIE_FILE" "$refresh_input" "$VERIFIER_NAME" "$VERIFIER_SCHEMA_VERSION"
import json, sys
artifact_dir, cookie_file, refresh_desc, verifier_name, verifier_schema_version = sys.argv[1:6]
print(json.dumps({
    "status": "ok",
    "mode": "dry-run",
    "verifier": verifier_name,
    "verifierSchemaVersion": int(verifier_schema_version),
    "artifactDir": artifact_dir,
    "cookieFile": cookie_file,
    "refreshInput": refresh_desc,
    "steps": [
        "chatgpt-direct --auth-only --require-auth --require-pro --cookies <cookieFile> --json",
        "oracle-browser --auth-only --require-auth --require-pro --cookies <cookieFile> --json",
        "check-wrapper.sh --live --cookie-file <cookieFile> --json",
    ],
}, indent=2))
PY
  else
    cat <<EOF
verify-after-auth-refresh.sh dry run
- artifact dir: $ARTIFACT_DIR
- cookie file: $COOKIE_FILE
- refresh input: $refresh_input
- planned steps:
  1. chatgpt-direct --auth-only --require-auth --require-pro --cookies <cookieFile> --json
  2. oracle-browser --auth-only --require-auth --require-pro --cookies <cookieFile> --json
  3. check-wrapper.sh --live --cookie-file <cookieFile> --json
EOF
  fi
}

fail() {
  local message="$1"
  local full_message="$message"
  local refresh_input
  refresh_input="$(refresh_desc)"
  if [[ -n "$FAILED_DETAIL" ]]; then
    full_message="$message: $FAILED_DETAIL"
  fi
  if $JSON; then
    python3 - <<'PY' \
      "$full_message" "$ARTIFACT_DIR" "$COOKIE_FILE" "$FAILED_STEP" "$FAILED_DETAIL" "$refresh_input" \
      "$step_status" "$direct_status" "$wrapper_status" "$check_wrapper_status" "$VERIFIER_NAME" "$VERIFIER_SCHEMA_VERSION"
import json, sys
message, artifact_dir, cookie_file, failed_step, failed_detail, refresh_input, refresh_status, direct_status, wrapper_status, check_wrapper_status, verifier_name, verifier_schema_version = sys.argv[1:13]
print(json.dumps({
    "status": "error",
    "verifier": verifier_name,
    "verifierSchemaVersion": int(verifier_schema_version),
    "message": message,
    "artifactDir": artifact_dir,
    "cookieFile": cookie_file,
    "failedStep": failed_step or None,
    "failedDetail": failed_detail or None,
    "refreshInput": refresh_input,
    "steps": {
        "refreshInput": refresh_status,
        "chatgptDirectAuth": direct_status,
        "oracleWrapperAuth": wrapper_status,
        "checkWrapperLive": check_wrapper_status,
    },
}, indent=2))
PY
  else
    echo "ERROR: $full_message" >&2
    if [[ -n "$FAILED_STEP" ]]; then
      echo "Failed step: $FAILED_STEP" >&2
    fi
    echo "Cookie file: $COOKIE_FILE" >&2
    echo "Artifacts: $ARTIFACT_DIR" >&2
  fi
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --token-file)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 2; }
      TOKEN_MODE="file"
      TOKEN_FILE="$2"
      shift 2
      ;;
    --token)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 2; }
      TOKEN_MODE="value"
      TOKEN_VALUE="$2"
      shift 2
      ;;
    --stdin)
      TOKEN_MODE="stdin"
      shift
      ;;
    --cookie-source)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 2; }
      COOKIE_SOURCE="$2"
      shift 2
      ;;
    --cookie-file)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 2; }
      COOKIE_FILE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --json)
      JSON=true
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

step_status="pending"
direct_status="pending"
wrapper_status="pending"
check_wrapper_status="pending"

if [[ -n "$TOKEN_MODE" && -n "$COOKIE_SOURCE" ]]; then
  FAILED_STEP="argumentValidation"
  fail "choose exactly one refresh input: token mode or --cookie-source"
fi

if $DRY_RUN; then
  emit_dry_run
  exit 0
fi

mkdir -p "$ARTIFACT_DIR"

if [[ -n "$COOKIE_SOURCE" ]]; then
  step_status="running"
  FAILED_STEP="refreshInput"
  if python3 "$SCRIPT_DIR/install-chatgpt-cookies.py" --cookie-file "$COOKIE_FILE" --source "$COOKIE_SOURCE" > "$ARTIFACT_DIR/01-install-chatgpt-cookies.json" 2> "$ARTIFACT_DIR/01-install-chatgpt-cookies.stderr"; then
    step_status="ok"
  else
    step_status="error"
    set_failed_detail_from_artifacts "$ARTIFACT_DIR/01-install-chatgpt-cookies.json" "$ARTIFACT_DIR/01-install-chatgpt-cookies.stderr"
    fail "full cookie-jar install failed"
  fi
elif [[ -n "$TOKEN_MODE" ]]; then
  step_status="running"
  FAILED_STEP="refreshInput"
  case "$TOKEN_MODE" in
    file)
      if python3 "$SCRIPT_DIR/replace-session-token.py" --cookie-file "$COOKIE_FILE" --token-file "$TOKEN_FILE" > "$ARTIFACT_DIR/01-replace-session-token.json" 2> "$ARTIFACT_DIR/01-replace-session-token.stderr"; then
        :
      else
        step_status="error"
        set_failed_detail_from_artifacts "$ARTIFACT_DIR/01-replace-session-token.json" "$ARTIFACT_DIR/01-replace-session-token.stderr"
        fail "session-token replacement failed"
      fi
      ;;
    value)
      if python3 "$SCRIPT_DIR/replace-session-token.py" --cookie-file "$COOKIE_FILE" --token "$TOKEN_VALUE" > "$ARTIFACT_DIR/01-replace-session-token.json" 2> "$ARTIFACT_DIR/01-replace-session-token.stderr"; then
        :
      else
        step_status="error"
        set_failed_detail_from_artifacts "$ARTIFACT_DIR/01-replace-session-token.json" "$ARTIFACT_DIR/01-replace-session-token.stderr"
        fail "session-token replacement failed"
      fi
      ;;
    stdin)
      if python3 "$SCRIPT_DIR/replace-session-token.py" --cookie-file "$COOKIE_FILE" --stdin > "$ARTIFACT_DIR/01-replace-session-token.json" 2> "$ARTIFACT_DIR/01-replace-session-token.stderr"; then
        :
      else
        step_status="error"
        set_failed_detail_from_artifacts "$ARTIFACT_DIR/01-replace-session-token.json" "$ARTIFACT_DIR/01-replace-session-token.stderr"
        fail "session-token replacement failed"
      fi
      ;;
  esac
  step_status="ok"
else
  step_status="skipped"
fi

direct_status="running"
FAILED_STEP="chatgptDirectAuth"
if "$SCRIPT_DIR/chatgpt-direct" --auth-only --require-auth --require-pro --cookies "$COOKIE_FILE" --json > "$ARTIFACT_DIR/02-chatgpt-direct-auth.json" 2> "$ARTIFACT_DIR/02-chatgpt-direct-auth.stderr"; then
  direct_status="ok"
else
  direct_status="error"
  set_failed_detail_from_artifacts "$ARTIFACT_DIR/02-chatgpt-direct-auth.json" "$ARTIFACT_DIR/02-chatgpt-direct-auth.stderr"
  fail "direct Camoufox auth/pro verification failed"
fi

wrapper_status="running"
FAILED_STEP="oracleWrapperAuth"
if "$SCRIPT_DIR/oracle-browser" --auth-only --require-auth --require-pro --cookies "$COOKIE_FILE" --json > "$ARTIFACT_DIR/03-oracle-wrapper-auth.json" 2> "$ARTIFACT_DIR/03-oracle-wrapper-auth.stderr"; then
  wrapper_status="ok"
else
  wrapper_status="error"
  set_failed_detail_from_artifacts "$ARTIFACT_DIR/03-oracle-wrapper-auth.json" "$ARTIFACT_DIR/03-oracle-wrapper-auth.stderr"
  fail "Oracle-style wrapper auth/pro verification failed"
fi

check_wrapper_status="running"
FAILED_STEP="checkWrapperLive"
if "$SCRIPT_DIR/check-wrapper.sh" --live --cookie-file "$COOKIE_FILE" --json > "$ARTIFACT_DIR/04-check-wrapper-live.json" 2> "$ARTIFACT_DIR/04-check-wrapper-live.stderr"; then
  check_wrapper_status="ok"
else
  check_wrapper_status="error"
  set_failed_detail_from_artifacts "$ARTIFACT_DIR/04-check-wrapper-live.json" "$ARTIFACT_DIR/04-check-wrapper-live.stderr"
  fail "full wrapper live verification failed"
fi

if $JSON; then
  python3 - <<'PY' "$ARTIFACT_DIR" "$COOKIE_FILE" "$(refresh_desc)" "$step_status" "$direct_status" "$wrapper_status" "$check_wrapper_status" "$VERIFIER_NAME" "$VERIFIER_SCHEMA_VERSION"
import json, sys
artifact_dir, cookie_file, refresh_input, refresh_status, direct_status, wrapper_status, check_wrapper_status, verifier_name, verifier_schema_version = sys.argv[1:10]
print(json.dumps({
    "status": "ok",
    "verifier": verifier_name,
    "verifierSchemaVersion": int(verifier_schema_version),
    "artifactDir": artifact_dir,
    "cookieFile": cookie_file,
    "refreshInput": refresh_input,
    "steps": {
        "refreshInput": refresh_status,
        "chatgptDirectAuth": direct_status,
        "oracleWrapperAuth": wrapper_status,
        "checkWrapperLive": check_wrapper_status,
    },
}, indent=2))
PY
else
  cat <<EOF
Oracle auth refresh verification OK
- artifact dir: $ARTIFACT_DIR
- cookie file: $COOKIE_FILE
- refresh input: $(refresh_desc)
- refresh step: $step_status
- chatgpt-direct auth/pro: $direct_status
- oracle-browser auth/pro: $wrapper_status
- check-wrapper live: $check_wrapper_status
EOF
fi
