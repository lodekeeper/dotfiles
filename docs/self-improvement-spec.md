# OpenClaw Agent Self-Improvement Spec: The Learning Loop

> How an AI agent identifies its own weaknesses, codifies fixes, and gets better over time.

**Author:** Lodekeeper 🌟
**Version:** 1.0
**Date:** 2026-04-04

---

## Overview

AI agents don't improve automatically. Without a deliberate feedback loop, the same mistakes repeat across sessions. This spec describes a system for turning failures into rules, weaknesses into strengths, and experience into documented wisdom.

**The core loop:**

```
Mistake / Failure
       │
       ▼
Daily Note (capture what happened)
       │
       ▼
Lesson (extract the principle)
       │
       ▼
Rule in AGENTS.md (enforce the fix)
       │
       ▼
Reduced future failures
```

---

## Part 1: Capturing Failures

### Immediate Documentation

When something goes wrong:
1. **Write it to today's daily note immediately** — not later, not "when I have time"
2. **Include:** what happened, why it happened, what the impact was
3. **Be honest** — don't minimize or rationalize

```markdown
### 14:30 UTC — Force-pushed PR #8924
- What: Rebased feature branch onto unstable and force-pushed
- Why: Thought it would clean up the commit history
- Impact: Matt's review comments became orphaned. 
  He had to re-find his place in the diff.
- Lesson: Never force push. Use merge. Squash on merge button.
```

### The "Scar" Principle

Every operational rule should be traceable to an incident. If you can't point to the time it went wrong, the rule might be theoretical rather than practical. Practical rules get followed. Theoretical rules get ignored.

---

## Part 2: Extracting Lessons

### From Daily Note to Lesson

The nightly consolidation pipeline (see `memory-spec.md`) extracts lessons automatically. But the highest-quality lessons come from deliberate reflection:

**Questions to ask:**
- What went wrong? (the symptom)
- Why did it go wrong? (the root cause)
- What should I have done instead? (the fix)
- How do I prevent this from happening again? (the rule)
- Is there a broader pattern here? (the meta-lesson)

### Lesson Quality Levels

| Level | Example | Impact |
|-------|---------|--------|
| **Symptom-level** | "Lint failed on PR" | Low — just a reminder |
| **Root-cause** | "Forgot to run lint before pushing" | Medium — explains the failure |
| **Systemic** | "No pre-push checklist exists" | High — fixes the category of failure |
| **Meta** | "I skip verification steps under time pressure" | Highest — changes behavior patterns |

Push lessons toward the systemic and meta levels. Symptom-level lessons don't prevent recurrence.

---

## Part 3: Codifying Rules

### The AGENTS.md Feedback Loop

When a lesson reaches the "systemic" level, it becomes a rule in AGENTS.md:

```markdown
## 🚫 Pre-Push Rules (MANDATORY)
- ALWAYS run `pnpm lint` before pushing — no exceptions
  (Incident: PR #8906, 2026-02-14 — biome formatting failure caught by Nico)
```

**Rules should include:**
- What to do (clear, actionable)
- The incident that created the rule (so future-you understands why)
- "No exceptions" if it's truly mandatory

### The IDENTITY.md Self-Assessment

Maintain an honest "Known Weaknesses" section:

```markdown
## Known Weaknesses
- Over-commit and under-document. When in flow, forget to take notes.
- Declare fixes done from partial test runs.
- Skip verification steps under time pressure.
- Over-build infrastructure when simpler would do.
```

**Why this matters:** Self-awareness drives targeted improvement. If you know you skip verification under pressure, you can add automation to force it (pre-push hooks, mandatory checklists).

### The MEMORY.md Lessons Section

Long-term lessons that survive session restarts:

```markdown
## Lessons Learned
- 2026-02-18: OUTSOURCE implementation to coding agents. 
  I am the orchestrator.
- 2026-02-20: BACKLOG entry BEFORE starting work — no exceptions.
- 2026-03-06: Sub-agent reviewers hallucinate. Verify everything.
```

These get read at session startup. They prime the agent's behavior before work begins.

---

## Part 4: Periodic Audits

### Weekly Autonomy Audit

A scheduled review (cron job or manual) that asks:

1. **What mistakes did I make this week?** (check daily notes)
2. **Are there patterns?** (same type of mistake recurring)
3. **Which rules am I not following?** (check AGENTS.md against actual behavior)
4. **What should I add to AGENTS.md?** (new rules from new failures)
5. **What should I remove?** (rules that are no longer relevant)
6. **Am I getting better at my known weaknesses?** (check IDENTITY.md)

### Memory Maintenance

Every few days (during heartbeats or dedicated sessions):
1. Read through recent daily notes
2. Identify significant lessons worth keeping long-term
3. Update MEMORY.md with distilled learnings
4. Remove outdated info from MEMORY.md
5. Check that bank/state.json entries are current

---

## Part 5: Improvement Vectors

### Capability Gaps

When you notice you can't do something:
- **Don't just note it** — fix it
- Add a cron job, write a script, create a skill, or document a workflow
- If it requires system changes, ask the human

### Process Improvements

When a workflow is clunky:
- Document the current process
- Identify the friction points
- Propose improvements to the human
- Implement once approved

### Tool Learning

When new tools become available:
- Test them in a safe environment
- Document usage in TOOLS.md
- Compare against existing tools
- Adopt if genuinely better, don't adopt just because they're new

---

## Part 6: The Confidence Discipline

### State Uncertainty Early

**Incident:** Declared a fix complete before full verification. Was challenged multiple times before admitting uncertainty.

**Rule:** When confidence is below full verification:
- Say "needs verification" immediately
- Don't use language that implies completion
- Distinguish between "I believe" and "I've confirmed"

### The Verification Ladder

| Confidence Level | Statement | Required Evidence |
|------------------|-----------|-------------------|
| Hypothesis | "I think X might fix it" | Reasoning only |
| Implemented | "I've written the fix" | Code exists |
| Locally tested | "Tests pass locally" | Test output |
| Fully verified | "This is fixed" | Full CI/validation suite passes |
| Production confirmed | "This is working in production" | Live metrics/logs |

**Only claim "fixed" at the "fully verified" level or above.**

---

## Anti-Patterns

### ❌ Incident amnesia
Something goes wrong. Agent moves on without documenting it. Same thing happens next week. **Document every failure in daily notes.**

### ❌ Symptom-level lessons only
"Remember to run lint." But no checklist, no automation, no process change. The symptom repeats. **Push lessons to the systemic level.**

### ❌ Rules without incidents
"Always do X" but nobody remembers why. The rule seems arbitrary. It gets ignored. **Link every rule to its originating incident.**

### ❌ Never auditing the rules
AGENTS.md grows to 100 rules. Many are outdated. The agent reads them all at startup but follows few. **Periodic audit: remove stale rules, reinforce active ones.**

### ❌ Ignoring patterns
The same type of failure happens three times. Each time it's treated as isolated. The pattern isn't identified. **Look for recurring failure types, not just individual incidents.**

### ❌ Defensive about weaknesses
Agent rationalizes failures instead of acknowledging them. "It was a flaky test" instead of "I should have run the full suite." **Honest self-assessment enables improvement.**

---

## Quick Start

1. Start capturing failures in daily notes (immediately, not retroactively)
2. Extract systemic lessons weekly
3. Add rules to AGENTS.md with incident references
4. Maintain a "Known Weaknesses" section in IDENTITY.md
5. Schedule a weekly audit (cron or manual)
6. Review and prune rules periodically
7. Push lessons toward systemic/meta levels, not just symptoms
