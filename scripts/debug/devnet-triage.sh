#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  devnet-triage.sh <node-name> [options]

Options:
  --port <n>           TCP port to check for listeners (repeatable).
                       Defaults: 9000, 9596, 5052
  --window <dur>       Lookback window for logs/metrics (default: 30m)
                       Supports: <n>s, <n>m, <n>h, <n>d
  --errors <n>         Max recent error log lines to print (default: 10)
  --selector <expr>    PromQL label selector (default: instance=~".*<node>.*")
  --loki-query <expr>  Override LogQL query for error snapshot
  --output <path>      Write markdown report to file
  -h, --help           Show help

Env:
  GRAFANA_URL          Grafana base URL (default: https://grafana-lodestar.chainsafe.io)
  GRAFANA_TOKEN        Grafana bearer token (required for Loki/Prometheus sections)
  PROM_DS_ID           Prometheus datasource id in Grafana (default: 1)
  LOKI_DS_ID           Loki datasource id in Grafana (default: 4)

Examples:
  devnet-triage.sh epbs-devnet-0
  devnet-triage.sh lodestar-b2 --port 9000 --port 9596 --window 1h
  devnet-triage.sh teku-node --selector 'group="epbs-devnet-0"'
EOF
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

NODE_NAME=""
WINDOW="30m"
ERROR_LIMIT=10
OUTPUT=""
PORTS=(9000 9596 5052)
SELECTOR=""
USER_LOKI_QUERY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORTS+=("${2:-}")
      shift 2
      ;;
    --window)
      WINDOW="${2:-}"
      shift 2
      ;;
    --errors)
      ERROR_LIMIT="${2:-}"
      shift 2
      ;;
    --selector)
      SELECTOR="${2:-}"
      shift 2
      ;;
    --loki-query)
      USER_LOKI_QUERY="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -z "$NODE_NAME" ]]; then
        NODE_NAME="$1"
      else
        echo "error: unexpected argument: $1" >&2
        usage
        exit 1
      fi
      shift
      ;;
  esac
done

if [[ -z "$NODE_NAME" ]]; then
  echo "error: missing <node-name>" >&2
  usage
  exit 1
fi

if ! [[ "$ERROR_LIMIT" =~ ^[0-9]+$ ]]; then
  echo "error: --errors must be an integer" >&2
  exit 1
fi

parse_window_seconds() {
  local raw="$1"
  if [[ "$raw" =~ ^([0-9]+)([smhd])$ ]]; then
    local n="${BASH_REMATCH[1]}"
    local u="${BASH_REMATCH[2]}"
    case "$u" in
      s) echo "$n" ;;
      m) echo $((n * 60)) ;;
      h) echo $((n * 3600)) ;;
      d) echo $((n * 86400)) ;;
    esac
    return 0
  fi
  return 1
}

if ! WINDOW_S="$(parse_window_seconds "$WINDOW")"; then
  echo "error: invalid --window '$WINDOW' (use e.g. 30m, 1h)" >&2
  exit 1
fi

GRAFANA_URL="${GRAFANA_URL:-https://grafana-lodestar.chainsafe.io}"
PROM_DS_ID="${PROM_DS_ID:-1}"
LOKI_DS_ID="${LOKI_DS_ID:-4}"

regex_escape() {
  printf '%s' "$1" | sed -E 's/[][(){}.^$*+?|\\]/\\\\&/g'
}

NODE_REGEX="$(regex_escape "$NODE_NAME")"
if [[ -z "$SELECTOR" ]]; then
  SELECTOR="instance=~\".*${NODE_REGEX}.*\""
fi

if [[ -n "$USER_LOKI_QUERY" ]]; then
  LOKI_QUERY="$USER_LOKI_QUERY"
else
  LOKI_QUERY="{instance=~\".*${NODE_REGEX}.*\"} |~ \"(?i)(error|fatal|panic|exception)\""
fi

RESTART_QUERY="{instance=~\".*${NODE_REGEX}.*\"} |~ \"(?i)(starting|started|boot|initializ|listening on)\""

NOW_S="$(date +%s)"
START_S=$((NOW_S - WINDOW_S))
START_NS="${START_S}000000000"
END_NS="${NOW_S}000000000"

have_jq=true
have_lsof=true
command -v jq >/dev/null 2>&1 || have_jq=false
command -v lsof >/dev/null 2>&1 || have_lsof=false

