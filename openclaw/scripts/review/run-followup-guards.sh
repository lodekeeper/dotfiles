#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/review/run-followup-guards.sh <PR_NUMBER> [options]
  scripts/review/run-followup-guards.sh --check-only [--json]

Options:
  --repo <owner/repo>         GitHub repo (default: ChainSafe/lodestar)
  --check-only                Validate local prerequisites without calling GitHub or writing reports
  --json                      Emit machine-readable output for --check-only
  --include-replies           Include in-thread reply comments for sync-gh
  --match-window-lines <n>    Line distance window for sync-gh matching (default: 5)
  --discussion-report <path>  Output path for full PR discussion coverage report
  --metadata-report <path>    Output path for metadata drift report
  --stale-report <path>       Output path for stale-findings report
  --stale-days <n>            Staleness threshold in days (default: 7)
  --stale-use-created         Compute staleness from created timestamp (default: updated)
  --skip-discussion-scan      Skip full PR discussion coverage scan
  --skip-stale-check          Skip stale-findings guard step
  --fail-on-stale             Exit non-zero when stale findings are detected
  --sync-dry-run              Run sync-gh in dry-run mode (no tracker writes)
  -h, --help                  Show this help

Behavior:
  1) Fetches all PR discussion surfaces (issue comments, inline comments, review bodies)
  2) Runs track-findings.py sync-gh for the PR
  3) Runs check-pr-metadata-drift.py and writes markdown artifact
  4) Runs track-findings.py stale and writes markdown artifact
  If metadata drift is detected (exit 2), prints exact gh pr edit reminder command

Exit codes:
  0 = guards passed
  2 = metadata drift detected
  3 = stale findings detected with --fail-on-stale
  4 = GitHub access currently unavailable/suspended
EOF
}

PR=""
REPO="ChainSafe/lodestar"
CHECK_ONLY=0
JSON=0
INCLUDE_REPLIES=0
MATCH_WINDOW_LINES=5
SYNC_DRY_RUN=0
DISCUSSION_REPORT=""
METADATA_REPORT=""
STALE_REPORT=""
STALE_DAYS=7
STALE_USE_CREATED=0
SKIP_DISCUSSION_SCAN=0
SKIP_STALE_CHECK=0
FAIL_ON_STALE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only)
      CHECK_ONLY=1
      shift
      ;;
    --json)
      JSON=1
      shift
      ;;
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --include-replies)
      INCLUDE_REPLIES=1
      shift
      ;;
    --match-window-lines)
      MATCH_WINDOW_LINES="${2:-}"
      shift 2
      ;;
    --metadata-report)
      METADATA_REPORT="${2:-}"
      shift 2
      ;;
    --discussion-report)
      DISCUSSION_REPORT="${2:-}"
      shift 2
      ;;
    --stale-report)
      STALE_REPORT="${2:-}"
      shift 2
      ;;
    --stale-days)
      STALE_DAYS="${2:-}"
      shift 2
      ;;
    --stale-use-created)
      STALE_USE_CREATED=1
      shift
      ;;
    --skip-discussion-scan)
      SKIP_DISCUSSION_SCAN=1
      shift
      ;;
    --skip-stale-check)
      SKIP_STALE_CHECK=1
      shift
      ;;
    --fail-on-stale)
      FAIL_ON_STALE=1
      shift
      ;;
    --sync-dry-run)
      SYNC_DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ "$1" =~ ^[0-9]+$ && -z "$PR" ]]; then
        PR="$1"
        shift
      else
        echo "ERROR: Unknown argument: $1" >&2
        usage
        exit 1
      fi
      ;;
  esac
done

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
TRACK_FINDINGS="$WORKSPACE_ROOT/scripts/review/track-findings.py"
DISCUSSION_FETCHER="$WORKSPACE_ROOT/scripts/review/fetch-pr-discussion.py"
METADATA_CHECKER="$WORKSPACE_ROOT/scripts/github/check-pr-metadata-drift.py"
GH_ACCESS_GUARD="$WORKSPACE_ROOT/scripts/github/check-github-access.sh"

if [[ "$JSON" -eq 1 && "$CHECK_ONLY" -ne 1 ]]; then
  echo "ERROR: --json is only supported with --check-only" >&2
  exit 1
fi

if [[ "$CHECK_ONLY" -ne 1 && -z "$PR" ]]; then
  echo "ERROR: First argument must be PR number unless --check-only is set" >&2
  usage
  exit 1
