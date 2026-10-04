---
name: dev-workflow
description: >
  Multi-agent development workflow for complex Lodestar features.
  Use for any task requiring architecture planning, implementation, and review.
  Covers spec design with gpt-advisor, implementation via Codex CLI or Claude CLI,
  review with sub-agents, and PR creation.
---

# Dev Workflow — Multi-Agent Feature Development

Use this workflow for **any task that benefits from delegation** — not just big features.
Even small PRs (a few minutes of coding) can be outsourced to a coding agent while
I focus on coordination, quality control, and responsiveness.

**My role: orchestrator.** I design, delegate, review, and ship. Coding agents implement.
I am responsible for the outcome — if the output is bad, that's on me, not the agent.

## Overview

```
Phase 0: Research              (me — for interop/cross-client features)
Phase 1: Spec & Architecture   (me + gpt-advisor)
Phase 2: Worktree Setup        (git worktree off origin/unstable)
Phase 2.5: Progress Tracker    (notes/<feature>/TRACKER.md)
Phase 3: Implementation        (Codex CLI in worktree, or me for simple phases)
Phase 4: Quality Gate           (me + gemini-reviewer + codex-reviewer)
Phase 5: PR                    (me)
```

## Related Skills

- `skills/deep-research/SKILL.md` — use for complex Phase 0/1 investigations that need formal decomposition + synthesis.
- `skills/web-scraping/SKILL.md` — use in Phase 0 when external sources are blocked by CF/JS and `web_fetch` is insufficient.
- `skills/oracle-bridge/SKILL.md` — use when deep-research needs Oracle browser mode on this server.

## Phase 0: Research (for interop/cross-client features)

**When to use:** Features that need to match other client implementations (Lighthouse, Prysm, etc.) or implement new EIPs/specs.

1. Clone/study reference implementations from other clients
2. Read the formal spec and note divergences in practice
3. Study devnet configs (kurtosis, etc.) for integration patterns
4. For external web sources, start with `web_fetch`; if blocked/incomplete, switch to `skills/web-scraping/SKILL.md`
5. Save research artifacts: `notes/<feature>/RESEARCH.md`, `*-DEEP-DIVE.md`, `*-MAPPING.md`
6. Document wire format differences between spec and actual devnet usage

**Output:** Research notes + clear understanding of what to actually implement (which may differ from the spec).

**Skip if:** Feature is Lodestar-internal (refactor, optimization, test improvement).

## Phase 1: Spec & Architecture

**Goal:** Produce a written spec that's good enough for someone else to implement.

1. Analyze the problem — read relevant code, specs, issues
2. Draft initial approach with key decisions, edge cases, test plan
3. Send to **gpt-advisor** (`openai/gpt-6.1-sol`; omit `thinking` — it inherits the global `max`) for feedback, with `runTimeoutSeconds: 3600`
4. Multiple rounds (3-5 typically) until converged
5. Output: `/tmp/spec-<feature>.md`

**Advisor timeout fallback policy (required):**
- Start each architecture consult at the inherited `max` thinking.
- If the run times out or returns empty/near-empty analysis, do **one** retry max at `max` with a tighter prompt.
- If it still times out, immediately fallback to `thinking: "xhigh"`, then `"high"` (shorter prompt, practical focus) instead of looping on `max`.
- Record each round's outcome (model/thinking/timeout/result) in `notes/<feature>/TRACKER.md` so follow-up sessions know what already failed.

**Hard-task escalation (subscription-billed, verified 2026-10-04):**
- Codex CLI, astra max: `codex exec -m gpt-6-astra -c model_reasoning_effort=max …` (see the `codex` skill for flags and detaching)
- Claude CLI, fable: `claude -p --model fable --effort max "<prompt>"`
- OpenClaw subagent: `sessions_spawn` with `model: "openai/gpt-6-astra"` or `"anthropic/claude-fable-5-1"` (thinking inherits `max`)

**Spec template:**
```markdown
# Feature: <name>

## Problem
What we're solving and why.

## Approach
High-level design decisions.

## Implementation Details
- Files to modify/create
- Key functions and interfaces
- Data flow

## Edge Cases & Security
- What could go wrong
- Spec compliance considerations
- Performance implications

## Test Plan
- Unit tests needed
- What to verify

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
```

