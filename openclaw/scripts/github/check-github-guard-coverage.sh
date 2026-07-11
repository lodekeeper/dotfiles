#!/usr/bin/env bash
# Verify that GitHub-dependent automation keeps the suspension pre-flight guard.
set -euo pipefail

WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"

failures=0

require_file() {
  local path="$1"
  if [[ ! -f "$WORKSPACE/$path" ]]; then
    echo "MISSING file: $path" >&2
    failures=$((failures + 1))
    return 1
  fi
  return 0
}

require_executable() {
  local path="$1"
  require_file "$path" || return 0
  if [[ ! -x "$WORKSPACE/$path" ]]; then
    echo "NOT_EXECUTABLE file: $path" >&2
    failures=$((failures + 1))
  fi
}

require_pattern() {
  local path="$1"
  local pattern="$2"
  require_file "$path" || return 0
  if ! grep -Fq -- "$pattern" "$WORKSPACE/$path"; then
    echo "MISSING pattern in $path: $pattern" >&2
    failures=$((failures + 1))
  fi
}

require_executable "scripts/github/check-github-access.sh"

require_pattern "scripts/github/github_notifications_sweep.py" "bail_if_github_suspended"
require_pattern "scripts/github/github_notifications_sweep.py" "HEARTBEAT_OK"
require_pattern "scripts/github/monitor_open_pr_ci.py" "bail_if_github_suspended"
require_pattern "scripts/github/monitor_open_pr_ci.py" "NO_REPLY"
require_pattern "scripts/ci/auto_fix_flaky.py" "bail_if_github_suspended"
require_pattern "scripts/ci/auto_fix_flaky.py" "GITHUB_SUSPENDED_SKIP"
require_executable "scripts/ci/fetch-run-logs.sh"
require_pattern "scripts/ci/fetch-run-logs.sh" "bail_if_github_suspended"
require_pattern "scripts/ci/fetch-run-logs.sh" "GITHUB_SUSPENDED_SKIP"
require_pattern "scripts/ci/fetch-run-logs.sh" "GITHUB_ACCESS_STATE_FILE"
require_pattern "scripts/ci/fetch-run-logs.sh" "--check-only"
if ! bash "$WORKSPACE/scripts/ci/fetch-run-logs.sh" --check-only >/dev/null; then
  echo "FAILED check-only preflight: scripts/ci/fetch-run-logs.sh" >&2
  failures=$((failures + 1))
fi
require_pattern "scripts/ci/CRON_PROMPT.md" "scripts/github/check-github-access.sh"
require_pattern "scripts/ci/CRON_PROMPT.md" "GITHUB_SUSPENDED_SKIP"
require_pattern "scripts/review/track-findings.py" "bail_if_github_suspended"
require_pattern "scripts/review/track-findings.py" "GITHUB_SUSPENDED_SKIP"
require_pattern "scripts/github/check-pr-metadata-drift.py" "bail_if_github_suspended"
require_pattern "scripts/github/check-pr-metadata-drift.py" "GITHUB_SUSPENDED_SKIP"
require_pattern "scripts/github/check-pr-metadata-drift.py" "--check-only"
if ! python3 "$WORKSPACE/scripts/github/check-pr-metadata-drift.py" --check-only --json >/dev/null; then
  echo "FAILED check-only JSON preflight: scripts/github/check-pr-metadata-drift.py" >&2
  failures=$((failures + 1))
fi
require_pattern "scripts/review/run-followup-guards.sh" "bail_if_github_suspended"
require_pattern "scripts/review/run-followup-guards.sh" "GITHUB_SUSPENDED_SKIP"
require_pattern "scripts/review/run-followup-guards.sh" "GITHUB_ACCESS_STATE_FILE"
require_pattern "scripts/review/run-followup-guards.sh" "--check-only"
if ! bash "$WORKSPACE/scripts/review/run-followup-guards.sh" --check-only --json >/dev/null; then
  echo "FAILED check-only JSON preflight: scripts/review/run-followup-guards.sh" >&2
  failures=$((failures + 1))
fi
require_executable "scripts/review/fetch-pr-discussion.py"
require_pattern "scripts/review/fetch-pr-discussion.py" "bail_if_github_suspended"
require_pattern "scripts/review/fetch-pr-discussion.py" "GITHUB_SUSPENDED_SKIP"
require_pattern "scripts/review/fetch-pr-discussion.py" "GITHUB_ACCESS_STATE_FILE"
if ! python3 "$WORKSPACE/scripts/review/fetch-pr-discussion.py" 1 --repo ChainSafe/lodestar --check-only --json >/dev/null; then
  echo "FAILED check-only JSON preflight: scripts/review/fetch-pr-discussion.py" >&2
  failures=$((failures + 1))
fi

if [[ "$failures" -ne 0 ]]; then
  echo "GitHub guard coverage: FAILED ($failures issue(s))" >&2
  exit 2
fi

echo "GitHub guard coverage: OK"
