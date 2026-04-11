#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"
FILE="notes/autonomy-gaps.md"
DATE=""
TIME_LABEL=""
FORCE=0
CARRY_FORWARD_STATUS=0

usage() {
  cat <<'EOF'
Usage: run-autonomy-audit-preflight.sh [options]

Runs daily autonomy-audit preflight checks:
1) Consistency guard on notes/autonomy-gaps.md
2) Cadence guard (advisory, latest-pair) to surface fresh missing-day snapshot gaps
3) Snapshot scaffold insertion for today's audit

Options:
  --file <path>         Target markdown file (default: notes/autonomy-gaps.md)
  --date <YYYY-MM-DD>   Snapshot date (default: current UTC date)
  --time-label <label>  Snapshot time label (default: current UTC HH:MM UTC)
  --force               Allow duplicate date scaffold insertion
  --carry-forward-status
                        Prefill required status lines from latest snapshot
  -h, --help            Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)
      FILE="$2"
      shift 2
      ;;
    --date)
      DATE="$2"
      shift 2
      ;;
    --time-label)
      TIME_LABEL="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --carry-forward-status)
      CARRY_FORWARD_STATUS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "$FILE" = /* ]]; then
  TARGET_FILE="$FILE"
else
  TARGET_FILE="$WORKSPACE/$FILE"
fi

CHECK_CMD=(python3 "$WORKSPACE/scripts/notes/check-autonomy-gaps-consistency.py" --file "$TARGET_FILE")
CADENCE_CMD=(python3 "$WORKSPACE/scripts/notes/check-autonomy-audit-cadence.py" --file "$TARGET_FILE" --latest-only --fail-on-gap)
PREPEND_CMD=(python3 "$WORKSPACE/scripts/notes/prepend-autonomy-audit-snapshot.py" --file "$TARGET_FILE")

if [[ -n "$DATE" ]]; then
  PREPEND_CMD+=(--date "$DATE")
fi

if [[ -n "$TIME_LABEL" ]]; then
  PREPEND_CMD+=(--time-label "$TIME_LABEL")
fi

if [[ "$FORCE" -eq 1 ]]; then
  PREPEND_CMD+=(--force)
fi

if [[ "$CARRY_FORWARD_STATUS" -eq 1 ]]; then
  PREPEND_CMD+=(--carry-forward-status)
fi

echo "[1/3] Running consistency guard on $TARGET_FILE"
"${CHECK_CMD[@]}"

echo "[2/3] Running cadence guard (advisory, latest-pair)"
set +e
"${CADENCE_CMD[@]}"
cadence_rc=$?
set -e
if [[ "$cadence_rc" -eq 2 ]]; then
  echo "⚠️ Cadence guard reported missing-day gaps. Continue with today's snapshot, and document root cause/fix in the audit workflow section."
elif [[ "$cadence_rc" -ne 0 ]]; then
  echo "❌ Cadence guard failed (exit $cadence_rc). Aborting preflight." >&2
  exit "$cadence_rc"
fi

echo "[3/3] Inserting daily snapshot scaffold"
"${PREPEND_CMD[@]}"

echo "✅ Preflight complete. Fill the new snapshot status blocks, then run scripts/notes/close-autonomy-audit.sh --date ${DATE:-$(date -u +%F)}"
echo "   (legacy two-step still works: finalize-autonomy-audit.py --fail-on-no-change + render-autonomy-audit-response.py)"
