#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/../.." && pwd)"
COOKIE_FILE="$HOME/.oracle/chatgpt-cookies.json"
ARTIFACT_ROOT="$WORKSPACE/research/oracle"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARTIFACT_DIR="$ARTIFACT_ROOT/refresh-verify-$STAMP"

TOKEN_MODE=""
TOKEN_VALUE=""
TOKEN_FILE=""
COOKIE_SOURCE=""
JSON=false
DRY_RUN=false

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
  --cookie-source <path> Replace the local jar from a full cookie export first
  --cookie-file <path>   Override destination cookie jar path (default: ~/.oracle/chatgpt-cookies.json)
  --dry-run              Print the planned verification sequence without changing anything
  --json                 Emit final summary as JSON
  -h, --help             Show help

Examples:
  scripts/oracle/verify-after-auth-refresh.sh --token-file /tmp/session-token.txt
  scripts/oracle/verify-after-auth-refresh.sh --cookie-source /tmp/chatgpt-cookies.json
  scripts/oracle/verify-after-auth-refresh.sh --dry-run --json
  scripts/oracle/verify-after-auth-refresh.sh --json
EOF
}

emit_dry_run() {
  local refresh_desc
  case "$TOKEN_MODE" in
    file) refresh_desc="replace-session-token from file: $TOKEN_FILE" ;;
    value) refresh_desc="replace-session-token from inline value" ;;
    stdin) refresh_desc="replace-session-token from stdin" ;;
    *)
      if [[ -n "$COOKIE_SOURCE" ]]; then
        refresh_desc="install full cookie export from: $COOKIE_SOURCE"
      else
        refresh_desc="no refresh input; verify existing cookie jar only"
      fi
      ;;
  esac

  if $JSON; then
    python3 - <<'PY' "$ARTIFACT_DIR" "$COOKIE_FILE" "$refresh_desc"
import json, sys
artifact_dir, cookie_file, refresh_desc = sys.argv[1:4]
print(json.dumps({
    "status": "ok",
    "mode": "dry-run",
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
- refresh input: $refresh_desc
- planned steps:
  1. chatgpt-direct --auth-only --require-auth --require-pro --cookies <cookieFile> --json
  2. oracle-browser --auth-only --require-auth --require-pro --cookies <cookieFile> --json
  3. check-wrapper.sh --live --cookie-file <cookieFile> --json
EOF
  fi
}

fail() {
  local message="$1"
  if $JSON; then
    python3 - <<'PY' "$message" "$ARTIFACT_DIR"
import json, sys
print(json.dumps({"status": "error", "message": sys.argv[1], "artifactDir": sys.argv[2]}, indent=2))
PY
  else
    echo "ERROR: $message" >&2
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
  fail "choose exactly one refresh input: token mode or --cookie-source"
fi

if $DRY_RUN; then
  emit_dry_run
  exit 0
fi

mkdir -p "$ARTIFACT_DIR"

if [[ -n "$COOKIE_SOURCE" ]]; then
  step_status="running"
  python3 "$SCRIPT_DIR/install-chatgpt-cookies.py" --cookie-file "$COOKIE_FILE" --source "$COOKIE_SOURCE" > "$ARTIFACT_DIR/01-install-chatgpt-cookies.json" \
    || fail "full cookie-jar install failed"
  step_status="ok"
elif [[ -n "$TOKEN_MODE" ]]; then
  step_status="running"
  case "$TOKEN_MODE" in
    file)
      python3 "$SCRIPT_DIR/replace-session-token.py" --cookie-file "$COOKIE_FILE" --token-file "$TOKEN_FILE" > "$ARTIFACT_DIR/01-replace-session-token.json" \
        || fail "session-token replacement failed"
      ;;
    value)
      python3 "$SCRIPT_DIR/replace-session-token.py" --cookie-file "$COOKIE_FILE" --token "$TOKEN_VALUE" > "$ARTIFACT_DIR/01-replace-session-token.json" \
        || fail "session-token replacement failed"
      ;;
    stdin)
      python3 "$SCRIPT_DIR/replace-session-token.py" --cookie-file "$COOKIE_FILE" --stdin > "$ARTIFACT_DIR/01-replace-session-token.json" \
        || fail "session-token replacement failed"
      ;;
  esac
  step_status="ok"
else
  step_status="skipped"
fi

direct_status="running"
if "$SCRIPT_DIR/chatgpt-direct" --auth-only --require-auth --require-pro --cookies "$COOKIE_FILE" --json > "$ARTIFACT_DIR/02-chatgpt-direct-auth.json"; then
  direct_status="ok"
else
  direct_status="error"
  fail "direct Camoufox auth/pro verification failed"
fi

wrapper_status="running"
if "$SCRIPT_DIR/oracle-browser" --auth-only --require-auth --require-pro --cookies "$COOKIE_FILE" --json > "$ARTIFACT_DIR/03-oracle-wrapper-auth.json"; then
  wrapper_status="ok"
else
  wrapper_status="error"
  fail "Oracle-style wrapper auth/pro verification failed"
fi

check_wrapper_status="running"
if "$SCRIPT_DIR/check-wrapper.sh" --live --cookie-file "$COOKIE_FILE" --json > "$ARTIFACT_DIR/04-check-wrapper-live.json"; then
  check_wrapper_status="ok"
else
  check_wrapper_status="error"
  fail "full wrapper live verification failed"
fi

if $JSON; then
  python3 - <<'PY' "$ARTIFACT_DIR" "$COOKIE_FILE" "$step_status" "$direct_status" "$wrapper_status" "$check_wrapper_status"
import json, sys
artifact_dir, cookie_file, refresh_status, direct_status, wrapper_status, check_wrapper_status = sys.argv[1:7]
print(json.dumps({
    "status": "ok",
    "artifactDir": artifact_dir,
    "cookieFile": cookie_file,
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
- refresh input: $step_status
- chatgpt-direct auth/pro: $direct_status
- oracle-browser auth/pro: $wrapper_status
- check-wrapper live: $check_wrapper_status
EOF
fi
