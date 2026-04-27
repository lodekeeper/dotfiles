# Autonomy Gaps — Daily Audit

> "What would I need to do this autonomously?"
> Updated: 2026-04-27 (19th pass)

---

## Daily Audit Snapshot — 2026-04-27 (self-improvement-audit-daily, 00:46 UTC)

### PR review
- **Status:** reviewer commit-affinity checks still relied on manually interpolating `Reviewed commit: <HEAD_SHA>` text in verifier commands, which is easy to mistype/skip during fast follow-up loops. **Fix applied this cycle:** extended `scripts/review/check-review-artifacts.sh` with `--require-reviewed-head` (auto-resolves `Reviewed commit: <HEAD_SHA>` from git) plus `--head-repo <path>`, and updated `skills/lodestar-review/SKILL.md` Step 4.1 to use the new deterministic guard.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-26 (self-improvement-audit-daily, 00:45 UTC)

### PR review
- **Status:** reviewer artifact freshness checks existed, but they still accepted files from the wrong head commit when those files were recently regenerated. **Fix applied this cycle:** extended `scripts/review/check-review-artifacts.sh` with repeatable `--require-text` markers and updated `skills/lodestar-review/SKILL.md` to stamp/verify `Reviewed commit: <HEAD_SHA>` in each reviewer artifact.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-25 (self-improvement-audit-daily, 00:44 UTC)

### PR review
- **Status:** reviewer artifact presence/size checks existed, but stale files from prior review rounds could still pass and be mistaken as fresh output. **Fix applied this cycle:** extended `scripts/review/check-review-artifacts.sh` with `--max-age-minutes` stale-artifact enforcement and updated `skills/lodestar-review/SKILL.md` Step 4.1 to run the verifier with age bounds (`--max-age-minutes 180`).

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-24 (self-improvement-audit-daily, 00:44 UTC)

### PR review
- **Status:** transport-failure fallback required reviewer artifacts, but there was no one-command guard to verify all expected reviewer files exist before synthesis. **Fix applied this cycle:** added `scripts/review/check-review-artifacts.sh` (checks `pr-<PR>-<agent-id>.md` presence/size and supports `--allow-empty-no-findings`) and wired its usage into `skills/lodestar-review/SKILL.md` Step 4.1 so missing reviewer outputs are caught immediately.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-23 (self-improvement-audit-daily, 00:44 UTC)

### PR review
- **Status:** reviewer-result transport can fail (completion pings without full findings payload), which can silently drop review input in follow-up loops. **Fix applied this cycle:** updated `skills/lodestar-review/SKILL.md` to require durable per-reviewer report artifacts in `notes/review-reports/pr-<PR>-<agent-id>.md` and added a mandatory transport-failure fallback step (read artifact/re-run missing reviewer before synthesis).

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-22 (self-improvement-audit-daily, 00:44 UTC)

