# Autonomy audit evidence — 2026-10-11

## Scope and improvement

The 2026-10-10 16:58 UTC daily note records three completed devnet task entries prepended above `# BACKLOG`, displacing the standing recovery banner beyond the backlog status helper's first-12-line window. Independent inspection found the same position-dependent check in the memory-index source filter. The former could list guarded data without its normal refusal; the latter could make recovery data eligible for indexing.

Removed only the line caps in `scripts/backlog/list_statuses.py` and `scripts/memory/rebuild_index.py`; both already read the entire file. Existing exact warning markers now match anywhere in backlog text. Quoted exact markers conservatively remain guarded. No new shared-module/import architecture, automatic file relocation, or change to GitHub notification sweeping's deliberately different structural policy.

## Independent review

Native child `/root/audit_guard_review` inspected the existing helpers/tests and approved this minimal design before implementation. Independent code review compared the three existing files against the recorded baselines, inspected the new test, reran the backlog parser/CLI tests and all five index tests, and parsed the 28 prerequisite records. Verdict: **APPROVE, no findings**. The proposed response was approved with the distinction that all four gap assessments were updated, not that four workflows became fully autonomous.

## Verification

- Pre-change fixture: three five-line done-task blocks followed by the header and banner, warning at **line 18**. Both listing guard detection and memory-index exclusion returned **false**. Baseline copies: `/tmp/autonomy-guard-20261011-2cudgx6w/`.
- `python3 scripts/backlog/test_list_statuses.py`: existing parser/status tests and new displaced-banner regressions passed. Both marker variants retain default/refusal-with-required-guard exit **2**, empty stdout on refusal and explicit audit exit **0**. Existing missing-required-guard exit **3** is preserved; quoted exact warning and non-marker controls passed.
- `python3 scripts/memory/test_backlog_guard.py`: **5 tests passed**, including both displaced marker variants, preamble guard, unguarded backlog, unrelated markdown and conservative quoted-marker exclusion.
- Python compilation of the changed runtime helpers/new index test passed. Tracked-file, baseline-relative existing-file and new-file whitespace checks passed.
- Live `BACKLOG.md`: index exclusion **true**, default required-guard refusal **2**, explicit required+allow audit **0**. No backlog relocation or index rebuild performed.
- Gateway `check-autonomy-domain-preflights.py --json`: **28/28 prerequisites passed** (PR review **5**, CI fix **9**, spec implementation **8**, devnet debugging **6**), **16 unique commands / 12 command reuses**. Full output: `notes/autonomy-preflight-2026-10-11.json`.
- Structured prerequisite health: **no drift** from the previous baseline. This guard repair does not alter the four-domain preflight signatures.
- Snapshot finalization/consistency, current-date latest-pair cadence and duplicate-date checks passed (**171** dated snapshots).

## Unchanged autonomy limits

Upstream Actions reruns require a maintainer; credential/package prerequisites are not a live model verdict. Source cache `aa16bb4c1` is clean, but `generatedFixturesVerified=false`: pin generation provenance and actual fixture-case coverage during a real spec task. Grafana is unavailable in this execution environment; Panda discovery is ready, not a completed devnet diagnosis. Existing monitors retain incident ownership.

No config/scheduler/auth changes, restart, dependency install, index rebuild, workspace commit/push or external publication.

## Proposed cron summary

Hardened backlog recovery checks against displaced banners and kept guarded data out of memory indexing. Regression tests passed; all 28 prerequisite checks passed. Updated the four autonomy-gap assessments; existing CI-rerun, Grafana and fixture-verification limits remain.
