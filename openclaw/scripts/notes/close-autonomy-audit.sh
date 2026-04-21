#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"
FILE="notes/autonomy-gaps.md"
DATE=""
VERBOSE=0
STRICT_CADENCE=0
SKIP_CADENCE_CHECK=0

usage() {
  cat <<'EOF'
Usage: close-autonomy-audit.sh [options]

Runs daily autonomy-audit close-out in one command:
1) finalize snapshot + consistency/delta guards
2) render cron-ready response text

Options:
  --file <path>         Target markdown file (default: notes/autonomy-gaps.md)
  --date <YYYY-MM-DD>   Snapshot date (default: current UTC date)
  --strict-cadence      Treat cadence gaps as hard failures (default: advisory warning)
  --skip-cadence-check  Skip cadence guard during close-out
  -v, --verbose         Print finalize logs to stderr
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
    --strict-cadence)
      STRICT_CADENCE=1
      shift
      ;;
    --skip-cadence-check)
      SKIP_CADENCE_CHECK=1
      shift
      ;;
    -v|--verbose)
      VERBOSE=1
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

TARGET_DATE="${DATE:-$(date -u +%F)}"

FINALIZE_CMD=(
  python3 "$WORKSPACE/scripts/notes/finalize-autonomy-audit.py"
  --file "$TARGET_FILE"
  --date "$TARGET_DATE"
  --fail-on-no-change
)

finalize_log="$(mktemp)"
cleanup() {
  rm -f "$finalize_log"
}
trap cleanup EXIT

set +e
"${FINALIZE_CMD[@]}" >"$finalize_log" 2>&1
finalize_rc=$?
set -e

if [[ "$VERBOSE" -eq 1 && -s "$finalize_log" ]]; then
  cat "$finalize_log" >&2
fi

if [[ "$finalize_rc" -ne 0 && "$finalize_rc" -ne 3 ]]; then
  if [[ "$VERBOSE" -ne 1 && -s "$finalize_log" ]]; then
    cat "$finalize_log" >&2
  fi
  exit "$finalize_rc"
fi

if [[ "$SKIP_CADENCE_CHECK" -ne 1 ]]; then
  CADENCE_CMD=(
    python3 "$WORKSPACE/scripts/notes/check-autonomy-audit-cadence.py"
    --file "$TARGET_FILE"
    --latest-only
    --require-current
    --reference-date "$TARGET_DATE"
    --fail-on-gap
  )

  cadence_log="$(mktemp)"
  trap 'rm -f "$finalize_log" "$cadence_log"' EXIT

  set +e
  "${CADENCE_CMD[@]}" >"$cadence_log" 2>&1
  cadence_rc=$?
  set -e

  if [[ "$VERBOSE" -eq 1 && -s "$cadence_log" ]]; then
    cat "$cadence_log" >&2
  fi

  if [[ "$cadence_rc" -eq 2 ]]; then
    if [[ "$VERBOSE" -ne 1 && -s "$cadence_log" ]]; then
      cat "$cadence_log" >&2
    fi
    if [[ "$STRICT_CADENCE" -eq 1 ]]; then
      echo "❌ Cadence guard reported missing-day gaps and --strict-cadence is enabled." >&2
      exit 2
    fi
    echo "⚠️ Cadence guard reported missing-day gaps; continuing in advisory mode." >&2
  elif [[ "$cadence_rc" -ne 0 ]]; then
    if [[ "$VERBOSE" -ne 1 && -s "$cadence_log" ]]; then
      cat "$cadence_log" >&2
    fi
    echo "❌ Cadence guard failed during close-out (exit $cadence_rc)." >&2
    exit "$cadence_rc"
  fi
fi

if [[ "$finalize_rc" -eq 3 ]]; then
  echo "NO_REPLY"
  exit 0
fi

python3 "$WORKSPACE/scripts/notes/render-autonomy-audit-response.py" \
  --file "$TARGET_FILE" \
  --date "$TARGET_DATE"