prom_query_first_value() {
  local query="$1"
  [[ -n "${GRAFANA_TOKEN:-}" ]] || return 1
  [[ "$have_jq" == true ]] || return 1

  local resp
  if ! resp="$(curl -fsS -G \
    "${GRAFANA_URL}/api/datasources/proxy/${PROM_DS_ID}/api/v1/query" \
    -H "Authorization: Bearer ${GRAFANA_TOKEN}" \
    --data-urlencode "query=${query}" 2>/dev/null)"; then
    return 1
  fi

  printf '%s' "$resp" | jq -r '.data.result[0].value[1] // empty'
}

prom_query_first_nonempty() {
  local q
  for q in "$@"; do
    local v
    if v="$(prom_query_first_value "$q")" && [[ -n "$v" ]]; then
      printf '%s\t%s\n' "$v" "$q"
      return 0
    fi
  done
  return 1
}

loki_query_lines() {
  local query="$1"
  local limit="$2"
  [[ -n "${GRAFANA_TOKEN:-}" ]] || return 1
  [[ "$have_jq" == true ]] || return 1

  local resp
  if ! resp="$(curl -fsS -G \
    "${GRAFANA_URL}/api/datasources/proxy/${LOKI_DS_ID}/loki/api/v1/query_range" \
    -H "Authorization: Bearer ${GRAFANA_TOKEN}" \
    --data-urlencode "query=${query}" \
    --data-urlencode "start=${START_NS}" \
    --data-urlencode "end=${END_NS}" \
    --data-urlencode "limit=${limit}" \
    --data-urlencode "direction=BACKWARD" 2>/dev/null)"; then
    return 1
  fi

  printf '%s' "$resp" | jq -r '.data.result[]?.values[]?[1]' | sed '/^$/d' | head -n "$limit"
}

