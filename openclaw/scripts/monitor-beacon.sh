#!/bin/bash
# Monitor mainnet-consensus-1 logs for anomalies
# Called by cron job, outputs findings or nothing

CONTAINER="mainnet-consensus-1"
SINCE="24h"

# Grab recent logs, strip ANSI codes
LOGS=$(docker logs "$CONTAINER" --since "$SINCE" 2>&1 | sed 's/\x1b\[[0-9;]*m//g')

ALERTS=""

# 1. Check for errors (exclude known noisy getBlockV2 warnings)
ERRORS=$(echo "$LOGS" | grep -E '\berror\b|\bwarn\b' | grep -v 'getBlockV2 failed reason=Block not found' | grep -v 'getBlockV2 failed reason=No block' | grep -v 'getBlockHeader failed reason=Block not found' | grep -v 'Route GET:/ not found' | tail -10)
if [ -n "$ERRORS" ]; then
  COUNT=$(echo "$ERRORS" | wc -l)
  ALERTS+="⚠️ **$COUNT error/warn lines** (excluding known getBlockV2 noise):\n"
  ALERTS+='```\n'
  ALERTS+="$(echo "$ERRORS" | head -5)\n"
  ALERTS+='```\n\n'
fi

# 2. Sync + liveness via the REST API — authoritative source of truth.
#    (This container logs to a FILE, not docker stdout: `docker logs` is empty and the
#    info-level "Synced" line never reaches stdout, so the old grep always false-fired.)
BN_IP=$(docker inspect "$CONTAINER" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' 2>/dev/null | awk '{print $1}')
SYNCING=$(curl -s --max-time 8 "http://${BN_IP}:5052/eth/v1/node/syncing" 2>/dev/null)
if [ -z "$SYNCING" ] || ! echo "$SYNCING" | grep -q '"head_slot"'; then
  # REST unreachable = the real "node down / unresponsive" signal
  ALERTS+="🔴 **Beacon REST API unreachable** (http://${BN_IP}:5052) — node may be down or unresponsive\n\n"
else
  SYNC_DIST=$(echo "$SYNCING" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['sync_distance'])" 2>/dev/null || echo "")
  IS_SYNCING=$(echo "$SYNCING" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['is_syncing'])" 2>/dev/null || echo "?")
  EL_OFFLINE=$(echo "$SYNCING" | python3 -c "import sys,json;print(json.load(sys.stdin)['data'].get('el_offline',False))" 2>/dev/null || echo "?")
  if [ -n "$SYNC_DIST" ] && [ "$SYNC_DIST" -gt 10 ] 2>/dev/null; then
    ALERTS+="🔴 **Node behind head: sync_distance=$SYNC_DIST slots** (is_syncing=$IS_SYNCING) — may be stuck/struggling\n\n"
  fi
  if [ "$EL_OFFLINE" = "True" ]; then
    ALERTS+="🔴 **Execution client offline** (el_offline=true)\n\n"
  fi
  # Peer count via REST
  PEERS=$(curl -s --max-time 8 "http://${BN_IP}:5052/eth/v1/node/peer_count" 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['connected'])" 2>/dev/null || echo "")
  if [ -n "$PEERS" ] && [ "$PEERS" -lt 50 ] 2>/dev/null; then
    ALERTS+="🟡 **Low peer count: $PEERS** (expected ~200)\n\n"
  fi
fi

# 3. Check for crash/OOM signals
# Exclude REST request-log lines: request IDs are random short strings (req-oom, req-fatal, etc.)
# that can coincidentally word-match a crash keyword without any real crash/OOM occurring.
CRASH=$(echo "$LOGS" | grep -iE '\bfatal\b|SIGTERM|SIGKILL|\bOOM\b|heap out|JavaScript heap|Allocation failed|v8::' | grep -v 'Req req-' | head -3)
if [ -n "$CRASH" ]; then
  ALERTS+="🔴 **Crash/OOM signal detected:**\n"
  ALERTS+='```\n'
  ALERTS+="$(echo "$CRASH")\n"
  ALERTS+='```\n\n'
fi

# 4. Check for EL communication errors
EL_ERR=$(echo "$LOGS" | grep -iE 'EXECUTION_ERROR|engine.*error|newPayload.*error|forkchoiceUpdate.*error|Execution client.*not.*respond' | grep -v 'getBlockV2' | head -3)
if [ -n "$EL_ERR" ]; then
  ALERTS+="🟡 **EL communication issues:**\n"
  ALERTS+='```\n'
  ALERTS+="$(echo "$EL_ERR")\n"
  ALERTS+='```\n\n'
fi

# 5. Check for finalization issues (comparing finalized epoch to expected)
# Just flag if we see "not finalized" or similar
FINALITY=$(echo "$LOGS" | grep -iE 'not finaliz|finality.*issue|checkpoint.*behind' | head -2)
if [ -n "$FINALITY" ]; then
  ALERTS+="🟡 **Finality concerns:**\n"
  ALERTS+="$(echo "$FINALITY")\n\n"
fi

if [ -n "$ALERTS" ]; then
  echo -e "$ALERTS"
else
  echo ""
fi