**Critical:** This is an Ethereum client. Spec compliance, security, and performance are non-negotiable. Invest time here — the better the spec, the better the implementation.

## Phase 2: Worktree Setup

Branch from `origin/unstable` (local `unstable` lags origin):

```bash
git -C ~/lodestar fetch origin unstable && git -C ~/lodestar worktree add -b feat/<feature> ~/lodestar-<feature> origin/unstable
```

Don't run `pnpm install` — the worktree has no `node_modules`; build and test in `~/lodestar` (Phase 4). List worktrees with `git -C ~/lodestar worktree list`.

## Phase 2.5: Progress Tracker

For multi-phase features, create a tracker file to maintain continuity across sessions:

```bash
# Create tracker
notes/<feature>/TRACKER.md
```

**Tracker template:**
```markdown
# <Feature> — Tracker

Last updated: <timestamp>

## Goal
One-line success criteria.

## Phase Plan
- [x] Phase done
- [~] Phase in progress
- [ ] Phase pending

## Completed Work
- `<commit>` — description

## Next Immediate Steps
1. What to do next (resumable)

## Interop/Validation Target
- What must pass before PR

## Spec Compliance Artifacts (for spec/protocol changes)
- `notes/<feature>/spec-compliance-<symbol>.md` — status: pending/pass/diverged
- If not applicable, write: `N/A (reason)`
```

**Why:** Context gets compacted between sessions. The tracker is a single file that tells future-you exactly where you left off, what's done, and what's next. Update it after each commit.

**Multi-session continuity:** track the feature as a 🔴 `BACKLOG.md` item tagged `[topic:ID]` that points to the tracker — the heartbeat checklist nudges every BACKLOG item not marked ✅ into its topic session. Don't create `HEARTBEAT.md` (not read since OpenClaw 2026.9.8) or add prose to the heartbeat scratch.

```markdown
### 🔴 <Feature Name> [topic:<ID>]
- **Tracker:** `notes/<feature>/TRACKER.md`
- **Status:** 🔄 Phase B in progress — next: <step>
```

## Phase 3: Implementation

Two modes: **lodeloop** (multi-story, autonomous) or **direct CLI** (single task, interactive).

### Option A: lodeloop (preferred for multi-story features)

Use lodeloop when the feature has multiple stories/steps that should be implemented autonomously with verification gates. The agent runs in a loop until all stories pass.