render_report() {
  cat <<EOF
# Devnet Triage Report

- Node: ${NODE_NAME}
- Generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')
- Window: ${WINDOW} (from $(date -u -d "@${START_S}" '+%Y-%m-%d %H:%M:%S UTC') to $(date -u -d "@${NOW_S}" '+%Y-%m-%d %H:%M:%S UTC'))
- Selector: ${SELECTOR}

## 1) Process + uptime
EOF

  local pids=""
  local matches=()
  mapfile -t matches < <(pgrep -fa "$NODE_NAME" 2>/dev/null || true)

  local line pid cmd
  for line in "${matches[@]}"; do
    pid="${line%% *}"
    cmd="${line#* }"

    [[ -n "$pid" ]] || continue
    [[ "$pid" == "$$" || "$pid" == "$PPID" ]] && continue
    [[ "$cmd" == *"devnet-triage.sh"* ]] && continue
    [[ "$cmd" == *"pgrep -fa"* ]] && continue

    pids+="$pid"$'\n'
  done

  pids="$(printf '%s' "$pids" | sed '/^$/d' || true)"
  if [[ -z "$pids" ]]; then
    echo "- No local process matched: \`$NODE_NAME\`"
  else
    echo "- Matching process count: $(printf '%s\n' "$pids" | sed '/^$/d' | wc -l | tr -d ' ')"
    while read -r pid; do
      [[ -n "$pid" ]] || continue
      if ps -p "$pid" >/dev/null 2>&1; then
        ps -p "$pid" -o pid=,lstart=,etime=,cmd= 2>/dev/null | sed 's/^/- /' || true
      else
        echo "- PID $pid exited before inspection"
      fi
    done <<<"$pids"
  fi

  cat <<'EOF'

## 2) Port listener check (zombie/process conflicts)
EOF

  if [[ "$have_lsof" != true ]]; then
    echo "- lsof not installed; skipping port listener check"
  else
    # de-dupe ports while preserving order
    declare -A seen_port=()
    local ordered_ports=()
    local p
    for p in "${PORTS[@]}"; do
      [[ "$p" =~ ^[0-9]+$ ]] || continue
      if [[ -z "${seen_port[$p]:-}" ]]; then
        seen_port[$p]=1
        ordered_ports+=("$p")
      fi
    done

    for p in "${ordered_ports[@]}"; do
      local rows
      rows="$(lsof -nP -iTCP:"$p" -sTCP:LISTEN 2>/dev/null || true)"
      if [[ -z "$rows" ]]; then
        echo "- Port $p: free"
      else
        echo "- Port $p: LISTEN in use"
        echo "$rows" | sed 's/^/  /'
      fi
    done
  fi

  cat <<'EOF'

## 3) Recent error logs (Loki)
EOF

  if [[ -z "${GRAFANA_TOKEN:-}" ]]; then
    echo "- GRAFANA_TOKEN not set; skipping Loki query"
  elif [[ "$have_jq" != true ]]; then
    echo "- jq not installed; skipping Loki query"
  else
    local err_lines
    err_lines="$(loki_query_lines "$LOKI_QUERY" "$ERROR_LIMIT" || true)"
    if [[ -z "$err_lines" ]]; then
      echo "- No matching error lines in last ${WINDOW} (or no matching streams)."
    else
      local idx=0
      while IFS= read -r line; do
        idx=$((idx + 1))
        printf -- '- [%02d] %s\n' "$idx" "$line"
      done <<<"$err_lines"
    fi
  fi

  cat <<'EOF'

## 4) Peer/attestation health snapshot (Prometheus via Grafana)
EOF

  if [[ -z "${GRAFANA_TOKEN:-}" ]]; then
    echo "- GRAFANA_TOKEN not set; skipping Prometheus metrics"
  elif [[ "$have_jq" != true ]]; then
    echo "- jq not installed; skipping Prometheus metrics"
  else
    local peer_data att_data peer_val peer_q att_val att_q

    peer_data="$(prom_query_first_nonempty \
      "max(lodestar_peer_count{${SELECTOR}})" \
      "max(libp2p_peers{${SELECTOR}})" \
      "max_over_time(lodestar_peer_count{${SELECTOR}}[${WINDOW}])" \
      || true)"

    if [[ -n "$peer_data" ]]; then
      peer_val="${peer_data%%$'\t'*}"
      peer_q="${peer_data#*$'\t'}"
      echo "- Peer count snapshot: ${peer_val}"
      echo "  - query: \`${peer_q}\`"
    else
      echo "- Peer count: no matching metric result"
    fi

    att_data="$(prom_query_first_nonempty \
      "avg_over_time(lodestar_validator_monitor_prev_epoch_on_chain_attester_hit_rate{${SELECTOR}}[${WINDOW}])" \
      "avg_over_time(lodestar_validator_prev_epoch_on_chain_attester_hit_rate{${SELECTOR}}[${WINDOW}])" \
      "avg_over_time(lodestar_attestation_effectiveness{${SELECTOR}}[${WINDOW}])" \
      || true)"

    if [[ -n "$att_data" ]]; then
      att_val="${att_data%%$'\t'*}"
      att_q="${att_data#*$'\t'}"
      echo "- Attestation effectiveness (avg over ${WINDOW}): ${att_val}"
      echo "  - query: \`${att_q}\`"
    else
      echo "- Attestation effectiveness: no matching metric result"
    fi
  fi

  cat <<'EOF'

## 5) Restart hints (from logs)
EOF

  if [[ -z "${GRAFANA_TOKEN:-}" ]]; then
    echo "- GRAFANA_TOKEN not set; skipping restart hint query"
  elif [[ "$have_jq" != true ]]; then
    echo "- jq not installed; skipping restart hint query"
  else
    local restart_lines restart_count
    restart_lines="$(loki_query_lines "$RESTART_QUERY" 200 || true)"
    restart_count=0
    if [[ -n "$restart_lines" ]]; then
      restart_count="$(printf '%s\n' "$restart_lines" | sed '/^$/d' | wc -l | tr -d ' ')"
    fi
    echo "- Restart/startup markers in last ${WINDOW}: ${restart_count}"
    if [[ -n "$restart_lines" ]]; then
      echo "- Latest markers:"
      printf '%s\n' "$restart_lines" | head -n 5 | sed 's/^/  - /'
    fi
  fi

  cat <<'EOF'

## Triage summary
EOF

  local busy_ports
  busy_ports=""
  if [[ "$have_lsof" == true ]]; then
    local p
    for p in "${PORTS[@]}"; do
      [[ "$p" =~ ^[0-9]+$ ]] || continue
      if lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
        busy_ports+=" $p"
      fi
    done
  fi

  if [[ -n "$busy_ports" ]]; then
    echo "- Port conflicts/listeners detected on:${busy_ports}"
  else
    echo "- No listener conflicts detected on requested ports"
  fi
  echo "- If logs/metrics are empty, refine --selector or override --loki-query"
}

if [[ -n "$OUTPUT" ]]; then
  mkdir -p "$(dirname "$OUTPUT")"
  render_report >"$OUTPUT"
  echo "Wrote triage report: $OUTPUT"
else
  render_report
fi
