#!/usr/bin/env bash
# Poll glamsterdam-devnet-12 Lodestar nodes during the deposit attack
LOG=/home/openclaw/.openclaw/workspace/memory/devnet12-deposit-attack-monitor.log
NODES="lodestar-erigon-1 lodestar-ethrex-1"
END=$(( $(date +%s) + ${DURATION_SEC:-10800} ))
while [ "$(date +%s)" -lt "$END" ]; do
  for n in $NODES; do
    (
    out=$(timeout 40 ssh -o ConnectTimeout=8 -o BatchMode=yes devops@$n.srv.glamsterdam-devnet-12.ethpandaops.io '
      s=$(curl -s --max-time 8 localhost:5052/eth/v1/node/syncing)
      p=$(curl -s --max-time 8 localhost:5052/eth/v1/node/peer_count | grep -o "\"connected\":\"[0-9]*\"" | grep -o "[0-9]*")
      f=$(curl -s --max-time 8 localhost:5052/eth/v1/beacon/states/head/finality_checkpoints | grep -o "\"finalized\":{\"epoch\":\"[0-9]*\"" | grep -o "[0-9]*")
      pd=$(curl -s --max-time 15 localhost:5052/eth/v1/beacon/states/head/pending_deposits | grep -o "\"pubkey\"" | wc -l)
      m=$(curl -s --max-time 8 localhost:5054/metrics)
      rss=$(echo "$m" | grep -E "^process_resident_memory_bytes " | head -1 | awk "{printf \"%.0f\", \$2/1048576}")
      heap=$(echo "$m" | grep -E "^nodejs_heap_size_used_bytes " | head -1 | awk "{printf \"%.0f\", \$2/1048576}")
      lag=$(echo "$m" | grep -E "^nodejs_eventloop_lag_p99_seconds " | head -1 | awk "{print \$2}")
      ep=$(echo "$m" | grep -E "^lodestar_stfn_epoch_transition_seconds_sum |^lodestar_stfn_epoch_transition_seconds_count " | awk "{print \$2}" | tr "\n" "/")
      logs=$(docker logs --since 60s beacon 2>&1)
      errs=$(echo "$logs" | grep -c -E "\berror\b|\[error\]|error:" )
      warns=$(echo "$logs" | grep -c -iE "\bwarn\b")
      lasterr=$(echo "$logs" | grep -iE "error" | tail -1 | cut -c1-220)
      echo "sync=$s peers=$p fin=$f pendingDeposits=$pd rssMB=$rss heapMB=$heap lagP99=$lag epochTr(sum/count)=$ep err60s=$errs warn60s=$warns lastErr=$lasterr"
    ' 2>&1 | tr "\n" " ")
    echo "$(date -u +%H:%M:%S) $n $out" >> "$LOG"
    ) &
  done
  wait
  sleep ${INTERVAL_SEC:-60}
done