**Tool:** `~/lodeloop/lodeloop.sh` — [github.com/lodekeeper/lodeloop](https://github.com/lodekeeper/lodeloop)

```bash
# 1. Create task.json in the worktree
cat > ~/lodestar-<feature>/.lodeloop/task.json << 'EOF'
{
  "project": "lodestar",
  "feature": "<feature description>",
  "branch": "feat/<feature-name>",
  "workdir": "~/lodestar-<feature>",
  "constraints": "Do not push, open PRs, or use any GitHub plugin/connector.",
  "agent": "codex",
  "verify": {
    "commands": [
      "pnpm check-types",
      "pnpm lint",
      "pnpm test:unit"
    ],
    "timeout": 300
  },
  "context_files": [
    "~/.openclaw/workspace/CODING_CONTEXT.md"
  ],
  "stories": [
    {
      "id": "S1",
      "title": "Story title",
      "description": "What to implement",
      "acceptance": ["Criteria 1", "Criteria 2", "Typecheck passes"],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
EOF

# 2. Launch detached — exec/run_in_background jobs die at session teardown
setsid bash -c 'cd ~/lodestar-<feature> && source ~/.nvm/nvm.sh && nvm use 24 2>/dev/null && ~/lodeloop/lodeloop.sh -a codex -n 15 .lodeloop/task.json > /tmp/lodeloop-<feature>.log 2>&1' </dev/null >/dev/null 2>&1 & disown

# 3. Check status
~/lodeloop/lodeloop.sh --status ~/lodestar-<feature>/.lodeloop/task.json

# 4. Check result
cat ~/lodestar-<feature>/.lodeloop/result.json
```

**When to use lodeloop:**
- Feature has 2+ discrete stories
- Verification gates are well-defined (typecheck + lint + test)
- I want to set-and-forget while doing other work
- Task is well-scoped (each story fits one context window)

**Story sizing:** Each story must be completable in one iteration. "Add a config field" ✅. "Build the entire subsystem" ❌ — split it.

**Agent:** Default to **Codex CLI** (`-a codex`). Claude is supported (`-a claude`) but Codex is preferred for Lodestar work.

**Completion signal:** The agent must output `LODELOOP_DONE: <story-id>` after completing each story. This is included in the prompt template automatically.

### Option B: Direct CLI (for single focused tasks)

Use direct Codex/Claude CLI for single-shot tasks that don't need a loop. Launch detached (`setsid … & disown`) — `exec`/`run_in_background` jobs die at session teardown. Every implementer prompt carries the GitHub boundary line; I push and open the PR myself (Phase 5).

```bash
# Codex (preferred; config default gpt-6-astra @ xhigh — add `-c model_reasoning_effort=max` for hard tasks)
setsid bash -c 'cd ~/lodestar-<feature> && source ~/.nvm/nvm.sh && nvm use 24 2>/dev/null && codex exec --dangerously-bypass-approvals-and-sandbox "Read ~/.openclaw/workspace/CODING_CONTEXT.md for project context. Do not push, open PRs, or use any GitHub plugin/connector. Then: <task>" > /tmp/codex-<feature>.log 2>&1' </dev/null >/dev/null 2>&1 & disown

# Claude (for broader reasoning tasks; add `--model fable --effort max` for hard tasks)
setsid bash -c 'cd ~/lodestar-<feature> && claude -p --permission-mode bypassPermissions "Read ~/.openclaw/workspace/CODING_CONTEXT.md for project context. Do not push, open PRs, or use any GitHub plugin/connector. Then: <task>" > /tmp/claude-<feature>.log 2>&1' </dev/null >/dev/null 2>&1 & disown
```

For long or quote-heavy tasks, write the brief to a file and pass `"$(cat /tmp/brief-<feature>.md)"` as the prompt. Check progress via ground truth (log tail, `git -C ~/lodestar-<feature> log --oneline -3`, `pgrep -af 'codex exec|claude -p'`), not a task notification.

`codex exec --full-auto` no longer exists (codex-cli 0.160.0 exits 2 on it); lodeloop was switched to `--dangerously-bypass-approvals-and-sandbox` in lodekeeper/lodeloop@650ef78.

**When to use direct CLI:**
- Single focused task (one story)
- Quick fix or one-liner
- Exploratory/debugging work
- Need interactive control

### Parallel execution

Both modes support parallelism across separate worktrees (each detached, own log):
```bash
# lodeloop in worktree A
setsid bash -c 'cd ~/lodestar-taskA && ~/lodeloop/lodeloop.sh ... > /tmp/lodeloop-taskA.log 2>&1' </dev/null >/dev/null 2>&1 & disown
# Direct codex in worktree B
setsid bash -c 'cd ~/lodestar-taskB && codex exec ... > /tmp/codex-taskB.log 2>&1' </dev/null >/dev/null 2>&1 & disown
# Monitor (detached jobs don't show in `process action:list`)
pgrep -af 'lodeloop.sh|codex exec'; tail -n 20 /tmp/lodeloop-taskA.log /tmp/codex-taskB.log
```

**After agent/loop finishes:**
- Review `git diff` in the worktree
- Check that all acceptance criteria from spec are met
- Run build/lint/tests myself to verify (in `~/lodestar` — see Phase 4)
- Check `.lodeloop/progress.md` and `.lodeloop/result.json` for lodeloop runs

## Phase 4: Quality Gate

1. **Self-review:** Read the diff carefully, check against spec
2. **Local verification** — the worktree has no `node_modules`, so build and test in `~/lodestar`. It is usually on an unrelated branch: record branch + SHA first, restore after.
   ```bash
   git -C ~/lodestar rev-parse --abbrev-ref HEAD; git -C ~/lodestar rev-parse HEAD   # record
   git -C ~/lodestar status --porcelain | grep -v '^??'                               # must print nothing
   cd ~/lodestar && git checkout --detach feat/<feature>                              # branch stays checked out in the worktree
   pnpm lint
   pnpm check-types
   pnpm build
   # Run targeted unit tests for changed packages
   git checkout <recorded-branch>                                                     # restore
   ```
   If pnpm tries to reinstall deps, use `pnpm --config.verify-deps-before-run=false …` or `npx tsc -p tsconfig.build.json` from the package dir. While a long build holds `~/lodestar`, mark the BACKLOG item "~/lodestar LOCKED".

   **Spec-vector gate (required for spec/protocol-facing changes before PR):**
   ```bash
   # 1) Local vectors must match the pin CI uses (version.txt is only the last-downloaded cache)
   git -C ~/lodestar fetch -q origin unstable
   git -C ~/lodestar show origin/unstable:spec-tests-version.json | grep -m1 specVersion
   cat ~/lodestar/packages/beacon-node/spec-tests/version.txt
   # Mismatch → re-download (`pnpm --config.verify-deps-before-run=false download-spec-tests` in packages/beacon-node)
   # or don't trust local spec results

   # 2) In ~/lodestar with the feature checked out (step 2, before restoring), run only the touched spec files/cases — not the full test:spec
   pnpm vitest run --project spec-minimal packages/beacon-node/test/spec/presets/<file>.test.ts -t "<case>"
   # mainnet preset: --project spec-mainnet
   ```

   **Spec-compliance gate (required for spec/protocol-facing changes before PR):**
   ```bash
   cd ~/.openclaw/workspace
   bash scripts/spec/prepr-compliance-gate.sh --check-only
   # Automation wrappers should use:
   bash scripts/spec/prepr-compliance-gate.sh --check-only --json

   python3 scripts/spec/check-compliance.py \
     --spec-query "<spec function or section>" \
     --ts-file "~/lodestar-<feature-name>/<path/to/file>.ts" \
     --ts-symbol "<functionName>" \
     --output "notes/<feature>/spec-compliance-<function>.md"
   ```
   After generating the report, immediately log the artifact path + verdict in `notes/<feature>/TRACKER.md` under **Spec Compliance Artifacts**.
   If the compliance gate is skipped, record the reason in both the tracker and the PR description (e.g., non-spec refactor or missing stable spec target).
3. **Multi-persona review:** Use the `lodestar-review` skill (`skills/lodestar-review/SKILL.md`):
   - Get the local diff in the worktree: `git fetch origin unstable && git diff origin/unstable...HEAD` (local `unstable` lags origin)
   - Read the skill for reviewer selection matrix and Lodestar-tailored persona prompts
   - Spawn appropriate reviewers (bugs, security, wisdom, architect, etc.) based on change type
   - Collect every reviewer's result with `subagents action:"wait" runIds:[…] timeoutSeconds:60` (repeat while pending) and/or the review artifacts (`lodestar-review` §4.1) — `sessions_yield` fails in the Claude-CLI harness
   - **This is a local review** — no PR exists yet. Fix issues directly in the worktree.
   - Re-run reviewers if changes were significant
4. **Fix issues:** Small fixes → do directly. Large issues → back to Codex
5. **Only proceed to Phase 5 (PR) after the review cycle is clean** — if a reviewer's result can't be collected, gate on your own lint/types/targeted tests and amend when its findings land

**Legacy reviewers** (codex-reviewer = GPT-6.1 Sol, gemini-reviewer = Gemini 3.5 Flash, gpt-advisor = GPT-6.1 Sol) are still available for general second opinions but the persona-based reviewers from `lodestar-review` are preferred for PR reviews.

## Phase 5: PR

1. Commit with clear message, sign with GPG
2. Push to fork
3. Open PR with description referencing the spec — with local `gh` after `gh auth status` shows `lodekeeper` active; never via a GitHub plugin/connector (the Codex connector is linked to nflaig's account)
4. For spec/protocol-facing changes, include a **Spec Compliance** block in the PR body:
   ```markdown
   ## Spec Compliance
   - Artifact: `notes/<feature>/spec-compliance-<function>.md`
   - Verdict: pass | partial | diverged
   - Notes: <key mismatches or N/A>
   ```
   If no compliance artifact exists, explicitly write why (e.g., pure refactor, no spec pseudocode touched).
5. Run the one-command pre-PR compliance gate before posting/re-requesting review:
   ```bash
   bash ~/.openclaw/workspace/scripts/spec/prepr-compliance-gate.sh \
     --tracker "notes/<feature>/TRACKER.md" \
     --pr-body "/tmp/pr-<feature>.md" \
     --check "<spec_query>|~/lodestar-<feature-name>/<path/to/file>.ts|<functionName>|notes/<feature>/spec-compliance-<function>.md" \
     --summary-out "/tmp/prepr-spec-compliance-<feature>.md"
   ```
   - This runs report generation + metadata presence validation and emits one pass/fail summary.
   - If you already generated reports in Phase 4, use `--skip-spec-checks` to run metadata validation + summary only.
6. Standard review process

## Small Fixes Exception

For trivial changes (lint fixes, one-liners, typos), skip this workflow and just do them directly. Use judgment — if it takes more than 15 minutes of thinking, use the full workflow.

## Iteration Log

Dated iteration log and per-feature learnings: `references/history.md` (append new entries there).

## Devnet / Interop Debugging Workflow

For features requiring multi-client devnet validation (kurtosis), follow this extended cycle:

### Setup
1. **Define acceptance criteria upfront** — list specific counters/log patterns that must be zero
   ```
   Example (EPBS): ISR=0, PU=0, lag=0, pubErr=0, pidNull=0, unkSync=0, elOld=0
   ```
2. **Use `Dockerfile.dev`** for all iterative builds — production `Dockerfile` + `--no-cache` only for debugging build/dependency issues. Source-only changes rebuild in seconds with `Dockerfile.dev` vs minutes with production.
3. **Create a monitoring script** that checks all acceptance counters in one pass — don't manually grep each time.

### Debug Cycle
```
instrument → rebuild (Dockerfile.dev) → rerun kurtosis → analyze → fix → repeat
```

- **Test both validator AND observer nodes** — bugs often only appear in the producer path (block production, FCU updates) while the observer stays clean. Always check both roles separately.
- **Use sub-agents during debugging** — gpt-advisor can catch race condition hypotheses from log patterns that you might miss while deep in implementation. Don't wait until PR review to get a second opinion.
- **Timeline analysis for race conditions** — when debugging timing-related bugs (gossip ordering, import races), reconstruct the exact event timeline from logs. Simple log grepping isn't enough — you need to see the ordering across components.

### Soak Testing
- **Define "pass" before running** — no moving goalposts. All counters must be zero for a sustained period.
- **Only report when ALL criteria are met** — don't send partial progress updates ("ISR=0 but still some lag"). Iterate silently until everything's green, then report once. Partial updates waste the reviewer's time.
- **Multiple passes may be needed** — first soak may pass then regress on edge cases. Run extended soaks (hours, not minutes) to catch intermittent issues.
- **Watch for stale references** — in-place mutations (e.g., fork-choice status updates) can leave other code paths holding stale object references. After any state mutation, verify all consumers see the updated state.

### Kurtosis Tips
- See `skills/kurtosis-devnet/SKILL.md` for full reference
- Use alt-port configs to avoid Docker bind collisions with other services
- `kurtosis clean -a` between runs — never use broad `docker system prune`
- For 50/50 multi-client topologies, start with 2+2 nodes (faster iteration) before scaling up

## Key Rules

- **I am responsible** for the final result — no blaming sub-agents
- **Spec quality = implementation quality** — invest time in Phase 1
- **Document learnings** — append to `references/history.md` after each use; fold durable rules into the procedure above
- **Fresh worktree per feature** — keep working states independent
- **Ignore sim/e2e failures** unless Nico specifically asks to investigate

---

## Self-Maintenance

If any commands, file paths, URLs, or configurations in this skill are outdated or no longer work, update this SKILL.md with the correct information after completing your current task. Skills should stay accurate and self-healing — fix what you find broken.
