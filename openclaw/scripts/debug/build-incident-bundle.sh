#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  build-incident-bundle.sh --node <name> [options]

Options:
  --peer <name>         Additional node to include in correlated timeline (repeatable)
  --window <dur>        Triage lookback window (default: 30m)
  --from <time>         Timeline start (default: -<window>)
  --to <time>           Timeline end (default: now)
  --title <text>        Incident title override
  --output <path>       Markdown output path
  --out-dir <path>      Output directory when --output is omitted (default: notes/incidents)
  --repo <path>         Repo path for git metadata (default: ~/lodestar)
  --errors <n>          Error lines for triage report (default: 10)
  --port <n>            Forwarded to devnet-triage.sh (repeatable)
  --selector <expr>     Forwarded PromQL selector for devnet-triage.sh
  --loki-query <expr>   Forwarded LogQL override for devnet-triage.sh
  -h, --help            Show help

Env:
  GRAFANA_URL           Grafana base URL (optional)
  GRAFANA_TOKEN         Grafana token (required for metrics/timeline sections)

Examples:
  build-incident-bundle.sh --node epbs-devnet-0 --peer lh-b2 --peer teku-b2
  build-incident-bundle.sh --node lodestar-b2 --window 1h --output notes/incidents/lh-b2-incident.md
EOF
}

NODE_NAME=""
WINDOW="30m"
FROM_RAW=""
TO_RAW="now"
TITLE=""
OUTPUT=""
OUT_DIR="notes/incidents"
REPO_PATH="${HOME}/lodestar"
ERROR_LIMIT=10
SELECTOR=""
LOKI_QUERY=""
PEERS=()
PORTS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --node)
      NODE_NAME="${2:-}"
      shift 2
      ;;
    --peer)
      PEERS+=("${2:-}")
      shift 2
      ;;
    --window)
      WINDOW="${2:-}"
      shift 2
      ;;
    --from)
      FROM_RAW="${2:-}"
      shift 2
      ;;
    --to)
      TO_RAW="${2:-}"
      shift 2
      ;;
    --title)
      TITLE="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --repo)
      REPO_PATH="${2:-}"
      shift 2
      ;;
    --errors)
      ERROR_LIMIT="${2:-}"
      shift 2
      ;;
    --port)
      PORTS+=("${2:-}")
      shift 2
      ;;
    --selector)
      SELECTOR="${2:-}"
      shift 2
      ;;
    --loki-query)
      LOKI_QUERY="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument '$1'" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$NODE_NAME" ]]; then
  echo "error: --node is required" >&2
  usage
  exit 1
fi

if ! [[ "$ERROR_LIMIT" =~ ^[0-9]+$ ]]; then
  echo "error: --errors must be an integer" >&2
  exit 1
fi

if [[ -z "$FROM_RAW" ]]; then
  FROM_RAW="-${WINDOW}"
fi

slugify() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRIAGE_SCRIPT="${SCRIPT_DIR}/devnet-triage.sh"
CORRELATE_SCRIPT="${SCRIPT_DIR}/correlate-logs.sh"

if [[ ! -f "$TRIAGE_SCRIPT" ]]; then
  echo "error: missing helper script: $TRIAGE_SCRIPT" >&2
  exit 1
fi
if [[ ! -f "$CORRELATE_SCRIPT" ]]; then
  echo "error: missing helper script: $CORRELATE_SCRIPT" >&2
  exit 1
fi

TIMESTAMP="$(date -u +%Y%m%d-%H%M%SZ)"
INCIDENT_SLUG="$(slugify "${TITLE:-$NODE_NAME}")"
if [[ -z "$INCIDENT_SLUG" ]]; then
  INCIDENT_SLUG="incident"
fi
INCIDENT_ID="incident-${INCIDENT_SLUG}-${TIMESTAMP}"

if [[ -z "$OUTPUT" ]]; then
  OUTPUT="${OUT_DIR}/${INCIDENT_ID}.md"
fi

mkdir -p "$(dirname "$OUTPUT")"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TRIAGE_MD="$TMP_DIR/triage.md"
TRIAGE_ERR="$TMP_DIR/triage.err"
TRIAGE_STATUS="ok"

triage_cmd=(bash "$TRIAGE_SCRIPT" "$NODE_NAME" --window "$WINDOW" --errors "$ERROR_LIMIT" --output "$TRIAGE_MD")
for p in "${PORTS[@]}"; do
  triage_cmd+=(--port "$p")
done
if [[ -n "$SELECTOR" ]]; then
  triage_cmd+=(--selector "$SELECTOR")
fi
if [[ -n "$LOKI_QUERY" ]]; then
  triage_cmd+=(--loki-query "$LOKI_QUERY")
fi

if ! "${triage_cmd[@]}" >/dev/null 2>"$TRIAGE_ERR"; then
  TRIAGE_STATUS="failed"
  cat >"$TRIAGE_MD" <<EOF
