#!/usr/bin/env bash
set -euo pipefail

BASE_REPO="${BASE_REPO:-$HOME/consensus-specs}"
TARGET_REPO="${SPEC_REPO_FRESH_CACHE:-$HOME/.cache/lodekeeper/consensus-specs-fresh}"
REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-master}"
REMOTE_URL="${REMOTE_URL:-https://github.com/ethereum/consensus-specs.git}"
MAX_AGE_DAYS=14
CHECK_ONLY=false
JSON_OUTPUT=false

usage() {
  cat <<'EOF'
Usage: ensure-fresh-test-vectors.sh [options]

Ensure a dedicated, clean consensus-specs checkout exists for test-vector
readiness checks. This avoids mutating an active ~/consensus-specs feature
branch when the daily autonomy preflight only needs current upstream vectors.

Options:
  --base-repo <path>       Existing consensus-specs repo to fetch/worktree from
                           (default: ~/consensus-specs)
  --target-repo <path>     Dedicated checkout/cache path
                           (default: ~/.cache/lodekeeper/consensus-specs-fresh)
  --remote <name>          Git remote name when using --base-repo (default: origin)
  --branch <name>          Upstream branch to track (default: master)
  --remote-url <url>       Clone URL if --base-repo is unavailable
  --max-age-days <days>    Freshness threshold for tests/ history (default: 14)
  --check-only             Do not fetch/create/update; only validate target cache
  --json                   Emit machine-readable status on stdout
  --help                   Show help

Exit codes:
  0  Fresh target checkout is ready
  2  Target checkout is missing/stale/dirty or vectors are not fresh enough
  1  Invalid args or unexpected failure
EOF
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

emit_json() {
  local ok="$1"
  local status="$2"
  local message="$3"
  local readiness_json="${4:-}"

  python3 - \
    "$ok" \
    "$status" \
    "$message" \
    "$BASE_REPO" \
    "$TARGET_REPO" \
    "$REMOTE" \
    "$BRANCH" \
    "$MAX_AGE_DAYS" \
    "$CHECK_ONLY" \
    "$readiness_json" <<'PY'
import json
import sys

readiness_raw = sys.argv[10]
readiness = None
if readiness_raw:
    try:
        readiness = json.loads(readiness_raw)
    except json.JSONDecodeError:
        readiness = {"raw": readiness_raw}

payload = {
    "ok": sys.argv[1] == "true",
    "status": sys.argv[2],
    "message": sys.argv[3],
    "baseRepo": sys.argv[4],
    "targetRepo": sys.argv[5],
    "remote": sys.argv[6],
    "branch": sys.argv[7],
    "maxAgeDays": int(sys.argv[8]),
    "checkOnly": sys.argv[9] == "true",
    "readiness": readiness,
}
print(json.dumps(payload, sort_keys=True))
PY
}

expand_path() {
  local p="$1"
  if [[ "$p" == ~* ]]; then
    echo "${p/#\~/$HOME}"
  else
    echo "$p"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-repo)
      [[ $# -ge 2 ]] || fail "Missing value for --base-repo"
      BASE_REPO="$2"
      shift 2
      ;;
    --target-repo)
      [[ $# -ge 2 ]] || fail "Missing value for --target-repo"
      TARGET_REPO="$2"
      shift 2
      ;;
    --remote)
      [[ $# -ge 2 ]] || fail "Missing value for --remote"
      REMOTE="$2"
      shift 2
      ;;
    --branch)
      [[ $# -ge 2 ]] || fail "Missing value for --branch"
      BRANCH="$2"
      shift 2
      ;;
    --remote-url)
      [[ $# -ge 2 ]] || fail "Missing value for --remote-url"
      REMOTE_URL="$2"
      shift 2
      ;;
    --max-age-days)
      [[ $# -ge 2 ]] || fail "Missing value for --max-age-days"
      MAX_AGE_DAYS="$2"
      if ! [[ "$MAX_AGE_DAYS" =~ ^[0-9]+$ ]]; then
        fail "Invalid --max-age-days: $MAX_AGE_DAYS"
      fi
      shift 2
      ;;
    --check-only)
      CHECK_ONLY=true
      shift
      ;;
    --json)
      JSON_OUTPUT=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

BASE_REPO="$(expand_path "$BASE_REPO")"
TARGET_REPO="$(expand_path "$TARGET_REPO")"
WORKSPACE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
READINESS_SCRIPT="$WORKSPACE_ROOT/scripts/spec/check-test-vector-readiness.sh"

if [[ "$CHECK_ONLY" == "true" ]]; then
  if [[ ! -d "$TARGET_REPO/.git" && ! -f "$TARGET_REPO/.git" ]]; then
    message="fresh consensus-specs cache is missing; run scripts/spec/ensure-fresh-test-vectors.sh"
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      emit_json false "missing_cache" "$message"
    else
      echo "❌ $message" >&2
    fi
    exit 2
  fi
else
  mkdir -p "$(dirname "$TARGET_REPO")"
  if [[ ! -d "$TARGET_REPO/.git" && ! -f "$TARGET_REPO/.git" ]]; then
    if [[ -d "$BASE_REPO/.git" ]]; then
      git -C "$BASE_REPO" fetch "$REMOTE" "$BRANCH"
      git -C "$BASE_REPO" worktree add --detach "$TARGET_REPO" "$REMOTE/$BRANCH"
    else
      git clone --branch "$BRANCH" "$REMOTE_URL" "$TARGET_REPO"
    fi
  else
    dirty_status="$(git -C "$TARGET_REPO" status --porcelain)"
    if [[ -n "$dirty_status" ]]; then
      message="target consensus-specs cache is dirty; refusing to overwrite $TARGET_REPO"
      if [[ "$JSON_OUTPUT" == "true" ]]; then
        emit_json false "dirty_cache" "$message"
      else
        echo "❌ $message" >&2
        echo "$dirty_status" >&2
      fi
      exit 2
    fi

    if git -C "$TARGET_REPO" remote get-url "$REMOTE" >/dev/null 2>&1; then
      git -C "$TARGET_REPO" fetch "$REMOTE" "$BRANCH"
      git -C "$TARGET_REPO" checkout --detach "$REMOTE/$BRANCH"
    elif [[ -d "$BASE_REPO/.git" ]]; then
      git -C "$BASE_REPO" fetch "$REMOTE" "$BRANCH"
      git -C "$TARGET_REPO" checkout --detach "$REMOTE/$BRANCH"
    else
      message="target cache has no '$REMOTE' remote and base repo is unavailable"
      if [[ "$JSON_OUTPUT" == "true" ]]; then
        emit_json false "missing_remote" "$message"
      else
        echo "❌ $message" >&2
      fi
      exit 2
    fi
  fi
fi

set +e
readiness_json="$(
  bash "$READINESS_SCRIPT" \
    --spec-repo "$TARGET_REPO" \
    --max-age-days "$MAX_AGE_DAYS" \
    --require-fresh \
    --json
)"
readiness_rc=$?
set -e

if [[ "$JSON_OUTPUT" == "true" ]]; then
  if [[ "$readiness_rc" -eq 0 ]]; then
    emit_json true "ready" "fresh consensus-specs test-vector cache is ready" "$readiness_json"
  else
    emit_json false "not_ready" "fresh consensus-specs test-vector cache is not ready" "$readiness_json"
  fi
else
  if [[ "$readiness_rc" -eq 0 ]]; then
    echo "✅ Fresh consensus-specs test-vector cache is ready: $TARGET_REPO"
  else
    echo "❌ Fresh consensus-specs test-vector cache is not ready: $TARGET_REPO" >&2
  fi
  bash "$READINESS_SCRIPT" \
    --spec-repo "$TARGET_REPO" \
    --max-age-days "$MAX_AGE_DAYS" \
    --require-fresh
fi

if [[ "$readiness_rc" -eq 0 ]]; then
  exit 0
fi
exit 2
