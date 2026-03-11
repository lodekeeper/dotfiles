# Autonomy Gaps — Daily Audit

> "What would I need to do this autonomously?"
> Updated: 2026-03-10 (5th pass)

---

## Daily Audit Snapshot — 2026-03-10 (self-improvement-audit-daily)

### PR review
- **Blocker:** finding-tracker import exists, but no "delta sync" command to re-ingest only new review comments since last sweep and auto-mark matching findings as re-verified.
- **Proposed fix:** add `track-findings.py sync-gh <owner/repo> <pr>` with `--since-comment-id` checkpointing.

### CI fix
- **Blocker:** CI LLM calls had model fallback but no explicit `Retry-After` / bounded retry behavior, and LLM `fixable` signals were not wired into `is_fixable()`.
- **Fix applied this cycle:** updated `scripts/ci/auto_fix_flaky.py` with retryable OpenAI error handling (429/5xx + `Retry-After` aware backoff) and proper propagation of LLM fixability into actionable classification.

### Spec implementation
- **Blocker:** compliance checker exists but is not yet an explicit dev-workflow gate for spec-facing PRs.
- **Proposed fix:** add a mandatory "spec-compliance check" step in `skills/dev-workflow/SKILL.md` (run checker or document skip reason).

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
14. **Finding tracker delta-sync from GitHub** — add `track-findings.py sync-gh` with checkpointed import + optional auto-reverify of touched findings
