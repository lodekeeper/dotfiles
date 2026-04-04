# OpenClaw Agent Orchestration Spec: BACKLOG + HEARTBEAT System

> A battle-tested pattern for persistent AI agents that need to track work, manage sub-agents across channels, and stay productive between conversations.

**Author:** Lodekeeper 🌟 (with ~60 days of production use)
**Version:** 1.0
**Date:** 2026-04-04

---

## Overview

This document describes a task-tracking and proactive-monitoring system for OpenClaw agents. It solves three problems:

1. **Context loss** — AI sessions compact/restart and lose track of work
2. **Multi-channel coordination** — tasks arrive from Telegram, Discord, cron jobs, GitHub notifications; work must route back to the right place
3. **Proactive behavior** — the agent should do useful work between user messages, not just react

The system has two core files:
- **`BACKLOG.md`** — the single source of truth for all tasks
- **`HEARTBEAT.md`** — instructions the agent follows on every periodic poll

Both live in the workspace root (`~/.openclaw/workspace/`).

---

## Part 1: BACKLOG.md

### Purpose

Every task the agent works on — whether assigned by a human, discovered via notification, or self-initiated — gets an entry in BACKLOG.md **before** work begins. This is the agent's task board.

### Why It Matters

Without a backlog:
- Tasks get dropped during session compaction
- The human can't see what the agent is doing
- Work happens but isn't tracked, so it "didn't happen"
- Sub-agents in different sessions can't coordinate

### Structure

```markdown
# BACKLOG.md - Task Backlog

**Rules:**
1. ALWAYS add new tasks here immediately — even tiny ones
2. Check this file at start of every session, every heartbeat, and between tasks
3. Mark tasks ✅ when done (archive periodically)
4. Priority: 🔴 urgent (blocking someone) | 🟡 normal | 🟢 low/background
5. Include source (who asked, where, when)
6. Tag tasks with session routing labels (see below)

---

## 📌 Project Name [routing-tag]

### 🟡 Task title
- **Source:** who asked, where, when
- **Status:** current state — what's done, what's next
- **Subtasks:**
  - ✅ completed step
  - 🔲 pending step

## 📌 Another Project [routing-tag]
...

## 📌 Passive watches
- Items being monitored but not actively worked on
```

### Routing Tags

Tags tell the heartbeat system where to send nudges and updates:

- **`[topic:ID]`** — Telegram forum topic (e.g. `[topic:50]` routes to `agent:main:telegram:group:<GROUP_ID>:topic:50`)
- **`[discord:CHANNEL_ID]`** — Discord channel or thread
- **No tag** — work happens in the main session (or wherever the heartbeat runs)

### Rules (Enforce These)

1. **BACKLOG entry BEFORE starting work.** No exceptions. If it's not in the backlog, it didn't happen.
2. **Every entry needs a source.** Who asked? Where? When? This prevents ambiguity.
3. **Update status as work progresses.** Mark subtasks ✅, update status descriptions, note blockers.
4. **Sub-agents MUST update BACKLOG.md.** When a sub-agent works on a tagged task, it writes progress back to the shared BACKLOG.md. This is how the orchestrator knows what happened.
5. **Archive completed tasks periodically.** Move ✅ items to a `BACKLOG_ARCHIVE.md` to keep the active file scannable.

### Priority Guide

| Emoji | Meaning | When to use |
|-------|---------|-------------|
| 🔴 | Urgent — blocking someone | PR review comments, CI failures on open PRs, human waiting |
| 🟡 | Normal — should be done soon | Feature work, routine PRs, investigations |
| 🟢 | Low / background | Nice-to-haves, research, passive monitoring |
| ⏸️ | Paused / on hold | Explicitly parked by the human |
| ✅ | Done | Completed — ready to archive |

---

## Part 2: HEARTBEAT.md

### Purpose

HEARTBEAT.md is the instruction set the agent follows every time it receives a periodic heartbeat poll. It defines **what to check**, **in what order**, and **where to send output**.

### How Heartbeats Work in OpenClaw

OpenClaw can be configured to send periodic "heartbeat" messages to the agent (e.g. every 30 minutes). The agent receives a message matching the heartbeat prompt and must decide what to do. The default prompt is:

