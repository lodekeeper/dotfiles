#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"
FILE="notes/autonomy-gaps.md"
DATE=""
TIME_LABEL=""
FORCE=0
CARRY_FORWARD_STATUS=1
DEDUPE_APPLY=0
STRICT_CADENCE=0
RUN_DOMAIN_PREFLIGHTS=1
STRICT_CI_API_KEY=0
REQUIRE_DEVNET_GRAFANA=0
ENSURE_DAILY_MEMORY_NOTE=1
SEED_AUDIT_MEMORY_ENTRY=1

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
                        Prefill required status lines from latest snapshot (default)
  --no-carry-forward-status
                        Disable status prefill and insert blank placeholders
  --dedupe-apply        Auto-remove older duplicate snapshot blocks before preflight
  --strict-cadence      Treat cadence gaps as hard failures (default: advisory warning)
  --check-domains       Run side-effect-free PR/CI/spec/devnet domain preflights (default)
  --skip-domain-preflights
                        Skip domain preflights before snapshot insertion
  --strict-ci-api-key   Require a real OPENAI_API_KEY in the CI-fix quality-gate preflight
  --require-devnet-grafana
                        Require Grafana token/tooling in the devnet-debugging preflight
  --ensure-daily-memory-note
                        Ensure memory/<date>.md exists before snapshot insertion (default)
  --no-ensure-daily-memory-note
                        Skip creating/checking memory/<date>.md
  --seed-audit-memory-entry
                        Append a one-time daily audit log stub to memory/<date>.md (default)
  --no-seed-audit-memory-entry
                        Skip appending the daily audit log stub
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
    --no-carry-forward-status)
      CARRY_FORWARD_STATUS=0
      shift
      ;;
    --dedupe-apply)
      DEDUPE_APPLY=1
      shift
      ;;
    --strict-cadence)
      STRICT_CADENCE=1
      shift
      ;;
    --check-domains)
      RUN_DOMAIN_PREFLIGHTS=1
      shift
      ;;
    --skip-domain-preflights)
      RUN_DOMAIN_PREFLIGHTS=0
      shift
      ;;
    --strict-ci-api-key)
      STRICT_CI_API_KEY=1
      shift
      ;;
    --require-devnet-grafana)
      REQUIRE_DEVNET_GRAFANA=1
      shift
      ;;
    --ensure-daily-memory-note)
      ENSURE_DAILY_MEMORY_NOTE=1
      shift
      ;;
    --no-ensure-daily-memory-note)
      ENSURE_DAILY_MEMORY_NOTE=0
      shift
      ;;
    --seed-audit-memory-entry)
      SEED_AUDIT_MEMORY_ENTRY=1
      shift
      ;;
    --no-seed-audit-memory-entry)
      SEED_AUDIT_MEMORY_ENTRY=0
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
TARGET_TIME_LABEL="${TIME_LABEL:-$(date -u '+%H:%M UTC')}"

DEDUPE_CMD=(python3 "$WORKSPACE/scripts/notes/dedupe-autonomy-audit-snapshots.py" --file "$TARGET_FILE")
CHECK_CMD=(python3 "$WORKSPACE/scripts/notes/check-autonomy-gaps-consistency.py" --file "$TARGET_FILE")
CADENCE_CMD=(python3 "$WORKSPACE/scripts/notes/check-autonomy-audit-cadence.py" --file "$TARGET_FILE" --latest-only --require-current --fail-on-gap)
DOMAIN_PREFLIGHT_CMD=(python3 "$WORKSPACE/scripts/notes/check-autonomy-domain-preflights.py")
PREPEND_CMD=(python3 "$WORKSPACE/scripts/notes/prepend-autonomy-audit-snapshot.py" --file "$TARGET_FILE")

if [[ -n "$DATE" ]]; then
  PREPEND_CMD+=(--date "$DATE")
  CADENCE_CMD+=(--reference-date "$DATE")
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

if [[ "$DEDUPE_APPLY" -eq 1 ]]; then
  DEDUPE_CMD+=(--apply)
fi

if [[ "$STRICT_CI_API_KEY" -eq 1 ]]; then
  DOMAIN_PREFLIGHT_CMD+=(--strict-ci-api-key)
