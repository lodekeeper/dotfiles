# Autonomy Gaps — Daily Audit

> "What would I need to do this autonomously?"
> Updated: 2026-03-07

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

#### 🟡 No reviewer task pre-injection of changed-file scope
Reviewer prompts don't currently include the file list — so reviewers have to infer scope from the diff content, which they sometimes miss.

**Proposed fix:** Prepend `## Files Changed\n<list>` block to every reviewer task. Low-effort, high-ROI.

#### 🟢 No automated convergence triage
When multiple reviewers flag the same issue, I manually merge. A simple post-processing step that groups findings by file+line range would save synthesis time.

---

## 2. CI Fix

### Current State
CI autofix cron (`573d18ec`) runs hourly, classifies flaky failures, applies pattern-based fixes via Codex, opens PRs against `unstable`. Pattern library covers: shutdown-race, peer-count-flaky, timeout, vitest-crash.

### Gaps

#### 🟡 No auto-linkage to existing GitHub issues
When CI autofix opens a fix PR, it doesn't check whether an open issue already tracks that failure, and doesn't reference/close it.

**Proposed fix:** In `CRON_PROMPT.md`, add step: after opening fix PR, search for related issues via `gh issue list --search "<test name> is:open"` and comment/reference from the PR.

#### 🟡 Pattern-based classifier misses semantic failures
The classifier matches keyword patterns. Failures with novel error messages or new test paths fall through unclassified.

**Proposed fix:** Add LLM-based fallback classification for unmatched patterns. After keyword classifier returns `unknown`, ask GPT to classify based on full error context.

#### 🟢 No confidence score in fix quality
Codex applies fixes but there's no check on whether the fix actually addresses root cause vs. masking (e.g., bumping timeout). This leads to PRs that merge but don't fix the underlying issue.

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

### ✅ Fork implementation checklist template added
Created `notes/fork-implementation-checklist.md`:
- end-to-end fork coverage checklist (spec intake → types/state transition → fork choice → networking → API → storage)
- explicit test matrix (unit/integration/e2e/spec vectors)
- interop/devnet validation gates
- PR hygiene/review flow checks
- merge readiness/exit criteria summary block for PR descriptions

---

## Next Audit Priorities (next daily cycles)

1. Add LLM fallback classification for unknown CI failure patterns
2. Add confidence scoring/check in CI autofix outputs (root-cause vs masking)
3. Create `notes/debug-session-template.md` and standardize usage in investigations
