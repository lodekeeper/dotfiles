#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  fetch-run-logs.sh <run-id> [--repo owner/repo] [--output <path>]
  fetch-run-logs.sh --check-only

Fetch failed logs for a GitHub Actions run with a full-log fallback.

Examples:
  scripts/ci/fetch-run-logs.sh --check-only
  scripts/ci/fetch-run-logs.sh 23124218154
  scripts/ci/fetch-run-logs.sh 23124218154 --repo ChainSafe/lodestar --output tmp/ci-logs/run-23124218154.log

Options:
  --check-only  Validate local prerequisites without calling GitHub
EOF
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
GH_ACCESS_GUARD="$WORKSPACE_ROOT/scripts/github/check-github-access.sh"

bail_if_github_suspended() {
  [[ -x "$GH_ACCESS_GUARD" ]] || return 0

  local guard_cmd=("$GH_ACCESS_GUARD")
  if [[ -n "${GITHUB_ACCESS_STATE_FILE:-}" ]]; then
    guard_cmd+=(--state-file "$GITHUB_ACCESS_STATE_FILE")
  fi
  if [[ -n "${GITHUB_ACCESS_MAX_AGE_MINUTES:-}" ]]; then
    guard_cmd+=(--max-age-minutes "$GITHUB_ACCESS_MAX_AGE_MINUTES")
  fi

  local guard_output=""
  local guard_rc=0
  set +e
  guard_output="$(timeout 20s "${guard_cmd[@]}" 2>&1)"
  guard_rc=$?
  set -e

  if [[ "$guard_rc" -eq 2 ]]; then
    echo "GITHUB_SUSPENDED_SKIP"
    exit 4
  fi
}

repo="ChainSafe/lodestar"
out=""
run_id=""
check_only=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only)
      check_only=1
      shift
      ;;
    --repo)
      repo="$2"
      shift 2
      ;;
    --output)
      out="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -n "$run_id" ]]; then
        echo "Unexpected extra argument: $1" >&2
        usage >&2
        exit 1
      fi
      run_id="$1"
      shift
      ;;
  esac
done

if [[ "$check_only" -eq 1 ]]; then
  if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR: gh CLI is not available" >&2
    exit 1
  fi
  if [[ ! -x "$GH_ACCESS_GUARD" ]]; then
    echo "ERROR: GitHub access guard is missing or not executable: $GH_ACCESS_GUARD" >&2
    exit 1
  fi
  echo "CI log fetch preflight OK"
  echo "Repo: $repo"
  echo "GitHub guard: $GH_ACCESS_GUARD"
  exit 0
fi

if [[ -z "$run_id" ]]; then
  usage >&2
  exit 1
fi

if ! [[ "$run_id" =~ ^[0-9]+$ ]]; then
  echo "Run ID must be numeric: $run_id" >&2
  usage >&2
  exit 1
fi

if [[ -z "$out" ]]; then
  out="tmp/ci-logs/run-${run_id}.log"
fi

bail_if_github_suspended

mkdir -p "$(dirname "$out")"
err_file="${out}.err"

if gh run view "$run_id" --repo "$repo" --log-failed >"$out" 2>"$err_file"; then
  mode="failed-only"
else
  if gh run view "$run_id" --repo "$repo" --log >"$out" 2>>"$err_file"; then
    mode="full-fallback"
  else
    echo "❌ Failed to fetch run logs for run $run_id ($repo)." >&2
    cat "$err_file" >&2
    exit 1
  fi
fi

lines=$(wc -l <"$out" | tr -d ' ')
bytes=$(wc -c <"$out" | tr -d ' ')

rm -f "$err_file"

echo "✅ Saved $mode logs for run $run_id ($repo)"
echo "   output: $out"
echo "   lines:  $lines"
echo "   bytes:  $bytes"
