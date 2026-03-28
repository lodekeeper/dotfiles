#!/usr/bin/env bash
# stale-findings-report.sh — Scan all tracked PRs for stale unresolved review findings.
#
# Usage:
#   stale-findings-report.sh [--days 7] [--severity critical major] [--output report.md]
#   stale-findings-report.sh --prs 8993 8924  # scan specific PRs only
#
# Exit codes:
#   0 — no stale findings
#   2 — stale findings detected (report written)
#   1 — error
#
# Designed to run as a cron wrapper: when stale findings exist, writes a
# markdown report suitable for BACKLOG insertion or topic-thread posting.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TRACKER="$SCRIPT_DIR/track-findings.py"
FINDINGS_DIR="$SCRIPT_DIR/../notes/review-findings"
REPORT_DIR="$SCRIPT_DIR/../notes/review-reports"

# Defaults
DAYS=7
SEVERITY=(critical major)
OUTPUT=""
SPECIFIC_PRS=()

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --days)     DAYS="$2"; shift 2 ;;
    --severity) shift; SEVERITY=(); while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do SEVERITY+=("$1"); shift; done ;;
    --output)   OUTPUT="$2"; shift 2 ;;
    --prs)      shift; while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do SPECIFIC_PRS+=("$1"); shift; done ;;
    -h|--help)
      sed -n '2,/^$/{ s/^# //; s/^#$//; p }' "$0"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Build severity args
SEV_ARGS=()
if [[ ${#SEVERITY[@]} -gt 0 ]]; then
  SEV_ARGS+=(--severity "${SEVERITY[@]}")
fi

# Discover PRs to scan
discover_prs() {
  if [[ ${#SPECIFIC_PRS[@]} -gt 0 ]]; then
    printf '%s\n' "${SPECIFIC_PRS[@]}"
    return
  fi
  # Scan findings directory for PR-*.json files
  if [[ -d "$FINDINGS_DIR" ]]; then
    find "$FINDINGS_DIR" -maxdepth 1 -name 'PR-*.json' -printf '%f\n' 2>/dev/null \
      | sed 's/^PR-//; s/\.json$//' \
      | sort -n
  fi
}

PRS=($(discover_prs))

if [[ ${#PRS[@]} -eq 0 ]]; then
  echo "No tracked PRs found in $FINDINGS_DIR"
  exit 0
fi

# Run stale check on each PR, collect results
STALE_FOUND=false
REPORT_LINES=()
REPORT_LINES+=("# Stale Review Findings Report")
REPORT_LINES+=("")
REPORT_LINES+=("Generated: $(date -u '+%Y-%m-%d %H:%M UTC')")
REPORT_LINES+=("Threshold: open ${SEVERITY[*]} findings older than ${DAYS} days")
REPORT_LINES+=("")

for PR in "${PRS[@]}"; do
  # Capture stale output; exit code 2 = stale findings exist
  STALE_OUTPUT=""
  EXIT_CODE=0
  STALE_OUTPUT=$(python3 "$TRACKER" stale "$PR" --days "$DAYS" "${SEV_ARGS[@]}" --fail-on-match 2>&1) || EXIT_CODE=$?

  if [[ $EXIT_CODE -eq 2 ]]; then
    STALE_FOUND=true
    REPORT_LINES+=("## PR #${PR}")
    REPORT_LINES+=("")
    REPORT_LINES+=('```')
    REPORT_LINES+=("$STALE_OUTPUT")
    REPORT_LINES+=('```')
    REPORT_LINES+=("")
  elif [[ $EXIT_CODE -ne 0 ]]; then
    REPORT_LINES+=("## PR #${PR}")
    REPORT_LINES+=("")
    REPORT_LINES+=("⚠️ Error running stale check (exit $EXIT_CODE):")
    REPORT_LINES+=('```')
    REPORT_LINES+=("$STALE_OUTPUT")
    REPORT_LINES+=('```')
    REPORT_LINES+=("")
  fi
  # exit 0 = no stale findings for this PR, skip silently
done

if [[ "$STALE_FOUND" == "false" ]]; then
  echo "✅ No stale findings across ${#PRS[@]} tracked PR(s)."
  exit 0
fi

# Build final report
REPORT_LINES+=("---")
REPORT_LINES+=("**Action required:** Address or acknowledge these stale findings.")
REPORT_LINES+=("Use \`track-findings.py resolve <pr> <id> --note '...'\` to update status.")

REPORT_CONTENT=$(printf '%s\n' "${REPORT_LINES[@]}")

# Write report
mkdir -p "$REPORT_DIR"
if [[ -n "$OUTPUT" ]]; then
  echo "$REPORT_CONTENT" > "$OUTPUT"
  echo "Report written to: $OUTPUT"
else
  TIMESTAMP=$(date -u '+%Y%m%d-%H%M')
  DEFAULT_OUT="$REPORT_DIR/stale-findings-${TIMESTAMP}.md"
  echo "$REPORT_CONTENT" > "$DEFAULT_OUT"
  echo "Report written to: $DEFAULT_OUT"
fi

# Also print to stdout for cron capture
echo ""
echo "$REPORT_CONTENT"

exit 2
