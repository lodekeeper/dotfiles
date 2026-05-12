#!/usr/bin/env bash
set -euo pipefail

# Nudge a topic session (or any sessionKey-routed session) via the openclaw
# Gateway. Replaces the deprecated `sessions_send` tool, which isn't exposed
# in claude-cli cron contexts (see ~/.openclaw/openclaw.json: cliBackends).
#
# Usage:
#   nudge-topic-session.sh <sessionKey> "<message>"
#   printf "<message>" | nudge-topic-session.sh <sessionKey>
#
# Example:
#   nudge-topic-session.sh \
#     "agent:main:telegram:group:-1003764039429:topic:50" \
#     "Investigate failing CI on PR #1234, see ..."
#
# Notes:
# - This uses the Gateway `sessions.send` method directly.
# - We intentionally do NOT hop through `openclaw agent --session-id`; that path
#   was verified on 2026-05-11 to fall back into `agent:main:main` instead of
#   waking the target topic session.

OPENCLAW_BIN="${OPENCLAW_BIN:-/home/openclaw/.nvm/versions/node/v22.22.0/bin/openclaw}"
TIMEOUT="${OPENCLAW_AGENT_TIMEOUT:-1200}"
GATEWAY_TIMEOUT_MS="${OPENCLAW_GATEWAY_TIMEOUT_MS:-30000}"

usage() {
  cat <<'EOF'
Usage:
  nudge-topic-session.sh <sessionKey> "<message>"
  printf "<message>" | nudge-topic-session.sh <sessionKey>

Checks that the sessionKey exists via `openclaw gateway call sessions.resolve`,
then nudges it via `openclaw gateway call sessions.send` so the target session
actually wakes and processes the message.

Exit codes:
  0  - sent successfully
  2  - bad invocation
  3  - sessionKey not found in the session store
  4  - sessions.send gateway call failed
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 2
fi

SESSION_KEY="$1"
shift

if [[ $# -gt 0 ]]; then
  MESSAGE="$*"
else
  if [[ -t 0 ]]; then
    usage >&2
    exit 2
  fi
  MESSAGE="$(cat)"
fi

if [[ -z "${MESSAGE//[$'\t\r\n ']/}" ]]; then
  echo "nudge-topic-session: refusing to send an empty message" >&2
  exit 2
fi

if [[ ! -x "$OPENCLAW_BIN" ]]; then
  echo "nudge-topic-session: openclaw binary not found or not executable: $OPENCLAW_BIN" >&2
  exit 2
fi

SESSION_KEY_JSON="$(SESSION_KEY="$SESSION_KEY" python3 - <<'PY'
import json, os
print(json.dumps(os.environ['SESSION_KEY']))
PY
)"
MESSAGE_JSON="$(MESSAGE="$MESSAGE" python3 - <<'PY'
import json, os
print(json.dumps(os.environ['MESSAGE']))
PY
)"
IDEMPOTENCY_KEY="$(SESSION_KEY="$SESSION_KEY" MESSAGE="$MESSAGE" python3 - <<'PY'
import hashlib, os
seed = f"{os.environ['SESSION_KEY']}\0{os.environ['MESSAGE']}"
print('nudge-' + hashlib.sha256(seed.encode()).hexdigest()[:16])
PY
)"

# Validate that the target session exists before nudging it.
RESOLVE_PARAMS="$(SESSION_KEY_JSON="$SESSION_KEY_JSON" python3 - <<'PY'
import json, os
print(json.dumps({'key': json.loads(os.environ['SESSION_KEY_JSON'])}))
PY
)"
RESOLVE_JSON="$($OPENCLAW_BIN gateway call sessions.resolve --json --timeout "$GATEWAY_TIMEOUT_MS" --params "$RESOLVE_PARAMS" 2>/dev/null || true)"

if [[ -z "$RESOLVE_JSON" ]] || ! RESOLVE_JSON="$RESOLVE_JSON" SESSION_KEY="$SESSION_KEY" python3 - <<'PY'
import json, os, sys
try:
    data = json.loads(os.environ['RESOLVE_JSON'])
except Exception:
    sys.exit(1)
if data.get('key') != os.environ['SESSION_KEY']:
    sys.exit(1)
PY
then
  echo "nudge-topic-session: sessionKey not found in store: $SESSION_KEY" >&2
  echo "  hint: an existing session must have been started for this sessionKey at least once" >&2
  exit 3
fi

PARAMS="$(SESSION_KEY_JSON="$SESSION_KEY_JSON" MESSAGE_JSON="$MESSAGE_JSON" TIMEOUT="$TIMEOUT" IDEMPOTENCY_KEY="$IDEMPOTENCY_KEY" python3 - <<'PY'
import json, os
print(json.dumps({
    'key': json.loads(os.environ['SESSION_KEY_JSON']),
    'message': json.loads(os.environ['MESSAGE_JSON']),
    'timeoutMs': int(os.environ['TIMEOUT']) * 1000,
    'idempotencyKey': os.environ['IDEMPOTENCY_KEY'],
}))
PY
)"

exec "$OPENCLAW_BIN" gateway call sessions.send \
  --json \
  --timeout "$GATEWAY_TIMEOUT_MS" \
  --params "$PARAMS"
