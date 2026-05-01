#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_BIN="${OPENCLAW_BIN:-/home/openclaw/.nvm/versions/node/v22.22.0/bin/openclaw}"
TARGET="${ROUTINE_STATUS_TARGET:--1003764039429}"
THREAD_ID="${ROUTINE_STATUS_THREAD_ID:-347}"

usage() {
  cat <<'EOF'
Usage:
  send-routine-status-topic347.sh "message text"
  printf 'message text' | send-routine-status-topic347.sh

Sends a routine Telegram status update to Lodestar WG topic #347 using the
OpenClaw CLI direct-send path (not sessions_send).
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -x "$OPENCLAW_BIN" ]]; then
  echo "openclaw binary not found or not executable: $OPENCLAW_BIN" >&2
  exit 1
fi

if [[ $# -gt 0 ]]; then
  message="$*"
else
  if [[ -t 0 ]]; then
    usage >&2
    exit 2
  fi
  message="$(cat)"
fi

if [[ -z "${message//[$'\t\r\n ']/}" ]]; then
  echo "refusing to send an empty routine status message" >&2
  exit 2
fi

exec "$OPENCLAW_BIN" message send \
  --channel telegram \
  --target "$TARGET" \
  --thread-id "$THREAD_ID" \
  --message "$message"
