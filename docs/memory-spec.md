# OpenClaw Agent Memory Spec: Persistent Memory Pipeline

> How an AI agent remembers across sessions when every conversation eventually compacts.

**Author:** Lodekeeper 🌟
**Version:** 1.0
**Date:** 2026-04-04

---

## Overview

AI agent sessions compact — conversation history gets summarized, detail is lost. Without a memory system, every session starts from zero. This spec describes a layered memory pipeline that gives agents persistent, searchable memory across sessions.

**The core insight:** Memory has different time horizons. Raw notes are for today. Structured entries are for weeks. Curated memory is for months. Each layer serves a different purpose.

---

## Architecture

```
Daily Work
    │
    ▼
memory/YYYY-MM-DD.md          ← Raw daily journal (written during work)
    │
    ▼ [nightly consolidation cron]
    │
    ├── bank/state.json        ← Structured entries (facts, decisions, preferences, lessons)
    ├── bank/entities/         ← Auto-generated entity pages (people, projects, PRs)
    ├── bank/*.md              ← Human-readable views by kind
    │
    ▼ [index rebuild]
    │
    ├── .memory/index.sqlite   ← Full-text search index
    └── QMD collections        ← Hybrid search (BM25 + vector + reranking)

MEMORY.md                      ← Curated long-term memory (manually maintained)
STATE.md                       ← Current working state (see orchestration-spec.md)
```

---

## Layer 1: Daily Notes (`memory/YYYY-MM-DD.md`)

**Purpose:** Raw journal of what happened during the day. Written as work happens, plus a nightly summary cron.

**What to capture:**
- Decisions made and why
- Investigation progress (hypotheses, findings, dead ends)
- PR activity (opened, reviewed, feedback received)
- Conversations that matter (who said what, commitments made)
- Lessons learned (mistakes, surprises, things that worked)
- Environment changes (config updates, tool installs)

**When to write:**
- During work — capture context as it happens, not retroactively
- At session boundaries — before compaction flushes
- At end of day — nightly summary cron produces a structured recap

**Format:**
```markdown
# 2026-04-04 Daily Notes

## Morning session (07:00–12:00 UTC)

### Wrote orchestration spec for Matthew Keil
- Request came in Discord #lodestar-ai-playground
- Covered BACKLOG.md, HEARTBEAT.md, STATE.md, session routing
- Published to dotfiles repo: commits 97b7aad, 7fbd8c3
- Matt asked for expanded coverage of all operational subsystems

### PR #9170 — gossip counter perf
- CI green, awaiting human review
- No new comments since yesterday
```

**Retention:** Keep 7–14 days of recent daily notes accessible. Older notes get archived but remain searchable via index.

---

## Layer 2: Structured Bank (`bank/state.json`)

**Purpose:** Durable, typed, searchable entries extracted from daily notes. Each entry is a fact, decision, preference, or lesson with metadata.

**Entry schema:**
```json
{
  "id": "entry:9d5fc9b2e639d299",
  "kind": "lesson",
  "text": "Always verify reviewer findings against actual PR diff",
  "subject": "lesson:code-review",
  "importance": 0.85,
  "project": "lodestar",
  "tags": ["code-review", "sub-agents"],
  "status": "active",
  "valid_from": "2026-03-06T00:00:00Z",
  "valid_until": null,
  "supersedes": null,
  "superseded_by": null,
  "source_path": "memory/2026-03-06.md",
  "source_line": 42,
  "created_at": "2026-03-07T03:30:00Z",
  "updated_at": "2026-03-07T03:30:00Z"
}
```

**Entry kinds:**

| Kind | Count* | Purpose |
|------|--------|---------|
| `fact` | 844 | Durable facts (people, configs, endpoints, relationships) |
| `decision` | 188 | Decisions with rationale (why we chose X over Y) |
| `lesson` | 176 | Lessons learned from mistakes or successes |
| `preference` | 68 | User or agent preferences (communication style, tools, workflows) |

*Counts from 60 days of production use.

**Key features:**
- **Validity tracking:** `valid_from`/`valid_until` — facts can expire
- **Supersedes chains:** When a decision changes, the new entry links to what it replaced
- **Importance scoring:** 0.0–1.0, influences search ranking
- **Deduplication:** Consolidation script detects and merges duplicate entries
- **Status:** `active` or `superseded` — queries can filter

**Human-readable views:** `bank/facts.md`, `bank/decisions.md`, `bank/lessons.md`, `bank/preferences.md` — auto-generated from state.json for easy browsing.

### Entity Pages (`bank/entities/`)

Auto-generated reference pages organized by type:
- `bank/entities/people/` — one page per person (who they are, interactions, preferences)
- `bank/entities/projects/` — one page per project (status, key decisions, links)
- `bank/entities/prs/` — one page per PR (timeline, review status, outcomes)

These are generated from bank entries that reference the entity. Useful for quick context when someone mentions a person or project.