fi

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

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  failures=0
  python_available=0
  gh_available=0
  self_syntax_ok=0
  track_findings_present=0
  track_findings_help_ok=0
  track_findings_sync_gh_help_ok=0
  track_findings_stale_help_ok=0
  discussion_fetcher_present=0
  discussion_fetcher_preflight_ok=0
  metadata_checker_present=0
  metadata_checker_help_ok=0
  metadata_checker_check_only_json_ok=0
  github_guard_executable=0
  report_dir_ready=0

  if command -v python3 >/dev/null 2>&1; then
    python_available=1
  else
    [[ "$JSON" -eq 1 ]] || echo "ERROR: python3 is not available" >&2
    failures=$((failures + 1))
  fi

  if command -v gh >/dev/null 2>&1; then
    gh_available=1
  else
    [[ "$JSON" -eq 1 ]] || echo "ERROR: gh CLI is not available" >&2
    failures=$((failures + 1))
  fi

  if bash -n "$0" >/dev/null 2>&1; then
    self_syntax_ok=1
  else
    [[ "$JSON" -eq 1 ]] || echo "ERROR: run-followup-guards.sh syntax check failed" >&2
    failures=$((failures + 1))
  fi

  if [[ -f "$TRACK_FINDINGS" ]]; then
    track_findings_present=1
  else
    [[ "$JSON" -eq 1 ]] || echo "ERROR: missing helper: $TRACK_FINDINGS" >&2
    failures=$((failures + 1))
  fi

  if [[ "$python_available" -eq 1 && "$track_findings_present" -eq 1 ]]; then
    if python3 "$TRACK_FINDINGS" --help >/dev/null 2>&1; then
      track_findings_help_ok=1
    else
      [[ "$JSON" -eq 1 ]] || echo "ERROR: track-findings.py help path failed" >&2
      failures=$((failures + 1))
    fi

    if python3 "$TRACK_FINDINGS" sync-gh --help >/dev/null 2>&1; then
      track_findings_sync_gh_help_ok=1
    else
      [[ "$JSON" -eq 1 ]] || echo "ERROR: track-findings.py sync-gh help path failed" >&2
      failures=$((failures + 1))
    fi

    if python3 "$TRACK_FINDINGS" stale --help >/dev/null 2>&1; then
      track_findings_stale_help_ok=1
    else
      [[ "$JSON" -eq 1 ]] || echo "ERROR: track-findings.py stale help path failed" >&2
      failures=$((failures + 1))
    fi
  fi

  if [[ -x "$DISCUSSION_FETCHER" ]]; then
    discussion_fetcher_present=1
  else
    [[ "$JSON" -eq 1 ]] || echo "ERROR: missing or non-executable helper: $DISCUSSION_FETCHER" >&2
    failures=$((failures + 1))
  fi

  if [[ "$python_available" -eq 1 && "$discussion_fetcher_present" -eq 1 ]]; then
    if python3 "$DISCUSSION_FETCHER" 1 --repo "$REPO" --check-only --json >/dev/null 2>&1; then
      discussion_fetcher_preflight_ok=1
    else
      [[ "$JSON" -eq 1 ]] || echo "ERROR: fetch-pr-discussion.py check-only JSON preflight failed" >&2
      failures=$((failures + 1))
    fi
  fi

  if [[ -f "$METADATA_CHECKER" ]]; then
    metadata_checker_present=1
  else
    [[ "$JSON" -eq 1 ]] || echo "ERROR: missing helper: $METADATA_CHECKER" >&2
    failures=$((failures + 1))
  fi

  if [[ "$python_available" -eq 1 && "$metadata_checker_present" -eq 1 ]]; then
    if python3 "$METADATA_CHECKER" --help >/dev/null 2>&1; then
      metadata_checker_help_ok=1
    else
      [[ "$JSON" -eq 1 ]] || echo "ERROR: check-pr-metadata-drift.py help path failed" >&2
      failures=$((failures + 1))
    fi

    if python3 "$METADATA_CHECKER" --repo "$REPO" --check-only --json >/dev/null 2>&1; then
      metadata_checker_check_only_json_ok=1
    else
      [[ "$JSON" -eq 1 ]] || echo "ERROR: check-pr-metadata-drift.py check-only JSON preflight failed" >&2
      failures=$((failures + 1))
    fi
  fi

  if [[ -x "$GH_ACCESS_GUARD" ]]; then
    github_guard_executable=1
  else
    [[ "$JSON" -eq 1 ]] || echo "ERROR: GitHub access guard is missing or not executable: $GH_ACCESS_GUARD" >&2
    failures=$((failures + 1))
  fi

  report_dir="$WORKSPACE_ROOT/notes/review-reports"
  if { [[ -d "$report_dir" && -w "$report_dir" ]] || [[ ! -e "$report_dir" && -d "$(dirname -- "$report_dir")" && -w "$(dirname -- "$report_dir")" ]]; }; then
    report_dir_ready=1
  else
    [[ "$JSON" -eq 1 ]] || echo "ERROR: report directory is not writable or creatable: $report_dir" >&2
    failures=$((failures + 1))
  fi

  if [[ "$JSON" -eq 1 ]]; then
    if [[ "$python_available" -eq 1 ]]; then
      python3 - \
        "$failures" \
        "$WORKSPACE_ROOT" \
        "$REPO" \
        "$python_available" \
        "$gh_available" \
        "$self_syntax_ok" \
        "$TRACK_FINDINGS" \
        "$track_findings_present" \
        "$track_findings_help_ok" \
        "$track_findings_sync_gh_help_ok" \
        "$track_findings_stale_help_ok" \
        "$DISCUSSION_FETCHER" \
        "$discussion_fetcher_present" \
        "$discussion_fetcher_preflight_ok" \
        "$METADATA_CHECKER" \
        "$metadata_checker_present" \
        "$metadata_checker_help_ok" \
        "$metadata_checker_check_only_json_ok" \
        "$GH_ACCESS_GUARD" \
        "$github_guard_executable" \
        "$report_dir" \
        "$report_dir_ready" <<'PY'