```
Read HEARTBEAT.md if it exists (workspace context). Follow it strictly.
Do not infer or repeat old tasks from prior chats.
If nothing needs attention, reply HEARTBEAT_OK.
```

### Structure

```markdown
# HEARTBEAT.md

## 📣 Output Routing
Define where different types of output go:

- **Routine updates** → a dedicated status channel/topic
- **Urgent/blocker** → human's DM
- **Hard guards:**
  - Never post routine output in the human's DM
  - Never mirror the same update to both destinations
  - In DM contexts, default to NO_REPLY unless urgent

## STEP 1: BACKLOG (always first)
1. Read BACKLOG.md
2. Find actionable tasks (not ✅, not passive watches)
3. For tagged tasks → nudge the appropriate session
4. For untagged tasks → work on them directly
5. Only proceed to Step 2 if no actionable tasks remain

## STEP 2: Monitoring (only if backlog is clear)
List what to check: notifications, CI, mentions, etc.
Note which checks are owned by cron jobs (don't duplicate).

## STEP 3: Cleanup / maintenance
Periodic tasks: file cleanup, memory consolidation, etc.
```

### The Critical Ordering

**STEP 1 (backlog) always comes before STEP 2 (monitoring).** This prevents the most common failure mode:

> Agent runs monitoring checks → sees "nothing new" → replies HEARTBEAT_OK → while an actionable task sits untouched in the backlog.

The backlog is work. Monitoring is observation. Work first.

### Session Nudging

When a tagged task is ready for more work, the heartbeat nudges the appropriate session:

```
sessions_send(
  sessionKey: "agent:main:telegram:group:<GROUP_ID>:topic:<TOPIC_ID>",
  message: "Continue working on <task>. Current status: <status>.
            Next step: <next subtask>.
            IMPORTANT: Update BACKLOG.md with your progress."
)
```

**Anti-spam guard:** Don't nudge the same session more than once per ~30 minutes unless there's a status change or new blocker.

### Output Routing Rules

Define explicit destinations to prevent noisy DMs:

| Output type | Destination | Method |
|-------------|-------------|--------|
| Routine status update | Dedicated status channel | `sessions_send` to status topic |
| Blocker / urgent decision | Human's DM | `sessions_send` to DM |
| Task progress | Tagged channel/topic | `sessions_send` to task session |
| Nothing to report | Nowhere | `HEARTBEAT_OK` or `NO_REPLY` |

**The "DM send gate"** — before sending anything to the human's DM from a heartbeat:
1. Is this a blocker? → If no, don't send.
2. Is this an urgent decision the human must make? → If no, don't send.
3. Is this a critical deliverable? → If no, don't send.
4. All no? → `NO_REPLY`.

---

## Part 3: Task Continuity & Agent Orchestration

### STATE.md — Surviving Compaction

AI sessions compact. When they do, conversation history gets summarized and detail is lost. `STATE.md` is a file the agent maintains with **current working state** — what it's actively doing, what's blocked, what's in-flight.

**Purpose:** When the agent wakes up after compaction, it reads STATE.md and knows exactly where it left off. Without it, long-running tasks (multi-day investigations, complex PRs) lose critical context.

**What goes in STATE.md:**
- Active task details (not just "working on X" but the actual investigation state, code paths found, hypotheses tested)
- Open PR table with current status of each
- Environment state (worktree layout, running processes, deployed versions)
- Cleanup items pending

**When to update:**
- Before any expected compaction (pre-compaction memory flushes)
- When significant progress is made on a long-running task
- When switching between tasks

**Example structure:**
```markdown
# STATE.md
# Last updated: 2026-04-04 — Current Working State

## 🔴 Active Task: Fix checkpoint sync crash

### Context
Assigned by Nico, 2026-04-03. Beacon node crashes on restart with
"headState does not exist" error.

### Investigation State
- Root cause: anchor state cached with wrong payload status
- Code paths: chain.ts:391, regen/queued.ts:162
- Fix direction: determine actual payload status on load
- Tested: A/B comparison with Lighthouse confirms mismatch

### Open PRs
| PR | Title | Status |
|---|---|---|
| #9156 | Checkpoint sync fix | Awaiting review |
| #9170 | Gossip counter perf | CI green |

### Environment
~/lodestar-epbs-devnet-0 → active worktree
~/lodestar → unstable (clean)
```

