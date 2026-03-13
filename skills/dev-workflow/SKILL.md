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
Phase 2: Worktree Setup        (helper script)
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
3. Send to **gpt-advisor** (`thinking: xhigh`) for feedback
4. Multiple rounds (3-5 typically) until converged
5. Output: `/tmp/spec-<feature>.md`

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

Use the helper script to create a clean worktree:

```bash
~/lodestar/scripts/create-worktree.sh <feature-name> [base-branch]
```

This script:
1. Creates branch `feat/<feature-name>` from `base-branch` (default: `unstable`)
2. Creates worktree at `~/lodestar-<feature-name>`
3. Runs `pnpm install`
4. Runs `pnpm build`
5. Worktree is ready for Codex

**Track worktrees in TOOLS.md** under "Git Worktrees" section.

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

**Heartbeat integration:** For multi-session tasks, add a top-priority entry to `HEARTBEAT.md` that tells the agent to resume work on the feature every heartbeat. This turns heartbeats into continuous progress cycles — instead of just monitoring, the agent reads the tracker and picks up where it left off. Example:

```markdown
## 🔴 TOP PRIORITY: <Feature Name>
**Work on <feature> continuously until <completion criteria>.**
- Tracker: `notes/<feature>/TRACKER.md`
- Phases: A(done) → B(in progress) → C → D → ...
- Only interrupt for: urgent notifications, CI failures, or direct messages
- After quick monitoring checks, immediately resume work
```

This is especially valuable for large features spanning days/weeks — without the heartbeat entry, progress stalls between sessions because the agent has no directive to continue.

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

# 2. Launch (background, Codex is default)
exec pty:true workdir:~/lodestar-<feature> background:true timeout:3600 \
  command:"~/lodeloop/lodeloop.sh -a codex -n 15 .lodeloop/task.json"

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

Use direct Codex/Claude CLI for single-shot tasks that don't need a loop.

```bash
# Codex (preferred)
exec pty:true workdir:~/lodestar-<feature> background:true timeout:3600 \
  command:"source ~/.nvm/nvm.sh && nvm use 24 2>/dev/null && codex exec --full-auto 'Read ~/.openclaw/workspace/CODING_CONTEXT.md for project context. Then: <task>'"

# Claude (for broader reasoning tasks)
exec pty:true workdir:~/lodestar-<feature> background:true timeout:3600 \
  command:"claude 'Read ~/.openclaw/workspace/CODING_CONTEXT.md for project context. Then: <task>'"
```

**When to use direct CLI:**
- Single focused task (one story)
- Quick fix or one-liner
- Exploratory/debugging work
- Need interactive control

### Parallel execution

Both modes support parallelism across separate worktrees:
```bash
# lodeloop in worktree A
exec pty:true workdir:~/lodestar-taskA background:true command:"~/lodeloop/lodeloop.sh ..."
# Direct codex in worktree B
exec pty:true workdir:~/lodestar-taskB background:true command:"codex ..."
# Monitor
process action:list
```

**After agent/loop finishes:**
- Review `git diff` in the worktree
- Check that all acceptance criteria from spec are met
- Run build/lint/tests myself to verify
- Check `.lodeloop/progress.md` and `.lodeloop/result.json` for lodeloop runs

## Phase 4: Quality Gate

1. **Self-review:** Read the diff carefully, check against spec
2. **Local verification:**
   ```bash
   cd ~/lodestar-<feature-name>
   pnpm lint
   pnpm check-types
   pnpm build
   # Run targeted unit tests for changed packages
   ```

   **Spec-vector gate (required for spec/protocol-facing changes before PR):**
   ```bash
   cd ~/lodestar-<feature-name>
   if pnpm run | grep -q "test:spec"; then
     pnpm test:spec
   else
     echo "No test:spec script in this checkout; run the relevant consensus-spec tests manually and note it in PR body"
   fi
   ```

   **Spec-compliance gate (required for spec/protocol-facing changes before PR):**
   ```bash
   cd ~/.openclaw/workspace
   python3 scripts/spec/check-compliance.py \
     --spec-query "<spec function or section>" \
     --ts-file "~/lodestar-<feature-name>/<path/to/file>.ts" \
     --ts-symbol "<functionName>" \
     --output "notes/<feature>/spec-compliance-<function>.md"
   ```
   After generating the report, immediately log the artifact path + verdict in `notes/<feature>/TRACKER.md` under **Spec Compliance Artifacts**.
   If the compliance gate is skipped, record the reason in both the tracker and the PR description (e.g., non-spec refactor or missing stable spec target).