fi

if [[ "$REQUIRE_DEVNET_GRAFANA" -eq 1 ]]; then
  DOMAIN_PREFLIGHT_CMD+=(--require-devnet-grafana)
fi

echo "[0/6] Running duplicate-snapshot guard"
set +e
"${DEDUPE_CMD[@]}"
dedupe_rc=$?
set -e
if [[ "$dedupe_rc" -eq 2 ]]; then
  echo "❌ Duplicate snapshot blocks detected. Re-run preflight with --dedupe-apply (or run dedupe-autonomy-audit-snapshots.py --apply) before continuing." >&2
  exit 2
elif [[ "$dedupe_rc" -ne 0 ]]; then
  echo "❌ Duplicate-snapshot guard failed (exit $dedupe_rc). Aborting preflight." >&2
  exit "$dedupe_rc"
fi

echo "[1/6] Running consistency guard on $TARGET_FILE"
"${CHECK_CMD[@]}"

echo "[2/6] Running cadence guard (advisory, latest-pair + current-date freshness)"
set +e
"${CADENCE_CMD[@]}"
cadence_rc=$?
set -e
if [[ "$cadence_rc" -eq 2 ]]; then
  if [[ "$STRICT_CADENCE" -eq 1 ]]; then
    echo "❌ Cadence guard reported missing-day gaps and --strict-cadence is enabled. Resolve cadence drift before continuing." >&2
    exit 2
  fi
  echo "⚠️ Cadence guard reported missing-day gaps. Continue with today's snapshot, and document root cause/fix in the audit workflow section."
elif [[ "$cadence_rc" -ne 0 ]]; then
  echo "❌ Cadence guard failed (exit $cadence_rc). Aborting preflight." >&2
  exit "$cadence_rc"
fi

if [[ "$RUN_DOMAIN_PREFLIGHTS" -eq 1 ]]; then
  echo "[3/6] Running autonomy domain preflights"
  "${DOMAIN_PREFLIGHT_CMD[@]}"
else
  echo "[3/6] Skipping autonomy domain preflights (--skip-domain-preflights)"
fi

if [[ "$ENSURE_DAILY_MEMORY_NOTE" -eq 1 ]]; then
  echo "[4/6] Ensuring daily memory note + audit stub"
  DAILY_MEMORY_FILE="$WORKSPACE/memory/$TARGET_DATE.md"
  mkdir -p "$(dirname "$DAILY_MEMORY_FILE")"
  if [[ ! -f "$DAILY_MEMORY_FILE" ]]; then
    printf "# Daily Notes — %s\n\n" "$TARGET_DATE" > "$DAILY_MEMORY_FILE"
    echo "📝 Created missing daily memory note: $DAILY_MEMORY_FILE"
  else
    echo "ℹ️ Daily memory note already exists: $DAILY_MEMORY_FILE"
  fi

  if [[ "$SEED_AUDIT_MEMORY_ENTRY" -eq 1 ]]; then
    if grep -Fq "self-improvement-audit-daily (preflight)" "$DAILY_MEMORY_FILE"; then
      echo "ℹ️ Daily audit memory stub already present: $DAILY_MEMORY_FILE"
    else
      {
        printf "## %s — self-improvement-audit-daily (preflight)\n" "$TARGET_TIME_LABEL"
        printf '%s\n' "- Started daily autonomy-audit preflight for notes/autonomy-gaps.md."
        printf '%s\n' "- Snapshot date: ${TARGET_DATE}."
        printf '%s\n\n' "- Outcome: _fill in after close-out_."
      } >> "$DAILY_MEMORY_FILE"
      echo "📝 Appended daily audit memory stub: $DAILY_MEMORY_FILE"
    fi
  fi
else
  echo "[4/6] Skipping daily memory note creation (--no-ensure-daily-memory-note)"
fi

echo "[5/6] Inserting daily snapshot scaffold"
"${PREPEND_CMD[@]}"

echo "✅ Preflight complete. Review/update the new snapshot status blocks, then run scripts/notes/close-autonomy-audit.sh --date $TARGET_DATE"
echo "   (legacy two-step still works: finalize-autonomy-audit.py --fail-on-no-change + render-autonomy-audit-response.py)"
