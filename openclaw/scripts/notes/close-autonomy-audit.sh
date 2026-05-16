#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"
FILE="notes/autonomy-gaps.md"
DATE=""
VERBOSE=0
STRICT_CADENCE=0
SKIP_CADENCE_CHECK=0
ALLOW_LIVE_PRIORITIES_NO_REPLY=0
SKIP_MEMORY_OUTCOME_CHECK=0
MEMORY_OUTCOME=""

usage() {
  cat <<'EOF'
Usage: close-autonomy-audit.sh [options]

Runs daily autonomy-audit close-out in one command:
1) finalize snapshot + consistency/delta guards
2) render cron-ready response text

Options:
  --file <path>         Target markdown file (default: notes/autonomy-gaps.md)
  --date <YYYY-MM-DD>   Snapshot date (default: current UTC date)
  --update-memory-outcome <text>
                        Replace the "_fill in after close-out_." placeholder in
                        memory/<date>.md with <text> before the outcome guard runs.
                        Eliminates the separate manual edit step.
  --strict-cadence      Treat cadence gaps as hard failures (default: advisory warning)
  --skip-cadence-check  Skip cadence guard during close-out
  --allow-live-priorities-no-reply
                        Allow NO_REPLY even when "Next Audit Priorities" has live items
  --skip-memory-outcome-check
                        Skip guard that requires today's daily-note audit outcome to be filled
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
    --update-memory-outcome)
      MEMORY_OUTCOME="$2"
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
    --allow-live-priorities-no-reply)
      ALLOW_LIVE_PRIORITIES_NO_REPLY=1
      shift
      ;;
    --skip-memory-outcome-check)
      SKIP_MEMORY_OUTCOME_CHECK=1
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

if [[ -n "$MEMORY_OUTCOME" ]]; then
  DAILY_MEMORY_FILE="$WORKSPACE/memory/$TARGET_DATE.md"
  if [[ ! -f "$DAILY_MEMORY_FILE" ]]; then
    echo "❌ close-autonomy-audit: --update-memory-outcome set but daily memory note is missing: $DAILY_MEMORY_FILE" >&2
    exit 2
  fi
  PLACEHOLDER="- Outcome: _fill in after close-out_."
  if grep -Fq -- "$PLACEHOLDER" "$DAILY_MEMORY_FILE"; then
    TMP_MEMORY="$(mktemp --tmpdir="$(dirname "$DAILY_MEMORY_FILE")")"
    python3 - "$DAILY_MEMORY_FILE" "$TMP_MEMORY" "$MEMORY_OUTCOME" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
outcome = sys.argv[3]
placeholder = "- Outcome: _fill in after close-out_."
replacement = f"- Outcome: {outcome}"
text = source.read_text(encoding="utf-8")
count = text.count(placeholder)
text = text.replace(placeholder, replacement, 1)
target.write_text(text, encoding="utf-8")
if count > 1:
    print(
        f"⚠️ close-autonomy-audit: found {count} unresolved outcome placeholders in {source}; updated only the first one.",
        file=sys.stderr,
    )
PY
    mv "$TMP_MEMORY" "$DAILY_MEMORY_FILE"
    echo "✅ Updated memory outcome in $DAILY_MEMORY_FILE"
  else
    echo "ℹ️  --update-memory-outcome: placeholder not found in $DAILY_MEMORY_FILE; skipping update."
  fi
fi

if [[ "$SKIP_MEMORY_OUTCOME_CHECK" -ne 1 ]]; then
  DAILY_MEMORY_FILE="$WORKSPACE/memory/$TARGET_DATE.md"
  if [[ ! -f "$DAILY_MEMORY_FILE" ]]; then
    echo "❌ close-autonomy-audit: missing daily memory note $DAILY_MEMORY_FILE" >&2
    echo "   Run preflight first (or create the note), then update the audit outcome before close-out." >&2
    echo "   Override only if intentional: --skip-memory-outcome-check" >&2
    exit 2
  fi

  if grep -Fq -- "- Outcome: _fill in after close-out_." "$DAILY_MEMORY_FILE"; then
    echo "❌ close-autonomy-audit: daily audit outcome is still a placeholder in $DAILY_MEMORY_FILE" >&2
    echo "   Update the preflight audit note outcome before closing out (or use --update-memory-outcome <text>)." >&2
    exit 3
  fi
fi

if [[ "$finalize_rc" -eq 3 ]]; then
  if [[ "$ALLOW_LIVE_PRIORITIES_NO_REPLY" -ne 1 ]]; then
    NEXT_PRIORITIES_CMD=(
      python3 "$WORKSPACE/scripts/notes/check-next-audit-priorities.py"
      --file "$TARGET_FILE"
      --quiet
      --fail-if-live
    )

    set +e
    "${NEXT_PRIORITIES_CMD[@]}" >/dev/null 2>&1
    priorities_rc=$?
    set -e

    if [[ "$priorities_rc" -eq 3 ]]; then
      echo "❌ close-autonomy-audit: finalize reported NO_CHANGE, but 'Next Audit Priorities' still has live items." >&2
      echo "   Resolve/remove those items first, or rerun with --allow-live-priorities-no-reply to override." >&2
      exit 3
    elif [[ "$priorities_rc" -ne 0 ]]; then
      echo "❌ close-autonomy-audit: next-priorities check failed (exit $priorities_rc)." >&2
      exit "$priorities_rc"
    fi
  fi

  echo "NO_REPLY"
  exit 0
fi

python3 "$WORKSPACE/scripts/notes/render-autonomy-audit-response.py" \
  --file "$TARGET_FILE" \
  --date "$TARGET_DATE"
