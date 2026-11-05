#!/usr/bin/env bash
# Embedding phase of the nightly memory cycle, launched detached (setsid) by
# scripts/memory/nightly_memory_cycle.sh and appending to its log.
#
# On CPU qmd embeds ~1.4 KB/s (645 chunks = 15m42s on 2026-11-05) and the nightly workload (~35
# changed docs, ~1k chunks) does not fit the cron's 900s timeout, which left
# nightly-memory-consolidation red (timeouts 2026-11-01, 11-03, 11-04, 11-05) and the embeddings to
# a manual heartbeat resume. Running this phase detached lets the cron finish in minutes.
#
# This is the same flow the inline Step 4 ran: plain `qmd embed`, no vector clearing. Do not swap in
# qmd_embed_resume.sh: its clear-and-retry cannot converge on backlog-archive.md (~1.1k chunks, more
# than one 30-min qmd session) and starved 20 other docs on 2026-10-30.
#
# It prints the final "Nightly memory cycle complete" line itself, after Step 4b, because
# scripts/cron/check_cron_health.py treats that line as "embedding finished" and then runs the
# completeness checker. No footer means the worker did not finish: a failure path logs a "FAILED"
# line, but a SIGKILL (gateway restart, KillMode=mixed) logs nothing and the watchdog does not alert
# on a missing footer, so check the cycle log tail when the cron is green but embeddings look stale.
set -euo pipefail

cd "$(dirname "$0")/../.."
export PATH="$HOME/.local/bin:$PATH"

ts() { date -u +%FT%TZ; }

on_exit() {
  local rc=$?
  [[ $rc -eq 0 ]] || echo "[$(ts)] nightly embed phase FAILED before completion (exit $rc); embeddings may be incomplete"
}
trap on_exit EXIT

# The launching cycle holds the nightly lock until it exits, so wait for it, then keep the lock for
# the whole embed so a later cycle cannot race the embedding session (data loss 2026-08-22,
# 2026-08-30). /tmp/qmd-embed.lock serializes with manual embeds (qmd_embed_resume.sh, heartbeat).
exec 200>/tmp/lodekeeper-nightly-memory-cycle.lock
flock -w 180 200 || { echo "[$(ts)] nightly cycle lock still held after 180s; not embedding"; exit 75; }
exec 9>/tmp/qmd-embed.lock
flock -w 1800 9 || { echo "[$(ts)] /tmp/qmd-embed.lock still held after 1800s; not embedding"; exit 75; }

echo "[$(ts)] Step 4 (embeddings): qmd embed"
nice -n 15 ionice -c3 qmd embed 2>&1 || true

# `qmd embed` hard-caps each run at 30 min (withLLMSession maxDuration in qmd 1.0.7 dist/qmd.js);
# every chunk still queued at the cap fails with SessionReleasedError. Docs left with NO vectors are
# re-queued, so give them fresh sessions (bounded). Docs whose seq 0 was embedded before the cap stay
# partial until their content changes - a re-run cannot fix those.
for pass in 2 3; do
  status_out="$(qmd status 2>&1 || true)"
  # `qmd status` prints "Pending:  N need embedding" only when N > 0 (dist/qmd.js showStatus)
  if ! grep -Eq "Pending:[[:space:]]+[0-9]+ need embedding" <<<"$status_out"; then
    break
  fi
  echo "Step 4 (embed pass $pass): docs still without vectors after a capped run - fresh embed session"
  nice -n 15 ionice -c3 qmd embed 2>&1 || true
done

echo "Step 4b: verify QMD embedding completeness"
python3 scripts/memory/check_qmd_embedding_completeness.py 2>&1 || true

echo "[$(ts)] Nightly memory cycle complete"
