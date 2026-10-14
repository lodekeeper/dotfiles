#!/usr/bin/env bash
# Drive QMD embedding to completion despite qmd 1.0.7's 30-min embed-session cap
# (withLLMSession maxDuration in dist/qmd.js). On CPU one capped run embeds ~1.5k chunks; every
# chunk still queued at the cap fails with SessionReleasedError, and the document being processed
# is left partial (seq 0 embedded, tail missing). A plain re-run skips partial hashes, so before
# each run this clears the vectors of every hash the completeness checker reports as partially
# embedded, then lets `qmd embed` re-queue them. Stops when the checker passes or after max rounds.
#
# Usage: scripts/memory/qmd_embed_resume.sh [max_rounds]   (default 8, ~30 min each on CPU)
# Exit: 0 complete, 3 still incomplete after max rounds, 75 another embed/nightly cycle is running.
set -euo pipefail

cd "$(dirname "$0")/../.."
export PATH="$HOME/.local/bin:$PATH"

MAX_ROUNDS="${1:-8}"
QMD_NODE="${QMD_NODE_DIR:-$HOME/.nvm/versions/node/v22.22.0}/bin/node"
INDEX="${QMD_INDEX:-$HOME/.cache/qmd/index.sqlite}"
CHECK=scripts/memory/check_qmd_embedding_completeness.py
CLEAR=scripts/memory/qmd_clear_hash_vectors.mjs

ts() { date -u +%FT%TZ; }

# Two concurrent embed sessions on one index lose data (2026-08-22, 2026-08-30), so hold both the
# ad-hoc embed lock and the nightly-cycle lock for the whole run.
exec 8>/tmp/lodekeeper-nightly-memory-cycle.lock
flock -n 8 || { echo "[$(ts)] nightly memory cycle is running; not starting" >&2; exit 75; }
exec 9>/tmp/qmd-embed.lock
flock -n 9 || { echo "[$(ts)] another qmd embed holds /tmp/qmd-embed.lock; not starting" >&2; exit 75; }

partial_hashes() {
  python3 "$CHECK" --index "$INDEX" --json --limit 1000000 | python3 -c '
import json, sys
report = json.load(sys.stdin)
print(" ".join(i["hash"] for i in report["issues"] if i["embeddedChunks"] > 0))
print(report["incompleteHashes"], file=sys.stderr)
'
}

for round in $(seq 1 "$MAX_ROUNDS"); do
  if python3 "$CHECK" --index "$INDEX" >/dev/null 2>&1; then
    echo "[$(ts)] embedding complete before round $round"
    exit 0
  fi
  read -r -a partial <<<"$(partial_hashes 2>/tmp/qmd-embed-resume-incomplete.txt)"
  echo "[$(ts)] round $round/$MAX_ROUNDS: $(cat /tmp/qmd-embed-resume-incomplete.txt) incomplete hash(es), ${#partial[@]} partial"
  if ((${#partial[@]} > 0)); then
    "$QMD_NODE" "$CLEAR" "$INDEX" "${partial[@]}"
  fi
  nice -n 15 ionice -c3 qmd embed 2>&1 | tr '\r' '\n' | grep -v -E '^[[:space:]]*$|█|░|Error embedding' || true
done

if python3 "$CHECK" --index "$INDEX"; then
  echo "[$(ts)] embedding complete after $MAX_ROUNDS rounds"
  exit 0
fi
echo "[$(ts)] still incomplete after $MAX_ROUNDS rounds"
exit 3
