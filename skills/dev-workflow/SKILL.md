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

## Phase 0: Research (for interop/cross-client features)

**When to use:** Features that need to match other client implementations (Lighthouse, Prysm, etc.) or implement new EIPs/specs.

1. Clone/study reference implementations from other clients
2. Read the formal spec and note divergences in practice
3. Study devnet configs (kurtosis, etc.) for integration patterns
4. Save research artifacts: `notes/<feature>/RESEARCH.md`, `*-DEEP-DIVE.md`, `*-MAPPING.md`
5. Document wire format differences between spec and actual devnet usage

**Output:** Research notes + clear understanding of what to actually implement (which may differ from the spec).

**Skip if:** Feature is Lodestar-internal (refactor, optimization, test improvement).

## Phase 1: Spec & Architecture

**Goal:** Produce a written spec that's good enough for someone else to implement.

1. Analyze the problem — read relevant code, specs, issues
2. Draft initial approach with key decisions, edge cases, test plan
3. Send to **gpt-advisor** (`thinking: high`) for feedback
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

## Phase 3: Implementation (Codex CLI or Claude CLI)

Choose agent based on task characteristics:

| Use Codex CLI when... | Use Claude CLI when... |
|---|---|
| Clear, focused implementation tasks | Tasks needing broader reasoning |
| "Implement this interface" | Refactoring, debugging, test writing |
| Structured/repetitive code | Understanding system-wide implications |
| Speed is priority | Nuanced design decisions |

### Spawning a coding agent

```bash
# Always provide CODING_CONTEXT.md + task-specific instructions
cd ~/lodestar-<feature-name>

# Codex CLI
codex exec --full-auto "Read CODING_CONTEXT.md in ~/.openclaw/workspace/ for project context. Then: <task description>"

# Claude CLI
claude "Read CODING_CONTEXT.md in ~/.openclaw/workspace/ for project context. Then: <task description>"
```

For complex tasks, write a task file first:
```bash
# Write task instructions
cat > /tmp/task-<feature>.md << 'EOF'
# Task: <description>
Read ~/.openclaw/workspace/CODING_CONTEXT.md for project conventions.
## Requirements
...
## Files to modify
...
## Acceptance criteria
...
EOF

# Hand off (background + PTY for monitoring)
# Codex:
exec pty:true workdir:~/lodestar-<feature> background:true \
  command:"codex --full-auto exec 'Follow instructions in /tmp/task-<feature>.md'"
# Claude:
exec pty:true workdir:~/lodestar-<feature> background:true \
  command:"claude 'Follow instructions in /tmp/task-<feature>.md'"
```

### Parallel execution

Spawn multiple agents in separate worktrees for independent tasks:
```bash
# Task A in worktree A
exec pty:true workdir:~/lodestar-taskA background:true command:"codex ..."
# Task B in worktree B  
exec pty:true workdir:~/lodestar-taskB background:true command:"claude ..."
# Monitor both
process action:list
```

**The coding agent has full access to the worktree** — it can:
- Read and modify files
- Run `pnpm build`, `pnpm lint`, `pnpm check-types`
- Run targeted unit tests
- Iterate on its own errors

**After agent finishes:**
- Review `git diff` in the worktree
- Check that all acceptance criteria from spec are met
- Run build/lint/tests myself to verify

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
3. **Sub-agent review:** Send diff to gemini-reviewer and/or codex-reviewer
4. **Fix issues:** Small fixes → do directly. Large issues → back to Codex

## Phase 5: PR

1. Commit with clear message, sign with GPG
2. Push to fork
3. Open PR with description referencing the spec
4. Standard review process

## Small Fixes Exception

For trivial changes (lint fixes, one-liners, typos), skip this workflow and just do them directly. Use judgment — if it takes more than 15 minutes of thinking, use the full workflow.

## Iteration Log

Track what works and what doesn't after each use:

| Date | Feature | What worked | What to improve |
|------|---------|-------------|-----------------|
| 2026-02-15 | pre-validate.mjs | Spec rounds with advisor caught edge cases early; Codex produced working 662-line script | Codex hung on first attempt (long prompt); needed concise retry. Codex doesn't understand project-specific conventions (global vs per-package lint/build) — always verify. Gemini reviewer failed without file access — need to pass code inline. |
| 2026-02-16 | EIP-8025 optional proofs | Deep research phase paid off — studying 54 Lighthouse files + Prysm + kurtosis configs before speccing prevented wrong assumptions. gpt-advisor confirmed interop-first approach in 2 rounds. Phase A (types) done cleanly. | Need Phase 0 (Research) for cross-client interop features. Simple foundation work (types/constants) faster done directly than via Codex. Break big features into sub-phases with verification between each. |
| 2026-02-17 | EIP-8025 kurtosis revalidation (orchestrator test) | Claude CLI produced 406-line validation script from task file spec in ~75s. Parallel execution (Docker + Claude CLI) eliminated wait time. Stayed responsive to notifications throughout. CODING_CONTEXT.md reusable across tasks. | Task files must be in worktree (not /tmp). `--print` doesn't write files. Trust prompt on first run. Always include env-specific constants (slot time etc.) in task file. Review is the bottleneck — consider delegating that too. |

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

## Key Rules

- **I am responsible** for the final result — no blaming sub-agents
- **Spec quality = implementation quality** — invest time in Phase 1
- **Document learnings** — update this skill after each use
- **Fresh worktree per feature** — keep working states independent
- **Ignore sim/e2e failures** unless Nico specifically asks to investigate