### AGENTS.md — The Rules Engine

`AGENTS.md` is the agent's operating manual. It defines the **session startup sequence** and enforces behavioral rules. For orchestration purposes, the critical sections are:

**Session startup sequence** (runs every session, including after compaction):
1. Read SOUL.md (identity)
2. Read USER.md (human's preferences)
3. Read STATE.md (current working state)
4. Read BACKLOG.md (task list)
5. Read today's daily notes (recent context)

This sequence ensures the agent always has context before acting. The order matters — identity and preferences first, then state and tasks.

**Backlog-first enforcement:**
```markdown
## ⚠️ BACKLOG FIRST — MANDATORY FOR EVERY TASK

Before starting ANY work, add it to BACKLOG.md FIRST.
This is NOT optional. If it's not in the backlog, it didn't happen.
```

**Sub-agent rules:** When to delegate, which personas to use, the Think → Consult → Verify → Deliver workflow. This is where you define your agent's delegation patterns.

### Session Routing & Sub-Agent Coordination

OpenClaw sessions are keyed by channel:
- `agent:main:telegram:group:<GROUP_ID>:topic:<TOPIC_ID>` — Telegram forum topic
- `agent:main:discord:channel:<CHANNEL_ID>` — Discord channel/thread
- `agent:main:telegram:direct:<USER_ID>` — Telegram DM
- `agent:main:main` — the main/default session

**The coordination loop:**
1. Task arrives in channel X → agent adds to BACKLOG.md with routing tag
2. Heartbeat fires in main session → reads BACKLOG.md → sees tagged task
3. If task is tagged for a different session → nudge that session via `sessions_send`
4. Sub-agent session works on task → updates BACKLOG.md with progress
5. Next heartbeat → orchestrator reads updated BACKLOG.md → sees progress → decides next action

**The shared file contract:** BACKLOG.md is the coordination surface. Every session that works on a task MUST write its progress back. The nudge message explicitly includes this:

```
"Continue working on <task>. Current status: <status>.
 Next step: <next subtask>.
 IMPORTANT: Update BACKLOG.md (~/.openclaw/workspace/BACKLOG.md)
 with your progress — mark subtasks ✅ as you complete them,
 add new subtasks as discovered."
```

### Cron Jobs — Delegating Recurring Work

Some monitoring tasks run better as isolated cron jobs than as heartbeat checks:

**When to use cron vs heartbeat:**

| Feature | Heartbeat | Cron |
|---------|-----------|------|
| Timing | Approximate (~30 min) | Exact (crontab precision) |
| Context | Has conversation history | Isolated session |
| Batching | Multiple checks in one turn | One task per job |
| Model | Uses session model | Can specify different model |
| Output | Routes via heartbeat rules | Delivers directly to target |

**Rule of thumb:** Batch periodic checks into heartbeats. Use cron for exact-timing tasks and tasks that need isolation.

### Dashboard Integration (Optional)

If you have a status dashboard, heartbeats can update it:
- Working on a task → set status to "working: <task>"
- Idle (only monitoring) → let auto-idle handle it
- Never set "working" for heartbeat polling itself

---

## Part 4: Anti-Patterns (Lessons Learned)

These are failure modes I've hit in production. Save yourself the pain.

### ❌ "I'll remember to do it later"
If you don't write it to BACKLOG.md, it won't survive compaction. Mental notes are lies.

### ❌ Monitoring before backlog
The agent spends its whole heartbeat turn checking notifications and GitHub, finds nothing new, replies HEARTBEAT_OK — while a task from yesterday sits unfinished in the backlog. **Always check backlog first.**

### ❌ Nudge spam
Heartbeat fires every 30 minutes. Agent nudges the same stuck task every time with no status change. The sub-agent session gets flooded with identical messages. **Anti-spam guard: skip nudge if last nudge was <30 min ago and nothing changed.**

### ❌ Routine updates in human's DM
Human gets pinged every 30 minutes with "checked notifications, nothing new." Annoying. **Route routine status to a dedicated channel. DM only for blockers.**

### ❌ Sub-agent doesn't update backlog
A sub-agent does great work in its topic session but never writes back to BACKLOG.md. The orchestrator thinks nothing happened and nudges again. **Every nudge message must include: "IMPORTANT: Update BACKLOG.md with your progress."**

### ❌ No source on tasks
A task appears in the backlog with no source. Two sessions later, nobody remembers who asked for it or why. Was it urgent? Was it a joke in Discord? **Always include source: who, where, when.**

### ❌ Archiving too late
BACKLOG.md grows to 500 lines. Every heartbeat reads the whole thing. Token burn increases. Agent gets confused by completed tasks. **Archive ✅ items regularly.**

### ❌ Stale STATE.md
Agent updates STATE.md once, then works for three days without updating it. Compaction hits. Agent reads STATE.md and acts on stale context. **Update STATE.md whenever significant progress is made or the active task changes.**

### ❌ Sub-agent works outside BACKLOG
A sub-agent receives a nudge, does the work, posts results in its channel — but never updates BACKLOG.md. The orchestrator can't see the progress and either re-nudges or considers the task stuck. **The shared file is the contract. No update = no visibility.**

---

## Part 5: Quick Start Template

### Minimal BACKLOG.md

```markdown
# BACKLOG.md

**Rules:**
1. Add tasks here BEFORE starting work
2. Check every session start and heartbeat
3. ✅ = done, archive periodically
4. 🔴 urgent | 🟡 normal | 🟢 low
5. Always include source

---

## 📌 Active Work

(tasks go here)

## 📌 Passive Watches

(monitoring items go here)
```

### Minimal HEARTBEAT.md

```markdown
# HEARTBEAT.md

## Output Routing
- Routine → dedicated status channel
- Urgent → human DM
- Nothing → HEARTBEAT_OK

## STEP 1: BACKLOG
1. Read BACKLOG.md
2. Actionable tasks? → Work on them or nudge tagged sessions
3. Only passive items? → Proceed to Step 2

## STEP 2: Monitoring
- Check GitHub notifications (if not cron-owned)
- Check for new messages/mentions
- Other periodic checks as needed
```

### AGENTS.md Integration

Add to your AGENTS.md:

```markdown
## ⚠️ BACKLOG FIRST — MANDATORY FOR EVERY TASK

Before starting ANY work, add it to BACKLOG.md FIRST:
1. Add the task with source (who asked, where, when)
2. Set priority and status
3. THEN start working
4. Update status as you go

This is NOT optional. If it's not in the backlog, it didn't happen.
```

---

## Part 6: Advanced Patterns

### Multi-Channel Task Routing

For agents operating across multiple channels (Telegram topics, Discord threads, etc.):

1. **Tag tasks with their origin channel** in BACKLOG.md
2. **Route all updates to the tagged channel** — don't cross-post
3. **Use `sessions_send`** to nudge channel-specific sessions
4. **Session keys follow the pattern:** `agent:main:<platform>:<scope>:<id>`

### Heartbeat State Tracking

Track when checks last ran to avoid redundant work:

```json
// memory/heartbeat-state.json
{
  "lastChecks": {
    "github": 1712188800,
    "email": 1712185200
  },
  "lastNudges": {
    "topic:50": 1712188800,
    "discord:123456": 1712185200
  }
}
```

### Escalation Patterns

When a task is stuck:
1. First heartbeat: nudge the session
2. Second heartbeat (30 min later): nudge again with "still waiting"
3. Third heartbeat: escalate to human — "task X has been stuck for >1h, may need intervention"

### Graceful Degradation

If BACKLOG.md is missing or corrupted:
- Create a fresh one from the template
- Check daily notes for recent tasks
- Don't panic — the system is self-healing if the agent follows the rules

---

## Acknowledgments

This system evolved over ~60 days of production use on the Lodestar project. The anti-patterns section is written in scar tissue. Every rule exists because it was broken at least once.

The key insight: **files are memory, heartbeats are rhythm, backlogs are accountability.** Together they make an agent that doesn't just respond — it *works*.
