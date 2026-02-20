#!/bin/bash
# Monitor mainnet-consensus-1 logs for anomalies
# Called by cron job, outputs findings or nothing

CONTAINER="mainnet-consensus-1"
SINCE="31m"

# Grab recent logs, strip ANSI codes
LOGS=$(docker logs "$CONTAINER" --since "$SINCE" 2>&1 | sed 's/\x1b\[[0-9;]*m//g')

ALERTS=""

# 1. Check for errors (exclude known noisy getBlockV2 warnings)
ERRORS=$(echo "$LOGS" | grep -E '\berror\b|\bwarn\b' | grep -v 'getBlockV2 failed reason=Block not found' | grep -v 'getBlockV2 failed reason=No block' | grep -v 'getBlockHeader failed reason=Block not found' | tail -10)
if [ -n "$ERRORS" ]; then
  COUNT=$(echo "$ERRORS" | wc -l)
  ALERTS+="⚠️ **$COUNT error/warn lines** (excluding known getBlockV2 noise):\n"
  ALERTS+='```\n'
  ALERTS+="$(echo "$ERRORS" | head -5)\n"
  ALERTS+='```\n\n'
fi

# 2. Check sync status from latest info line
LATEST_INFO=$(echo "$LOGS" | grep 'info.*Synced' | tail -1)
if [ -z "$LATEST_INFO" ]; then
  # No "Synced" line in last 6 min — node may be struggling
  ALERTS+="🔴 **No 'Synced' log line in last $SINCE** — node may be down or stuck\n\n"
else
  # Check peer count
  PEERS=$(echo "$LATEST_INFO" | grep -oP 'peers: \K[0-9]+')
  if [ -n "$PEERS" ] && [ "$PEERS" -lt 50 ]; then
    ALERTS+="🟡 **Low peer count: $PEERS** (expected ~200)\n\n"
  fi
fi

# 3. Check for crash/OOM signals
CRASH=$(echo "$LOGS" | grep -iE 'fatal|SIGTERM|SIGKILL|OOM|heap out|JavaScript heap|Allocation failed|v8::' | head -3)
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
