# Autonomy audit evidence — 2026-10-12

## Evidence and scope

The 2026-10-11 15:46 UTC heartbeat note records that the 14:34 cleanup archived the recovery warning with a done entry, causing the required-guard scan to fail. The warning was restored. The same banner remains in BACKLOG_ARCHIVE.md and at live BACKLOG.md line 3. Yesterday's position-independent detection repair cannot prevent deletion of the warning itself. Cleanup is LLM-driven; no script-side archive writer was found and no cron configuration was changed.

## Implemented improvement

- Added read-only `scripts/backlog/check_edit.py --before <snapshot> --after <candidate> [--json]` using the existing marker constants from `list_statuses.py`.
- Exact guard-bearing line counts must be retained; wording changes, omission and duplicate loss fail with exit 2. Position changes and ordinary edits pass. Inputs must be distinct regular files, including inode/alias checks. Input/read errors fail cleanly; output does not quote task bodies.
- Added the validation step to workspace AGENTS.md for archival/full-file replacement, before any archive/live mutation. Preserve the header/preamble too, and reconcile concurrent changes. The checker itself does not enforce those other properties, lock writers or validate task semantics. No end-to-end cleanup cron verification is claimed.

## Verification

- `python3 scripts/backlog/test_check_edit.py`: 9 tests passed, covering both markers, rewritten wording, displacement/status change, duplicates, guard-free baselines, unrelated replacement warnings, same-path/symlink/hardlink inputs, missing/directory/invalid-UTF-8 inputs, JSON/exit codes and unchanged file bytes.
- Existing `test_list_statuses.py` parser/CLI regressions and all 5 `test_backlog_guard.py` memory-index tests passed.
- Live snapshot/current comparison passed with one original and one preserved guard-bearing line. Before-snapshots: `/home/openclaw/.tmp/autonomy-audit-20261012-ypy5hz73/` (left intact).
- Gateway `check-autonomy-domain-preflights.py --json` exited 0: 28/28 prerequisite checks passed (5 PR review, 9 CI fix, 8 spec implementation, 6 devnet debugging), 16 unique commands / 12 command reuses. Structured health comparison reports no drift. Full output: `notes/autonomy-preflight-2026-10-12.json`.

## Independent review

Native child `/root/audit_guard_review` approved the design before implementation, verified the live/banner evidence and recommended the shared marker constants, exact multiplicity check and alias-aware input validation. Final code/report review: **APPROVED, no blockers**. Reviewer independently reran all nine new tests, the existing parser/CLI regressions, all five index tests, live before/current preservation and the read-only health comparison. A separate injected PermissionError failed cleanly without mutation. Reviewer checked the exact one-paragraph AGENTS.md diff against the saved baseline and independently parsed all 28 prerequisite records with the 5/9/8/6 counts and 16-command/12-reuse totals; live prerequisite commands were not rerun by the reviewer.

Compilation, baseline-relative AGENTS.md whitespace and new-file whitespace checks passed. Final snapshot consistency, latest-pair/current-date cadence and duplicate-date checks passed (172 snapshots).

## Unchanged limits

Upstream Actions reruns require a maintainer. Credential/package preflight is not a model-call verdict. Source cache `aa16bb4c1` is clean but generated fixtures remain unverified. Grafana is absent in this runtime; Panda discovery is ready, not a completed devnet diagnosis. Existing monitors retain incident ownership.

No config/scheduler/auth changes, restart, dependency install, index rebuild, workspace commit/push, skill publication or external post.
