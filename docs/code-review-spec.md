# OpenClaw Agent Code Review Spec: Multi-Persona Review Workflow

> How to review code with specialized sub-agent personas for comprehensive coverage.

**Author:** Lodekeeper 🌟
**Version:** 1.0
**Date:** 2026-04-04

---

## Overview

A single reviewer catches ~60% of issues. Multiple specialized reviewers with different perspectives catch ~90%. This spec describes a multi-persona code review system where the orchestrating agent delegates review to specialized sub-agents, synthesizes findings, and posts a consolidated review.

---

## The Think → Consult → Verify → Deliver Pipeline

Every review follows this flow:

```
1. THINK    — Read the PR, form initial impressions
2. CONSULT  — Send diff to specialized reviewer agents
3. VERIFY   — Cross-check findings against actual diff
4. DELIVER  — Synthesize into one consolidated review
```

**Why not just review directly?** Blind spots. A single perspective misses categories of issues. The bug hunter finds logic errors but misses security implications. The architect sees structural problems but misses off-by-one errors. Specialization + synthesis > generalist review.

---

## Reviewer Personas

Each persona has a focused mandate and review lens:

| Persona | Focus | When to Use |
|---------|-------|-------------|
| `review-bugs` | Functional correctness, logic errors, edge cases | Always — every PR |
| `review-security` | Exploitable vulnerabilities, input validation | PRs touching networking, APIs, auth, crypto |
| `reviewer-architect` | Design alignment, structural fit, abstraction levels | PRs adding new subsystems, refactors, API changes |
| `review-wisdom` | Best practices, maintainability, code health | PRs with complex logic, new patterns |
| `review-linter` | Style consistency, naming, convention alignment | PRs from new contributors, style-heavy changes |
| `review-defender` | Malicious code, supply chain risks, insider threats | Dependency updates, external contributor PRs |
| `review-devils-advocate` | Challenge the premise — is this change even needed? | Feature PRs, large refactors |
| `codex-reviewer` | General code quality, correctness | Final quality gate |
| `gpt-advisor` | Architecture consultation, spec interpretation | Complex design decisions, spec-adjacent PRs |

### Reviewer Selection Matrix

Not every PR needs all reviewers. Select based on scope:

| PR Type | Recommended Reviewers |
|---------|----------------------|
| Bug fix (small) | `review-bugs`, `codex-reviewer` |
| Bug fix (complex) | `review-bugs`, `review-security`, `codex-reviewer` |
| New feature | `review-bugs`, `reviewer-architect`, `review-wisdom`, `review-devils-advocate` |
| Refactor | `reviewer-architect`, `review-wisdom`, `review-devils-advocate` |
| Security-sensitive | `review-bugs`, `review-security`, `review-defender` |
| Dependency update | `review-defender`, `review-bugs` |
| Performance | `review-bugs`, `review-wisdom`, `codex-reviewer` |
| External contributor | `review-bugs`, `review-security`, `review-defender`, `review-linter` |

---

## The Review Process

### Step 1: Gather Context

```bash
# Get the diff
gh pr diff <PR_NUMBER>

# Get PR description and metadata
gh pr view <PR_NUMBER>

# Get all existing review comments
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments
```

### Step 2: Spawn Reviewers

Send the diff + context to each selected reviewer as a sub-agent:

```
Task: Review this PR diff for [persona focus].

Context:
- PR title: <title>
- PR description: <description>
- Files changed: <file list>

<diff content>

Focus on: [persona-specific instructions]
Report findings as: severity (critical/warning/nit), file, line, description
```

**Important:** Spawn reviewers in parallel — they're independent.

### Step 3: Verify Findings (CRITICAL)

**Sub-agents hallucinate.** They sometimes flag files that aren't in the diff, reference non-existent functions, or invent issues.

Before including any finding in the review:
1. **Check the file is in the diff:** `git diff --name-only origin/unstable...HEAD`
2. **Check the line exists:** Read the actual file at the referenced line
3. **Check the issue is real:** Does the code actually do what the reviewer claims?

False positives pollute the review and waste the PR author's time. Verify everything.

### Step 4: Synthesize and Post

Combine findings from all reviewers into one consolidated review:

```markdown
## Review Summary

**Reviewers consulted:** review-bugs, reviewer-architect, review-security

### Critical
- [file:line] Description of critical issue (found by: review-bugs)

### Warnings
- [file:line] Description of warning (found by: reviewer-architect)

### Nits
- [file:line] Style suggestion (found by: review-wisdom)

### Positive
- Good use of X pattern in Y file
- Clean separation of concerns in Z
```

**Always include positives.** Reviews that are 100% criticism are demoralizing and often miss the forest for the trees.

---

## Handling PR Feedback

When review comments come back from the PR author:

### Reply + Code, Not Reply-Only

When a reviewer comment asks for a code change:
1. **Reply** acknowledging the feedback
2. **Push code** addressing it — in the same session
3. If you can't fix immediately, add to BACKLOG.md as 🔴 urgent

**The failure mode:** Replying "Good point, will fix" but not pushing code. Words without commits aren't addressing feedback.

### Reply In-Thread

```bash
# Get comment ID
gh api repos/{owner}/{repo}/pulls/{pr}/comments --jq '.[] | {id, body}'

# Reply in the same thread
gh api -X POST repos/{owner}/{repo}/pulls/{pr}/comments \
  -f body="Fixed in <commit>" \
  -F in_reply_to=<comment_id>
```

**Don't** use `gh pr comment` for review responses — that creates a standalone comment, not a thread reply.

### Address ALL Comments

Including bot reviewers (Gemini, CodeRabbit, etc.). Don't skip comments just because they came from a bot. The human expects every comment addressed.

---

## Anti-Patterns

### ❌ Trusting reviewer findings without verification
Reviewer says "file X has a bug on line Y." You include it in the review. File X isn't even in the diff. **Always verify against `git diff --name-only`.**

### ❌ Posting before all reviewers finish
Two of three reviewers respond. You post the review. The third reviewer finds a critical issue. Now you need to amend. **Wait for all sub-agents to complete.**

### ❌ Review walls of criticism
Every finding is a problem, no positives mentioned. The author feels attacked. **Include what's good. Balance matters.**

### ❌ Reply-only feedback
Author asks for a change. You reply "will fix." You don't push code for an hour. **Reply + code in the same session.**

### ❌ One-size-fits-all reviewer selection
Every PR gets all 9 reviewers. Token burn is massive, most findings are irrelevant for small PRs. **Select reviewers based on PR scope.**

---

## Quick Start

1. Define 2-3 reviewer personas (start with `review-bugs` + `codex-reviewer`)
2. For each PR: gather diff → spawn reviewers → verify findings → synthesize
3. Always verify findings against actual diff before posting
4. Reply to feedback with code, not just words
5. Add more personas as you identify blind spots in your reviews
