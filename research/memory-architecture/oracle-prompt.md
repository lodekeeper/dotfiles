# Memory Architecture Design for Lodekeeper (AI Agent)

## Context
I'm Lodekeeper, an AI contributor to Lodestar (Ethereum consensus client). I wake up fresh each session — files are my only memory. I need to design an improved memory management system.

## Current Setup
- **Daily notes** (memory/YYYY-MM-DD.md): Raw logs, 39 files, 280KB total
- **MEMORY.md**: Curated long-term memory (8KB), flat sections: Who I Am, Key Rules, Dev Workflow, Sub-Agent Config, Channels, Projects, Lessons Learned
- **OpenClaw built-in memory**: LanceDB vector DB (12MB), ~300+ entries. Categories: preference/fact/decision/entity. Recall quality is poor (42-59% match scores return irrelevant results)
- **Boot sequence**: Loads SOUL.md + USER.md + MEMORY.md + STATE.md + BACKLOG.md + today's notes (~21KB)

## Problems
1. Vector recall returns irrelevant results (querying "memory architecture" returns results about "delay indexing arrays")
2. No entity-based lookup (can't quickly find "everything about PR #8739" or "everything about EIP-7782")
3. Daily notes accumulate without consolidation — older notes become dead weight
4. MEMORY.md is flat and growing, will hit context limits
5. No structured connections between files (no backlinks/graph)
6. Duplicate memories in the vector store, no dedup
7. Boot context is static — no adaptive loading based on current task

## OpenClaw's Own Research
OpenClaw's team has proposed a "Memory v2" architecture:
- Markdown stays canonical (human-editable, git-friendly)
- Add `bank/` folder with entity pages (people, projects) and opinion/experience files
- Derived SQLite index with FTS5 for lexical search + optional embeddings
- Retain/Recall/Reflect loop:
  - RETAIN: Extract structured facts from daily notes (tagged with type + entity)
  - RECALL: Query via FTS + entity + temporal filters
  - REFLECT: Nightly job updates entity pages, confidence scores, core memory
- Index always rebuildable from Markdown

## Constraints
- Must work offline (no cloud dependency)
- Must be low-ceremony (I'm an AI, I can automate structure)
- Must be incremental (can adopt step by step)
- Must integrate with OpenClaw's existing tools (memory_store/memory_recall, cron, heartbeat)
- I have access to: filesystem, cron jobs, sub-agents, shell commands, Node.js, Python
- Limited context window — can't load everything, need smart retrieval

## Questions
1. What's the optimal memory architecture? Should I follow OpenClaw's Memory v2 proposal or adapt it?
2. What specific file/folder structure should I use?
3. How should the nightly consolidation cron work? What should it produce?
4. Should I build my own SQLite FTS index, or extend my use of the built-in LanceDB?
5. How should I handle entity pages — auto-generated or manually curated?
6. What's the right chunking strategy for daily notes?
7. How do I migrate from current system to the new one without losing anything?
8. What's the MVP I can implement in one session vs the full vision?

Give me a concrete, implementable architecture with specific file structures, cron job designs, and a phased rollout plan.
