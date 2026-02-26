# Research: Context Compaction Resilience & Memory Robustness

**Date:** 2026-02-26
**Requested by:** Nico
**Constraint:** Research only — do NOT apply any changes yet

## Problem Statement

When OpenClaw's context window fills up (~200k tokens), it compacts the conversation into a summary. This causes:
1. **Loss of in-progress work state** — Oracle output mid-run, partial analysis, tool results
2. **Loss of task continuity** — forget what was being worked on, decisions made during session
3. **Loss of nuance** — compaction summary is lossy; subtle context disappears
4. **Re-discovery overhead** — have to re-read files, re-check state after compaction

Current mitigations are ad-hoc:
- MEMORY.md (manual, high-level)
- Daily notes in memory/ dir (manual, inconsistent)
- BACKLOG.md (task tracking)
- Heartbeat checks
- "Always tee output to file" rule

## Sub-Questions

### Q1: How does OpenClaw compaction actually work?
- What triggers compaction? Token threshold? Auto or manual?
- What goes into the summary vs what's lost?
- Can we influence what the compactor preserves?
- What are the configurable knobs (if any)?

### Q2: What state is most vulnerable to compaction loss?
- Audit recent compaction events — what was lost each time?
- Tool output (exec results, web fetches, file reads)
- In-flight async operations (Oracle runs, sub-agents, background processes)
- Intermediate reasoning and decisions
- Conversation context with the human

### Q3: What memory/persistence strategies exist for AI agents?
- How do other agent frameworks handle context limits?
- Retrieval-augmented memory (vector stores, knowledge graphs)
- Working memory vs long-term memory patterns
- Session checkpointing / state serialization
- Progressive summarization techniques

### Q4: How can our file-based memory system be improved?
- Current: MEMORY.md, BACKLOG.md, daily notes, skill files
- Gaps: no structured working memory, no auto-checkpointing
- Could we use a structured format (JSON/YAML) for machine-readable state?
- Should we checkpoint before known high-risk operations (Oracle, long tasks)?
- How to make memory writes more automatic/less forgettable?

### Q5: What architectural changes would help?
- Pre-compaction hooks (if available) — auto-save state before compaction
- Working memory file that's always read on session resume
- Task-specific state files (like TRACKER.md but automatic)
- Sub-agent state persistence
- How to handle in-flight operations across compaction boundaries

## Research Plan

1. **Q1:** Read OpenClaw docs on compaction behavior and configuration
2. **Q2:** Review recent session history, memory files, and MEMORY.md lessons for compaction-related incidents
3. **Q3:** Web search for agent memory architectures, context management patterns
4. **Q4:** Analyze current file-based system, identify gaps
5. **Q5:** Synthesize findings into concrete architectural proposals