### PR review
- **Status:** carry-forward status prefill could copy prior-cycle "implemented this cycle" wording into new snapshots, which created stale self-claims in fresh daily entries. **Fix applied this cycle:** `scripts/notes/prepend-autonomy-audit-snapshot.py` now sanitizes change-event wording (`fix applied` / `implemented` / `added` / `updated`) during `--carry-forward-status` and falls back to section steady-state status templates.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-21 (self-improvement-audit-daily, 00:40 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; implemented a close-out cadence guard in `scripts/notes/close-autonomy-audit.sh` so missing-day drift is checked even when someone runs close-out directly without preflight.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-20 (self-improvement-audit-daily, 00:40 UTC)

### PR review
- **Status:** no new PR-review blocker discovered this cycle; latest-pair cadence noise is now naturally clear with consecutive snapshots (`2026-04-19` → `2026-04-20`). Implemented a stricter preflight control in `run-autonomy-audit-preflight.sh`: new `--strict-cadence` mode hard-fails on missing-day gaps instead of advisory-only warnings.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-19 (self-improvement-audit-daily, 00:39 UTC)

### PR review
- **Status:** audit-workflow integrity blocker found and fixed this cycle: duplicate snapshot dates could accumulate silently and drift `> Updated:` pass counts out of sync. Added a duplicate-snapshot guard to `run-autonomy-audit-preflight.sh` plus `--dedupe-apply` for one-command cleanup, then removed the stale duplicate `2026-03-15` snapshot block so preflight/finalize checks are deterministic again. Cadence guard still surfaces the historical 2026-03-20→2026-04-18 gap, but now does so explicitly on every run.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-04-18 (self-improvement-audit-daily, 00:38 UTC)

### PR review
- **Status:** audit-workflow blocker found and fixed this cycle: preflight cadence checks only compared the latest snapshot pair, so long outages after the latest snapshot could be silently missed. Added current-date freshness enforcement (`--require-current`) plus deterministic `--reference-date` support in `check-autonomy-audit-cadence.py`, and wired both into `run-autonomy-audit-preflight.sh`.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---
## Daily Audit Snapshot — 2026-03-20 (self-improvement-audit-daily, 23:46 UTC)

### PR review
- **Blocker:** follow-up guard wrapper handled GitHub delta sync + metadata drift, but stale unresolved critical/major findings were still a separate manual command, so reviewers could miss aging blockers in re-review loops.
- **Fix applied this cycle:** expanded `scripts/review/run-followup-guards.sh` into a 3-step guard:
  - runs `track-findings.py sync-gh`,
  - runs `check-pr-metadata-drift.py` and stores `pr-<PR>-metadata-drift.md`,
  - runs `track-findings.py stale --days 7 --severity critical major` and stores `pr-<PR>-stale-findings.md`.
- Added `--fail-on-stale`, `--stale-days`, and `--skip-stale-check` controls, and updated `skills/lodestar-review/SKILL.md` so this is the default follow-up path.

### CI fix
- **Status:** retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.

---

## Daily Audit Snapshot — 2026-03-19 (self-improvement-audit-daily, 23:46 UTC)

### PR review
- **Blocker (previous cycle):** PR metadata drift checker existed, but follow-up review workflow docs did not require running it before re-review.
- **Fix applied this cycle:** wired a mandatory metadata-drift guard step into `skills/lodestar-review/SKILL.md` Finding Resolution Tracking workflow:
  - run `scripts/github/check-pr-metadata-drift.py` on follow-up commits,
  - persist report to `notes/review-reports/pr-<PR>-metadata-drift.md`,
  - update title/body via `gh pr edit` when exit code `2` signals drift.

### CI fix
- **Status:** retry telemetry + `logs-unavailable` fallback path remain healthy; no new blocker discovered this cycle.

### Spec implementation
- **Status:** advisor timeout fallback policy remains codified and operational; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage/correlator/incident bundle path remains healthy; no new blocker discovered this cycle.

---

## Daily Audit Snapshot — 2026-03-18 (self-improvement-audit-daily, 23:46 UTC)

### PR review
- **Status:** finding tracker + stale escalation path are healthy; no new blocker discovered this cycle.

### CI fix
- **Status:** `logs-unavailable` fallback wiring is operational (auto-fetch + reclassification metadata); no new blocker discovered this cycle.

### Spec implementation
- **Blocker:** architecture consult loops can stall on repeated `gpt-advisor` `thinking: xhigh` timeouts, delaying convergence and wasting audit cycles.
- **Fix applied this cycle:** updated `skills/dev-workflow/SKILL.md` with a required timeout fallback policy:
  - start with `xhigh`,
  - allow one tighter retry max,
  - then fallback to `thinking: high` with practical scope,
  - log each round outcome in `TRACKER.md` for resumable context.

### Devnet debugging
- **Status:** triage/correlator/incident bundle path remains healthy; no new blocker discovered this cycle.

---

## Daily Audit Snapshot — 2026-03-17 (self-improvement-audit-daily, 23:46 UTC)

### PR review
- **Status:** finding tracker + stale-escalation cron path are operational; no new blocker discovered this cycle.

### CI fix
- **Blocker:** `logs-unavailable` CI classifications are still slow to triage because there was no one-command fallback to pull failed/full run logs into a local artifact.
- **Fix applied this cycle:** added `scripts/ci/fetch-run-logs.sh <run-id> [--repo owner/repo] [--output <path>]`.
  - tries `gh run view --log-failed` first, then falls back to `--log`,
  - saves logs under `tmp/ci-logs/` by default,
  - prints fetch mode + line/byte counts for quick auditability.

### Spec implementation
- **Status:** extraction + compliance + vector-readiness gates are operational; no new blocker discovered this cycle.

### Devnet debugging
- **Status:** triage, correlator, incident bundle, and startup helper scripts are operational; no new blocker discovered this cycle.

---

## Daily Audit Snapshot — 2026-03-16 (self-improvement-audit-daily, 23:46 UTC)

### PR review
- **Status:** stale-finding weekly escalation cron is now live and reporting correctly; no new blocker discovered this cycle.

### CI fix
- **Status:** retry telemetry + rolling-window degradation detection are operational; no new blocker discovered this cycle.

### Spec implementation
- **Blocker (previous cycle):** test-vector freshness checks were implicit (easy to skip).
- **Fix applied this cycle:** added `scripts/spec/check-test-vector-readiness.sh` and wired it into `skills/dev-workflow/SKILL.md` spec-vector gate.
  - verifies `~/consensus-specs/tests/` exists and is populated,
  - reports `tests/` recency based on git history,
  - supports `--require-fresh` to hard-fail when vectors are stale.

### Devnet debugging
- **Status:** triage, correlator, incident bundle, and startup helper scripts are operational; no new blocker discovered this cycle.

---

## Daily Audit Snapshot — 2026-03-15 (self-improvement-audit-daily, 23:46 UTC)

### PR review
- **Blocker:** stale-finding report exists, but no scheduled escalation wrapper is wired yet.
- **Proposed fix:** add a weekly cron around `scripts/review/stale-findings-report.sh` that only emits when stale critical/major findings are present.

### CI fix
- **Blocker (previous cycle):** retry telemetry existed but no threshold-based sustained-degradation detection.
- **Fix applied this cycle:** added rolling-window escalation in `scripts/ci/auto_fix_flaky.py`:
  - persists `scan_history` with retry telemetry per run,
  - computes `llm_retry_escalation` over configurable window/thresholds,
  - emits escalation status in clean/failure JSON output,
  - stores escalation snapshot under `last_scan` for tracker visibility.
- **Workflow update:** updated `scripts/ci/CRON_PROMPT.md` to require explicit warning when `llm_retry_escalation.degraded=true`.

### Spec implementation
- **Status:** extraction + compliance gates operational; no new gap discovered this cycle.

### Devnet debugging
- **Status:** triage, correlator, and incident bundle scripts operational; no new gap discovered this cycle.

---

## Daily Audit Snapshot — 2026-03-14 (self-improvement-audit-daily)

### PR review
- **Blocker:** stale-finding query exists, but no automation path currently opens/refreshes a follow-up backlog item when stale critical findings are detected.
- **Proposed fix:** add a lightweight cron wrapper around `track-findings.py stale --fail-on-match` that writes/updates a single backlog-facing report.

### CI fix
- **Blocker:** retry telemetry now exists in detector output, but no threshold-based escalation policy is codified (e.g., retry_count spikes over rolling runs).
- **Proposed fix:** add a tracker-level threshold check (`llm_retry_count` / `llm_retry_wait_s`) with explicit warning output when sustained degradation is detected.

### Spec implementation
- **Blocker (previous cycle):** compliance checks were split across multiple commands and easy to run inconsistently.
- **Fix applied this cycle:** added one-command wrapper `scripts/spec/prepr-compliance-gate.sh` to run report generation + metadata checks and emit a single pass/fail summary.

### Devnet debugging
- **Blocker:** incident packaging is still manual (logs + metrics + timeline + environment metadata in one bundle).
- **Proposed fix:** add `scripts/debug/build-incident-bundle.sh` to produce one timestamped markdown bundle for sharing in topic threads/PRs.

---

## Daily Audit Snapshot — 2026-03-13 (self-improvement-audit-daily)

### PR review
- **Blocker (previous cycle):** no explicit escalation query for stale unresolved findings.
- **Fix applied this cycle:** added `python3 scripts/review/track-findings.py stale <PR>` (+ `--severity`, `--days`, `--use-created`, `--fail-on-match`) and documented it in `skills/lodestar-review/SKILL.md`.

### CI fix
- **Blocker:** retry/backoff exists, but concise cron summaries still do not surface retry telemetry (hard to spot degraded API health quickly).
- **Proposed fix:** include `retry_count`, `retry_wait_s`, and `retry_after_seen` in detector summary/tracker line items.

### Spec implementation
- **Blocker:** compliance artifact checks now exist for tracker + PR body, but there is no single pre-PR wrapper that runs the full compliance bundle and emits one pass/fail summary.
- **Proposed fix:** add `scripts/spec/prepr-compliance-gate.sh` to run checker + artifact-presence check and produce one markdown summary block for PR descriptions.

### Devnet debugging
- **Blocker:** incident packaging is still manual (logs + metrics + timeline + environment metadata in one bundle).
- **Proposed fix:** add `scripts/debug/build-incident-bundle.sh` to produce one timestamped markdown bundle for sharing in topic threads/PRs.

---

## Daily Audit Snapshot — 2026-03-12 (self-improvement-audit-daily)

### PR review
- **Blocker:** reviewer findings are tracked, but there is still no explicit escalation policy for stale unresolved findings (e.g., open >7 days with no author response).
- **Proposed fix:** add a `track-findings.py stale` command (or cron wrapper) that flags unresolved high-severity findings older than a threshold.

### CI fix
- **Blocker:** LLM retry/backoff exists, but retry telemetry is still not surfaced in concise cron summaries (hard to spot degraded API health quickly).
- **Proposed fix:** include retry-count/backoff stats in the final detector summary line and tracker notes for each run.

### Spec implementation
- **Blocker:** compliance artifacts were generated but still easy to omit from tracker/PR write-ups.
- **Fix applied this cycle:** updated `skills/dev-workflow/SKILL.md` to require recording compliance artifacts in `TRACKER.md` and including a dedicated "Spec Compliance" block in PR descriptions; added reusable template `notes/spec-compliance-pr-block.md`.
- **Next focus:** add lightweight lint/check script that validates tracker + PR body contain compliance artifact references before merge.

### Devnet debugging
- **Blocker:** incident packaging is still manual (logs + metrics + timeline + environment metadata in one bundle).
- **Proposed fix:** add `scripts/debug/build-incident-bundle.sh` to produce one timestamped markdown bundle for sharing in topic threads/PRs.

---

## 1. PR Review

### Current State
Multi-persona review via `lodestar-review` skill. Parallel spawning, persona prompts, inline GitHub comment posting. Works well when diff scope is clear.

### Gaps

#### ~~🔴 Reviewer false positives~~ ✅ FIXED (2026-03-08)
~~Sub-agents sometimes flag files **not in the PR diff** (confirmed on PR #8993: `dataColumns.ts`, `gloas.ts` flagged but not changed). This wastes effort and can lead to spurious follow-up commits.~~

**Fix applied:** mandatory false-positive guard in `lodestar-review/SKILL.md`:
- get `git diff --name-only` before acting on findings,
- include changed-file list in reviewer prompts,
- discard findings for files outside the diff.

#### ~~🟡 No reviewer task pre-injection of changed-file scope~~ ✅ FIXED (2026-03-08)
~~Reviewer prompts don't currently include the file list — so reviewers have to infer scope from the diff content, which they sometimes miss.~~

**Fix applied:** `lodestar-review/SKILL.md` Step 3 spawn task template now explicitly includes the `## Files Changed in This PR` block (from Step 1.5) between the persona and the diff, with the "IMPORTANT: Only flag issues in the files listed above" instruction baked into the template literal.

#### ~~🟢 No automated convergence triage~~ ✅ FIXED (2026-03-08)
~~When multiple reviewers flag the same issue, I manually merge.~~

**Fix applied:** `scripts/review/track-findings.py dedup <PR>` groups open findings by file+line proximity (±5 lines), showing which locations are flagged by multiple reviewers. Also added `import --markdown` to parse free-form reviewer output into structured findings, and `check --changed-files` to flag findings on files touched by a new commit.

#### ~~🟡 No stale unresolved-finding escalation query~~ ✅ FIXED (2026-03-13)
~~Reviewer findings are tracked, but there was no fast way to answer: "which open critical/major findings are stale (>7d)?"~~

**Fix applied:** extended `scripts/review/track-findings.py` with `stale` command:
- `track-findings.py stale <PR>` defaults to open `critical|major` findings older than 7 days (`updated` timestamp)
- supports `--severity`, `--days`, `--use-created`, and `--fail-on-match` (for cron/automation wrappers)
- wired usage into `skills/lodestar-review/SKILL.md` follow-up workflow

#### ~~🔴 No review finding resolution tracking~~ ✅ FIXED (2026-03-08)
~~After posting a review, when the author pushes new commits, I have no system for tracking which findings got addressed. I manually re-read everything.~~

**Fix applied:** added `scripts/review/track-findings.py` workflows (`check`, `resolve`, `sync-gh`, `dump`) for explicit re-verification after follow-up commits.

---

## 2. CI Fix

### Current State
CI autofix cron (`573d18ec`) runs hourly, classifies flaky failures, applies pattern-based fixes via Codex, opens PRs against `unstable`. Pattern library covers: shutdown-race, peer-count-flaky, timeout, vitest-crash.

### Gaps

#### ~~🟡 No auto-linkage to existing GitHub issues~~ ✅ FIXED (2026-03-07)
~~When CI autofix opens a fix PR, it doesn't check whether an open issue already tracks that failure, and doesn't reference/close it.~~

**Fix applied:** `CRON_PROMPT.md` Step 2 now has an "Issue linkage (mandatory)" step (Step 4): search `gh issue list --search "<test-name> in:title,in:body is:issue state:open"`, if hits found post a PR comment linking them, log linked issue IDs in the tracker update.

#### ~~🟡 Pattern-based classifier misses semantic failures~~ ✅ FIXED (2026-03-07)
~~The classifier matches keyword patterns. Failures with novel error messages or new test paths fall through unclassified.~~

**Fix applied:** Added `classify_with_llm()` to `auto_fix_flaky.py`. When keyword classifier returns `unknown-failure`, it now calls `gpt-4o-mini` with a structured system prompt and 13-category taxonomy. Returns `classification`, `confidence`, `fixable`, and `fix_hint`. Falls back gracefully if OPENAI_API_KEY is missing or call fails. `--no-llm` flag available for offline use.

#### ~~🟢 No confidence score in fix quality~~ ✅ FIXED (2026-03-07)
~~Codex applies fixes but there's no check on whether the fix actually addresses root cause vs. masking (e.g., bumping timeout). This leads to PRs that merge but don't fix the underlying issue.~~

**Fix applied:** Added `confidence` field (high/medium/low based on classification source) and `fix_confidence` field (`root-cause` | `likely-root-cause` | `masking-risk` | `unknown`) to all findings in `auto_fix_flaky.py`. `CRON_PROMPT.md` updated: if `fix_confidence` is `masking-risk`/`unknown`, cron agent must add PR comment flagging it for human review.

---

## 3. Spec Implementation

### Current State
Use `dev-workflow` skill for multi-agent development. Codex/Claude CLI for implementation. `~/consensus-specs` available locally. `scripts/pre-validate.mjs` for basic pre-flight checks.

### Gaps

#### ~~🔴 No automated spec section extraction~~ ✅ FIXED (2026-03-07)
~~I manually grep `~/consensus-specs` for relevant pseudocode when implementing. This is slow and error-prone (easy to miss related functions/types across files).~~

**Fix applied:** added `scripts/spec/extract-spec-section.sh` to search spec markdown and follow symbol-import chains for related definitions.

#### ~~🔴 No LLM spec compliance check (new — 2026-03-08)~~ ✅ FIXED (2026-03-09)
Before this was implemented, spec-function ports could ship without a structured pseudocode-vs-TS parity check, relying on slow and error-prone manual reading.

**Fix applied:** `scripts/spec/check-compliance.py <spec-function> <ts-file> <ts-function>` now:
- Extracts the pseudocode block from `~/consensus-specs`
- Compares it against the TS implementation with an LLM pass
- Emits a diff-style compliance report: implemented ✅ / missing ⚠️ / diverged ❌

#### ~~🟡 No test-vector auto-download awareness~~ ✅ FIXED (2026-03-16)
~~When implementing spec functions, I sometimes forget to run against official test vectors. The vectors live in `~/consensus-specs/tests/` but need a separate download step.~~

**Fix applied:** added `scripts/spec/check-test-vector-readiness.sh` and wired it into the `skills/dev-workflow/SKILL.md` spec-vector gate.
- validates `~/consensus-specs/tests/` exists and has vector files,
- reports staleness of `tests/` from git history,
- supports `--require-fresh` to fail fast when vectors are too old.

#### ~~🟢 No implementation checklist per fork type~~ ✅ FIXED (2026-03-07)
~~Each fork (Gloas, Fulu, etc.) has different patterns: new SSZ types, new gossip topics, new reqresp methods, new fork-choice fields, new API endpoints. No single checklist ensures all are covered.~~

**Fix applied:** added `notes/fork-implementation-checklist.md` covering fork surfaces, test matrix, interop gates, and PR readiness criteria.

---

## 4. Devnet Debugging

### Current State
`grafana-loki` skill for log queries. `join-devnet` skill for local beacon node. `kurtosis-devnet` skill for full multi-client devnets. `local-mainnet-debug` skill for mainnet simulation. Good tooling, but each debugging session starts from scratch.

### Gaps

#### ~~🔴 No multi-node log correlator~~ ✅ FIXED (2026-03-09)
When debugging consensus failures across a devnet, logs from 4-8 nodes all matter. Today I query Loki once per node and manually cross-reference timestamps. A script that fetches logs from multiple nodes in parallel, merges + sorts by timestamp, and highlights consensus-relevant events (proposal, attestation, fork-choice updates) would turn a 30-min investigation into a 5-min one.

**Fix applied:** `scripts/debug/correlate-logs.sh [node1] [node2...] --from <ts> --to <ts>` now:
- Queries Loki for each node in parallel
- Merges results sorted by timestamp
- Highlights lines matching `/fork_choice|attestation|proposal|head_block|finalized/`
- Outputs a unified timeline with node-prefixed lines

#### ~~🔴 No scripted first-5-minutes diagnostic~~ ✅ FIXED (2026-03-09)
~~Every devnet debugging session starts with the same manual sequence: check zombie processes, check ports, check Loki for recent errors, compare Grafana metrics, check peer count. This takes 10-15 minutes every time.~~

**Fix applied:** added `scripts/debug/devnet-triage.sh` for one-command first-pass diagnostics (processes, ports, Loki errors, Prometheus probes, restart hints).

#### ~~🟡 No structured debugging session template~~ ✅ FIXED (2026-03-07)
~~When investigating complex issues (like feat4 QUIC crashes), I accumulate evidence across many tool calls without a clear structure. Later it's hard to reconstruct what was ruled out and why.~~

**Fix applied:** created `notes/debug-session-template.md` and integrated it into investigation workflow.

#### ~~🟡 Mixed-peer devnet startup is still manual~~ ✅ FIXED (2026-03-08)
~~Spinning up a mixed-peer devnet (e.g., Lodestar B2 + C2 nodes against ePBS devnet) requires multiple manual steps and ad-hoc configuration.~~

**Fix applied:** codified EPBS devnet-0 startup flow in `scripts/devnet/start-epbs-devnet.sh` for repeatable bring-up.

---

## Improvements Implemented This Cycle

### ✅ Reviewer HEAD-marker auto-resolution guard added (2026-04-27)
Extended `scripts/review/check-review-artifacts.sh` with built-in reviewed-commit marker resolution so follow-up verifier commands no longer rely on manual SHA interpolation.
- new CLI option: `--require-reviewed-head` (requires marker `Reviewed commit: <HEAD_SHA>`)
- new CLI option: `--head-repo <path>` (deterministic HEAD source; defaults to current directory)
- verifier now fails fast if HEAD cannot be resolved from the selected repo
- updated `skills/lodestar-review/SKILL.md` Step 4.1 quick verifier to use `--require-reviewed-head --head-repo /absolute/path/to/repo`

**Rationale:** keeps commit-affinity checks deterministic in autonomous follow-up loops and reduces accidental false passes from hand-written SHA marker strings.

### ✅ Reviewer-artifact commit-affinity guard added (2026-04-26)
Extended `scripts/review/check-review-artifacts.sh` with repeatable `--require-text <value>` markers so artifact validation can enforce run-specific metadata (for example, exact head SHA markers).
- new repeatable CLI option: `--require-text "..."`
- verifier now prints required markers and fails with exit `2` when a marker is missing (`missing_text=<count>` in summary)
- updated `skills/lodestar-review/SKILL.md` to require reviewer artifacts to include `Reviewed commit: <HEAD_SHA>` and to verify that marker during Step 4.1

**Rationale:** age checks catch stale files, but they do not prove the artifact belongs to the current head commit. Marker-based validation blocks fresh-but-wrong artifacts from previous review rounds.

### ✅ Reviewer-artifact freshness guard added (2026-04-25)
Extended `scripts/review/check-review-artifacts.sh` so the verifier can reject stale reviewer artifacts with a new `--max-age-minutes <n>` option.
- adds stale-age validation via artifact mtime (summary now reports `stale=<count>`)
- keeps existing missing/invalid checks and `--allow-empty-no-findings` behavior
- updated `skills/lodestar-review/SKILL.md` Step 4.1 quick verifier to include `--max-age-minutes 180` and stale-artifact guidance

**Rationale:** presence checks alone can pass old reviewer files from a previous diff. Age-bounding the artifact set ensures synthesis uses fresh findings from the current review round.

### ✅ Reviewer-artifact completeness guard script added (2026-04-24)
Added `scripts/review/check-review-artifacts.sh` and updated `skills/lodestar-review/SKILL.md` to call it during transport-failure fallback before synthesis.
- validates expected reviewer artifacts: `notes/review-reports/pr-<PR>-<agent-id>.md`
- flags missing/undersized files with exit `2`
- supports `--allow-empty-no-findings` so intentional "No findings" reports pass

**Rationale:** durable artifacts only help if every expected reviewer actually wrote one. This turns that check into a fast deterministic guard instead of a manual file-by-file scan.

### ✅ Durable reviewer-artifact fallback added to lodestar-review workflow (2026-04-23)
Updated `skills/lodestar-review/SKILL.md` to harden PR-review autonomy against flaky sub-agent result transport:
- reviewer spawn tasks now include a mandatory durable-output contract (`notes/review-reports/pr-<PR>-<agent-id>.md`),
- reviewers must always write a report artifact (including explicit "no findings" cases),
- synthesis workflow now includes a mandatory transport-failure fallback step (read artifact directly / re-run missing reviewer before proceeding).

**Rationale:** prevents silent loss of reviewer findings when completion announces arrive without full payloads, preserving deterministic review loops without depending on session-message transport alone.

### ✅ Carry-forward status sanitizer added to autonomy-audit snapshot scaffolding (2026-04-22)
Updated `scripts/notes/prepend-autonomy-audit-snapshot.py` so `--carry-forward-status` no longer blindly copies prior-cycle change-event language.
- Added change-event pattern detection (`fix applied this cycle`, `implemented`, `added`, `updated`).
- When detected, carry-forward now uses section-specific steady-state status templates instead of stale prior-cycle claims.
- Preserves normal carry-forward behavior for stable "no new blocker" status lines.

**Rationale:** daily snapshot scaffolding should accelerate status updates without accidentally copying yesterday’s "I implemented X this cycle" wording into today’s audit entry.

### ✅ Close-out cadence guard added to autonomy-audit wrapper (2026-04-21)
Updated `scripts/notes/close-autonomy-audit.sh` so daily close-out now runs `check-autonomy-audit-cadence.py` with `--require-current` against the selected audit date before rendering output.
- Added `--strict-cadence` to hard-fail on missing-day gaps when desired.
- Added `--skip-cadence-check` for explicit manual override/backfill flows.
- Preserved existing `NO_REPLY` behavior when finalize reports no meaningful delta.

**Rationale:** preflight already enforced cadence, but direct close-out calls could bypass that signal. This closes the workflow gap by keeping freshness/cadence checks on both entry and exit paths.

### ✅ Optional strict cadence enforcement added to autonomy-audit preflight (2026-04-20)
Updated `scripts/notes/run-autonomy-audit-preflight.sh` with a new `--strict-cadence` flag:
- keeps existing default behavior (cadence gaps are advisory warnings),
- allows strict runs to hard-fail immediately when `check-autonomy-audit-cadence.py` reports missing-day gaps,
- preserves deterministic preflight flow while giving scheduled runs a policy switch for stricter discipline.

**Rationale:** turns cadence handling from one-size-fits-all into an explicit policy choice, so autonomous runs can enforce daily-audit continuity when needed instead of relying on warning-only behavior.

### ✅ Duplicate-snapshot guard wired into autonomy-audit preflight (2026-04-19)
Updated `scripts/notes/run-autonomy-audit-preflight.sh` with a new step-zero duplicate check:
- runs `dedupe-autonomy-audit-snapshots.py` before consistency/cadence checks,
- fails fast when older duplicate snapshot dates exist,
- supports `--dedupe-apply` for one-command cleanup during preflight.

Also applied the cleanup to `notes/autonomy-gaps.md` this cycle (removed the stale duplicate `2026-03-15` block), then re-synced `> Updated:` metadata so pass counts match snapshot count.

**Rationale:** prevents silent drift in audit history where duplicate date blocks break pass-count metadata and make finalize/preflight checks flaky.

### ✅ Autonomy-audit freshness guard added to cadence checks (2026-04-18)
Updated `scripts/notes/check-autonomy-audit-cadence.py` with:
- `--require-current` to enforce latest-snapshot freshness against a reference date,
- `--reference-date YYYY-MM-DD` for deterministic backfill/manual runs.

Updated `scripts/notes/run-autonomy-audit-preflight.sh` to always run cadence checks with `--require-current`, and to pass the selected `--date` as `--reference-date` so preflight detects long audit outages instead of only comparing the latest two snapshot headings.

**Rationale:** closes a workflow-integrity gap where a long pause in daily audits could go unnoticed once historical snapshot spacing looked clean.

### ✅ Follow-up stale-finding guard fused into wrapper + skill docs (2026-03-20)
Expanded `scripts/review/run-followup-guards.sh` and refreshed `skills/lodestar-review/SKILL.md` so follow-up rounds now run three checks in one command:
- `track-findings.py sync-gh` delta sync,
- `check-pr-metadata-drift.py` artifact generation,
- `track-findings.py stale` artifact generation for unresolved critical/major findings.

Added wrapper controls: `--fail-on-stale`, `--stale-days`, `--skip-stale-check`, `--stale-use-created`, and default stale artifact path `notes/review-reports/pr-<PR>-stale-findings.md`.

**Rationale:** removes the last manual follow-up step where stale blockers could be missed during re-review, while keeping strict mode opt-in for teams that want stale findings to hard-block.

### ✅ Review-loop follow-up guard wrapper added (2026-03-20)
Created `scripts/review/run-followup-guards.sh` and wired usage into `skills/lodestar-review/SKILL.md`.
- runs `track-findings.py sync-gh` and `check-pr-metadata-drift.py` in one command,
- writes metadata artifact to `notes/review-reports/pr-<PR>-metadata-drift.md` by default,
- preserves exit-code semantics (`0` pass, `2` drift) and prints an explicit `gh pr edit` reminder command when drift is detected.

**Rationale:** closes the final follow-up ergonomics gap by replacing a fragile two-command manual sequence with a single repeatable guard command for re-review loops.

### ✅ Review-loop metadata drift guard wired into lodestar-review skill (2026-03-19)
Updated `skills/lodestar-review/SKILL.md` Finding Resolution Tracking workflow with a mandatory follow-up step:
- run `scripts/github/check-pr-metadata-drift.py --pr <PR>` before posting re-review,
- persist output to `notes/review-reports/pr-<PR>-metadata-drift.md`,
- treat exit code `2` as required metadata update (`gh pr edit`) before requesting re-review.

**Rationale:** closes the process gap between having the checker script and actually enforcing it in follow-up review loops.

### ✅ PR metadata drift guard script added (2026-03-19)
Created `scripts/github/check-pr-metadata-drift.py`:
- pulls live PR metadata + file list via `gh pr view --json title,body,changedFiles,files`,
- scans title/body for stale scope signals (path references not in current diff, narrow-scope wording vs broad file count),
- compares semver claims in metadata against semvers added/removed in the current patch,
- emits a concise markdown report and exits `2` on drift signals for cron/review-loop integration.

**Rationale:** catches title/body drift after follow-up commits before re-review, reducing mismatches like stale version claims or outdated scope descriptions.

### ✅ Spec architecture-consult timeout fallback policy codified (2026-03-18)
Updated `skills/dev-workflow/SKILL.md` Phase 1 with a required advisor fallback path:
- start architecture rounds with `gpt-advisor` `thinking: xhigh`,
- allow one tighter `xhigh` retry max on timeout/empty output,
- fallback to `thinking: high` instead of repeated `xhigh` loops,
- record round outcome metadata in `notes/<feature>/TRACKER.md`.

**Rationale:** converts an ad-hoc timeout workaround into a deterministic workflow rule, reducing stalled spec/design loops and preserving context across sessions.

### ✅ CI `logs-unavailable` fallback wiring added (2026-03-18)
Updated `scripts/ci/auto_fix_flaky.py` so `logs-unavailable` findings now automatically trigger `scripts/ci/fetch-run-logs.sh <run-id>` once per run, then:
- persist fallback metadata (`logs_fallback_status`, `logs_fallback_artifact`, `logs_fallback_command`, `logs_fallback_error`, `logs_fallback_reclassified`) into both detector findings and tracker entries,
- reuse fetched artifact logs for immediate re-classification when available.

**Rationale:** closes the handoff gap between detection and follow-up triage by attaching the exact log artifact path/command directly to the finding instead of leaving logs retrieval as a separate manual step.

### ✅ CI run-log fallback fetcher added (2026-03-17)
Created `scripts/ci/fetch-run-logs.sh`:
- fetches run logs by run ID with `gh run view --log-failed` first and `--log` fallback,
- supports explicit `--repo` and `--output` options,
- writes local artifacts under `tmp/ci-logs/` by default,
- prints deterministic output metadata (mode + line/byte counts) for tracker notes.

**Rationale:** closes the CI triage gap for `logs-unavailable` findings by making fallback log acquisition one command instead of ad-hoc/manual command hunting.

### ✅ Autonomy-gaps consistency guard added (2026-03-17)
Created `scripts/notes/check-autonomy-gaps-consistency.py`:
- parses `### Gaps` items and `## Improvements Implemented This Cycle` entries,
- flags contradictory status when the same gap appears both open and fixed,
- flags path-level contradictions when a script/doc path appears in both an open gap and an implemented improvement,
- exits with code `2` on contradictions for cron-friendly enforcement.

**Rationale:** prevents drift where autonomy-gap items are marked implemented but remain open elsewhere in the same file.

### ✅ Spec test-vector readiness gate added (2026-03-16)
Added `scripts/spec/check-test-vector-readiness.sh` and wired it into `skills/dev-workflow/SKILL.md`.
- validates local `~/consensus-specs/tests/` presence with a real sample file check,
- reports `tests/` freshness from git history,
- supports `--require-fresh` for fail-fast enforcement in pre-PR spec workflows.

**Rationale:** closes the last spec-vector gap where test vectors were available but freshness checks were manual/easy to skip.

### ✅ CI retry rolling-window escalation added (2026-03-15)
Updated `scripts/ci/auto_fix_flaky.py` to convert per-run retry telemetry into a sustained-health signal:
- persists bounded `scan_history` entries (`scanned_at`, `new_failures`, `llm_retry_telemetry`)
- computes `llm_retry_escalation` with configurable rolling-window thresholds for retry count, retry wait, and `Retry-After` frequency
- emits escalation data in detector JSON (`status=clean` and `status=failures_found`)
- stores escalation snapshot under `last_scan.llm_retry_escalation` when `--apply` is used

Also updated `scripts/ci/CRON_PROMPT.md` so cron summaries must explicitly warn when escalation is degraded.

**Rationale:** turns isolated retry counters into actionable trend detection so persistent API degradation is surfaced automatically instead of being noticed ad hoc.

### ✅ PR stale-finding cron wrapper added (2026-03-15)
Created `scripts/review/stale-findings-report.sh`:
- Scans all tracked PRs in findings directory for stale unresolved findings
- Supports `--days`, `--severity`, `--prs`, and `--output` options
- Exit code 2 when stale findings detected; writes timestamped markdown report to `notes/review-reports/`
- Reports include per-PR sections with stale finding details and resolution instructions
- Designed for cron usage: zero output (exit 0) when clean, actionable report when stale

**Rationale:** converts a manual "remember to check old findings" task into an automatable health signal that can feed into backlog or topic escalation.

### ✅ Devnet incident bundle script added (2026-03-15)
Created `scripts/debug/build-incident-bundle.sh` to produce one timestamped markdown artifact combining:
- environment metadata (host/tooling + repo branch/commit)
- `devnet-triage.sh` output (process, ports, logs, metrics, restart hints)
- optional multi-node timeline via `correlate-logs.sh` when peers + Grafana token are available
- structured incident-notes checklist for root-cause write-up

Also tightened `scripts/debug/devnet-triage.sh` process filtering so bundle generation commands are not misreported as node processes.

### ✅ One-command pre-PR compliance gate added (2026-03-14)
Created `scripts/spec/prepr-compliance-gate.sh` and wired usage into `skills/dev-workflow/SKILL.md`:
- accepts repeatable `--check "spec_query|ts_file|ts_symbol|report_out"` tuples
- runs `check-compliance.py` for each tuple and captures verdict/confidence
- runs `check-compliance-artifacts.sh` for tracker + PR body metadata enforcement
- emits one markdown pass/fail summary (stdout + optional `--summary-out`) including a reusable PR block snippet

**Rationale:** replaces a fragile multi-command sequence with one deterministic gate, so spec-compliance evidence is generated and validated consistently before PR/re-review.

### ✅ CI retry telemetry surfaced in detector output + tracker entries (2026-03-14)
Updated `scripts/ci/auto_fix_flaky.py` to expose retry/backoff health signals directly in the detector JSON and per-finding tracker line items:
- top-level summary now includes `llm_retry_count`, `llm_retry_wait_s`, and `llm_retry_after_seen`
- each finding + persisted tracker entry now carries per-classification retry telemetry (`llm_retry_*` fields)
- `--apply` runs now persist `last_scan.llm_retry_telemetry` in `memory/unstable-ci-tracker.json`

**Rationale:** makes degraded LLM/API health visible in concise cron summaries instead of hiding retries in stderr-only logs.

### ✅ Stale unresolved-finding escalation command added (2026-03-13)
Updated `scripts/review/track-findings.py` with `stale` command:
- lists open findings older than a threshold (default: `critical|major`, `updated >= 7d`)
- supports severity/age tuning (`--severity`, `--days`) and timestamp mode (`--use-created`)
- supports automation mode (`--fail-on-match`) for non-zero exit when stale findings exist
- updated `skills/lodestar-review/SKILL.md` workflow to run this in follow-up rounds

**Rationale:** converts stale-review escalation from a manual judgment call into a one-command query that can be scripted and monitored.

### ✅ Compliance artifact presence check script + workflow gate added (2026-03-13)
Created `scripts/spec/check-compliance-artifacts.sh` and wired it into `skills/dev-workflow/SKILL.md` Phase 5:
- verifies `notes/<feature>/TRACKER.md` has a populated `## Spec Compliance Artifacts` section
- verifies PR body has a populated `## Spec Compliance` section
- enforces either `spec-compliance-*.md` references **or** explicit `N/A` + reason
- enforces `Verdict:` when an artifact file is referenced

**Rationale:** this closes the final traceability gap between generating compliance artifacts and actually surfacing them in both tracker + PR metadata.

### ✅ Spec-compliance artifact traceability codified in dev-workflow (2026-03-12)
Updated `skills/dev-workflow/SKILL.md` so spec/protocol work now has explicit artifact linkage requirements:
- `TRACKER.md` template now includes **Spec Compliance Artifacts** section
- Phase 4 requires logging artifact path + verdict right after running compliance checks
- Phase 5 PR instructions require a dedicated **Spec Compliance** block with artifact path and verdict
- Added reusable snippet file: `notes/spec-compliance-pr-block.md`

**Rationale:** the compliance checker existed, but artifact references were easy to lose during PR prep. This closes the gap between "checker ran" and "evidence is attached to the review trail".

### ✅ Review-loop delta-sync step codified in lodestar-review skill (2026-03-12)
Updated `skills/lodestar-review/SKILL.md` finding-tracking workflow with a mandatory follow-up round step:
- run `python3 ~/.openclaw/workspace/scripts/review/track-findings.py sync-gh <PR> --repo ChainSafe/lodestar` whenever revisiting a PR with new review comments
- optional `--include-replies` guidance when reviewer discussion happens in threaded replies

**Rationale:** `sync-gh` existed, but without being part of the default loop it was easy to skip delta imports and miss re-verification handoffs.

### ✅ Dev-workflow spec-compliance gate codified (2026-03-11)
Updated `skills/dev-workflow/SKILL.md` Phase 4 with an explicit **Spec-compliance gate** for spec/protocol-facing changes:
- run `python3 scripts/spec/check-compliance.py --spec-query ... --ts-file ... --ts-symbol ... --output ...`
- if skipped, document reason in PR description

**Rationale:** the checker existed, but without an explicit workflow gate it was easy to omit during fast iterations.

### ✅ PR review false-positive guard added to lodestar-review SKILL.md
Added Step 1.5 between "Get the diff" and "Read persona prompts":
- Get `git diff --name-only origin/unstable...HEAD` before spawning reviewers
- Include file list in reviewer task prompt
- Mandatory post-review filter: discard findings for files not in the changed-file list

**Rationale:** PR #8993 — two reviewer sub-agents flagged `dataColumns.ts` and `gloas.ts`, which were not in the diff. I spent time verifying these before discovering they were noise. This is a repeating failure mode.

### ✅ Spec section extractor script implemented
Created `scripts/spec/extract-spec-section.sh`:
- supports query + `--spec-root`
- extracts primary pseudocode matches from specs markdown
- follows import chains for related symbol definitions
- emits markdown report to stdout or `--output`
- supports `rg` with `grep` fallback

### ✅ Devnet first-5-minutes triage script implemented
Created `scripts/debug/devnet-triage.sh`:
- process/uptime snapshot for matching local node processes
- listener/zombie check over configurable ports (default 9000/9596/5052)
- Loki error snapshot via Grafana datasource proxy (configurable window + query)
- Prometheus peer/attestation probes with fallback query candidates
- startup/restart hint count from logs
- markdown report output (`--output`) for easy sharing

### ✅ LLM fallback classification added to CI autofix detector
Updated `scripts/ci/auto_fix_flaky.py`:
- `classify_with_llm(job_name, logs)` using `gpt-4o-mini` + JSON response format
- 13-category taxonomy in system prompt; validated against known categories
- Graceful fallback if API key missing or call fails; `--no-llm` flag for offline
- `confidence` field on every finding: `high` (keyword), `medium` (LLM), `low` (no match)
- `fix_confidence` field: `root-cause` | `likely-root-cause` | `masking-risk` | `unknown`
- `fix_hint` field: LLM-generated short fix suggestion passed to cron agent
- `CRON_PROMPT.md` updated with guidance: flag masking-risk fixes for human review

### ✅ Fork implementation checklist template added
Created `notes/fork-implementation-checklist.md`:
- end-to-end fork coverage checklist (spec intake → types/state transition → fork choice → networking → API → storage)
- explicit test matrix (unit/integration/e2e/spec vectors)
- interop/devnet validation gates
- PR hygiene/review flow checks
- merge readiness/exit criteria summary block for PR descriptions

---

### ✅ Multi-node log correlator implemented (2026-03-09)
Created `scripts/debug/correlate-logs.sh`:
- accepts multiple node names + `--from/--to` range
- runs per-node Loki queries in parallel and merges results into a single timestamp-sorted timeline
- prefixes each line with node name and marks consensus-relevant lines (`fork_choice`, `attestation`, `proposal`, `head_block`, `finalized`)
- supports `--highlights-only`, custom query template (`{{NODE}}` placeholder), and markdown file output

### ✅ Review finding resolution tracker implemented (2026-03-08)
Created `scripts/review/track-findings.py`:
- `add <pr>` — store a finding (file, line, severity, reviewer, body)
- `list <pr> [--open-only]` — show findings sorted by severity
- `resolve <pr> <id> [--commit <sha>]` — mark as addressed/acknowledged/wontfix
- `check <pr> --changed-files <...>` — given new commit's file list, flag findings on changed files as "needs verification" vs. still-untouched
- `dump <pr>` — markdown summary for GitHub comment copy-paste
- `import <pr> --markdown <file>` — parse free-form reviewer output into structured findings
- `dedup <pr>` — group by file+line proximity (±5 lines), showing multi-reviewer overlap

Updated `lodestar-review/SKILL.md` with "Finding Resolution Tracking" section explaining the workflow.

**Rationale:** When PR authors push follow-up commits, I currently re-read my entire review and the new diff manually (10-15 min per follow-up). `check --changed-files` reduces this to <1 min: it immediately shows which of my findings are on changed files (go verify) vs. still-untouched (still open).

### ✅ CI auto-fix PRs now labeled `auto-fix` (2026-03-08)
Updated `CRON_PROMPT.md` Step 4 `gh pr create` command to include `--label "auto-fix"`, with a comment showing how to create the label if it doesn't exist yet. Makes auto-fix PRs instantly filterable in the ChainSafe/lodestar PR queue.

### ✅ Dev-workflow spec-vector gate added (2026-03-09)
Updated `skills/dev-workflow/SKILL.md` Phase 4 (Quality Gate) with an explicit **Spec-vector gate**:
- run `pnpm test:spec` when available before PR on spec/protocol-facing changes
- if unavailable/skipped, document reason in PR body

**Rationale:** test-vector checks were a known recurring omission risk in spec work. Making it a codified gate reduces regressions from "looks right" implementations that diverge from official vectors.

### ✅ Debug session template created
Created `notes/debug-session-template.md` (2026-03-07):
- Structured header (date, topic, linked PR, environment, time budget)
- Hypothesis-first section (list before looking at evidence)
- Timestamped evidence log with bash command blocks
- "Ruled out" table to track eliminated hypotheses
- Working theory + root cause + fix sections
- Lessons learned → feeds back into skill updates
- Quick-reference bash snippets for common starting points

### ✅ GitHub review-comment ingestion added to finding tracker (2026-03-10)
Updated `scripts/review/track-findings.py` with `import-gh` command:
- Fetches PR review comments via `gh api repos/<owner>/<repo>/pulls/<pr>/comments`
- Imports comments as structured findings with source metadata (`kind: github-review-comment`, comment id/url)
- Skips already-imported comments using source-id dedup
- Optional `--include-replies` to include in-thread reply comments

### ✅ Finding-tracker GitHub delta-sync added (2026-03-11)
Updated `scripts/review/track-findings.py` with `sync-gh` command:
- Checkpointed delta sync via persisted state (`data.sync.github[repo].last_comment_id`)
- Imports only new comments (`id > checkpoint`), with optional `--since-comment-id` override
- Optional `--include-replies` and configurable `--match-window-lines`
- Adds re-verification metadata to matching existing findings (`needs_reverify`, `reverify.events`)
- Supports `--dry-run` for safe validation

### ✅ CI LLM retry/backoff + fixability wiring in autofix detector (2026-03-10)
Updated `scripts/ci/auto_fix_flaky.py`:
- Added bounded retry behavior for OpenAI calls in `_openai_completion()`
- Added retryability detection for 429/5xx + transient errors
- Added `Retry-After` header/message parsing and exponential backoff fallback
- Fixed LLM fixability propagation: `classify_failure()` now returns `llm_fixable`, and `scan()` passes it to `is_fixable()`
- Persisted `llm_fixable` into findings/tracker entries for auditability

---

## Next Audit Priorities (next daily cycles)

All previously listed priority items in this section are complete as of **2026-04-18**. To avoid stale reminder churn:

1. Only add a new item here when the **latest daily audit snapshot** introduces a still-open blocker or concrete follow-up.
2. If the latest snapshot is fully green, leave this section empty of filler work and use `BACKLOG.md` for unrelated concrete tasks.
3. When repopulating the list, prefer one specific automation gap that is **not already marked `✅ done` elsewhere in this file**.
4. If a reminder fires while this section has no live items, the correct outcome is routine silence / `NO_REPLY`.

Helper: `python3 scripts/notes/check-next-audit-priorities.py --json` returns whether this section contains live items or only the default empty-state guidance.
