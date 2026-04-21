#!/bin/bash
# Detects orphan `python3 -` / `python3 -c` processes owned by openclaw that run
# beyond a normal Claude-session tool call (>2 min) and captures root-cause
# evidence (cmdline, env, cwd, parent chain, fds, stack) the first time each
# PID is seen. Kills at hard ceiling to protect the CPU from thermal damage.
set -euo pipefail

LOG_DIR="${LOG_DIR:-/home/openclaw/.openclaw/logs}"
LOG_FILE="$LOG_DIR/python3-leak.log"
STATE_FILE="$LOG_DIR/python3-leak.state"
LOG_THRESHOLD_SEC="${LOG_THRESHOLD_SEC:-120}"      # >2m → collect evidence
KILL_THRESHOLD_SEC="${KILL_THRESHOLD_SEC:-1800}"   # >30m → kill
mkdir -p "$LOG_DIR"
touch "$STATE_FILE"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

log() {
  # newline-safe append
  printf '%s\n' "$1" >> "$LOG_FILE"
}

was_logged() {
  # state line: <pid>:<starttime-from-/proc/pid/stat>
  local pid=$1 starttime=$2
  grep -qxF "$pid:$starttime" "$STATE_FILE"
}

mark_logged() {
  local pid=$1 starttime=$2
  printf '%s:%s\n' "$pid" "$starttime" >> "$STATE_FILE"
}

capture_evidence() {
  local pid=$1
  local header="===== [$(ts)] python3 leak candidate pid=$pid ====="
  log "$header"

  # stat fields: pid (comm) state ppid ...
  local stat_line comm state ppid starttime utime stime
  if stat_line=$(cat "/proc/$pid/stat" 2>/dev/null); then
    # drop the (comm) field which may contain spaces
    comm=$(sed -E 's/^[^(]*\(([^)]*)\).*/\1/' <<<"$stat_line")
    rest=$(sed -E 's/^[^)]*\) //' <<<"$stat_line")
    read -r state ppid _ <<<"$rest"
    log "comm=$comm state=$state ppid=$ppid"
  else
    log "(could not read /proc/$pid/stat — process gone?)"
    return
  fi

  log "cmdline: $(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null)"
  log "cwd: $(readlink "/proc/$pid/cwd" 2>/dev/null || echo '?')"
  log "exe: $(readlink "/proc/$pid/exe" 2>/dev/null || echo '?')"
  log "wchan: $(cat "/proc/$pid/wchan" 2>/dev/null || echo '?')"

  log "--- parent chain ---"
  local cur=$pid
  while [ "$cur" -gt 1 ] 2>/dev/null; do
    local line
    line=$(ps -o pid,ppid,user,etime,comm,cmd -p "$cur" 2>/dev/null | tail -n +2)
    [ -z "$line" ] && break
    log "  $line"
    cur=$(awk '{print $2}' <<<"$line")
  done

  log "--- open fds (first 20) ---"
  ls -l "/proc/$pid/fd" 2>/dev/null | head -20 | while read -r l; do log "  $l"; done

  log "--- environ (CLAUDE_*, OPENCLAW_*, PATH) ---"
  tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null \
    | grep -E '^(CLAUDE_|OPENCLAW_|SKILL_|PATH=|PWD=|HOME=)' \
    | while read -r l; do log "  $l"; done

  log "--- stack (if readable) ---"
  head -40 "/proc/$pid/stack" 2>/dev/null | while read -r l; do log "  $l"; done || log "  (permission denied)"

  log ""
}

# Main sweep
now=$(date +%s)
# match literal `python3 -` or `python3 -c ...` commands
# also catch python3 with just `-` as first arg (stdin script)
# use pgrep with full command line
mapfile -t pids < <(pgrep -U openclaw -f '^python3 (-$|-c |-u - |-u -$| -$)')
# fallback — include bare `python3 -` that pgrep above might miss on some syntax
while IFS= read -r extra; do
  pids+=("$extra")
done < <(pgrep -U openclaw -f 'python3 -' || true)

# dedupe
pids=($(printf '%s\n' "${pids[@]}" | awk 'NF' | sort -u))

for pid in "${pids[@]}"; do
  [ -d "/proc/$pid" ] || continue
  # skip self + descendants (defensive)
  [ "$pid" -eq $$ ] && continue

  # verify it really is an orphan `python3 -` style process
  cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null)
  case "$cmd" in
    "python3 - "*|"python3 -"|"python3 -c "*|"python3 -u - "*|"python3 -u -"*) ;;
    *) continue ;;
  esac

  # runtime in seconds
  lstart=$(stat -c %Y "/proc/$pid" 2>/dev/null || echo "$now")
  runtime=$((now - lstart))

  [ "$runtime" -lt "$LOG_THRESHOLD_SEC" ] && continue

  # per-pid stable key (pid may be reused across boots; include starttime)
  starttime=$(awk '{print $22}' "/proc/$pid/stat" 2>/dev/null || echo "0")

  if ! was_logged "$pid" "$starttime"; then
    capture_evidence "$pid"
    mark_logged "$pid" "$starttime"
  fi

  if [ "$runtime" -ge "$KILL_THRESHOLD_SEC" ]; then
    log "[$(ts)] KILLING pid=$pid (runtime ${runtime}s exceeds ${KILL_THRESHOLD_SEC}s)"
    kill "$pid" 2>/dev/null || true
    sleep 2
    if [ -d "/proc/$pid" ]; then
      log "[$(ts)] KILL -9 pid=$pid (SIGTERM ignored)"
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
done

# rotate log if >5MB (keep 1 rotation)
if [ -f "$LOG_FILE" ] && [ "$(stat -c %s "$LOG_FILE")" -gt 5242880 ]; then
  mv "$LOG_FILE" "$LOG_FILE.1"
fi

# trim state file: keep last 100 entries
if [ "$(wc -l < "$STATE_FILE")" -gt 100 ]; then
  tail -50 "$STATE_FILE" > "$STATE_FILE.new" && mv "$STATE_FILE.new" "$STATE_FILE"
fi
