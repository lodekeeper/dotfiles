# Daily autonomy audit — 2026-11-14

## Practical improvements

1. Added one baseline-attribution paragraph to `CODING_CONTEXT.md`: before deferring a behavioral failure as pre-existing/unrelated, reproduce it on a comparable baseline through the relevant target entry point, recording both revisions/diffs, relevant inputs/ordering, setup differences and outcomes. Identical arguments/source shape or library-only/mock evidence do not establish equivalent behavior. Infeasible comparison means attribution stays unverified, without authorizing setup changes or unrelated fixes. This is handoff guidance, not mechanical enforcement or a new runtime test.
2. Repaired an observed spec-source readiness failure with the existing dedicated-cache helper. Initial prerequisites were 31/32: clean cache `204fb4a19` had tests-history age **15/14 days**. `bash scripts/spec/ensure-fresh-test-vectors.sh --json` advanced only the dedicated checkout to `313cbfe561517a81eb11607fea7c6985e562eaa9`. The cache is clean, tests-history age is **0/14 days**, and refreshed prerequisites pass **32/32**. No fixtures were generated or tested.

## Evidence behind the handoff change

Yesterday's saved investigation records a provisional pre-existing deferral based on identical initial-state arguments. A comparable baseline run through actual signed batches, including production-worker verification, showed baseline passes/fixed fails; the deferral was revoked and the regression fixed before publication. Existing handoff instructions covered the target evidence layer but not comparable-baseline attribution. This audit reviewed the saved record, not the underlying runtime experiment anew. Independent native design review approved the narrow addition. No code changed and no code tests were needed for the prose-only change.

The saved record also reports a broad process-name stop catching a sibling build driver. Keep exact-owned job handles/PIDs during authorized process control. This audit makes no process-control implementation claim and did not signal any processes.

## Four-workflow audit

| Workflow | Concrete blocker | Proposed next step |
| --- | --- | --- |
| PR review | Passing prerequisites are not current-head CI, reconciled findings or a delivered verdict; an unsupported pre-existing deferral can hide a regression. | On the next authorized review collect exact-head CI, trace relevant construction/timer paths, apply comparable-baseline attribution and verify provider delivery. |
| CI fix | lodekeeper has no upstream write role; actual fixes still need complete evidence and quality/review gates. | Maintainers own upstream approval/reruns; use raw-job recovery, all-author duplicate checks, isolated dependencies and the new attribution rule for local/fork work. |
| Spec implementation | Stale source cache repaired; generated fixtures/provenance/coverage remain unverified. | During an actual fixture task retain generation-time provenance, artifact inventory, executed counts, valid nonempty inputs, construction/ordering paths and harness overrides. |
| Devnet debugging | Advertised sources and saved fleet state do not establish query usability, verified incidents or received reports. | Query the relevant target during an authorized investigation, verify incidents independently, keep delivery repair owner-gated and verify receipt before acknowledgment. |

## Fresh evidence and limits

- Inherited-Gateway prerequisites **32/32** after refresh: PR 6, CI 10, spec 9, devnet 7; 17 unique commands, 15 cached reuses. Prerequisites only, not end-to-end tests or a quality verdict. Existing CI credential/package presence was checked without a model request.
- No structured drift versus yesterday. Persistent-baseline drift still reflects only the previously recorded `local-kurtosis` discovery. Six source names advertised; no target or query exercised. Persistent baseline unchanged.
- Dedicated source cache clean; `generatedFixturesVerified=false`. No active feature checkout edit, fixture generation or Lodestar tests by this audit.
- Grafana absent only in the inherited check environment; no broader credential outage established.
- Saved fleet observability: fresh **11-13 07:13 UTC** snapshot, **25 open / 21 new-or-worsened** keys relative to 25 acknowledged on 10-06; receipt unverified. These are not independent incident, resolution or delivery counts. No relay, acknowledgment or fleet probe.
- Today's 02:18 monitor note records all 30 Lodestar at sampled head. Attributed monitor evidence, not this audit's network re-probe. Historical 11-07 setup miss remains documented, not backfilled or claimed repaired.

Private before-snapshots, initial/refreshed prerequisites, source-refresh output, drift comparison and preservation checks: `memory/autonomy-audit-2026-11-14/`. All 203 prior snapshots and trailing history remain byte-identical; current count 204. Consistency, deduplication and latest-pair/current-date cadence checks passed.

No install, auth/config/scheduler edit, restart, fixture generation, Lodestar code/test change, detector/tracker mutation, CI rerun, fleet operation, commit/push or external post.

Final independent factual review: APPROVE, no blocking findings. The reviewer independently verified the actual handoff patch, byte-identical preservation of all previous history, counts, unchanged persistent baseline and evidence qualifications. Incorporated the wording correction that guidance requires evidence rather than mechanically prevents a wrong attribution.

Scheduled summary: Updated the four-workflow autonomy audit. Added baseline-evidence guidance before dismissing behavioral failures as pre-existing, and refreshed the stale spec-source cache. Prerequisite checks now pass 32/32; generated fixtures remain unverified. No configuration changes.