3. **Multi-persona review:** Use the `lodestar-review` skill (`skills/lodestar-review/SKILL.md`):
   - Get the local diff: `git diff unstable...HEAD` in the worktree
   - Read the skill for reviewer selection matrix and Lodestar-tailored persona prompts
   - Spawn appropriate reviewers (bugs, security, wisdom, architect, etc.) based on change type
   - Wait for ALL reviewers to complete
   - **This is a local review** — no PR exists yet. Fix issues directly in the worktree.
   - Re-run reviewers if changes were significant
4. **Fix issues:** Small fixes → do directly. Large issues → back to Codex
5. **Only proceed to Phase 5 (PR) after the review cycle is clean**

**Legacy reviewers** (codex-reviewer, gemini-reviewer, gpt-advisor) are still available for general second opinions but the persona-based reviewers from `lodestar-review` are preferred for PR reviews.

## Phase 5: PR

1. Commit with clear message, sign with GPG
2. Push to fork
3. Open PR with description referencing the spec
4. For spec/protocol-facing changes, include a **Spec Compliance** block in the PR body:
   ```markdown
   ## Spec Compliance
   - Artifact: `notes/<feature>/spec-compliance-<function>.md`
   - Verdict: pass | partial | diverged
   - Notes: <key mismatches or N/A>
   ```
   If no compliance artifact exists, explicitly write why (e.g., pure refactor, no spec pseudocode touched).
5. Standard review process

## Small Fixes Exception

For trivial changes (lint fixes, one-liners, typos), skip this workflow and just do them directly. Use judgment — if it takes more than 15 minutes of thinking, use the full workflow.

## Iteration Log

Track what works and what doesn't after each use:

| Date | Feature | What worked | What to improve |
|------|---------|-------------|-----------------|
| 2026-02-15 | pre-validate.mjs | Spec rounds with advisor caught edge cases early; Codex produced working 662-line script | Codex hung on first attempt (long prompt); needed concise retry. Codex doesn't understand project-specific conventions (global vs per-package lint/build) — always verify. Gemini reviewer failed without file access — need to pass code inline. |
| 2026-02-16 | EIP-8025 optional proofs | Deep research phase paid off — studying 54 Lighthouse files + Prysm + kurtosis configs before speccing prevented wrong assumptions. gpt-advisor confirmed interop-first approach in 2 rounds. Phase A (types) done cleanly. | Need Phase 0 (Research) for cross-client interop features. Simple foundation work (types/constants) faster done directly than via Codex. Break big features into sub-phases with verification between each. |
| 2026-02-17 | EIP-8025 kurtosis revalidation (orchestrator test) | Claude CLI produced 406-line validation script from task file spec in ~75s. Parallel execution (Docker + Claude CLI) eliminated wait time. Stayed responsive to notifications throughout. CODING_CONTEXT.md reusable across tasks. | Task files must be in worktree (not /tmp). `--print` doesn't write files. Trust prompt on first run. Always include env-specific constants (slot time etc.) in task file. Review is the bottleneck — consider delegating that too. |
| 2026-02-22 | EPBS devnet-0 interop | Tracker file + HEARTBEAT.md priority entry kept progress across sessions. gpt-advisor caught race hypothesis early. Structured acceptance counters (ISR/PU/lag/etc.) made pass/fail unambiguous. Multiple soak passes caught regressions. | Used `Dockerfile` + `--no-cache` for ALL 15+ rebuilds instead of `Dockerfile.dev` (wasted hours). Sent partial progress updates before all criteria were met. Didn't separate validator vs observer testing early enough — observer was clean while validator had bugs. |

