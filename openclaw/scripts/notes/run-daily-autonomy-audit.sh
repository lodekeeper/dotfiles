#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"
FILE="notes/autonomy-gaps.md"
DATE=""
TIME_LABEL=""
STRICT_CADENCE=0
ALLOW_LIVE_PRIORITIES_NO_REPLY=0
STRICT_CI_API_KEY=0
REQUIRE_DEVNET_GRAFANA=0
SKIP_DOMAIN_PREFLIGHTS=0
SKIP_CADENCE_CHECK=0
VERBOSE=0

usage() {
  cat <<'EOF'
Usage: run-daily-autonomy-audit.sh [options]

Runs the full daily autonomy audit lifecycle:
1) run-autonomy-audit-preflight.sh with fresh domain preflights
2) close-autonomy-audit.sh with the daily memory outcome filled
3) print the cron-ready final response (summary or NO_REPLY)

Options:
  --file <path>         Target markdown file (default: notes/autonomy-gaps.md)
  --date <YYYY-MM-DD>   Snapshot date (default: current UTC date)
  --time-label <label>  Snapshot time label (default: current UTC HH:MM UTC)
  --strict-cadence      Treat cadence gaps as hard failures in preflight/close-out
  --skip-cadence-check  Skip cadence guard during close-out
  --skip-domain-preflights
                        Skip PR/CI/spec/devnet preflights before snapshot insertion
  --strict-ci-api-key   Require a real OPENAI_API_KEY in the CI-fix preflight
  --require-devnet-grafana
                        Require Grafana token/tooling in the devnet preflight
  --allow-live-priorities-no-reply
                        Allow NO_REPLY even when "Next Audit Priorities" has live items
  -v, --verbose         Print close-out guard logs to stderr
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
    --strict-cadence)
      STRICT_CADENCE=1
      shift
      ;;
    --skip-cadence-check)
      SKIP_CADENCE_CHECK=1
      shift
      ;;
    --skip-domain-preflights)
      SKIP_DOMAIN_PREFLIGHTS=1
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
    --allow-live-priorities-no-reply)
      ALLOW_LIVE_PRIORITIES_NO_REPLY=1
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

TARGET_DATE="${DATE:-$(date -u +%F)}"
TARGET_TIME_LABEL="${TIME_LABEL:-$(date -u '+%H:%M UTC')}"

PREFLIGHT_CMD=(
  bash "$WORKSPACE/scripts/notes/run-autonomy-audit-preflight.sh"
  --file "$FILE"
  --date "$TARGET_DATE"
  --time-label "$TARGET_TIME_LABEL"
  --document-domain-failures
)

if [[ "$STRICT_CADENCE" -eq 1 ]]; then
  PREFLIGHT_CMD+=(--strict-cadence)
fi
if [[ "$SKIP_DOMAIN_PREFLIGHTS" -eq 1 ]]; then
  PREFLIGHT_CMD+=(--skip-domain-preflights)
fi
if [[ "$STRICT_CI_API_KEY" -eq 1 ]]; then
  PREFLIGHT_CMD+=(--strict-ci-api-key)
fi
if [[ "$REQUIRE_DEVNET_GRAFANA" -eq 1 ]]; then
  PREFLIGHT_CMD+=(--require-devnet-grafana)
fi

"${PREFLIGHT_CMD[@]}"

CLOSE_CMD=(
  bash "$WORKSPACE/scripts/notes/close-autonomy-audit.sh"
  --file "$FILE"
  --date "$TARGET_DATE"
  --update-memory-outcome
  "Daily autonomy audit completed via scripts/notes/run-daily-autonomy-audit.sh; see notes/autonomy-gaps.md for the snapshot and stdout for the cron response."
)

if [[ "$STRICT_CADENCE" -eq 1 ]]; then
  CLOSE_CMD+=(--strict-cadence)
fi
if [[ "$SKIP_CADENCE_CHECK" -eq 1 ]]; then
  CLOSE_CMD+=(--skip-cadence-check)
fi
if [[ "$ALLOW_LIVE_PRIORITIES_NO_REPLY" -eq 1 ]]; then
  CLOSE_CMD+=(--allow-live-priorities-no-reply)
fi
if [[ "$VERBOSE" -eq 1 ]]; then
  CLOSE_CMD+=(--verbose)
fi

"${CLOSE_CMD[@]}"
