# Autonomy Gaps — Daily Audit

> "What would I need to do this autonomously?"
> Updated: 2026-03-14 (9th pass)

---

## Daily Audit Snapshot — 2026-03-15 (self-improvement-audit-daily)

### PR review
- **Blocker (previous cycle):** stale-finding detection required manual invocation per PR.
- **Fix applied this cycle:** added `scripts/review/stale-findings-report.sh` — batch scanner across all tracked PRs with cron-friendly exit codes and markdown report output.
- **Next:** wire as a cron job on a weekly cadence (low urgency while PR tracking volume is low).

### CI fix
- **Blocker:** retry telemetry is surfaced in output, but no threshold-based escalation policy exists for sustained degradation detection.
- **Proposed fix:** add rolling-window threshold check for `llm_retry_count`/`llm_retry_wait_s` in tracker.

### Spec implementation
- **Status:** compliance gate, artifact checks, and pre-PR wrapper all operational. No new gaps.

### Devnet debugging
- **Status:** incident bundle, triage, and correlator scripts operational. No new gaps.

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

#### 🔴 Reviewer false positives (FIXED this cycle — see below)
Sub-agents sometimes flag files **not in the PR diff** (confirmed on PR #8993: `dataColumns.ts`, `gloas.ts` flagged but not changed). This wastes effort and can lead to spurious follow-up commits.

**Fix:** Added mandatory false-positive guard step to `lodestar-review/SKILL.md`:
- Get `git diff --name-only` before acting on findings
- Include actual changed-file list in reviewer task prompt
- Discard any finding referencing a file not in that list

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

#### 🔴 No review finding resolution tracking
After posting a review, when the author pushes new commits, I have no system for tracking which findings got addressed. I manually re-read everything.

**Status:** ✅ FIXED this cycle — see "Improvements Implemented This Cycle" below.

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

#### 🔴 No automated spec section extraction
I manually grep `~/consensus-specs` for relevant pseudocode when implementing. This is slow and error-prone (easy to miss related functions/types across files).

**Proposed fix:** Write `scripts/spec/extract-spec-section.sh <feature-name>` that:
- Searches `~/consensus-specs/specs/` for function/type definitions matching a pattern
- Outputs relevant pseudocode blocks in a format suitable for Codex context injection
- Follows import chains to pull related types

#### ~~🔴 No LLM spec compliance check (new — 2026-03-08)~~ ✅ FIXED (2026-03-09)
After implementing a spec function in TypeScript, before opening a PR, I don't run a systematic check: "does this TS code faithfully implement the pseudocode?" I verify manually by reading both, which is slow and error-prone.

**Proposed fix:** `scripts/spec/check-compliance.py <spec-function> <ts-file> <ts-function>` that:
- Extracts the pseudocode block from `~/consensus-specs`
- Sends it + the TS implementation to GPT/Codex: "do these match? what's missing?"
- Outputs a diff-style compliance report: implemented ✅ / missing ⚠️ / diverged ❌

#### 🟡 No test-vector auto-download awareness
When implementing spec functions, I sometimes forget to run against official test vectors. The vectors live in `~/consensus-specs/tests/` but need a separate download step.

**Proposed fix:** Add check in dev-workflow skill: before opening PR, run `python3 scripts/pre-validate.mjs --spec-tests` or equivalent to confirm test-vector coverage.

#### 🟢 No implementation checklist per fork type
Each fork (Gloas, Fulu, etc.) has different patterns: new SSZ types, new gossip topics, new reqresp methods, new fork-choice fields, new API endpoints. No single checklist ensures all are covered.

**Proposed fix:** Add `notes/fork-implementation-checklist.md` template that covers all surface areas.

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

#### 🔴 No scripted first-5-minutes diagnostic
Every devnet debugging session starts with the same manual sequence: check zombie processes, check ports, check Loki for recent errors, compare Grafana metrics, check peer count. This takes 10-15 minutes every time.

**Proposed fix:** Write `scripts/debug/devnet-triage.sh [node-name]` that:
1. `lsof -iTCP:<port> -sTCP:LISTEN` — zombie check
2. Loki: last 10 errors for the target node
3. Grafana: peer count + attestation effectiveness (last 30m)
4. Check process uptime + recent restart count
5. Output a concise triage summary

#### 🟡 No structured debugging session template
When investigating complex issues (like feat4 QUIC crashes), I accumulate evidence across many tool calls without a clear structure. Later it's hard to reconstruct what was ruled out and why.

**Proposed fix:** Create `notes/debug-session-template.md` and use it at the start of each investigation: hypothesis, evidence collected, ruled-out explanations, current working theory, next steps.

#### 🟡 Mixed-peer devnet startup is still manual
Spinning up a mixed-peer devnet (e.g., Lodestar B2 + C2 nodes against ePBS devnet) requires multiple manual steps and ad-hoc configuration. I have the `kurtosis-devnet` and `join-devnet` skills but no quick-start path for a specific devnet variant.

**Proposed fix:** Codify the EPBS devnet-0 startup sequence into `scripts/devnet/start-epbs-devnet.sh` so I can reproduce the environment in <5 minutes.

---

## Improvements Implemented This Cycle

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

1. ~~Add LLM fallback classification for unknown CI failure patterns (`auto_fix_flaky.py`)~~ ✅ done
2. ~~Add confidence scoring/check in CI autofix outputs (root-cause vs masking)~~ ✅ done
3. ~~Add issue-linkage step to CI autofix cron prompt~~ ✅ done (2026-03-07)
4. ~~Add reviewer file-scope injection to `lodestar-review` SKILL.md~~ ✅ done (2026-03-08)
5. ~~Codify EPBS devnet-0 startup into `scripts/devnet/start-epbs-devnet.sh`~~ ✅ done (2026-03-08)
6. ~~Add LLM-based fix *quality* check post-Codex~~ ✅ done (2026-03-08)
7. ~~Review finding resolution tracker~~ ✅ done (2026-03-08)
8. ~~CI auto-fix `auto-fix` label~~ ✅ done (2026-03-08)
9. ~~**Implement multi-node log correlator** (`scripts/debug/correlate-logs.sh`)~~ ✅ done (2026-03-09)
10. ~~**Implement spec compliance checker** (`scripts/spec/check-compliance.py`) — LLM-based "does this TS faithfully implement the pseudocode?"~~ ✅ done (2026-03-09)
11. ~~**Test-vector auto-check** — add `pnpm test:spec` gate to dev-workflow skill before PR opening~~ ✅ done (2026-03-09)
12. ~~**GitHub review-comment ingestion for finding tracker** — add API import path so `track-findings.py` can bootstrap from PR review comments without manual entry~~ ✅ done (2026-03-10)
13. ~~**CI LLM retry + `Retry-After` handling in autofix detector** — bounded retry budget for 429/5xx and propagate LLM `fixable` verdict into actionable selection~~ ✅ done (2026-03-10)
14. ~~**Finding tracker delta-sync from GitHub** — add `track-findings.py sync-gh` with checkpointed import + optional auto-reverify of touched findings~~ ✅ done (2026-03-11)
15. ~~**Review-loop integration for finding delta sync** — add a codified follow-up step in `skills/lodestar-review/SKILL.md` to run `track-findings.py sync-gh` whenever new review comments land on a PR.~~ ✅ done (2026-03-12)
16. ~~**Spec compliance artifact traceability** — add PR-template/tracker field that links generated `spec-compliance-*.md` reports for spec/protocol PRs.~~ ✅ done (2026-03-12)
17. ~~**Compliance artifact presence check** — add a lightweight pre-PR check that verifies tracker + PR body include spec-compliance artifact references for spec/protocol changes.~~ ✅ done (2026-03-13)
18. ~~**Stale unresolved-review escalation** — add `track-findings.py stale` command and wire into review workflow.~~ ✅ done (2026-03-13)
19. ~~**CI retry telemetry surfacing** — include retry/backoff counters in cron detector summary output.~~ ✅ done (2026-03-14)
20. ~~**Spec pre-PR compliance wrapper** — one command to run compliance checker + artifact-presence checks with a single pass/fail summary.~~ ✅ done (2026-03-14)
21. ~~**Devnet incident bundle script** — package logs + metrics + timeline + env metadata into one shareable markdown artifact.~~ ✅ done (2026-03-15)
22. ~~**PR stale-finding cron wrapper** — automate `track-findings.py stale --fail-on-match` into a backlog-facing report/escalation signal.~~ ✅ done (2026-03-15)
23. **CI retry telemetry threshold-based escalation** — add tracker-level threshold check for `llm_retry_count`/`llm_retry_wait_s` with explicit warning when sustained degradation is detected across rolling runs.
24. **Spec section auto-extraction** — write `scripts/spec/extract-spec-section.sh <feature>` to search consensus-specs for function/type definitions and follow import chains for related types.
