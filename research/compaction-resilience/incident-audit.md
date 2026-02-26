# Compaction Incident Audit & Memory System Analysis

**Date:** 2026-02-26
**Author:** Lodekeeper (subagent: compaction-incident-audit)
**Source:** MEMORY.md, BACKLOG.md, daily notes (memory/*.md), skill files, plan.md

---

## 1. Inventory of Compaction Incidents

### 1.1 Documented Incidents (from MEMORY.md Lessons Learned)

| Date | Incident | What Was Lost | Mitigation Added |
|------|----------|---------------|------------------|
| **2026-02-01** | Context compacted during work session | Track of current tasks, decisions made, feedback received | Added rule: "Always take notes while working! Write to daily notes during work sessions" |
| **2026-02-26** | Oracle (GPT-5.2-pro) output lost mid-run | Entire `tidy-prairie` session architecture consultation output — minutes of processing gone | Added rule: "Always tee Oracle output to a file. EVERY Oracle invocation must use `\| tee ~/research/<topic>/oracle-output.md`" |

### 1.2 Inferred Incidents (from daily notes patterns)

| Date | Evidence | Likely Loss |
|------|----------|-------------|
| **2026-02-25** | Daily note says "Context hit 91%. Need to check that session result" — referring to Oracle output during web scraping research | Web scraping Oracle synthesis output (tidy-prairie session). Note was written *after* compaction as a recovery breadcrumb. |
| **2026-02-20** | Nico flagged "dashboard showed no activity" for dotfiles repo work — entire task done without BACKLOG entry | Task context likely lost between compaction and Nico's check. The work happened in a "gap" invisible to persistence. |
| **2026-02-14** | Missed Nico's "yes, move it to 3" follow-up on PR #8909; dismissed notification without re-reading | Post-compaction state lacked awareness of the notification's updated content. |
| **2026-02-17** | Self-reflection exercise identified 5 failures: tunnel vision, missing Discord mentions, dropping tasks | Multiple compaction-adjacent failures — tasks that were "in working memory" but never persisted to files. |
| **2026-02-04** | Missed @mention on issue #7559 because GitHub notification `updated_at > last_read_at` was missed | Notification state (what's already handled vs. what's new) is purely in-context. After compaction, re-read notifications look "already handled." |

### 1.3 Near-Miss Incidents

| Date | Situation | Why It Didn't Fail |
|------|-----------|-------------------|
| **2026-02-24** | Multi-day libp2p identify investigation with dozens of exec outputs, monkeypatches, A/B experiments | Extensive daily notes captured root cause finding (23:35 UTC), all experiment results, and next steps. This is the gold standard of our note-taking. |
| **2026-02-23** | EPBS devnet-0 interop marathon — 5 fix iterations, spec insights | Detailed daily notes captured every fix iteration with commit hashes. Survived compaction. |
| **2026-02-21** | 26-commit EPBS sprint, Docker incident, multiple soak runs | Very thorough daily note (7453 bytes). All critical state survived. |

---

## 2. Current Memory System — Structural Analysis

### 2.1 MEMORY.md

**Size:** ~4.5KB, 80 lines
**Structure:**
- Who I Am (identity)
- Key Rules (behavioral)
- Dev Workflow (process)
- Sub-Agent Config (tooling)
- Channels (infra)
- Projects (repos)
- Ongoing Responsibilities (recurring)
- Lessons Learned (chronological list)

**Strengths:**
- Compact enough to fit in context window injection
- Identity and rules are clear and actionable
- Lessons Learned section is the most valuable part — captures post-incident rules
- Dev workflow section prevents re-discovery of process

**Weaknesses:**
- **Lessons Learned is append-only and unsorted.** 20 entries, no categories, no severity. Hard to scan for relevant lessons during a specific task.
- **No "current state" section.** After compaction, there's no "what am I working on RIGHT NOW?" — you must infer from BACKLOG.md.
- **No relationship map.** Doesn't capture which PRs are related, which tasks depend on each other, or multi-day context threads.
- **Missing: technical knowledge.** Only one technical entry (fork-choice `getHead()` cache). Deep debugging knowledge (like the libp2p identify root cause) lives in daily notes, not here.
- **Missing: people context.** No notes on collaborators' preferences, timezone patterns, communication styles (beyond "Nico is boss").
- **No versioning.** No way to tell what was recently added vs. stale.

### 2.2 Daily Notes (memory/YYYY-MM-DD.md)

**Coverage:** 25/25 days for Feb 2026 (no gaps), plus 3 earlier dates.
**Total files:** 36 (including supplementary files like `-afternoon.md`, `-late.md`, analysis files)
**Size range:** 707 bytes (2026-02-06, minimal) to 12,523 bytes (2026-02-16, marathon day)

**Format consistency analysis:**
| Section | Present in % of notes | Notes |
|---------|----------------------|-------|
| PRs Opened/Merged/Reviewed | ~80% | Most common structure element |
| Key Technical Work | ~70% | Deep debugging days have this |
| Lessons Learned | ~60% | Most valuable but not always present |
| Status/Monitoring | ~50% | Heartbeat-style checks |
| Code Written | ~40% | Sometimes merged into technical work |
| Tomorrow's Focus | ~20% | Only early days, abandoned quickly |
| Headline/Summary | ~40% | Useful for quick scanning |

**Strengths:**
- **No date gaps** — every day from Feb 1-25 has a note. Excellent consistency.
- **Heavy days produce detailed notes** — EPBS marathon days (Feb 21, 23, 24) have excellent documentation with commit hashes, experiment results, and decision rationale.
- **Multiple notes per day** when needed (Feb 21 has both main + afternoon, Feb 25 has main + late).
- **Supplementary files** for deep dives (OOM analysis, release report, deep review).

**Weaknesses:**
- **Format inconsistency.** Early notes (Feb 1-3) use different headings than later ones. No template enforced.
- **Lightweight days produce thin notes.** Feb 6 is only 12 lines — just a notification acknowledgment. Feb 8 and 10 are also very thin.
- **No "resumption context."** Notes are written as end-of-day summaries, not as "here's what you need to know if you're picking this up cold." They narrate what happened, not what the current state IS.
- **No forward pointers.** Notes rarely say "next: do X" in a way that's machine-actionable.
- **Buried in detail.** Finding a specific fact (e.g., "what was the root cause of the identify issue?") requires reading multiple day files.

### 2.3 BACKLOG.md

**Size:** ~10KB, well-structured
**Format:** Priority tags (🔴/🟡/🟢), source attribution, sub-task checklists, status markers

**Strengths:**
- **Excellent task tracking.** Sub-tasks with checkboxes show progress clearly.
- **Source attribution.** Every task records who asked and when — critical for accountability.
- **Priority system.** 🔴/🟡/🟢 enables triage.
- **Active vs. Completed separation.** Clean lifecycle.
- **Detailed sub-tasks.** The libp2p investigation (13 sub-tasks) is exemplary — each step documented with results.

**Weaknesses:**
- **Gets long fast.** Completed tasks accumulate. Feb 24's completed section alone has 20+ entries. Need periodic archival.
- **Tasks that don't start as BACKLOG entries get lost.** The 2026-02-20 dotfiles incident proves this — work done outside BACKLOG is invisible.
- **No "blocked-by" relationships.** Tasks are flat lists, not dependency graphs. The libp2p npm publish block is noted but not linked to anything.
- **Stale entries linger.** PR #8924 and #8931 have been "awaiting review" since mid-February.
- **Missing: micro-tasks.** Quick actions (reply to a comment, check a notification) often don't get BACKLOG entries despite the "add everything" rule.

### 2.4 Skill Files (skills/*/SKILL.md)