---

## Layer 3: Curated Memory (`MEMORY.md`)

**Purpose:** Long-term wisdom distilled from daily notes and bank entries. The agent's "personality memory" — what it's learned about itself, its human, its work patterns.

**What goes here:**
- Key rules and preferences (the stuff that doesn't change week to week)
- Relationship context (who's who, communication styles)
- Workflow decisions (why we use X instead of Y)
- Self-knowledge (strengths, weaknesses, patterns)
- Channel/tool configurations worth remembering

**What doesn't go here:**
- Transient task state (that's STATE.md)
- Raw event logs (that's daily notes)
- Structured data (that's bank/state.json)

**Maintenance:** Periodically (every few days), review recent daily notes and update MEMORY.md. Remove outdated info. This is like a human reviewing their journal and updating their mental model.

**Security note:** MEMORY.md may contain personal context about the human. Only load it in private/main sessions — never in group chats or shared contexts where it could leak.

---

## Layer 4: Search Indices

### SQLite FTS (`.memory/index.sqlite`)

Lightweight full-text search over all memory files. Fast keyword lookup without loading models.

```bash
python3 scripts/memory/query_index.py "PR #9170" --limit 5
python3 scripts/memory/query_index.py "Matthew Keil" --kind fact
```

### QMD (Hybrid Search)

More sophisticated search combining BM25 (keyword), vector similarity (semantic), and reranking:

```bash
qmd search "gossip clock disparity" -n 5      # BM25 keyword
qmd vsearch "how did we fix the sync stall" -n 5  # semantic
qmd query "EIP-7782 fork boundary" -n 5        # hybrid + reranking (best quality)
```

Collections: `daily-notes` (memory/), `memory-bank` (bank/), `workspace-core` (root *.md files).

**When to use which:**
- Exact terms (PR numbers, names) → `qmd search` or SQLite FTS
- Conceptual queries ("how did we handle X") → `qmd vsearch`
- Best quality (complex queries) → `qmd query`

---

## The Nightly Consolidation Pipeline

A cron job runs at 03:30 UTC daily:

```bash
#!/usr/bin/env bash
# nightly_memory_cycle.sh

# Step 1: Extract structured entries from recent daily notes
python3 scripts/memory/consolidate_from_daily.py --limit 7 --mode auto --apply

# Step 2: Generate entity pages from bank entries
python3 scripts/memory/generate_entity_pages.py

# Step 3: Rebuild SQLite FTS index
python3 scripts/memory/rebuild_index.py

# Step 4: Update QMD search collections + embeddings
qmd update && qmd embed

# Step 5: Prune old cycle logs (keep 14 days)
find memory/ -name "memory-cycle-*.log" -mtime +14 -delete
```

**Consolidation modes:**
- `auto` — uses LLM extraction if API key is available, falls back to heuristic
- `llm` — always uses LLM (higher quality, costs tokens)
- `heuristic` — pattern-based extraction (free, lower quality)

**The LLM extraction** reads each daily note and produces structured entries with proper typing, importance scoring, and deduplication against existing bank entries.

---

## Session Startup: How Memory Gets Loaded

From AGENTS.md, every session reads (in order):
1. SOUL.md (identity)
2. USER.md (human preferences)
3. STATE.md (current working state)
4. BACKLOG.md (tasks)
5. Today + yesterday's daily notes (recent context)
6. MEMORY.md (only in private/main sessions)

This gives the agent enough context to function without loading the entire memory bank. For deeper queries, use the search indices on demand.

---

## Anti-Patterns

### ❌ Writing nothing during work, relying on nightly consolidation
The nightly pipeline can only extract what's written down. If you don't capture decisions and context during work, they're lost. **Write daily notes as you go.**

### ❌ Putting everything in MEMORY.md
MEMORY.md should be curated wisdom, not a dump. If it grows past ~500 lines, it's too big. Move details to daily notes or bank entries. **MEMORY.md is the distilled essence.**

### ❌ Never querying memory before answering
The agent makes a claim about past work without checking. Gets it wrong. Human loses trust. **Query before asserting. `qmd search` is fast.**

### ❌ Loading MEMORY.md in group chats
MEMORY.md contains personal context. Loading it in Discord or group Telegram exposes private information. **Only load in private sessions.**

### ❌ Trusting vector search alone for technical queries
Vector similarity returns semantically related but often wrong results for specific technical queries (PR numbers, exact config values). **Use keyword search (BM25/FTS) for precise lookups, semantic search for conceptual queries.**

---

## Quick Start

1. Create `memory/` directory
2. Start writing daily notes: `memory/YYYY-MM-DD.md`
3. Create `MEMORY.md` with key long-term context
4. Set up nightly consolidation cron (or run manually)
5. Add memory queries to your workflow: search before answering
6. Periodically review daily notes → update MEMORY.md

The system bootstraps from daily notes. Everything else builds on top.
