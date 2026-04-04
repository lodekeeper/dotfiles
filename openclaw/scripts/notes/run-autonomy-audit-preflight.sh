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
2) Snapshot scaffold insertion for today's audit

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

echo "[1/2] Running consistency guard on $TARGET_FILE"
"${CHECK_CMD[@]}"

echo "[2/2] Inserting daily snapshot scaffold"
"${PREPEND_CMD[@]}"

echo "✅ Preflight complete. Fill the new snapshot status blocks, then run scripts/notes/finalize-autonomy-audit.py --date ${DATE:-$(date -u +%F)} --fail-on-no-change"
echo "   After finalize, render the cron response with scripts/notes/render-autonomy-audit-response.py --date ${DATE:-$(date -u +%F)}"