**Count:** 11 skill files
**Total size:** ~125KB
**Skills:** deep-research, dev-workflow, eth-rnd-archive, grafana-loki, kurtosis-devnet, local-mainnet-debug, lodestar-review, oracle-bridge, release-metrics, release-notes, web-scraping

**Strengths:**
- **Excellent durable memory.** Skills encode procedural knowledge that survives all compaction events. They're essentially "how to do X" long-term memory.
- **Self-contained.** Each skill has everything needed to execute the procedure.
- **Evolve over time.** dev-workflow has been updated multiple times as process improves.
- **Reusable across sessions.** Any new session can read a skill and execute it without prior context.

**Weaknesses:**
- **Only encode procedures, not state.** A skill tells you HOW to debug libp2p, but not WHERE you left off in a debugging session.
- **Not indexed.** No manifest or catalog. Must `ls skills/` to discover what exists.
- **Large.** web-scraping is 25KB, dev-workflow is 22KB, deep-research is 20KB. Reading all skills would consume significant context.
- **No versioning or changelog.** Can't tell when a skill was last updated or what changed.

### 2.5 Supplementary State Files

| File | Purpose | Staleness Risk |
|------|---------|---------------|
| `agent-status.json` | Current task/status | **HIGH** — shows "CF bypass research" from Feb 25, no auto-update |
| `heartbeat-state.json` | Last check timestamps | **HIGH** — timestamps from Feb 2026, `consensus_specs_latest: v1.6.1` likely stale |
| `discord-threads.json` | Tracked Discord threads | **MEDIUM** — static tracking data |
| `unstable-ci-tracker.json` | CI failure tracking | **MEDIUM** — useful but needs regular updates |
| `pr-todo.md`, `pr-review-backlog.md` | PR tracking | **MEDIUM** — supplementary to BACKLOG.md |
| `gloas-implementation-status.md` | EPBS implementation tracking | **LOW** — reference doc |