import json
import sys

failures = int(sys.argv[1])
payload = {
    "ok": failures == 0,
    "workspace": sys.argv[2],
    "repo": sys.argv[3],
    "python3Available": bool(int(sys.argv[4])),
    "ghAvailable": bool(int(sys.argv[5])),
    "selfSyntaxOk": bool(int(sys.argv[6])),
    "helpers": {
        "trackFindings": {
            "path": sys.argv[7],
            "present": bool(int(sys.argv[8])),
            "helpOk": bool(int(sys.argv[9])),
            "syncGhHelpOk": bool(int(sys.argv[10])),
            "staleHelpOk": bool(int(sys.argv[11])),
        },
        "fetchPrDiscussion": {
            "path": sys.argv[12],
            "present": bool(int(sys.argv[13])),
            "checkOnlyJsonOk": bool(int(sys.argv[14])),
        },
        "checkPrMetadataDrift": {
            "path": sys.argv[15],
            "present": bool(int(sys.argv[16])),
            "helpOk": bool(int(sys.argv[17])),
            "checkOnlyJsonOk": bool(int(sys.argv[18])),
        },
        "githubAccessGuard": {
            "path": sys.argv[19],
            "executable": bool(int(sys.argv[20])),
        },
    },
    "reportDirectory": {
        "path": sys.argv[21],
        "ready": bool(int(sys.argv[22])),
    },
}
print(json.dumps(payload, sort_keys=True))
PY
    else
      printf '{"helpers":{},"ok":false,"python3Available":false,"workspace":"%s"}\n' "$WORKSPACE_ROOT"
    fi

    if [[ "$failures" -ne 0 ]]; then
      exit 2
    fi
    exit 0
  fi

  if [[ "$failures" -ne 0 ]]; then
    exit 2
  fi

  echo "PR follow-up guard preflight OK"
  echo "Workspace: $WORKSPACE_ROOT"
  echo "Repo: $REPO"
  echo "Discussion fetcher: $DISCUSSION_FETCHER"
  echo "Finding tracker: $TRACK_FINDINGS"
  echo "Metadata checker: $METADATA_CHECKER"
  echo "GitHub guard: $GH_ACCESS_GUARD"
  echo "Report directory: $report_dir"
  exit 0
fi

if [[ -z "$METADATA_REPORT" ]]; then
  METADATA_REPORT="$WORKSPACE_ROOT/notes/review-reports/pr-${PR}-metadata-drift.md"
fi

if [[ -z "$DISCUSSION_REPORT" ]]; then
  DISCUSSION_REPORT="$WORKSPACE_ROOT/notes/review-reports/pr-${PR}-discussion.md"
