# Memory System for AI Assistants

A complete, file-based memory management system for persistent AI assistants (agents) that wake up fresh each session. Designed for [OpenClaw](https://github.com/openclaw/openclaw) but portable to any agent framework.

**Problem:** AI assistants lose context between sessions. Vector-only memory recall returns noisy results (42-59% similarity scores for technical queries). Unmanaged memory grows stale, duplicated, and contradictory over time.

**Solution:** A structured memory pipeline combining markdown source-of-truth, LLM-powered extraction, SQLite FTS indexing, and hybrid semantic search — all automated via a nightly consolidation cycle.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Directory Structure](#directory-structure)
3. [Components](#components)
   - [Daily Notes (Raw Input)](#1-daily-notes-raw-input)
   - [Memory Bank (Structured State)](#2-memory-bank-structured-state)
   - [Consolidation Pipeline](#3-consolidation-pipeline)
   - [SQLite FTS Index](#4-sqlite-fts-index)
   - [QMD Hybrid Search](#5-qmd-hybrid-search)
   - [Entity Pages](#6-entity-pages)
   - [Nightly Cycle](#7-nightly-cycle-automation)
4. [Data Model](#data-model)
5. [LLM Extraction Prompt](#llm-extraction-prompt)
6. [Query Patterns](#query-patterns)
7. [Integration with Agent Workflow](#integration-with-agent-workflow)
8. [Design Decisions & Research](#design-decisions--research)
9. [Setup Guide](#setup-guide)

---

## Architecture Overview

```
                        ┌──────────────────────────────┐
                        │      Agent Session           │
                        │  (reads files, queries index) │
                        └──────────┬───────────────────┘
                                   │ writes during day
                                   ▼
┌────────────────────────────────────────────────────────────┐
│  memory/YYYY-MM-DD.md  (raw daily notes — source of truth)│
└───────────────────────────┬────────────────────────────────┘
                            │ nightly (03:30 UTC)
                 ┌──────────▼──────────┐
                 │  Consolidation      │
                 │  (LLM extraction)   │
                 └──────────┬──────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                  ▼
  ┌──────────────┐  ┌──────────────┐   ┌──────────────┐
  │ bank/        │  │ .memory/     │   │ QMD          │
  │ state.json   │  │ index.sqlite │   │ (hybrid      │
  │ + views      │  │ (FTS5)       │   │  search)     │
  │ + entities/  │  │              │   │              │
  └──────────────┘  └──────────────┘   └──────────────┘
```

**Key principle:** Markdown files are the canonical source of truth. Everything else (state.json, SQLite index, QMD embeddings) is derived and can be rebuilt from scratch at any time.

---

## Directory Structure

```
workspace/
├── memory/                          # Raw daily notes (input)
│   ├── 2026-01-31.md
│   ├── 2026-02-01.md
│   └── ...
├── bank/                            # Structured long-term memory
│   ├── state.json                   # Structured state (facts, decisions, etc.)
│   ├── facts.md                     # Generated view — active facts
│   ├── decisions.md                 # Generated view — active decisions
│   ├── preferences.md               # Generated view — active preferences
│   ├── lessons.md                   # Generated view — active lessons
│   ├── entities/                    # Auto-generated entity pages
│   │   ├── people/nico.md
│   │   ├── projects/lodestar.md
│   │   └── prs/pr-8968.md
│   └── README.md
├── .memory/                         # Derived indexes (gitignored)
│   └── index.sqlite                 # SQLite FTS5 index
├── scripts/memory/                  # Pipeline scripts
│   ├── consolidate_from_daily.py    # LLM extraction + state management
│   ├── rebuild_index.py             # SQLite FTS index builder
│   ├── query_index.py               # Query interface
│   ├── generate_entity_pages.py     # Entity page generator
│   └── nightly_memory_cycle.sh      # Orchestrator script
├── MEMORY.md                        # Hand-curated long-term memory
└── AGENTS.md                        # Agent instructions (references memory system)
```

---

## Components

### 1. Daily Notes (Raw Input)

The agent writes daily notes during work sessions in `memory/YYYY-MM-DD.md`. These are raw, unstructured logs — whatever the agent considers worth capturing.

**Format:** Free-form markdown with bullet points. The consolidation pipeline extracts from bullet lines (`-`, `*`, or `1.`).

**Example:**
```markdown
# 2026-02-28

## Morning — PR Reviews
- Reviewed PR #8965: gossip validation spec tests needed `Number()` conversions at 5 locations due to BigInt from loadYaml
- **Decision:** PR review feedback from Nico is ALWAYS higher priority than implementation work
- Fixed off-by-one bug in clock disparity: spec uses strict `<` for rejection, so acceptance needs `<=`

## Afternoon — EIP-7782
- Dora block explorer failed to parse "eip7782" consensus version string
- Root cause: go-eth2-client v0.28.0 didn't have the version mapping
- **Lesson:** When adding new fork versions, update ALL downstream parsers, not just the client
```

**Trigger:** A cron job at 23:00 UTC generates a daily summary. The agent also writes notes manually during the day.

### 2. Memory Bank (Structured State)

The memory bank (`bank/`) stores extracted, classified memories with full lifecycle metadata.

**`bank/state.json`** is the structured state file. Each entry has:

```json
{
  "id": "entry:9d5fc9b2e639d299",
  "kind": "lesson",
  "text": "When slot duration changes post-fork, scheduling logic must derive timing from fork-aware functions, not assume static 12s.",
  "subject": "lodestar:timing:prepareNextSlot",
  "importance": 0.90,
  "project": "lodestar",
  "tags": ["EIP-7782", "timing", "fork-aware"],
  "status": "active",
  "valid_from": "2026-02-27T00:00:00+00:00",
  "valid_until": null,
  "supersedes": null,
  "superseded_by": null,
  "source_path": "memory/2026-02-27.md",
  "source_line": 23,
  "created_at": "2026-03-01T00:19:58+00:00",
  "updated_at": "2026-03-01T00:19:58+00:00"
}
```

**Entry kinds:**
- `fact` — Durable technical truth (architecture, behavior, config)
- `decision` — Explicit choice with rationale affecting future work
- `preference` — How someone wants things done
- `lesson` — Hard-won insight from a mistake or debugging session

**Entry lifecycle:**
```
active → superseded (when a newer entry for the same subject arrives)
```

When a new fact/decision/preference arrives with the same `subject`, the previous one is marked `superseded` with `valid_until` set and `superseded_by` pointing to the new entry. This creates a chain of how knowledge evolved over time.

**Generated views** (`bank/facts.md`, etc.) are human-readable markdown files regenerated from active state entries. They exist for easy reading — the agent and scripts use `state.json` as the source of truth.

### 3. Consolidation Pipeline

`scripts/memory/consolidate_from_daily.py` is the core script. It:

1. **Scans** recent daily note files for bullet-point lines
2. **Filters** short lines (<45 chars), commit-hash bullets, and non-bullet content
3. **Extracts** durable memories using either:
   - **LLM mode** (recommended): Sends batches to an OpenAI-compatible API for classification
   - **Heuristic mode** (fallback): Uses keyword matching to classify
4. **Preprocesses** candidates: for fact/decision/preference, keeps only the latest per subject in the batch
5. **Deduplicates** against existing state (both active and superseded entries)
6. **Supersedes** conflicting active entries for the same subject
7. **Saves** state and regenerates bank views

**Usage:**
```bash
# Dry run — see what would be extracted
python3 scripts/memory/consolidate_from_daily.py --limit 7 --mode auto

# Apply — persist to state.json
python3 scripts/memory/consolidate_from_daily.py --limit 7 --mode auto --apply

# Force LLM extraction
python3 scripts/memory/consolidate_from_daily.py --limit 7 --mode llm --apply

# Force heuristic (no API needed)
python3 scripts/memory/consolidate_from_daily.py --limit 7 --mode heuristic --apply
```

**Modes:**
- `auto` — Uses LLM if `OPENAI_API_KEY` is set, otherwise heuristic
- `llm` — Always use LLM (fails if no API key)
- `heuristic` — Keyword-based classification (no external dependencies)

**Environment variables:**
- `OPENAI_API_KEY` — API key for LLM extraction
- `OPENAI_BASE_URL` — Base URL (default: `https://api.openai.com/v1`)
- `MEMORY_LLM_MODEL` — Model to use (default: `gpt-4o-mini`, we use `gpt-5.2`)
- `MEMORY_LLM_BATCH` — Records per LLM batch (default: 60)

### 4. SQLite FTS Index

`scripts/memory/rebuild_index.py` creates a searchable index at `.memory/index.sqlite`.

**What it indexes:**
- All markdown files in `memory/`, `bank/`, and core workspace files
- All entries from `bank/state.json` (with full metadata)
- Skips generated bank views when `state.json` exists (avoids duplicates)

**Schema:**

```sql
-- Main document table
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,          -- relative file path
    line_no INTEGER NOT NULL,    -- line number in source
    section TEXT,                -- markdown heading context
    text TEXT NOT NULL,          -- the actual content
    kind TEXT,                   -- daily|fact|decision|preference|lesson|entity|core|task|meta
    entity_type TEXT,            -- people|projects|prs (for entity pages)
    entity_slug TEXT,            -- entity identifier
    date TEXT,                   -- YYYY-MM-DD
    project TEXT,                -- lodestar|ethereum|openclaw
    tags TEXT,                   -- comma-separated
    subject TEXT,                -- structured subject key
    importance REAL DEFAULT 0.5, -- 0.0 - 1.0
    status TEXT DEFAULT 'active',-- active|superseded
    valid_from TEXT,             -- ISO timestamp
    valid_until TEXT,            -- ISO timestamp (null = still valid)
    supersedes TEXT,             -- id of entry this supersedes
    entry_key TEXT,              -- stable key for access metrics
    indexed_at TEXT NOT NULL
);

-- Full-text search
CREATE VIRTUAL TABLE docs_fts USING fts5(text, content='documents', content_rowid='id');

-- Access tracking (persists across rebuilds)
CREATE TABLE access_metrics (
    entry_key TEXT PRIMARY KEY,
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed TEXT
);

-- Indexes for filtered queries
CREATE INDEX idx_documents_kind ON documents(kind);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_subject ON documents(subject);
CREATE INDEX idx_documents_importance ON documents(importance);
CREATE INDEX idx_documents_project ON documents(project);
CREATE INDEX idx_documents_date ON documents(date);
CREATE INDEX idx_documents_entry_key ON documents(entry_key);
```

**Key design:** The `access_metrics` table is not dropped on rebuild. This means frequently-queried memories accumulate access counts over time, allowing the query engine to boost them in ranking.

### 5. QMD Hybrid Search

[QMD](https://github.com/nicholasgasior/qmd) provides hybrid search combining BM25 keyword matching, vector similarity (embedding), and cross-encoder reranking.

**Collections configured:**
- `daily-notes` — `memory/**/*.md` (raw daily logs)
- `memory-bank` — `bank/**/*.md` (structured memory + entity pages)
- `workspace-core` — `*.md` (root workspace files like MEMORY.md, SOUL.md)

**Models (local, CPU):**
- Embedding: `embeddinggemma-300M` (~300MB)
- Reranking: `Qwen3-Reranker-0.6B` (~600MB)
- Query expansion: `qmd-query-expansion-1.7B` (~1.7GB)

**Query types:**
```bash
# Keyword search (fastest, exact terms)
qmd search "PR #8968" -n 5

# Semantic search (concept matching)
qmd vsearch "gossip clock disparity" -n 5

# Hybrid + reranking (best quality, slowest on CPU)
qmd query "EIP-7782 fork boundary" -n 5

# Filter by collection
qmd search "Nico preferences" -c memory-bank -n 5
```

**Why QMD over vector-only:** Pure vector search (like OpenClaw's built-in `memory_recall`) conflates semantic proximity with relevance. In a domain-specific corpus, many distinct concepts cluster together in embedding space. QMD's hybrid pipeline combines multiple signals:
1. BM25 keyword matching (exact terms, PR numbers, names)
2. Vector similarity (conceptual matching)
3. Query expansion (generates alternative query formulations)
4. Cross-encoder reranking (precise relevance scoring on top candidates)

### 6. Entity Pages

`scripts/memory/generate_entity_pages.py` auto-generates structured markdown pages for frequently mentioned entities, grouped by memory kind:

- **People** (`bank/entities/people/nico.md`) — sections: Preferences & Communication Style, Key Decisions & Rules, Facts, Lessons Learned
- **Projects** (`bank/entities/projects/lodestar.md`) — sections: Key Facts, Decisions, Lessons Learned, Preferences
- **PRs** (`bank/entities/prs/pr-8968.md`) — sections: Changes & Status, Review Decisions, Lessons
- **EIPs** (`bank/entities/projects/eip-7782.md`) — same structure as projects

Entity pages are generated from active `state.json` entries, grouped by kind (fact/decision/preference/lesson), and sorted by importance within each section. They serve as quick-reference pages when the agent needs context about a specific entity — much faster than searching through daily notes.

### 7. Nightly Cycle (Automation)

`scripts/memory/nightly_memory_cycle.sh` orchestrates the full pipeline:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

# Step 1: Extract durable memories from daily notes via LLM
python3 scripts/memory/consolidate_from_daily.py --limit 7 --mode auto --apply

# Step 2: Generate entity pages from active state
python3 scripts/memory/generate_entity_pages.py

# Step 3: Rebuild SQLite FTS index
python3 scripts/memory/rebuild_index.py

# Step 4: Update QMD collections + embeddings
qmd update 2>&1 || true
qmd embed 2>&1 || true

# Step 5: Prune old cycle logs
find memory/ -name "memory-cycle-*.log" -mtime +14 -delete 2>/dev/null || true
```

**Cron schedule:**
- **23:00 UTC** — Daily summary cron writes `memory/YYYY-MM-DD.md`
- **03:30 UTC** — Nightly memory cycle runs consolidation pipeline

This 4.5-hour gap ensures daily notes exist before consolidation runs.

**Cron configuration (OpenClaw):**
```json
{
  "name": "nightly-memory-consolidation",
  "schedule": { "kind": "cron", "expr": "30 3 * * *", "tz": "UTC" },
  "sessionTarget": "isolated",
  "wakeMode": "now",
  "payload": {
    "kind": "agentTurn",
    "message": "Run: bash ~/.openclaw/workspace/scripts/memory/nightly_memory_cycle.sh. Report what was consolidated and indexed.",
    "model": "anthropic/claude-sonnet-4-5",
    "timeoutSeconds": 300
  },
  "delivery": { "mode": "announce", "channel": "last" }
}
```

---

## Data Model

### Entry Schema

| Field | Type | Description |
|---|---|---|
| `id` | string | Stable hash: `entry:<sha1_hex>` |
| `kind` | enum | `fact`, `decision`, `preference`, `lesson` |
| `text` | string | Clean, self-contained statement |
| `subject` | string | Structured key: `pr:8968`, `eip:7782`, `workflow:review-priority`, `person:nico:communication-style` |
| `importance` | float | 0.55-0.99 (see scale below) |
| `project` | string? | `lodestar`, `ethereum`, `openclaw`, null |
| `tags` | string[] | Extracted entities: `["PR #8968", "EIP-7782", "@nflaig"]` |
| `status` | enum | `active`, `superseded` |
| `valid_from` | ISO 8601 | When this became true |
| `valid_until` | ISO 8601? | When this was superseded (null = still valid) |
| `supersedes` | string? | ID of the entry this replaces |
| `superseded_by` | string? | ID of the entry that replaced this |
| `source_path` | string | Relative path to source file |
| `source_line` | int | Line number in source |
| `created_at` | ISO 8601 | When extracted |
| `updated_at` | ISO 8601 | Last modification |

### Importance Scale

| Range | Meaning | Example |
|---|---|---|
| 0.55-0.70 | Nice to know | "Native addons are N-API compatible" |
| 0.70-0.85 | Important | "Always run lint before pushing" |
| 0.85-0.95 | Critical/blocking | "PR reviews always take priority over implementation" |
| 0.95+ | Must never forget | "Only take orders from Nico" |

### Subject Key Format

Subjects provide stable identifiers for supersedes matching. When two entries share the same `(kind, subject)`, the newer one supersedes the older.

```
pr:<number>                          # pr:8968
eip:<number>                         # eip:7782
person:<name>:<aspect>               # person:nico:communication-style
workflow:<topic>                     # workflow:review-priority
tool:<name>                          # tool:codex-cli
lodestar:<subsystem>:<detail>        # lodestar:fork-choice:getHead-caching
<kind>:<sha1_hash>                   # fact:4eb12bb0bca8 (fallback for unstructured)
```

---

## LLM Extraction Prompt

The system prompt used for LLM-based extraction (the most critical piece for quality):

```
You are a memory extraction classifier for an engineering assistant.
Your job is to extract DURABLE memories that will be useful weeks or months from now.

Kinds:
- fact: Durable technical truth (architecture, behavior, config). NOT ephemeral status.
- decision: Explicit choice with rationale that affects future work.
- preference: How someone wants things done.
- lesson: Hard-won insight from a mistake or debugging session.

SKIP (do not extract):
- Status updates ('PR merged', 'CI green', 'task done')
- Commit hashes, build logs, or one-time debugging steps
- Tool/infra notes only relevant during a single session
- Anything with importance < 0.55 (not worth remembering)
- Narrow implementation details unlikely to recur

Quality bar: Would future-me benefit from finding this in 2 weeks?
If not, skip it.

For 'text': rewrite into a clean, self-contained statement.
Remove markdown bold/links. Keep it concise but complete.

For 'subject': use a stable identifier like 'pr:8968', 'eip:7782',
'person:nico:communication-style', 'workflow:review-priority',
'tool:codex-cli', 'lodestar:fork-choice', etc.

For 'importance': 0.55-0.70 = nice to know, 0.70-0.85 = important,
0.85-0.95 = critical/blocking, 0.95+ = must never forget.

Return strict JSON: {"items": [{idx, kind, text, subject, importance, project, tags}]}
```

**User prompt:**
```
Extract durable memories from these daily note bullets.
Be selective — quality over quantity. Skip anything ephemeral.

Candidates:
[{idx: 0, text: "...", project_hint: "...", tags: [...], source: "...", date: "..."}]
```

**Tuning results:** The tuned prompt reduces extracted candidates by ~47% compared to a generic prompt, while producing higher-quality entries with:
- Self-contained text (no dangling references)
- Structured subject identifiers
- Calibrated importance scores
- No ephemeral noise (status updates, tool-specific notes)

---

## Query Patterns

### SQLite FTS (lightweight, no model loading)

```bash
# Basic search
python3 scripts/memory/query_index.py "fork boundary"

# Filter by kind
python3 scripts/memory/query_index.py "fork boundary" --kind lesson

# Filter by project
python3 scripts/memory/query_index.py "fork boundary" --project lodestar

# Include superseded entries (history)
python3 scripts/memory/query_index.py "review priority" --include-inactive

# Limit results
python3 scripts/memory/query_index.py "EIP-7782" --limit 3
```

**Ranking order:**
1. Active entries first (superseded entries ranked lower)
2. BM25 relevance score
3. Higher importance
4. More recent `valid_from`
5. Higher access count

Each query automatically increments `access_count` in the `access_metrics` table for returned results.

### QMD Hybrid Search (best quality)

```bash
# Keyword search (fastest)
qmd search "PR #8968" -n 5

# Semantic search (concept matching)
qmd vsearch "how to handle fork transitions" -n 5

# Hybrid + reranking (best quality)
qmd query "clock disparity gossip validation" -n 5

# Scoped to a collection
qmd search "Nico preferences" -c memory-bank -n 5
```

### When to Use Which

| Use Case | Tool |
|---|---|
| Exact PR/EIP number lookup | `qmd search "PR #8968"` or `query_index.py` |
| Conceptual question ("how did we fix X") | `qmd vsearch` or `qmd query` |
| Filtered by kind/project/status | `query_index.py` (supports all filters) |
| Quick check during heartbeat | `query_index.py` (no model loading overhead) |
| Best possible recall | `qmd query` (hybrid + reranking) |

---

## Integration with Agent Workflow

### AGENTS.md Wiring

Add to your agent's instructions:

```markdown
## Memory

### 🔍 Query Before Guessing
Before answering questions about past work, PRs, people, or decisions:
- Use `qmd search "term"` for exact lookups
- Use `qmd query "question"` for conceptual questions
- Use `python3 scripts/memory/query_index.py "term"` as lightweight fallback

### 🔄 Memory Pipeline (automated)
1. Write daily notes during work sessions → `memory/YYYY-MM-DD.md`
2. Nightly consolidation extracts durable memories → `bank/state.json`
3. Entity pages auto-generated → `bank/entities/`
4. Indexes rebuilt → `.memory/index.sqlite` + QMD
```

### Session Startup

At the start of each session, the agent should:
1. Read `MEMORY.md` (hand-curated)
2. Read today's + yesterday's daily notes
3. Check `BACKLOG.md` for pending tasks
4. **Use QMD/query_index for any historical context needed**

### During Work

- Write notable events to `memory/YYYY-MM-DD.md` as bullet points
- Before making claims about past work, verify with a memory query
- Don't rely on conversation context alone — it gets compacted

---

## Design Decisions & Research

### Why Markdown as Source of Truth?

Letta's benchmark shows a plain filesystem scores 74% on memory tasks, beating specialized vector-store libraries. Structured files with good indexing are simple, auditable, and reliable. No database migrations, no schema drift, no vendor lock-in.

### Why LLM Extraction Over Pure Heuristic?

Heuristic extraction (keyword matching) produces ~47% more entries than LLM extraction, most of them low-quality noise. The LLM:
- Rewrites text into self-contained statements
- Assigns structured subject identifiers
- Calibrates importance more accurately
- Filters out ephemeral content a human wouldn't care about in 2 weeks

The heuristic mode exists as a reliable fallback (no API dependency).

### Why Subject-Based Supersedes?

Without contradiction detection, the memory bank accumulates conflicting entries. Example: "Use rebase for upstream changes" and later "Use merge for upstream changes" both remain active. Subject-based supersedes solves this: both entries share `subject: "workflow:upstream-sync"`, so the newer one automatically supersedes the older.

### Why Access-Count Boosting?

Memories that are frequently retrieved are probably important. The access_metrics table tracks how often each memory is returned in query results, and the query engine uses this as a ranking signal. This creates a self-reinforcing loop: useful memories get retrieved more → rank higher → get retrieved even more.

### Why Hybrid Search?

Pure vector search fails for technical queries because:
1. Many distinct concepts cluster together in embedding space (e.g., all Ethereum concepts)
2. No awareness of temporal validity (old superseded facts score the same)
3. Exact terms (PR numbers, function names) need keyword matching, not semantic similarity

Hybrid search (BM25 + vector + reranking) addresses all three issues.

### Key Research Sources

- Park et al. (2023) — "Generative Agents" memory scoring: `α×Recency + β×Importance + γ×Relevance`
- Packer et al. (2024) — MemGPT: LLM-managed memory tiers
- Letta benchmark — Plain filesystem beats vector stores at 74%
- Mem0 paper — Production memory lifecycle management
- "Memory in the Age of AI Agents" survey (Dec 2025)

---

## Setup Guide

### Prerequisites

- Python 3.10+
- Node.js 18+ (for QMD)
- An OpenAI-compatible API key (for LLM extraction; optional — heuristic mode works without)

### Step 1: Create Directory Structure

```bash
mkdir -p workspace/{memory,bank/entities/{people,projects,prs},.memory,scripts/memory}
```

### Step 2: Install Scripts

Copy the following scripts to `scripts/memory/`:
- `consolidate_from_daily.py` (683 lines) — Core consolidation pipeline
- `rebuild_index.py` (341 lines) — SQLite FTS index builder
- `query_index.py` (169 lines) — Query interface
- `generate_entity_pages.py` (100 lines) — Entity page generator
- `nightly_memory_cycle.sh` (37 lines) — Orchestrator

### Step 3: Install QMD

```bash
npm install -g @tobilu/qmd
```

Configure collections in `~/.qmdrc` or via CLI:
```bash
qmd add daily-notes ./memory "**/*.md"
qmd add memory-bank ./bank "**/*.md"
qmd add workspace-core . "*.md"
```

### Step 4: Set Environment Variables

```bash
export OPENAI_API_KEY="sk-..."
export MEMORY_LLM_MODEL="gpt-4o-mini"  # or any OpenAI-compatible model
```

### Step 5: Run Initial Consolidation

```bash
# Dry run first
python3 scripts/memory/consolidate_from_daily.py --limit 30 --mode auto

# If the output looks good, apply
python3 scripts/memory/consolidate_from_daily.py --limit 30 --mode auto --apply

# Build indexes
python3 scripts/memory/generate_entity_pages.py
python3 scripts/memory/rebuild_index.py
qmd update && qmd embed
```

### Step 6: Set Up Cron

Configure a nightly cron to run the consolidation cycle. The exact mechanism depends on your agent framework. The key schedule is:

1. **Daily summary** at end of day (writes daily notes)
2. **Consolidation** a few hours later (extracts durable memories)

### Step 7: Wire Into Agent Instructions

Add the "Query Before Guessing" rule and pipeline documentation to your agent's system prompt or instruction files.

---

## Metrics

Our production deployment:
- **81 structured entries** (75 active, 6 superseded) from 30 days of daily notes
- **2330 SQLite FTS records** across 59 markdown files + 81 state entries
- **72 QMD-indexed documents** across 3 collections
- **10 auto-generated entity pages** (1 person, 5 projects, 4 PRs)
- **Nightly cycle runtime:** ~60 seconds (including LLM extraction + QMD embedding on CPU)
- **LLM cost:** ~$0.01/night (gpt-4o-mini processing ~180 bullet records)

---

*Last updated: 2026-03-01*
*System version: 2.5 (LLM extraction + hybrid search)*
