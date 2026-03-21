#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  correlate-logs.sh <node1> <node2> [nodeN ...] [options]

Options:
  --from <time>        Start time (default: -30m)
                       Examples: "-30m", "-2h", "2026-03-09T08:00:00Z"
  --to <time>          End time (default: now)
  --query <logql>      Override LogQL selector/filter. Use {{NODE}} placeholder for node regex
                       Default: {instance=~".*{{NODE}}.*"}
  --highlight <regex>  Regex to mark consensus-relevant lines
                       Default: (?i)(fork[_ ]?choice|attestation|proposal|head[_ ]?block|finalized)
  --highlights-only    Print only highlighted lines
  --limit <n>          Max lines fetched per node (default: 5000)
  --output <path>      Write timeline to file
  -h, --help           Show help

Env:
  GRAFANA_URL          Grafana base URL (default: https://grafana-lodestar.chainsafe.io)
  GRAFANA_TOKEN        Grafana bearer token (required)
  LOKI_DS_ID           Loki datasource id in Grafana (default: 4)

Examples:
  correlate-logs.sh lodestar-a lodestar-b --from -1h
  correlate-logs.sh lh-1 lh-2 teku-1 --from "2026-03-09T08:00:00Z" --to "2026-03-09T09:00:00Z"
EOF
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

FROM_RAW="-30m"
TO_RAW="now"
QUERY_TEMPLATE='{instance=~".*{{NODE}}.*"}'
HIGHLIGHT_REGEX='(?i)(fork[_ ]?choice|attestation|proposal|head[_ ]?block|finalized)'
HIGHLIGHTS_ONLY=false
LIMIT=5000
OUTPUT=""
NODES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)
      FROM_RAW="${2:-}"
      shift 2
      ;;
    --to)
      TO_RAW="${2:-}"
      shift 2
      ;;
    --query)
      QUERY_TEMPLATE="${2:-}"
      shift 2
      ;;
    --highlight)
      HIGHLIGHT_REGEX="${2:-}"
      shift 2
      ;;
    --highlights-only)
      HIGHLIGHTS_ONLY=true
      shift
      ;;
    --limit)
      LIMIT="${2:-}"
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
    --*)
      echo "error: unknown option: $1" >&2
      usage
      exit 1
      ;;
    *)
      NODES+=("$1")
      shift
      ;;
  esac
done

if [[ ${#NODES[@]} -lt 2 ]]; then
  echo "error: provide at least 2 node names" >&2
  usage
  exit 1
fi

if ! [[ "$LIMIT" =~ ^[0-9]+$ ]]; then
  echo "error: --limit must be an integer" >&2
  exit 1
fi

if [[ -z "${GRAFANA_TOKEN:-}" ]]; then
  echo "error: GRAFANA_TOKEN is required" >&2
  exit 1
fi

command -v jq >/dev/null 2>&1 || {
  echo "error: jq is required" >&2
  exit 1
}

GRAFANA_URL="${GRAFANA_URL:-https://grafana-lodestar.chainsafe.io}"
LOKI_DS_ID="${LOKI_DS_ID:-4}"

parse_time_ns() {
  local raw="$1"
  local secs now delta n u

  if [[ "$raw" == "now" ]]; then
    date -u +%s%N
    return 0
  fi

  if [[ "$raw" =~ ^-?([0-9]+)([smhd])$ ]]; then
    n="${BASH_REMATCH[1]}"
    u="${BASH_REMATCH[2]}"
    case "$u" in
      s) delta="$n" ;;
      m) delta=$((n * 60)) ;;
      h) delta=$((n * 3600)) ;;
      d) delta=$((n * 86400)) ;;
      *) return 1 ;;
    esac
    now="$(date -u +%s)"
    secs=$((now - delta))
    printf '%s000000000' "$secs"
    return 0
  fi

  if [[ "$raw" =~ ^[0-9]+$ ]]; then
    local len=${#raw}
    if (( len >= 16 )); then
      printf '%s' "$raw"
      return 0
    fi
    printf '%s000000000' "$raw"
    return 0
  fi

  if ! secs="$(date -u -d "$raw" +%s 2>/dev/null)"; then
    return 1
  fi
  printf '%s000000000' "$secs"
}

