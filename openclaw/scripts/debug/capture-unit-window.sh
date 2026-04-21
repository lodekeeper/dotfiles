#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  capture-unit-window.sh UNIT [options]

Capture a small systemd evidence bundle around a known restart time.

Options:
  --at <timestamp>      Anchor timestamp (recommended), e.g. "2026-03-03 16:31:00 UTC"
                        Include timezone explicitly to avoid ambiguity.
  --before <seconds>    Seconds before --at to include (default: 120)
  --after <seconds>     Seconds after --at to include (default: 180)
  --since <timestamp>   Explicit start time (alternative to --at)
  --until <timestamp>   Explicit end time (alternative to --at)
  --wrapper <path>      Optional wrapper script path to append verbatim
  --out <path>          Explicit output file path
  --out-dir <path>      Output directory when --out is omitted (default: notes/restart-evidence)
  -h, --help            Show help

Examples:
  capture-unit-window.sh beacon.service \
    --at "2026-03-03 16:31:00 UTC" \
    --before 90 \
    --after 180 \
    --wrapper /home/devops/beacon/beacon_run.sh

  capture-unit-window.sh beacon.service \
    --since "2026-03-03 16:30:30 UTC" \
    --until "2026-03-03 16:32:30 UTC"
EOF
}

if [[ $# -eq 0 ]]; then
  usage >&2
  exit 1
fi

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$1" == -* ]]; then
  echo "error: UNIT positional argument is required before options" >&2
  usage >&2
  exit 1
fi

UNIT="$1"
shift

AT_RAW=""
SINCE_RAW=""
UNTIL_RAW=""
BEFORE_SEC=120
AFTER_SEC=180
WRAPPER_PATH=""
OUT_PATH=""
OUT_DIR="notes/restart-evidence"

require_value() {
  local flag="$1"
  local count="$2"
  if (( count < 2 )); then
    echo "error: ${flag} requires a value" >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --at)
      require_value "$1" $#
      AT_RAW="$2"
      shift 2
      ;;
    --before)
      require_value "$1" $#
      BEFORE_SEC="$2"
      shift 2
      ;;
    --after)
      require_value "$1" $#
      AFTER_SEC="$2"
      shift 2
      ;;
    --since)
      require_value "$1" $#
      SINCE_RAW="$2"
      shift 2
      ;;
    --until)
      require_value "$1" $#
      UNTIL_RAW="$2"
      shift 2
      ;;
    --wrapper)
      require_value "$1" $#
      WRAPPER_PATH="$2"
      shift 2
      ;;
    --out)
      require_value "$1" $#
      OUT_PATH="$2"
      shift 2
      ;;
    --out-dir)
      require_value "$1" $#
      OUT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument '$1'" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! [[ "$BEFORE_SEC" =~ ^[0-9]+$ ]]; then
  echo "error: --before must be an integer number of seconds" >&2
  exit 1
fi
if ! [[ "$AFTER_SEC" =~ ^[0-9]+$ ]]; then
  echo "error: --after must be an integer number of seconds" >&2
  exit 1
fi

parse_utc_epoch() {
  local raw="$1"
  date -u -d "$raw" +%s
}

format_utc_from_epoch() {
  local epoch="$1"
  date -u -d "@${epoch}" '+%Y-%m-%d %H:%M:%S UTC'
}

format_utc_from_raw() {
  local raw="$1"
  date -u -d "$raw" '+%Y-%m-%d %H:%M:%S UTC'
}

if [[ -n "$AT_RAW" ]]; then
  if [[ -n "$SINCE_RAW" || -n "$UNTIL_RAW" ]]; then
    echo "error: use either --at or --since/--until, not both" >&2
    exit 1
  fi
  ANCHOR_EPOCH="$(parse_utc_epoch "$AT_RAW")"
  ANCHOR_UTC="$(format_utc_from_epoch "$ANCHOR_EPOCH")"
  SINCE_UTC="$(format_utc_from_epoch "$((ANCHOR_EPOCH - BEFORE_SEC))")"
  UNTIL_UTC="$(format_utc_from_epoch "$((ANCHOR_EPOCH + AFTER_SEC))")"
else
  if [[ -z "$SINCE_RAW" || -z "$UNTIL_RAW" ]]; then
    echo "error: provide either --at or both --since and --until" >&2
    exit 1
  fi
  SINCE_EPOCH="$(parse_utc_epoch "$SINCE_RAW")"
  UNTIL_EPOCH="$(parse_utc_epoch "$UNTIL_RAW")"
  if (( UNTIL_EPOCH < SINCE_EPOCH )); then
    echo "error: --until must be >= --since" >&2
    exit 1
  fi
  ANCHOR_EPOCH="$SINCE_EPOCH"
  ANCHOR_UTC="$(format_utc_from_epoch "$ANCHOR_EPOCH")"
  SINCE_UTC="$(format_utc_from_raw "$SINCE_RAW")"
  UNTIL_UTC="$(format_utc_from_raw "$UNTIL_RAW")"
fi

slugify() {
  printf '%s' "$1" | sed -E 's/[^A-Za-z0-9._-]+/_/g'
}

