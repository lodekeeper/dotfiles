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
# Do NOT judge "not finalizing" from it. The last COMPLETED epoch is the real signal.
LATEST=$(curl -fsS --max-time 15 "$DORA/api/v1/epoch/latest" 2>/dev/null || echo '{}')
CUR_EPOCH=$(echo "$LATEST" | jq -r '(.data // .).epoch // empty')
echo "$LATEST" \
  | jq '(.data // .) | {epoch, note: "IN-PROGRESS — partial", participation_pct_partial: .globalparticipationrate, finalized}' \
  || echo "  (dora epoch/latest unreachable)"
if [ -n "$CUR_EPOCH" ]; then
  DONE=$((CUR_EPOCH - 1))
  echo "  -> last COMPLETED epoch ($DONE) — judge finalization from THIS:"
  curl -fsS --max-time 15 "$DORA/api/v1/epoch/$DONE" \
    | jq '(.data // .) | {epoch, finalized, participation_pct: .globalparticipationrate, validators: .validatorscount, proposed: .proposedblocks, payloads_ok: .proposedpayloads, payloads_missed: .missedpayloads}' \
    || echo "  (dora epoch/$DONE unreachable)"
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