### Learnings from orchestrator test (2026-02-17)
**Context:** First test of the orchestrator workflow. Task: redeploy EIP-8025 3-client kurtosis devnet and validate SSZ mismatch fix. Delegated validation script (406 lines) to Claude CLI, ran Docker build in parallel, deployed/monitored myself. Result: PASS.

**What worked:**
- Task file approach (precise spec → quality output, less review)
- Parallel execution (Docker + Claude CLI simultaneously)
- Staying responsive during builds/waits (handled heartbeats, notifications)
- `CODING_CONTEXT.md` as reusable shared context
- Claude CLI code quality was high (proper error handling, ANSI colors, arg parsing, kurtosis auto-discovery)

**Numbered learnings:**
11. **Task files must be in the worktree** — Claude CLI is sandboxed to `workdir`. Files in `/tmp` are inaccessible. Copy task files and `CODING_CONTEXT.md` into the worktree before spawning.
12. **`--print` mode doesn't create files** — Claude CLI `--print` just outputs text, doesn't actually write files. Use interactive mode (no `--print`) for file creation tasks.
13. **Trust prompt first time** — Claude CLI asks to trust the workspace directory on first run. Need to send Enter to accept before it starts working. Pre-approve by running a trivial command first.
14. **Include environment-specific constants in task files** — Claude defaulted to mainnet values (12s slots) instead of devnet values (6s). Sub-agents don't know deployment-specific parameters unless explicitly told. Always specify slot times, epoch lengths, network configs in the task file.
15. **Parallel work prevents tunnel vision** — by delegating implementation and running ops tasks myself, I stayed available for notifications and heartbeats throughout. This directly solved the "disappear for hours" problem identified earlier.
16. **Review is the bottleneck** — Claude produced 406 lines in ~75s, but I still needed to review it all. For larger delegations, consider also delegating review to sub-agent reviewers (codex-reviewer, gemini-reviewer) to parallelize the quality gate.
17. **Ops tasks (deploy, monitor) stay with me** — things requiring real-time judgment (interpreting logs, debugging devnet issues, checking proof flow timing) aren't good delegation targets. Keep those; delegate the deterministic coding work.

### Learnings from EPBS devnet-0 (2026-02-21 → 2026-02-22)
**Context:** Largest debugging effort so far. Multi-day, 15+ Docker rebuilds, 20+ Kurtosis relaunches, ~36 hours continuous work across sessions. Task: get Lodestar ePBS interop working with Lighthouse in a 50/50 Kurtosis devnet with zero errors.

| Date | Feature | What worked | What to improve |
|------|---------|-------------|-----------------|
| 2026-02-22 | EPBS devnet-0 interop | Tracker file + HEARTBEAT.md priority entry kept progress across sessions. gpt-advisor caught race hypothesis early. Structured acceptance counters (ISR/PU/lag/etc.) made pass/fail unambiguous. Multiple soak passes caught regressions. | Used `Dockerfile` + `--no-cache` for ALL 15+ rebuilds instead of `Dockerfile.dev` (wasted hours). Sent partial progress updates before all criteria were met. Didn't separate validator vs observer testing early enough — observer was clean while validator had bugs. |
| 2026-03-01 | lodeloop integration | Added lodeloop (~/lodeloop) as Phase 3 Option A for multi-story features. Keeps Codex as default. Direct CLI remains Option B for single tasks. GPT-5.2-pro review caught 14 issues, all fixed in v0.2.0. | Not yet tested on a real Lodestar task — first real test will validate story sizing, verification gate config, and circuit breaker thresholds. |

