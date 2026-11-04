# Daily autonomy audit — 2026-11-04

## Practical improvement

Added explicit raw-job recovery to `scripts/ci/fetch-run-logs.sh`:

```bash
scripts/ci/fetch-run-logs.sh <run-id> --job-id <job-id> --output <distinct-log-path>
```

Yesterday's CI investigation recorded successful but shortened `gh run view --log-failed` and `--log` output; a raw per-job REST download exposed the keymanager bind error obscured by the detector's Vitest-crash classification. This audit adds the recovery path, not a speculative truncation detector or classifier change.

The helper verifies the returned job ID, run ID and completed status before requesting raw logs. It retains metadata/stderr, uses a job-specific default path, and downloads separately so API failure or an empty download cannot overwrite existing evidence. Directory output is rejected; a no-target-directory move also protects final placement. Default failed-log/run-log fallback behavior remains, with an explicit scope warning: success or size does not establish completeness. Its existing CI cron caller receives the recovery hint in normal output; no automation prompt or scheduler edit was required.

Independent design review approved the narrow approach. Code review reproduced a directory-target false-success edge, which was corrected and regression-tested before final review.

## Four-workflow audit

| Workflow | Concrete blocker | Proposed next step |
| --- | --- | --- |
| PR review | Prerequisites/local trackers do not prove exact-head CI, finding validity or completed delivery. | Collect current-head CI, reconcile all findings against current PR/code, then use the authorized provider session. Existing live-monitor integration remains owner-gated. |
| CI fix | Verified lodekeeper lacks upstream write role; formatted logs and detector labels can obscure the causal error. | Leave upstream approval/reruns to maintainers. Use raw-job recovery when evidence conflicts with job steps/annotations; preserve all-author duplicate checks, isolated dependencies and an actual quality verdict. |
| Spec implementation | Clean source cache is not verified generated fixtures or relevant runtime/input coverage. | On an actual fixture task retain generation-time provenance, inventory, executed cases, valid nonempty inputs, runner patches and the implementation layer exercised. Cache b834fa841 is clean at tests-history age 12/14 days; generatedFixturesVerified=false. |
| Devnet debugging | Tool availability/ack state do not establish node health or verified message receipt. | Discover fresh targets, corroborate incidents and retain evidence. Parent-owned verified posting then acknowledgment repair remains owner-gated; do not duplicate relays or auto-acknowledge. |

## Verification

- **10 offline CLI tests passed**, including successful-short-excerpt recovery, wrong job/run/incomplete metadata rejected before log download, API failures/empty downloads preserving an existing log, retained partial diagnostics, job-specific paths, directory-output rejection, legacy fallback and offline preflight. `bash -n` passed.
- Negative controls: the job-specific-path regression fails against the saved original helper; the directory-output regression reproduces the pre-correction false success. These test the absent feature and a real review finding, not just implementation shape.
- Fresh read-only retrieval of historical job **125801482921** in run **41601427704** returned **69,161 lines / 13,576,953 bytes**, containing the keymanager `EADDRINUSE`. Metadata identity/completed checks passed. This proves the raw recovery worked for that job; it does not prove every future download complete or reproduce today's formatted-log behavior. Raw logs, metadata, test output, negative controls and original helper stay in private `memory/autonomy-audit-2026-11-04/`.
- Fresh inherited-Gateway prerequisites passed **32/32**: PR 6, CI 10, spec 9, devnet 7; **17 unique commands / 15 cached reuses**. These are prerequisites, not end-to-end workflow tests or a model quality verdict. Structured health comparison found **no drift**, with persistent baseline unchanged. Evidence: `notes/autonomy-preflight-2026-11-04.json` and `notes/autonomy-health-drift-2026-11-04.json`.
- Read-only saved-fleet check: fresh 2026-11-03 07:13 UTC snapshot, **35 open / 31 new-or-worsened keys**, compared with 25 acknowledged on 10-06; weekly reminder due, receiptVerified=false. Exit **1 / unacknowledged_due** is documented report-due status, not collector failure, independently verified incidents or proven non-delivery. No probe, post or acknowledgment. Evidence: `notes/autonomy-fleet-delivery-2026-11-04.json`. Today's 02:18 monitor note separately records 30 Lodestar at canonical head; attributed monitor evidence, not this audit's network re-probe.
- Snapshot consistency/current-date cadence passed: **195 unique dates**, with all **194** previous snapshot blocks and trailing content byte-identical. The recovery-guarded backlog remains non-authoritative for historical decisions.

## Boundaries

Local helper/tests and audit records only, with read-only GitHub verification as lodekeeper. No PR review/approval/comment, CI rerun, detector/tracker mutation, new Lodestar fix, config/auth/scheduler/scratch edit, restart, install, source refresh, fixture generation, Lodestar tests, skill publication, commit/push or external post. Unrelated workspace changes were left alone. Backlog/daily-note close-out and final independent review are retained in private audit evidence.

Final independent code/factual review **APPROVED, no remaining findings**. The reviewer independently reran all 10 CLI tests and shell syntax, and verified evidence counts, historical preservation and the final response’s scope.