UNIT_SLUG="$(slugify "$UNIT")"
ANCHOR_SLUG="$(date -u -d "@${ANCHOR_EPOCH}" +%Y%m%dT%H%M%SZ)"

if [[ -z "$OUT_PATH" ]]; then
  OUT_PATH="${OUT_DIR}/${UNIT_SLUG}.${ANCHOR_SLUG}.bundle.txt"
  if [[ -e "$OUT_PATH" ]]; then
    OUT_PATH="${OUT_DIR}/${UNIT_SLUG}.${ANCHOR_SLUG}.capture-$(date -u +%Y%m%dT%H%M%SZ).bundle.txt"
  fi
fi

mkdir -p "$(dirname "$OUT_PATH")"

section() {
  printf '\n===== %s =====\n' "$1" >>"$OUT_PATH"
}

print_quoted_command() {
  local first=1
  printf '$' >>"$OUT_PATH"
  for arg in "$@"; do
    if (( first )); then
      printf ' %q' "$arg" >>"$OUT_PATH"
      first=0
    else
      printf ' %q' "$arg" >>"$OUT_PATH"
    fi
  done
  printf '\n' >>"$OUT_PATH"
}

capture_exec() {
  local title="$1"
  shift
  section "$title"
  print_quoted_command "$@"
  if "$@" >>"$OUT_PATH" 2>&1; then
    printf '\n[exit 0]\n' >>"$OUT_PATH"
  else
    local status=$?
    printf '\n[exit %s]\n' "$status" >>"$OUT_PATH"
  fi
}

capture_shell() {
  local title="$1"
  local script="$2"
  shift 2
  section "$title"
  print_quoted_command bash -c "$script" _ "$@"
  if bash -c "$script" _ "$@" >>"$OUT_PATH" 2>&1; then
    printf '\n[exit 0]\n' >>"$OUT_PATH"
  else
    local status=$?
    printf '\n[exit %s]\n' "$status" >>"$OUT_PATH"
  fi
}

capture_note() {
  local title="$1"
  local body="$2"
  section "$title"
  printf '%s\n' "$body" >>"$OUT_PATH"
}

CURRENT_UTC="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
cat >"$OUT_PATH" <<EOF
# systemd restart evidence bundle

captured_at_utc: ${CURRENT_UTC}
unit: ${UNIT}
anchor_utc: ${ANCHOR_UTC}
since_utc: ${SINCE_UTC}
until_utc: ${UNTIL_UTC}
wrapper_path: ${WRAPPER_PATH:-<none>}

notes:
- All timestamps in this bundle are normalized to UTC.
- journalctl sections are historical window captures.
- status/ps sections are live snapshots taken at capture time, not historical state.
EOF

capture_exec \
  "systemctl cat" \
  systemctl cat "$UNIT" --no-pager

capture_exec \
  "systemctl show (restart policy + PIDs)" \
  systemctl show "$UNIT" --property=Id,Names,LoadState,ActiveState,SubState,FragmentPath,DropInPaths,ExecStart,ExecStartPre,ExecStartPost,Restart,RestartUSec,NRestarts,Result,ExecMainPID,MainPID,InvocationID --no-pager

capture_exec \
  "unit journal window" \
  journalctl --utc -u "$UNIT" --since "$SINCE_UTC" --until "$UNTIL_UTC" -o short-precise --no-pager

capture_exec \
  "systemd manager lines in same window (raw PID 1 output)" \
  journalctl --utc --since "$SINCE_UTC" --until "$UNTIL_UTC" _PID=1 -o short-precise --no-pager

capture_exec \
  "systemctl status (live snapshot)" \
  systemctl status "$UNIT" --no-pager --full

EXEC_MAIN_PID="$(systemctl show "$UNIT" --value --property=ExecMainPID 2>/dev/null || true)"
MAIN_PID="$(systemctl show "$UNIT" --value --property=MainPID 2>/dev/null || true)"

if [[ -n "$EXEC_MAIN_PID" && "$EXEC_MAIN_PID" != "0" ]]; then
  capture_exec \
    "ps snapshot for ExecMainPID=${EXEC_MAIN_PID}" \
    ps -o pid,ppid,lstart,etimes,cmd -p "$EXEC_MAIN_PID"
elif [[ -n "$MAIN_PID" && "$MAIN_PID" != "0" ]]; then
  capture_exec \
    "ps snapshot for MainPID=${MAIN_PID}" \
    ps -o pid,ppid,lstart,etimes,cmd -p "$MAIN_PID"
else
  capture_note "ps snapshot" "No live ExecMainPID/MainPID was available at capture time."
fi

if [[ -n "$WRAPPER_PATH" ]]; then
  if [[ -r "$WRAPPER_PATH" ]]; then
    capture_exec \
      "wrapper source" \
      cat "$WRAPPER_PATH"

    WRAPPER_BASENAME="$(basename "$WRAPPER_PATH")"
    capture_shell \
      "live process lines mentioning wrapper basename (${WRAPPER_BASENAME})" \
      'ps -eo pid,ppid,lstart,etimes,cmd | grep -F -- "$1" || true' \
      "$WRAPPER_BASENAME"
  else
    capture_note "wrapper source" "Wrapper path was provided but is not readable: $WRAPPER_PATH"
  fi
fi

printf '%s\n' "$OUT_PATH"