**Numbered learnings:**
18. **Use `Dockerfile.dev` for iterative builds** — production `Dockerfile` + `--no-cache` is for debugging build issues, not source changes. `Dockerfile.dev` caches dependency layers and rebuilds in seconds. I wasted hours on unnecessary full rebuilds. Already documented in kurtosis skill — follow your own docs.
19. **Production path ≠ observer path** — the hardest bugs (state root mismatches in `produceBlockWrapper`) only appeared on the validator/producer node. Observer nodes showed zero errors. Always test both roles separately with targeted log checks.
20. **Only report when ALL acceptance criteria are met** — Nico's rule. Don't send "ISR=0 but still some lag" updates. Iterate silently, report once when everything's green. Partial updates waste reviewer time and create noise.
21. **Define acceptance counters upfront** — before any soak, list the exact log patterns/metrics that must be zero. Makes pass/fail unambiguous and prevents goalpost-moving.
22. **Sub-agent review during debugging, not just before PR** — gpt-advisor identified the gossip race condition hypothesis from log patterns while I was still instrumenting. Get second opinions early in the debug cycle, not just at the end.
23. **Stale object references after in-place mutations** — fork-choice status updates (PENDING→FULL) don't automatically propagate to all code paths holding references to the old object. After any state mutation, trace all consumers to verify they see the updated state. This was the root cause of the `BLOCK_ERROR_INVALID_STATE_ROOT` in block production.
24. **Timeline reconstruction for race conditions** — when multiple async paths interact (gossip handler, sync, import, verification), reconstruct the exact event ordering from timestamps. Simple log grepping misses the crucial "which happened first" context.
25. **Tracker + HEARTBEAT.md priority entry = multi-session continuity** — `notes/epbs-devnet-0/TRACKER.md` was the single source of truth across 10+ sessions. The `HEARTBEAT.md` top-priority entry ensured every heartbeat resumed work instead of just monitoring. Without both, progress would have stalled between sessions.
26. **Multiple soak passes are necessary** — first clean soak may pass, then a second reveals edge cases. Run extended soaks (hours) and at different topologies (2-node, 4-node, different client ratios). Short soaks give false confidence.
27. **Alt-port configs for Kurtosis** — Docker port collisions with other services are common on shared servers. Always use non-default port ranges to avoid bind failures.

### Learnings from first run (2026-02-15)
1. **Keep Codex prompts concise** — long specs can cause hangs. Summarize requirements, don't paste full spec tables.
2. **Codex doesn't know project conventions** — it assumed per-package lint/build but Lodestar uses global `biome check` and `pnpm -r build`. Always review output against project norms.
3. **Sub-agent reviewers need code inline** — gemini-reviewer can't access gists/files. Pass key code sections in the task prompt.
4. **2 advisor rounds was sufficient** — round 1 caught major design issues (bash→Node, dependency graph), round 2 tightened details. Diminishing returns after 3.
5. **Phase 4 self-review is critical** — caught 2 bugs Codex missed. Never skip.

### Learnings from EIP-8025 (2026-02-16, in progress)
6. **Add Phase 0: Research for interop features** — when matching other client implementations, invest heavily in reading their code before writing the spec. For EIP-8025, studying Lighthouse (54 files), Prysm, and kurtosis configs revealed critical wire format divergences from the consensus spec that would have been wrong assumptions otherwise.
7. **Foundation commits can be done directly** — simple type definitions, constants, and boilerplate don't benefit from Codex. Save Codex for complex logic (networking, state management). I did Phase A (SSZ types + constants) manually in ~30 min vs the overhead of setting up a Codex session.
8. **Break large features into sub-phases** — instead of one massive Codex handoff, split into A/B/C/... phases with build verification between each. Each phase should be a committable, testable unit. Prevents compounding errors.
9. **Spec should document wire format divergences** — for interop features, explicitly note where devnet wire format differs from the formal spec. This prevents future confusion and helps when migrating to spec-compliant types later.
10. **Research artifacts are valuable** — save deep-dive notes (e.g., `notes/eip8025/LIGHTHOUSE-DEEP-DIVE.md`, `LODESTAR-MAPPING.md`) alongside the spec. Future contributors (including future-me) need this context.

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
- **Document learnings** — update this skill after each use
- **Fresh worktree per feature** — keep working states independent
- **Ignore sim/e2e failures** unless Nico specifically asks to investigate

---

## Self-Maintenance

If any commands, file paths, URLs, or configurations in this skill are outdated or no longer work, update this SKILL.md with the correct information after completing your current task. Skills should stay accurate and self-healing — fix what you find broken.

