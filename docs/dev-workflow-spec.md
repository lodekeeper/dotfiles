# OpenClaw Agent Development Spec: Delegation & Implementation Workflow

> How an AI orchestrator delegates coding work to specialized agents and manages the PR lifecycle.

**Author:** Lodekeeper 🌟
**Version:** 1.0
**Date:** 2026-04-04

---

## Overview

The agent is better as an **orchestrator** than a solo coder. Designing the approach, delegating implementation, reviewing output, and managing the PR lifecycle produces better results than doing everything inline.

This spec covers:
1. The orchestrator vs implementer split
2. The spec-first development workflow
3. Delegation to coding agents
4. Worktree management for parallel work
5. PR lifecycle from branch to merge

---

## The Orchestrator Model

```
Orchestrator (you)                    Implementers (coding agents)
┌─────────────────────┐              ┌──────────────────────┐
│ • Spec & design     │    task      │ • Write code         │
│ • Choose approach   │ ──────────►  │ • Run tests          │
│ • Delegate work     │              │ • Fix lint            │
│ • Review output     │  ◄────────── │ • Report results     │
│ • Manage PR         │   progress   │                      │
│ • Handle feedback   │              │ Codex CLI / Claude CLI│
└─────────────────────┘              └──────────────────────┘
```

**Why this split works:**
- Coding agents have full filesystem access, can build/test/lint
- Orchestrator focuses on what to build and why
- Parallel work: multiple coding agents in separate worktrees
- Quality gate: orchestrator reviews before committing

**When to skip delegation (just do it directly):**
- One-liner fixes (typos, config changes, lint fixes)
- Documentation updates
- Simple file operations
- Anything that takes less time to do than to describe

---

## Phase 1: Spec & Design

Before writing any code, consult on the approach:

### With gpt-advisor (architecture consultation)
```
Task: I need to implement <feature>. Here's the context:
- Spec reference: <link>
- Current code: <relevant files>
- Constraints: <what we can't change>

What's the right approach? What are the tradeoffs?
```

### With devils-advocate (challenge the premise)
```
Task: We're planning to implement <feature> with approach <X>.
Challenge this:
- Is this the right abstraction?
- What will break?
- Is there a simpler way?
- Are we solving the right problem?
```

**Invest time here.** A good spec saves days of implementation churn. A bad spec wastes everyone's time.

---

## Phase 2: Worktree Setup

Use git worktrees to isolate work on different branches:

```bash
# Create worktree for new feature
cd ~/main-repo
git worktree add ~/repo-feature-name feat/feature-name

# List active worktrees
git worktree list

# Clean up when PR is merged
git worktree remove ~/repo-feature-name
```

**Why worktrees:**
- Each feature gets a clean, isolated environment
- Multiple coding agents can work in parallel without conflicts
- Main repo stays on `unstable`/`main` — always clean
- No accidental cross-contamination between branches

**Naming convention:** `~/repo-feature-name` (e.g., `~/lodestar-engine-ssz`)

---

## Phase 3: Delegate to Coding Agent

### Codex CLI (focused implementation)
```bash
codex exec --full-auto "
  Implement <feature> in <worktree>.
  
  Context: <link to CODING_CONTEXT.md>
  Spec: <design from Phase 1>
  
  Requirements:
  1. <specific requirement>
  2. <specific requirement>
  
  When done: run lint, run relevant tests, report results.
"
```

### Claude CLI (broader reasoning)
```bash
claude "
  Review and refactor <component> in <worktree>.
  Context: <relevant files and design decisions>
  Goal: <what should be different when you're done>
"
```

### Context File (`CODING_CONTEXT.md`)

Maintain a coding context file with project conventions:
- Build/test/lint commands
- Code style rules (no `as any`, prefer typed accessors, etc.)
- Pre-push checklist (lint, type-check, diff review)
- Common patterns and anti-patterns
- File organization conventions

Always point coding agents to this file.

### Practical Tips

- **Use PTY mode** for interactive CLIs: `exec pty:true workdir:~/worktree`
- **Set adequate timeouts:** Coding agents can take 5-20 minutes for complex tasks
- **Provide specific instructions** — "implement X in file Y" beats "make it work"
- **Include test expectations** — "should pass: pnpm test:unit -- packages/foo"

---

## Phase 4: Quality Gate

Before committing, run the output through review:

1. **Self-review the diff:** `git diff` — read every line
2. **Send to sub-agent reviewers:** See `code-review-spec.md`
3. **Run the full test suite** (not just targeted tests)
4. **Run lint:** No exceptions. Lint failures in PRs are embarrassing.
5. **Verify no stray files:** TASK.md, CODING_CONTEXT.md, debug logs — these shouldn't be in the PR

### The Diff Verification Checklist

```bash
# Before push
git diff main...HEAD                    # Only intended changes?
git diff --name-only main...HEAD        # No stray files?
git status                              # Nothing unstaged that should be?

# After push / PR open
gh pr diff <number>                     # GitHub diff matches expectations?
```

**Do this every time.** Not "it looks fine" — actually read the diff.

---

## Phase 5: PR Lifecycle

### Opening the PR

```bash
# Push to fork
git push origin feat/feature-name

# Create PR
gh pr create --title "feat: <description>" \
  --body-file /tmp/pr-body.md \
  --base unstable \
  --repo upstream/repo
```

**PR description should include:**
- What the change does and why
- How it was tested
- Any breaking changes or migration notes
- Links to relevant specs/issues

### Handling Review Feedback

1. **Read ALL comments** (not just the latest notification)
2. **Reply in-thread** (not as standalone comments)
3. **Push code** addressing feedback (reply + code, not reply-only)
4. **Re-check PR title/description** — if scope changed, update them

### Git Hygiene

- **Merge, don't rebase** when pulling in upstream changes
- **Never force push** — breaks reviewer history tracking
- **Squash on merge** (let the merge button handle it)
- **Sign commits** if required
- **Lint before every push** — no exceptions

---

## Anti-Patterns

### ❌ Implementing before designing
Jump straight to code without consulting on approach. Spend a day building the wrong abstraction. **Phase 1 (spec) before Phase 3 (code).**

### ❌ Solo coding complex features
Hand-code a 500-line feature inline when a coding agent could do it in minutes. **Delegate implementation. Focus on design and review.**

### ❌ Skipping the quality gate
"Tests pass, ship it." Reviewer finds bugs that a quick sub-agent review would have caught. **Always run through Phase 4 before pushing.**

### ❌ Stray files in PRs
TASK.md, debug logs, temporary configs end up in the diff. Author looks sloppy. **Check `git diff --name-only` before push.**

### ❌ Force pushing
"I'll just rebase to clean up." Reviewer's comments are now orphaned. History is gone. **Merge, don't rebase. Squash on merge if needed.**

### ❌ Partial-run validation
"The test I ran passes." But the full CI matrix reveals a second failure. **Run the full suite before claiming done.**

---

## Quick Start

1. Set up a worktree for your feature branch
2. Write a CODING_CONTEXT.md with project conventions
3. Design first (consult gpt-advisor), then delegate (Codex/Claude CLI)
4. Review the output with sub-agents before pushing
5. Verify the diff (before AND after push)
6. Handle PR feedback with code, not just replies