---

## 3. Current Memory System Strengths

1. **Daily note consistency is excellent.** 25/25 days covered, no gaps. This is the backbone.
2. **BACKLOG.md is the most compaction-resilient artifact.** It captures what needs doing and what's done, with source attribution.
3. **Skills encode durable procedural knowledge.** The local-mainnet-debug skill was created *from* a debugging investigation — crystallizing ephemeral knowledge into permanent form.
4. **MEMORY.md Lessons Learned captures post-incident rules.** Each lesson is a compaction mitigation in itself.
5. **Heavy investigation days produce great notes.** Feb 21, 23, 24 are model examples of state capture.
6. **Multiple files per day when needed.** The `-afternoon`, `-late`, analysis suffix pattern handles session boundaries.

---

## 4. Current Memory System Gaps & Weaknesses

### 4.1 No Working Memory / Session State File
**Gap:** There is no "what I'm doing RIGHT NOW and what I need to know to resume" file. After compaction, the agent must reconstruct current state from BACKLOG + daily notes + file system.

**Impact:** HIGH. This is the #1 source of post-compaction confusion.

### 4.2 Tool Output is Ephemeral
**Gap:** `exec` results, `web_fetch` content, sub-agent outputs live only in the conversation context. When compacted, they vanish entirely.

**Impact:** HIGH. The Oracle incident (Feb 26) is the clearest example — minutes of GPT-5.2-pro processing lost. The "tee to file" rule exists but requires manual discipline every time.

### 4.3 No Pre-Compaction Hook
**Gap:** There's no automatic save-state-before-compaction mechanism. Compaction happens when it happens, and whatever isn't persisted is lost.

**Impact:** HIGH. This is architectural — can't be fully solved by discipline alone.

### 4.4 Lessons Learned is Unstructured
**Gap:** 20 entries in a flat chronological list. No categorization by type (process, technical, communication, git).

**Impact:** MEDIUM. Hard to find relevant lessons when they're mixed together.

### 4.5 Daily Notes Lack Resumption Context
**Gap:** Notes are retrospective summaries, not forward-looking state dumps. They say "what happened" not "what to do next."

**Impact:** MEDIUM. Post-compaction, the agent reads notes but still needs to figure out what to do.

### 4.6 No Cross-File Linking
**Gap:** BACKLOG doesn't link to daily notes. Daily notes don't link to skills. MEMORY.md doesn't reference specific daily notes.

**Impact:** LOW-MEDIUM. Finding information requires grepping or reading multiple files.

### 4.7 Stale State Files
**Gap:** `agent-status.json` and `heartbeat-state.json` go stale and aren't reliable for current state.

**Impact:** LOW. These are supplementary, not primary.

---

## 5. Most Vulnerable State Types (What Gets Lost Most Often)

### Tier 1: Almost Always Lost (unless manually persisted)
1. **Tool output** — exec results, web fetches, file reads. The conversation is full of these; none survive compaction.
2. **Intermediate reasoning** — "I think the issue is X because of Y" chains. Compaction summary keeps conclusions, loses reasoning.
3. **Sub-agent outputs** — Review feedback, advisor consultations. Must be saved to files explicitly.
4. **In-flight async state** — Oracle runs, background processes, pending sub-agents. If compaction hits mid-run, both the request and response can be lost.

### Tier 2: Sometimes Lost (depends on note-taking discipline)
5. **Decision rationale** — "I chose approach A over B because..." Often captured in good daily notes, lost in thin ones.
6. **Notification state** — Which GitHub notifications are handled, which need action. Purely in-context.
7. **Task micro-state** — "I'm on step 3 of 7 in this debugging process." BACKLOG sub-tasks help, but only if updated in real-time.

