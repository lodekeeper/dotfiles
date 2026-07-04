#!/usr/bin/env bash
# Quick public-endpoint health snapshot for a hosted ethpandaops devnet.
# No auth, no panda — just curl+jq against the devnet's public Dora/config endpoints.
# Use as the "first 60 seconds": finality, active forks, topology. Then go deeper with panda.
set -euo pipefail
N="${1:?usage: net-health.sh <network>   e.g. glamsterdam-devnet-5}"
DORA="https://dora.$N.ethpandaops.io"
CFG="https://config.$N.ethpandaops.io"

echo "# $N — health snapshot ($(date -u +%Y-%m-%dT%H:%MZ))"

echo; echo "## finality / participation"
# NOTE: /api/v1/epoch/latest is the IN-PROGRESS epoch — its participation_pct is
# partial (attestations still being included) and routinely reads ~55-60% mid-epoch.
# Do NOT judge "not finalizing" from it.
LATEST=$(curl -fsS --max-time 15 "$DORA/api/v1/epoch/latest" 2>/dev/null || echo '{}')
CUR_EPOCH=$(echo "$LATEST" | jq -r '(.data // .).epoch // empty')
echo "$LATEST" \
  | jq '(.data // .) | {epoch, note: "IN-PROGRESS — partial", participation_pct_partial: .globalparticipationrate, finalized}' \
  || echo "  (dora epoch/latest unreachable)"
if [ -n "$CUR_EPOCH" ]; then
  DONE=$((CUR_EPOCH - 1))
  echo "  -> last COMPLETED epoch ($DONE):"
  curl -fsS --max-time 15 "$DORA/api/v1/epoch/$DONE" \
    | jq '(.data // .) | {epoch, finalized, participation_pct: .globalparticipationrate, validators: .validatorscount, proposed: .proposedblocks, payloads_ok: .proposedpayloads, payloads_missed: .missedpayloads}' \
    || echo "  (dora epoch/$DONE unreachable)"

  # --- finality VERDICT: judge by DISTANCE to the finalized checkpoint, NOT by whether
  # the last completed epoch is finalized yet. Finality ALWAYS lags the head by ~2 epochs
  # (you cannot finalize the in-progress or last-completed epoch), so "epoch N-1 finalized=false"
  # is the NORMAL, HEALTHY state — it is NOT "not finalizing". Walk back to the newest
  # finalized epoch and measure the gap. (This is the guard that stops the false non-finality
  # alerts, e.g. glamsterdam-devnet-6 epoch 2017: finalized=2017, current=2019, distance=2 = healthy.)
  FIN_EPOCH=""
  for back in 2 3 4 5 6 7 8; do
    E=$((CUR_EPOCH - back)); [ "$E" -lt 0 ] && break
    F=$(curl -fsS --max-time 10 "$DORA/api/v1/epoch/$E" 2>/dev/null | jq -r '(.data // .).finalized // false')
    if [ "$F" = "true" ]; then FIN_EPOCH=$E; break; fi
  done
  if [ -n "$FIN_EPOCH" ]; then
    DIST=$((CUR_EPOCH - FIN_EPOCH))
    if [ "$DIST" -le 3 ]; then
      echo "  -> finality_verdict: FINALIZING (normal) — finalized=epoch $FIN_EPOCH, current=$CUR_EPOCH, distance=$DIST (healthy is 2). NOT an alert."
    else
      echo "  -> finality_verdict: LAGGING — finalized=epoch $FIN_EPOCH, current=$CUR_EPOCH, distance=$DIST (>3). Candidate ONLY if sustained across runs (2h apart)."
    fi
  else
    echo "  -> finality_verdict: NO finalized epoch in last 8 — genuine non-finality candidate (verify it is sustained, not a fresh/restarting net)."
  fi
fi

echo; echo "## scheduled forks (epoch != far-future)"
curl -fsS --max-time 15 "$CFG/cl/config.yaml" 2>/dev/null \
  | grep -E "_FORK_EPOCH" | grep -v "18446744073709551615" \
  || echo "  (cl/config.yaml unreachable)"

echo; echo "## topology — node -> CL/EL client (+ CL image tag)"
curl -fsS --max-time 15 "$CFG/api/v1/nodes/inventory" 2>/dev/null \
  | jq -r '.ethereum_pairs | to_entries[] | "  \(.key): \(.value.consensus.client)/\(.value.execution.client)   \(.value.consensus.image)"' \
  || echo "  (nodes/inventory unreachable)"

echo; echo "## drill-down links"
echo "  forks:     $DORA/forks"
echo "  assertoor: https://assertoor.$N.ethpandaops.io  (tests: /api/v1/test_runs)"
echo "  syncoor:   https://syncoor.$N.ethpandaops.io"
