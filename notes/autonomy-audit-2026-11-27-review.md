# Daily autonomy audit — 2026-11-27

## Practical improvement

Added requirement-aware rollback guidance to the existing CODING_CONTEXT.md handoff and broadened its merge/conflict heading to include rollback. Before a requested revert, inspect the current head/diff and latest applicable owner/reviewer requirements; identify unwanted hunks/commits while preserving still-required changes bundled with them. Inspect unfamiliar changes, check the resulting tree, run narrow affected-behavior checks and refresh PR/test claims. Earlier results remain attributed to their tested tree.

This is an opt-in workflow improvement, not a mechanical rollback gate or proof that future workers will follow it. It grants no new write, push or deployment authority.

## Evidence

The saved 11-26 daily summary records a requirement lost during follow-up reverts. Read-only inspection of the local task history confirms the concrete sequence:

- `7be667629e` combined the Nethermind client selection with REST API-wait logic.
- `144a77a5c4` reverted that mixed-purpose commit, including the client choice.
- `1b068185f1` then removed the separate beacon-API workaround.
- `d96ea2b986` restored Nethermind without restoring the workaround.

The recovery-marked backlog supplied a lead, not authority to resume the task or proof of current PR status. The commits establish the code sequence; latest requirements are attributed to the saved discussion/daily summary. Parallel-worker authorship was not established and is not asserted. No live PR status, review request or dependency-release state was refreshed.

Independent design review approved this as distinct from the existing upstream-conflict guidance and corrected the exact reverting-commit attribution before the documentation was written.

## Four-workflow blockers and next steps

| Workflow | Concrete blocker | Next authorized step |
| --- | --- | --- |
| PR review | Follow-up edits can lose still-applicable requirements; local older dependencies and fork-gated CI limit verification claims. | Reconcile requirements against the resulting tree, preserve exact-head evidence and qualify setup differences. |
| CI fix | A mixed-purpose revert can remove required changes; healthy finality is not a passing complete nightly scenario. | Revert only unwanted behavior, preserve applicable requirements and obtain current-head required job/suite results. |
| Spec implementation | Source-cache readiness does not establish generated provenance, exercised cases or consumer schema compatibility. | Retain generation-time provenance, installed-fixture mapping, actual counts and relevant consumer-version evidence. |
| Devnet debugging | Saved monitors are not fresh target/query execution; helper adoption and fleet receipt remain unresolved. | Discover endpoints, verify target/query access and distinguish collection/decoder failure from node health. Delivery repair remains owner-gated. |

## Verification and limits

- Fresh `ensure-fresh-test-vectors.sh --check-only --json` passed: clean cache `313cbfe56`, tests-history age 13/14 days, `generatedFixturesVerified=false`. No fetch, checkout refresh or generated-fixture run.
- Saved 11-26 review evidence explicitly qualifies older local JS dependencies and fork-gated CI; saved nightly evidence distinguishes finalizing nodes from an incomplete full scenario. These are attributed records, not this audit's CI re-probe.
- Saved 11-27 02:18 monitoring reports three finalizing networks and all 24 Lodestar at sampled canonical head. No network re-probe, datasource discovery or sandbox query was performed here.
- This documentation-only change needs no product tests. Audit consistency, duplicate-date and current/latest-pair cadence checks passed for 217 snapshots. All 216 prior snapshots and trailing history remain byte-identical; the handoff diff only renames the heading and inserts the rollback paragraph. Logs and preservation hashes are recorded in private evidence.

Private before-snapshots, local commit evidence and command results: `memory/autonomy-audit/2026-11-27/`.

No dependency installs, repository lint-config edits, Gateway/config/scheduler changes, restarts, product patches, detector/tracker mutations, CI reruns, fleet operations, commits/pushes or external posts. Final delivery is scheduler-owned.
