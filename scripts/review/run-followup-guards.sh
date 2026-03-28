#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/review/run-followup-guards.sh <PR_NUMBER> [options]

Options:
  --repo <owner/repo>         GitHub repo (default: ChainSafe/lodestar)
  --include-replies           Include in-thread reply comments for sync-gh
  --match-window-lines <n>    Line distance window for sync-gh matching (default: 5)
  --metadata-report <path>    Output path for metadata drift report
  --stale-report <path>       Output path for stale-findings report
  --stale-days <n>            Staleness threshold in days (default: 7)
  --stale-use-created         Compute staleness from created timestamp (default: updated)
  --skip-stale-check          Skip stale-findings guard step
  --fail-on-stale             Exit non-zero when stale findings are detected
  --sync-dry-run              Run sync-gh in dry-run mode (no tracker writes)
  -h, --help                  Show this help

Behavior:
  1) Runs track-findings.py sync-gh for the PR
  2) Runs check-pr-metadata-drift.py and writes markdown artifact
  3) Runs track-findings.py stale and writes markdown artifact
  4) If metadata drift is detected (exit 2), prints exact gh pr edit reminder command
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

PR=""
REPO="ChainSafe/lodestar"
INCLUDE_REPLIES=0
MATCH_WINDOW_LINES=5
SYNC_DRY_RUN=0
METADATA_REPORT=""
STALE_REPORT=""
STALE_DAYS=7
STALE_USE_CREATED=0
SKIP_STALE_CHECK=0
FAIL_ON_STALE=0

if [[ "${1:-}" =~ ^[0-9]+$ ]]; then
  PR="$1"
  shift
elif [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
else
  echo "ERROR: First argument must be PR number" >&2
  usage
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
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
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
TRACK_FINDINGS="$WORKSPACE_ROOT/scripts/review/track-findings.py"
METADATA_CHECKER="$WORKSPACE_ROOT/scripts/github/check-pr-metadata-drift.py"

if [[ -z "$METADATA_REPORT" ]]; then
  METADATA_REPORT="$WORKSPACE_ROOT/notes/review-reports/pr-${PR}-metadata-drift.md"
fi

if [[ -z "$STALE_REPORT" ]]; then
  STALE_REPORT="$WORKSPACE_ROOT/notes/review-reports/pr-${PR}-stale-findings.md"
fi

mkdir -p "$(dirname -- "$METADATA_REPORT")"
mkdir -p "$(dirname -- "$STALE_REPORT")"

echo "==> [1/3] sync-gh guard (PR #$PR, repo: $REPO)"
SYNC_CMD=(python3 "$TRACK_FINDINGS" sync-gh "$PR" --repo "$REPO" --match-window-lines "$MATCH_WINDOW_LINES")
if [[ "$INCLUDE_REPLIES" -eq 1 ]]; then
  SYNC_CMD+=(--include-replies)
fi
if [[ "$SYNC_DRY_RUN" -eq 1 ]]; then
  SYNC_CMD+=(--dry-run)
fi
"${SYNC_CMD[@]}"

echo ""
echo "==> [2/3] metadata drift guard (artifact: $METADATA_REPORT)"
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
  echo "==> [3/3] stale-finding guard (artifact: $STALE_REPORT)"
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
