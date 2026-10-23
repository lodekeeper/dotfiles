# Daily autonomy audit — 2026-10-23

## Implemented improvement

Added a read-only PR CI evidence helper, `scripts/github/check-pr-ci-evidence.py`, plus 23 focused tests (`scripts/github/test_check_pr_ci_evidence.py`) and a **CI Status Evidence** section in the consumed `CODING_CONTEXT.md` handoff.

**Gap (evidence: `memory/2026-10-22.md` 15:56–16:36 and later heartbeat entries; `memory/2026-10-23.md`):** heartbeat notes called https://github.com/ChainSafe/lodestar/pull/10460 "CI green" three times, but all 7 `pull_request` workflows on head `feae3c50b9c` were `action_required` (the fork-PR approval gate). The 16:36 entry corrected it. Later entries still alternate between "0 failing checks" and naming the gate. Root cause: `gh pr checks` and `scripts/github/monitor_open_pr_ci.py` read only check runs. Approval-gated workflow runs create no check runs, so the monitor's `action_required` entry in `BAD_CONCLUSIONS` can never match. Negative control: feeding the monitor's `get_bad_checks` the live #10460 check-run shape returns `[]`.

**Helper:** uses only GET requests and parses arguments before any request. It joins workflow runs (`actions/runs?head_sha=`), check runs and combined status contexts for the PR head, then rechecks the head SHA after collection.
- **Current vs superseded:** the newest run per workflow/event and the newest check per suite/name are current. A newer skipped/neutral item does not supersede an older executed result. Checks in superseded runs' suites are superseded. Same-repo runs that belong only to another PR are excluded.
- **Verdict precedence:** `failing` > `action_required` > `pending` > `cancelled`. Otherwise `observed_green` only if at least one `pull_request`/`push`/`merge_group` workflow run, external check or status context succeeded; else `no_ci`. Skipped/neutral is counted separately and never counts as success.
- **Fails closed** (exit 1, `verdict: unknown`) on query errors (first stderr line included), malformed responses, more than 5 pages per endpoint, or a head move during collection.
- **Limits:** required-check coverage is not evaluated, so `observed_green` is not merge readiness.

**Live verification (03:2x UTC, read-only):**

| PR | Verdict | Detail |
| --- | --- | --- |
| #10460 | `action_required` | 7 gated workflows; old rollup "0 failing" |
| #10458, #10454 | `action_required` | Others' fork drafts; no action |
| #10447, #10448, #10457 | `observed_green` | |
| #10453 | `failing` | Benchmark |

## Independent review

First pass: **CHANGES-NEEDED.** Four false-green inputs were reproduced against the first version:
1. A newer skipped run hid an older failure.
2. Same-named jobs collapsed across workflows.
3. A `pull_request_target`-only head returned green.
4. An all-skipped head returned green.

There were also nits on other-PR runs sharing a head SHA, stderr detail, exit-code wording and doc overclaim. All were fixed, and each reproduced case is now a regression test.

Re-review: **APPROVE.** All four original repros now return `failing` or `no_ci`. Remaining findings, all addressed after approval:
- **Should-fix (fixed):** a newer *successful* run that skipped a job still dropped the older suite wholesale, hiding that job's failure. Supersession is now check-level: an older check is superseded only if the newest run of the same workflow/event re-executed a non-skipped job with that name.
- **Nit (fixed):** an Actions check not linked to any observed run could count as "external" success. That path now requires a non-`github-actions` app.
- **Nits (addressed):** the test helper now requires `suite=` for Actions checks. Doc point 3 now matches the code (`merge_group`, non-Actions check run). The other-PR caveat now says the match uses PR number only, only applies while PRs are open, and can't separate multi-PR runs.

These post-approval fixes were not re-reviewed. Instead they were mutation-checked: each new regression fails against the pre-fix logic and passes with the fix. 23 tests pass. Live verdicts are unchanged; merged #10463 also reads `failing` (`pull_request` Benchmark), which the reviewer confirmed is correct.

## Four-workflow audit

| Workflow | Concrete remaining blocker | Proposed next step |
| --- | --- | --- |
| PR review | Status reports could equate "0 failing checks" with green; exact-head evidence and authorized delivery still required | Use `check-pr-ci-evidence.py` for any CI-status/readiness claim; cite `headSha`/`observedAt`/`verdict`. |
| CI fix | Verified `lodekeeper` still has `repositoryWriteRole=false`; maintainers own workflow approvals and upstream reruns | Report `action_required` as a maintainer-owned gate, never as green or failing. No approval/rerun attempted. |
| Spec implementation | Clean source cache `aa16bb4c1` still `generatedFixturesVerified=false` | Unchanged: capture generation-time provenance and executed-case coverage on the next real fixture task. |
| Devnet debugging | Grafana absent in this environment. Fleet report delivery still unacknowledged: `latest.json` checked_at `2026-10-22T07:14:59Z`, `state.json` last_report_at `2026-10-06T11:32:25Z` | Unchanged owner-gated fix (parent-owned verified posting, then ack). Already escalated 10-21; not re-escalated. |

**Proposed, owner-gated (not done by this unattended run):**
1. Wire the helper into `monitor_open_pr_ci.py` so workflow-run `action_required`/pending states surface. This changes an alerting cron's output; seed the already-reported #10460 gate so it does not re-alert.
2. Point the heartbeat checklist's PR-status lines at the helper. This is an automation scratch edit.

## Verification

- Fresh inherited-environment prerequisite run: **32/32 passed** (PR review 6, CI fix 10, spec 9, devnet 7; 17 unique commands, 15 cached reuses). Evidence: `notes/autonomy-preflight-2026-10-23.json`.
- Read-only drift comparison: **no structured health drift**. Evidence: `notes/autonomy-health-drift-2026-10-23.json`. Baseline state not updated.
- `python3 -m unittest scripts/github/test_check_pr_ci_evidence.py`: 23 tests OK; `py_compile` clean. Negative controls: monitor `get_bad_checks` returns `[]` for the #10460 shape; both post-review regressions fail against the pre-fix logic.
- The `CODING_CONTEXT.md` diff against the baseline is a single inserted section. Before-copies are in `notes/autonomy-audit-2026-10-23-baseline/`.

## Boundaries

No PR approval, workflow approval, rerun, comment or other GitHub mutation (all API calls were GETs as verified `lodekeeper`). No config/auth/scheduler/automation-scratch change, restart, install, pnpm execution, source-cache refresh, fixture generation, Lodestar test run, index rebuild, commit/push, skill publication or external post. `monitor_open_pr_ci.py` is unchanged. Changes are local and uncommitted.

Context: today's scheduled run began on the Codex runtime. That runtime's run ended in a session-policy handoff error after its scope reviewer approved a doc-only change. This run continued it and added the helper. The heartbeat that made the error does not load `CODING_CONTEXT.md`, so guidance text alone would not reach it. The helper is the mechanical piece the proposed monitor/heartbeat wiring would call. Until that wiring is approved, the heartbeat surface itself is unchanged.