fi

if [[ -z "$STALE_REPORT" ]]; then
  STALE_REPORT="$WORKSPACE_ROOT/notes/review-reports/pr-${PR}-stale-findings.md"
fi

bail_if_github_suspended

mkdir -p "$(dirname -- "$DISCUSSION_REPORT")"
mkdir -p "$(dirname -- "$METADATA_REPORT")"
mkdir -p "$(dirname -- "$STALE_REPORT")"

if [[ "$SKIP_DISCUSSION_SCAN" -eq 0 ]]; then
  echo "==> [1/4] full PR discussion scan (artifact: $DISCUSSION_REPORT)"
  python3 "$DISCUSSION_FETCHER" "$PR" --repo "$REPO" > "$DISCUSSION_REPORT"
  cat "$DISCUSSION_REPORT"
  echo ""
  echo "Discussion report saved: $DISCUSSION_REPORT"
else
  echo "==> [1/4] skipping full PR discussion scan (--skip-discussion-scan)"
fi

echo ""
echo "==> [2/4] sync-gh guard (PR #$PR, repo: $REPO)"
SYNC_CMD=(python3 "$TRACK_FINDINGS" sync-gh "$PR" --repo "$REPO" --match-window-lines "$MATCH_WINDOW_LINES")
if [[ "$INCLUDE_REPLIES" -eq 1 ]]; then
  SYNC_CMD+=(--include-replies)
fi
if [[ "$SYNC_DRY_RUN" -eq 1 ]]; then
  SYNC_CMD+=(--dry-run)
fi
"${SYNC_CMD[@]}"

echo ""
echo "==> [3/4] metadata drift guard (artifact: $METADATA_REPORT)"
set +e
python3 "$METADATA_CHECKER" --pr "$PR" --repo "$REPO" > "$METADATA_REPORT"
DRIFT_RC=$?
set -e

cat "$METADATA_REPORT"
echo ""

echo "Metadata report saved: $METADATA_REPORT"

STALE_RC=0
if [[ "$SKIP_STALE_CHECK" -eq 0 ]]; then
  echo ""
  echo "==> [4/4] stale-finding guard (artifact: $STALE_REPORT)"
  STALE_CMD=(python3 "$TRACK_FINDINGS" stale "$PR" --days "$STALE_DAYS" --severity critical major --fail-on-match)
  if [[ "$STALE_USE_CREATED" -eq 1 ]]; then
    STALE_CMD+=(--use-created)
  fi

  set +e
  "${STALE_CMD[@]}" > "$STALE_REPORT"
  STALE_RC=$?
  set -e

  cat "$STALE_REPORT"
  echo ""

  echo "Stale findings report saved: $STALE_REPORT"
fi

if [[ "$DRIFT_RC" -ne 0 && "$DRIFT_RC" -ne 2 ]]; then
  echo "❌ Metadata guard failed (exit $DRIFT_RC). See report above." >&2
  exit "$DRIFT_RC"
fi

if [[ "$SKIP_STALE_CHECK" -eq 0 ]]; then
  if [[ "$STALE_RC" -ne 0 && "$STALE_RC" -ne 2 ]]; then
    echo "❌ Stale-finding guard failed (exit $STALE_RC). See report above." >&2
    exit "$STALE_RC"
  fi

  if [[ "$STALE_RC" -eq 2 ]]; then
    if [[ "$FAIL_ON_STALE" -eq 1 ]]; then
      echo "⚠️ Stale findings detected and --fail-on-stale set."
      # preserve metadata drift signal as highest-priority exit when both fire
      if [[ "$DRIFT_RC" -eq 2 ]]; then
        echo "⚠️ Metadata drift also detected. Update PR title/body before re-review."
        echo "Run: gh pr edit $PR --repo $REPO --title \"<updated title>\" --body-file <path-to-updated-body.md>"
        exit 2
      fi
      exit 3
    else
      echo "⚠️ Stale findings detected (non-fatal by default)."
      echo "Re-run with --fail-on-stale if you want stale findings to block re-review."
    fi
  fi
fi

if [[ "$DRIFT_RC" -eq 2 ]]; then
  echo "⚠️ Metadata drift detected. Update PR title/body before re-review."
  echo "Run: gh pr edit $PR --repo $REPO --title \"<updated title>\" --body-file <path-to-updated-body.md>"
  exit 2
fi

echo "✅ Follow-up guards passed."
exit 0