if ! START_NS="$(parse_time_ns "$FROM_RAW")"; then
  echo "error: could not parse --from '$FROM_RAW'" >&2
  exit 1
fi

if ! END_NS="$(parse_time_ns "$TO_RAW")"; then
  echo "error: could not parse --to '$TO_RAW'" >&2
  exit 1
fi

if (( END_NS <= START_NS )); then
  echo "error: --to must be later than --from" >&2
  exit 1
fi

regex_escape() {
  printf '%s' "$1" | sed -E 's/[][(){}.^$*+?|\\]/\\\\&/g'
}

fetch_node() {
  local node="$1"
  local out="$2"
  local node_regex query resp

  node_regex="$(regex_escape "$node")"
  query="${QUERY_TEMPLATE//\{\{NODE\}\}/$node_regex}"

  if ! resp="$(curl -fsS -G \
    "${GRAFANA_URL}/api/datasources/proxy/${LOKI_DS_ID}/loki/api/v1/query_range" \
    -H "Authorization: Bearer ${GRAFANA_TOKEN}" \
    --data-urlencode "query=${query}" \
    --data-urlencode "start=${START_NS}" \
    --data-urlencode "end=${END_NS}" \
    --data-urlencode "limit=${LIMIT}" \
    --data-urlencode "direction=FORWARD" 2>/dev/null)"; then
    echo "warn: failed Loki query for node '$node'" >&2
    : >"$out"
    return 0
  fi

  printf '%s' "$resp" \
    | jq -r --arg node "$node" '.data.result[]?.values[]? | [.[0], $node, .[1]] | @tsv' \
    >"$out" || true
}

format_iso_utc() {
  local ns="$1"
  local sec nano
  sec=$((ns / 1000000000))
  nano=$((ns % 1000000000))
  printf '%s.%09dZ' "$(date -u -d "@$sec" '+%Y-%m-%dT%H:%M:%S')" "$nano"
}

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

for node in "${NODES[@]}"; do
  fetch_node "$node" "$TMP_DIR/${node}.tsv" &
done
wait

MERGED_TSV="$TMP_DIR/merged.tsv"
cat "$TMP_DIR"/*.tsv 2>/dev/null | sed '/^$/d' | sort -t $'\t' -k1,1n >"$MERGED_TSV" || true

render() {
  cat <<EOF
# Multi-node log correlation timeline

- Nodes: ${NODES[*]}
- Range: $(format_iso_utc "$START_NS") → $(format_iso_utc "$END_NS")
- Query template: ${QUERY_TEMPLATE}
- Highlight regex: ${HIGHLIGHT_REGEX}
- Generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')

Legend: ★ highlighted consensus-relevant line, · regular line

EOF

  if [[ ! -s "$MERGED_TSV" ]]; then
    echo "(no log lines returned for the selected nodes/time range)"
    return 0
  fi

  local total=0 shown=0 highlighted=0
  local ts node line mark iso

  while IFS=$'\t' read -r ts node line; do
    [[ -n "$ts" ]] || continue
    total=$((total + 1))
    mark="·"
    if printf '%s\n' "$line" | grep -Eiq "$HIGHLIGHT_REGEX"; then
      mark="★"
      highlighted=$((highlighted + 1))
    elif [[ "$HIGHLIGHTS_ONLY" == true ]]; then
      continue
    fi

    shown=$((shown + 1))
    iso="$(format_iso_utc "$ts")"
    printf '%s %s [%s] %s\n' "$mark" "$iso" "$node" "$line"
  done <"$MERGED_TSV"

  cat <<EOF

---
Summary: total=${total}, highlighted=${highlighted}, shown=${shown}
EOF
}

if [[ -n "$OUTPUT" ]]; then
  mkdir -p "$(dirname "$OUTPUT")"
  render >"$OUTPUT"
  echo "Wrote correlated timeline: $OUTPUT"
else
  render
fi
