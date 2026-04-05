#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"
FILE="notes/autonomy-gaps.md"
DATE=""

usage() {
  cat <<'EOF'
Usage: close-autonomy-audit.sh [options]

Runs daily autonomy-audit close-out in one command:
1) finalize snapshot + consistency/delta guards
2) render cron-ready response text

Options:
  --file <path>         Target markdown file (default: notes/autonomy-gaps.md)
  --date <YYYY-MM-DD>   Snapshot date (default: current UTC date)
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

TARGET_DATE="${DATE:-$(date -u +%F)}"

FINALIZE_CMD=(
  python3 "$WORKSPACE/scripts/notes/finalize-autonomy-audit.py"
  --file "$TARGET_FILE"
  --date "$TARGET_DATE"
  --fail-on-no-change
)

set +e
"${FINALIZE_CMD[@]}"
finalize_rc=$?
set -e

if [[ "$finalize_rc" -eq 3 ]]; then
  echo "NO_REPLY"
  exit 0
fi

if [[ "$finalize_rc" -ne 0 ]]; then
  exit "$finalize_rc"
fi

python3 "$WORKSPACE/scripts/notes/render-autonomy-audit-response.py" \
  --file "$TARGET_FILE" \
  --date "$TARGET_DATE"

