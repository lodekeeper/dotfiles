# Current Memory State Analysis

## Architecture Overview

We have a **dual-layer system**: file-based workspace memory + OpenClaw's built-in vector memory (LanceDB).

### Layer 1: File-Based Memory (Workspace)

| File | Size | Purpose | Loaded When |
|------|------|---------|-------------|
| SOUL.md | 3.7KB | Identity, personality, values | Every session (boot) |
| USER.md | 0.8KB | Info about Nico | Every session (boot) |
| IDENTITY.md | 1.3KB | Name, role, strengths/weaknesses | Every session (boot) |
| MEMORY.md | 7.9KB | Curated long-term memory | Main session only (boot) |
| STATE.md | 0.3KB | Current working state | Every session (boot) |
| BACKLOG.md | 2.6KB | Task tracking | Every session (boot) |
| HEARTBEAT.md | 3.6KB | Heartbeat checklist | Every heartbeat |
| TOOLS.md | 4.8KB | Tool-specific notes | On demand |
| memory/YYYY-MM-DD.md | 1-12KB each | Daily notes (39 files) | Today + yesterday at boot |

**Total boot context**: ~21KB (SOUL + USER + IDENTITY + MEMORY + STATE + BACKLOG + today's notes)
**Total memory folder**: 280KB across 48 files

### Layer 2: OpenClaw Built-in Memory (LanceDB)

- **Storage**: LanceDB vector database at ~/.openclaw/memory/lancedb/
- **Size**: 12MB, ~311+ version manifests, ~399 lance data files
- **Access**: via `memory_store` and `memory_recall` tools
- **Embedding**: Automatic (handled by OpenClaw)
- **Categories**: preference, fact, decision, entity, other
- **Importance**: 0-1 scale

### Supplementary Files

- `memory/heartbeat-state.json` — tracks last check times
- `memory/discord-threads.json` — tracked Discord threads
- `memory/unstable-ci-tracker.json` — investigated CI failures
- `memory/agent-status.json` — sub-agent state
- `memory/gloas-implementation-status.md` — project-specific notes
- `memory/pr-*.md` — PR review notes

## Pain Points

### 1. Poor Vector Recall Quality
- `memory_recall` returns 42-59% match scores even for moderately relevant queries
- Often returns tangentially related or completely unrelated memories
- Example: querying "memory system architecture" returned results about "delay indexing" (array retry delays) and gossip system changes
- No way to filter by date, category, or importance during recall

### 2. Duplicate/Redundant Memories
- Same lesson stored multiple times (e.g., "PR review inline comments" appears as both a decision and a fact)
- No deduplication mechanism
- Over time, the vector DB accumulates noise

### 3. No Structured Lookup
- Can't answer "what do I know about PR #8739?" without grepping files
- Can't answer "what happened on Feb 14?" without reading the daily note
- Can't answer "what are all the EIPs I've worked on?" without scanning MEMORY.md manually
- No entity-based access (people, PRs, projects, EIPs)

### 4. Daily Notes Accumulate Without Consolidation
- 39 daily note files, growing ~1-2 per day
- No automated consolidation — HEARTBEAT.md says "every few days" but it rarely happens
- Older notes become dead weight — never read unless manually searched
- Key insights get buried in verbose daily logs

### 5. MEMORY.md is Flat and Growing
- Single file with sections, no cross-referencing
- "Lessons Learned" section is a long list with no categorization
- Will hit context window limits as it grows
- No mechanism to archive outdated entries

### 6. Boot Context is Static
- Same files loaded every session regardless of what's needed
- No "what's relevant to today's work?" adaptive loading
- MEMORY.md loaded in full even when only one section matters

### 7. No Semantic Connection Between Files
- Daily notes reference PRs, people, projects — but no backlinks
- MEMORY.md lessons relate to specific projects — but no linking
- Knowledge is siloed across files with no graph/index connecting them

## What Works Well

- **Daily notes pattern**: Good for raw logging, low friction
- **MEMORY.md curated memory**: Good for distilled wisdom
- **Boot sequence**: Reliable, ensures minimum context
- **BACKLOG.md**: Effective task tracking
- **Category system in memory_store**: Good intent, poor execution (recall doesn't leverage it well)
