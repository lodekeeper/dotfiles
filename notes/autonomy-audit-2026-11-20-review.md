# Daily autonomy audit — 2026-11-20

## Implemented improvement

Extended scripts/github/check-pr-ci-evidence.py with repeatable `--expect-workflow NAME`. Each exact named workflow needs a successful latest eligible run on the current PR head. Missing or non-successful expectations yield `insufficient_coverage` unless the existing failing/gated/pending/cancelled verdict takes precedence. An older success cannot satisfy a newer skipped run of the same workflow/event. Output includes matched run IDs, events, attempts and URLs. No added requests or remote writes; default verdict and exit contracts stay unchanged.

This is opt-in, not a retrofit of existing callers: task owners select relevant names. A successful workflow conclusion can still contain skipped jobs, so job/suite outcomes and temporary-trigger removal remain separate evidence requirements. Saved 11-19 #10666 partial-CI readiness and temporary-trigger evidence motivated the improvement; the helper does not claim to prevent all such mistakes.

## Four-workflow blockers and concrete next steps

| Workflow | Concrete blocker | Next step |
| --- | --- | --- |
| PR review | Exact-head coverage, findings reconciliation and delivery are not proven by prerequisites; a watch of known PRs can miss new fixes. | Rediscover all-author open PRs, select relevant CI workflow expectations, reconcile findings and verify authorized delivery. |
| CI fix | Upstream reruns require a maintainer; observed green does not prove relevant suites executed. | Use explicit expected workflows, inspect required job/suite results, retain temporary triggers until agreed verification completes, and keep isolated local/fork work plus quality gates. |
| Spec implementation | Clean test sources are not generated fixtures or executed coverage. | Record generation-time provenance, fixture inventory, actual counts, relevant nonempty/ordering paths and runner overrides during actual work. |
| Devnet debugging | Advertised datasources are not target/query access; one active network has unknown coverage; saved fleet receipt remains unverified. | Rediscover target/endpoints, report unavailable collection separately from health, and verify incidents/receipt before acknowledgment in authorized work. |

## Verification and limits

- Baseline29/29; updated38/38 targeted Python tests. Independent design and code reviews: APPROVE; reviewer independently passed38/38. Whitespace check passed.
- Live GET-only probe: [#10682](https://github.com/ChainSafe/lodestar/pull/10682), head `a0b1f67f9a7face3570ef50af526d7219209b1b7`, 03:20:34UTC: observed_green with explicit Tests expectation satisfied by [workflow44599109279](https://github.com/ChainSafe/lodestar/actions/runs/44599109279), attempt2. Not job-level coverage, a new PR review or merge readiness.
- Fresh inherited-Gateway prerequisites32/32: PR6/6, CI10/10, spec9/9, devnet7/7;17 unique commands,15 cached reuses. Not end-to-end tests. No structured drift versus yesterday; persistent baseline retains known datasource/search-signature changes and is unchanged.
- Verified lodekeeper has no upstream write role. Source cache313cbfe56 is clean, tests-history6/14days, generatedFixturesVerified=false. Panda advertises five names without production; no target query. Grafana absent only in inherited checks.
- Read saved02:18 monitor artifact:22 observed Lodestar at sampled head on three reachable finalizing networks; focil-devnet-3 unknown (null endpoints/public health unavailable). No audit network re-probe.
- Fleet observability returned exit1, status unacknowledged_due, for fresh saved11-19 07:13UTC snapshot:46 open/45 new-or-worsened keys versus25 acknowledged10-06; receiptVerified=false. This is the known owner-gated observability condition, not an exception or independent proof of incidents/resolutions/non-delivery. No relay or acknowledgment.
- Historical11-07 setup miss remains documented, not backfilled. All209 prior snapshots and trailing history preserved;210 unique dates after insertion.

Private evidence: memory/autonomy-audit-2026-11-20/. No install, auth/config/scheduler edit, restart, source refresh, fixtures, Lodestar code/tests, detector/tracker mutation, CI rerun, fleet operation, commit/push or external post.