### Tier 3: Usually Survives (good persistence exists)
8. **Task existence** — BACKLOG.md captures tasks well. What exists to do rarely gets lost.
9. **Process knowledge** — Skills and MEMORY.md rules survive permanently.
10. **Git state** — Branches, commits, PRs are durable by nature.
11. **Daily summaries** — Notes capture what happened, even if details are thin.

---

## 6. Patterns That Work vs. Patterns That Fail

### ✅ Patterns That Work

| Pattern | Why It Works | Example |
|---------|-------------|---------|
| **"Tee everything to file"** | Makes ephemeral output durable | Oracle tee rule, benchmark results saved to files |
| **Detailed daily notes on heavy days** | Dense notes are mini-state-dumps | Feb 24's root cause finding at 23:35 UTC |
| **BACKLOG sub-task checklists** | Granular progress tracking survives compaction | libp2p investigation: 13 sub-tasks, each checked |
| **Post-incident lesson capture** | Converts ephemeral learning into permanent rule | 20 lessons in MEMORY.md, each preventing recurrence |
| **Skills from investigations** | Crystallizes debugging knowledge | local-mainnet-debug skill from identify investigation |
| **Source attribution on tasks** | Prevents "why am I doing this?" confusion | Every BACKLOG entry has who/when/where |
| **Multiple notes per day** | Captures state at different points | Feb 25 main + late notes |
| **Supplementary analysis files** | Deep dives don't clutter daily notes | OOM analysis, release report, deep review files |

### ❌ Patterns That Fail

| Pattern | Why It Fails | Example |
|---------|-------------|---------|
| **"I'll remember to save it"** | Manual discipline breaks under load | Oracle output not tee'd (Feb 26) |
| **Relying on conversation context** | Context IS the thing that gets compacted | Feb 1 lesson: "don't rely on conversation context alone" |
| **End-of-day summaries only** | State is lost during the day, between compactions | Thin notes on light days (Feb 6: 12 lines) |
| **Status in JSON files** | Goes stale, not updated atomically with work | agent-status.json stuck on "CF bypass research" |
| **"I'll add it to BACKLOG later"** | Later never comes (or compaction comes first) | Dotfiles repo work invisible (Feb 20) |
| **Dismissing notifications before completion** | Post-compaction, no reminder to follow up | PR #8929 notification dismissed, then missed review |
| **Assuming stale notification = no new content** | GitHub's model: unread ≠ updated | Issue #7559 mention missed (Feb 4) |
| **Relying on a single pass** | If compaction happens during the one pass, it's gone | Mid-run Oracle compaction (Feb 25-26) |

---

## 7. Summary & Key Findings

### The Core Problem
Compaction is **unpredictable and unannounced.** The agent has no warning and no hook to save state. All mitigations are therefore **manual and discipline-dependent.** This creates an inherent fragility: the busier and more cognitively loaded the agent is (exactly when compaction is most likely due to high token usage), the less likely it is to remember manual persistence steps.

### The Bright Spots
The daily notes + BACKLOG + MEMORY.md + skills system is **remarkably effective** for a manual system. Zero date gaps in daily notes across 25 days is impressive. The Lessons Learned section creates a ratchet effect — each failure leads to a permanent rule. Skills crystallize ephemeral knowledge.

### The Structural Gaps
1. **No working memory file** — the biggest gap. Need a file that's always up-to-date with "current state."
2. **No automatic persistence** — everything depends on manual writes.
3. **Tool output is fire-and-forget** — the most information-dense artifacts (exec results, sub-agent outputs) are the most ephemeral.
4. **Notes are retrospective, not prospective** — they capture what happened, not what to do next.

### Reliability Assessment
- **MEMORY.md:** ~95% reliable (always present, always relevant)
- **BACKLOG.md:** ~85% reliable (tasks captured, but micro-tasks and ad-hoc work fall through)
- **Daily notes:** ~75% reliable (always exist, but quality varies; thin days lose detail)
- **Skills:** ~99% reliable (durable, self-contained, always useful)
- **agent-status.json:** ~30% reliable (usually stale)
- **Tool output in context:** ~0% reliable across compaction boundaries

---

*End of audit. This analysis should inform the design of compaction-resilience improvements in the next research phases.*
