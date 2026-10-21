# Deployed archiver fix verification — 2026-10-20 23:35 UTC

Read-only check after Nico reported deployment of next-4bacee3 in Discord message1562247530845044827.

## Deployment
Both public-hoodi-hzax41-0 and public-hoodi-hzax41-1 have lodestar_version commit4bacee3dacfe04629dc167947bad12fa95ae96f1. Hoodi public API independently reports Lodestar/v1.50.0/4bacee3, sync distance0, nonoptimistic and EL online. Both public mainnet instances still report003bd66; do not include them in a fixed-build recovery claim.

## Archive progress
- Hoodi-1: full Finish processing finalized checkpoint logs for131051 at23:11:13,131052 at23:17:42,131053 at23:26:28 and131054 at23:30:35. Began131055 at23:34:48. This is actual completion beyond previously stalled131029, not just a synced head.
- Hoodi-0: full finishes131043 at23:08:47,131044 at23:17:57 and131045 at23:27:07. Began131046 immediately afterward. Last two checkpoint durations about550seconds each, longer than a Hoodi epoch384seconds. Finalized epoch is131055, so last-completed archival lag10epochs at this snapshot. Do not call this node caught up or the entire issue resolved.
- Both post-startup archive_blocks and forkchoice_prune histogram counts have observations (7 on0,6 on1). These are successful task observations, not in-flight counters; successful completion logs are stronger evidence.
- Both start block migration and finish blob handling in milliseconds in the observed jobs. The remaining long interval is before dataColumnSidecars prune completion. This localizes an interval, not a confirmed native mechanism or exact filesystem/DB cause.
- Narrow15minute Loki query returned no error-level/Error processing finalized checkpoint lines. Not an exhaustive health or error-free guarantee.

## Limits
No source or remote service changes, deployments, restarts, DB maintenance, configuration changes or broad tests. Grafana queries use the existing read-only credential, never logged. Raw monitoring responses are stored beside this report. Deployment is confirmed; archival progress is confirmed; residual Hoodi-0 lag remains unresolved. Do not claim tombstones proven as the live root cause.