# Devnet Triage Report

Triage helper failed.

\`\`\`
$(cat "$TRIAGE_ERR")
\`\`\`
EOF
fi

TIMELINE_MD="$TMP_DIR/timeline.md"
TIMELINE_STATUS="skipped"
TIMELINE_REASON="Need at least two nodes (primary + one --peer)"
TIMELINE_ERR="$TMP_DIR/timeline.err"
TIMELINE_NODES=("$NODE_NAME" "${PEERS[@]}")

if (( ${#TIMELINE_NODES[@]} >= 2 )); then
  if [[ -z "${GRAFANA_TOKEN:-}" ]]; then
    TIMELINE_REASON="GRAFANA_TOKEN not set"
  else
    timeline_cmd=(bash "$CORRELATE_SCRIPT")
    for n in "${TIMELINE_NODES[@]}"; do
      timeline_cmd+=("$n")
    done
    timeline_cmd+=(--from "$FROM_RAW" --to "$TO_RAW" --output "$TIMELINE_MD")

    if "${timeline_cmd[@]}" >/dev/null 2>"$TIMELINE_ERR"; then
      TIMELINE_STATUS="ok"
      TIMELINE_REASON=""
    else
      TIMELINE_STATUS="failed"
      TIMELINE_REASON="$(cat "$TIMELINE_ERR")"
    fi
  fi
fi

if [[ -z "$TITLE" ]]; then
  TITLE="${NODE_NAME} incident"
fi

HOSTNAME_VAL="$(hostname 2>/dev/null || echo unknown)"
KERNEL_VAL="$(uname -srmo 2>/dev/null || uname -a)"
USER_VAL="$(whoami 2>/dev/null || echo unknown)"
NODE_VERSION="$(node -v 2>/dev/null || echo unavailable)"
PNPM_VERSION="$(pnpm -v 2>/dev/null || echo unavailable)"
GENERATED_AT="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"

GIT_BRANCH="n/a"
GIT_COMMIT="n/a"
GIT_STATUS="n/a"
if [[ -d "$REPO_PATH/.git" ]] || git -C "$REPO_PATH" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  GIT_BRANCH="$(git -C "$REPO_PATH" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  GIT_COMMIT="$(git -C "$REPO_PATH" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  if git -C "$REPO_PATH" diff --quiet >/dev/null 2>&1 && git -C "$REPO_PATH" diff --cached --quiet >/dev/null 2>&1; then
    GIT_STATUS="clean"
  else
    GIT_STATUS="dirty"
  fi
fi

cat >"$OUTPUT" <<EOF
# Incident Bundle: ${TITLE}

- Incident ID: \`${INCIDENT_ID}\`
- Generated: ${GENERATED_AT}
- Primary node: \`${NODE_NAME}\`
- Peer nodes: $(if ((${#PEERS[@]} == 0)); then echo "(none)"; else printf '`%s` ' "${PEERS[@]}"; fi)

## Environment metadata

- Host: \`${HOSTNAME_VAL}\`
- User: \`${USER_VAL}\`
- Kernel: \`${KERNEL_VAL}\`
- Node.js: \`${NODE_VERSION}\`
- pnpm: \`${PNPM_VERSION}\`
- Repo: \`${REPO_PATH}\`
- Repo branch/head: \`${GIT_BRANCH}\` @ \`${GIT_COMMIT}\` (${GIT_STATUS})
- Grafana URL: \`${GRAFANA_URL:-https://grafana-lodestar.chainsafe.io}\`
- Grafana token present: $(if [[ -n "${GRAFANA_TOKEN:-}" ]]; then echo "yes"; else echo "no"; fi)

## Triage snapshot (logs + metrics + process health)

_Triage status: **${TRIAGE_STATUS}**_

$(cat "$TRIAGE_MD")

## Correlated timeline

_Timeline status: **${TIMELINE_STATUS}**$(if [[ -n "$TIMELINE_REASON" ]]; then printf " — %s" "$TIMELINE_REASON"; fi)_

EOF

if [[ "$TIMELINE_STATUS" == "ok" ]]; then
  cat "$TIMELINE_MD" >>"$OUTPUT"
else
  cat >>"$OUTPUT" <<'EOF'
No cross-node timeline attached in this run.
- Add one or more `--peer` nodes for correlation.
- Ensure `GRAFANA_TOKEN` is set if timeline fetches are expected.
EOF
fi

cat >>"$OUTPUT" <<'EOF'

## Incident timeline notes

- [ ] First symptom observed (timestamp + source)
- [ ] Impact window (who/what affected)
- [ ] Candidate root cause(s)
- [ ] Confirmed root cause
- [ ] Mitigation / fix applied
- [ ] Follow-up actions (tests, alerts, docs)
EOF

echo "Wrote incident bundle: $OUTPUT"