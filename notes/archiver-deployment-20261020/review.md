# Hoodi next-4bacee3 deployment response QA

## Verdict

Parent draft is supported by the supplied monitoring evidence. It correctly separates observed recovery/progress from full resolution. Prefer “both nodes fully recovered” over “fleet issue fully resolved” to keep scope strictly public Hoodi; mainnet still advertises another commit and is not covered by this deployment verdict.

Suggested wording:

> Confirmed both public Hoodi nodes are on `4bacee3`, and archiving is moving again: `-1` has completed epoch 131054, well past 131029. `-0` is still behind—last completed 131045 versus finalized 131055, with recent checkpoints taking about nine minutes—so I would not call both nodes fully recovered yet.

## Evidence reviewed

Read parent's saved `version.json`, `archive.json`, `logs.json`, `current.json`, `phases.json`, `errors.json`; no additional live-service queries.

- Both `public-hoodi-hzax41-0` and `-1` advertise commit `4bacee3dacfe04629dc167947bad12fa95ae96f1` (`v1.50.0/4bacee3`). Public mainnet and Sepolia still advertise `003bd66543fa65b5c1e954eec9e8077054c226dc`; do not generalize version confirmation to them.
- At the supplied approximately 23:35 UTC snapshot, both Hoodi nodes report forkchoice-finalized epoch 131055.
- `-1` logs full processing completion for epochs 131051, 131052, 131053 and 131054 (latest at 23:30:35), then starts 131055 at 23:34:48. This is direct repeated processing progress beyond the previously reported 131029 stall.
- `-0` logs completion of 131043 at 23:08:47, 131044 at 23:17:57 and 131045 at 23:27:07; 131046 starts immediately afterwards. Recent completion cadence is approximately 9m10s/checkpoint, slower than normal epoch cadence; at the snapshot the latest completed processing is ten epochs behind forkchoice finality. This is ongoing progress with backlog, not proof of a new permanent stall.
- `-0` has blob-pruning progress after the blob-migration log for 131046. Prior 131045 column pruning completes at 23:27:06, immediately before full completion. These logs do not identify which underlying flat/legacy operation dominates the long gap.
- Current-process `archive_blocks` and `forkchoice_prune` histogram counts agree (7 on `-0`, 6 on `-1`). This supports successful completion counts, not the identity or duration of the in-flight job. Supplied error query returned no matching entries; that is bounded query evidence, not proof of no failures ever.

## Source interpretation and caveats

Reviewed `/home/openclaw/lodestar-archive-column-compaction` at clean PR head `9aec7dcad139b61f84eb4bc04a337081407f00f7` (parent reports merged deployment `4bacee3dacfe04629dc167947bad12fa95ae96f1`).

- `archiveStore/archiveStore.ts:284` logs `Finish processing finalized checkpoint` only after all prior awaited tasks and the final synchronous forkchoice prune return. Repeated increasing-epoch finish logs are the strongest observed completion evidence.
- `lodestar_process_finalized_checkpoint_seconds` (`metrics/metrics/lodestar.ts:1831`) is a histogram labelled by task source, not total process duration or an in-flight gauge. Each observation occurs after that individual task succeeds. `archive_blocks` proves `archiveBlocks` returned; `forkchoice_prune` is the final-stage completion signal. Failed/pending tasks emit no observation for their current attempt.
- Head, sync status and `beacon_finalized_epoch` are independent forkchoice/import state; none alone proves archival completion. Use same-instance post-restart samples and avoid mixing task labels into a completed-checkpoint total.
- This evidence establishes progress after deployment, not tombstones as the original host root cause, nor elimination of all slow paths. The draft makes no such causal claim.

No source/BACKLOG changes, tests, deployments or external messages by this reviewer. Only this report written.
