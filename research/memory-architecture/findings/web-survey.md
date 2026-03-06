# AI Agent Memory Management — Web Survey

*Compiled: 2026-02-28*

---

## 1. Felix / Nat Eliason's 3-Layer Memory System

**Source:** [Creator Economy interview](https://creatoreconomy.so/p/use-openclaw-to-build-a-business-that-runs-itself-nat-eliason) (Feb 2026), [TLDL summary](https://www.tldl.io/episodes/17886)

Nat Eliason's OpenClaw agent "Felix" uses a 3-layer memory system that Nat considers "the single biggest unlock" for agent reliability.

### Layer 1: Knowledge Graph (PARA `~/life/` folder)

- A `~/life/` directory organized using Tiago Forte's **PARA method**: **P**rojects, **A**reas, **R**esources, **A**rchives.
- Stores **durable facts** about people, projects, and domains.
- Each category has **summary files** for quick lookups — the agent doesn't need to read everything, it reads the summary first and drills deeper only when needed.
- Functions as a persistent, file-based "knowledge graph" — structured not with a graph DB, but with folder hierarchy and markdown.

### Layer 2: Daily Notes with Nightly Consolidation

- Dated markdown files log what happened each day (conversations, decisions, work completed).
- The agent writes to these **during conversations** as a running log.
- **Nightly consolidation** (automated via cron job):
  1. At night (exact time not specified, but described as "nightly"), a cron job triggers the agent.
  2. The agent reviews daily notes and **extracts important information** into Layer 1 (the `~/life/` PARA structure).
  3. It then **re-runs the indexing process** on the knowledge base (likely a QMD/embedding rebuild).
  4. Quote from the interview: *"It then reruns the indexing process. And so when I wake up, his knowledge base has been updated from everything that we worked on the day before."*
- This is essentially a **sleep-time consolidation** pattern — the agent processes raw experiences into structured long-term knowledge during downtime.

### Layer 3: Tacit Knowledge

- Facts about the user: communication preferences, workflow habits, hard rules, lessons learned from past mistakes.
- This is what makes the agent "feel like it actually knows you."
- Stored presumably in system-prompt-adjacent files (SOUL.md / USER.md equivalent).

### Key Insight

> "Get the memory structure in first because then your conversations from day one will be useful." — Nat Eliason

The PARA structure gives the agent a **semantic filing system** — it knows *where* to put things and *where* to look. Combined with nightly consolidation, raw daily conversations get automatically distilled into structured long-term knowledge.

---

## 2. MemGPT / Letta

**Sources:** [MemGPT paper](https://arxiv.org/pdf/2310.08560) (UC Berkeley, Oct 2023), [Letta docs](https://docs.letta.com/concepts/memgpt/), [Letta agent-memory blog](https://www.letta.com/blog/agent-memory), [Sleep-time compute blog](https://www.letta.com/blog/sleep-time-compute), [DataSciOcean explainer](https://datasciocean.com/en/paper-intro/memgpt/)

### Core Architecture: LLM as Operating System

MemGPT treats the LLM's context window like an **operating system manages RAM** — with explicit memory tiers and paging.

#### Short-Term Memory (In-Context)

The context window is divided into reserved sections:

| Section | Purpose |
|---------|---------|
| **System Prompt** | Instructions, tool descriptions |
| **Core Memory** | Small amount of critical info (persona, user profile) stored in labeled "blocks." Agent can edit via `core_memory_replace` / `core_memory_append` tools |
| **A/R Stats** | Counts of items in Archival and Recall memory — lets the agent know there's external memory to search |
| **Chat Summary** | Recursive summary of oldest conversation messages (auto-generated when history exceeds limits) |
| **Chat History** | Recent conversation messages (FIFO buffer) |

#### Long-Term Memory (External)

Two external stores act as overflow:

1. **Recall Memory** — stores all conversation history (messages evicted from Chat History go here, not deleted). Searchable via `conversation_search` tool. Think of it as a complete audit log.

2. **Archival Memory** — stores facts, preferences, and RAG data that don't fit in Core Memory. Searchable via `archival_memory_search` tool. When Core Memory fills up:
   - If new info is critical → move existing Core Memory to Archival, store new in Core
   - If new info is less important → store directly in Archival

#### Self-Directed Memory Management

Key design principles:
- **All outputs are tool calls** — even sending messages uses `send_message()`. This forces structured interaction.
- **Inner thoughts** — the agent thinks before acting, but thoughts are hidden from the user.
- **Heartbeat loop** — after each tool call, agent can set `request_heartbeat=True` to invoke itself again with results, enabling multi-step reasoning chains.
- **Self-editing** — the agent decides what to store, where, and when to evict. It manages its own memory.

### Letta Sleep-Time Compute (MemGPT 2.0)

**Paper:** [arxiv.org/abs/2504.13171](https://arxiv.org/abs/2504.13171) (April 2025)

The key evolution from MemGPT to Letta is the introduction of **sleep-time agents** — a separate agent that manages memory asynchronously during idle periods.

#### Architecture

When sleep-time is enabled, Letta creates **two agents**:

1. **Primary Agent** — handles user conversations. Has tools for sending messages, calling custom tools, searching Recall/Archival memory. But **cannot edit Core Memory** directly.

2. **Sleep-Time Agent** — runs in the background between conversations. Has tools to edit both its own Core Memory AND the primary agent's Core Memory. Can:
   - Consolidate fragmented memories
   - Identify patterns across conversations
   - Reorganize and deduplicate memory blocks
   - Archive and prune outdated information
   - Process uploaded documents asynchronously

#### Why This Matters

- **Non-blocking** — memory management doesn't slow down conversations.
- **Higher quality** — dedicated agent with potentially stronger model (e.g., primary uses gpt-4o-mini, sleep-time uses gpt-4.1 or Claude Sonnet).
- **Continuous improvement** — memories get cleaner over time instead of accumulating cruft.
- **Anytime reads** — primary agent reads from memory at any point, even while sleep-time agent is still processing.

This is conceptually identical to what Nat Eliason's Felix does with nightly consolidation cron jobs, but implemented as a framework feature rather than user-side scripting.

### Comparison: MemGPT vs Mem0 vs LangMem

| Feature | MemGPT/Letta | Mem0 | LangMem |
|---------|-------------|------|---------|
| Memory model | OS-style paging | Auto-extraction + graph | Namespace-scoped store |
| Short-term | Structured context sections | Chat compression | Conversation buffer |
| Long-term | Archival + Recall | Vector DB + graph DB | BaseStore (pluggable) |
| Management | Self-directed (agent decides) | Automatic extraction | Tool-based (manage/search) |
| Sleep-time | Yes (dedicated agent) | No | No |
| Graph support | No | Yes (Neo4j-backed) | Via triples extraction |

---

## 3. OpenClaw Community Memory Setups

### 3a. Nathan / madebynathan.com — Wikibase Entity Enrichment

**Source:** [madebynathan.com](https://madebynathan.com/2026/02/03/everything-ive-done-with-openclaw-so-far/) (Feb 2026)

Nathan runs an agent called "Reef" with arguably the most sophisticated memory setup in the OpenClaw community.

#### Architecture
- **Obsidian vault** (5,000+ notes) — the raw knowledge base.
- **Wikibase** (same software as Wikidata) — structured knowledge graph with typed entities, properties, relationships, and SPARQL queries.
- Standard OpenClaw files: SOUL.md, MEMORY.md, daily logs.

#### Automated Knowledge Pipeline (15+ cron jobs)

| Schedule | Job | Description |
|----------|-----|-------------|
| Every 6h | KB Data Entry Batch | Processes Obsidian notes → extract entities → populate Wikibase |
| Every 6h | Link Reconciliation | Convert `[[wiki links]]` in notes → Wikibase entity stubs |
| Every 8h | Entity Enrichment | Take stub entities, enrich by searching Gmail, ChatGPT, X, Obsidian exports |
| Daily | Wikibase Weekly Review | QA pass on recently created entities |
| 4am daily | Nightly Brainstorm | Creative exploration through notes/emails/exports looking for connections |

#### Key Innovation: Structured Entity Extraction
- From ChatGPT export alone: extracted **49,079 atomic facts** and **57 entities** (companies, technologies, concepts).
- Expanding to Claude Code history (174K+ messages), Obsidian (5K+ files), Notion, UpNote, Ghost.
- Uses **SPARQL queries** for structured retrieval: "all people who worked at company X", "all projects using technology Y".

This is the most ambitious example of using a **real knowledge graph** (not just files) for agent memory.

### 3b. s1nthagent/openclaw-memory — Community Plugin

**Source:** [GitHub](https://github.com/s1nthagent/openclaw-memory)

A community-built memory system (by S1nth, itself an AI agent) that implements 3-layer memory:

```
┌─────────────────────────────────────────┐
│ Hot Context (MEMORY.md)                 │
│ - Active work, open loops               │
│ - Recent history (7 days)               │
│ - Auto-loaded every session             │
└─────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────┐
│ Warm Retrieval (auto-consolidation)     │
│ - memory-consolidate.py                 │
│ - Extracts events from daily notes      │
│ - Updates MEMORY.md automatically       │
└─────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────┐
│ Cold Storage (daily notes)              │
│ - memory/YYYY-MM-DD.md                  │
│ - Full session logs                     │
│ - Searchable history                    │
└─────────────────────────────────────────┘
```

Key features:
- **Auto-consolidation** runs every 6 hours: scans last 7 days of daily notes, extracts significant events, updates MEMORY.md, prunes entries older than 7 days.
- **Context monitoring** (every 15 min): checks context window usage, alerts at 70%/85% thresholds for emergency flush.
- **SQLite-vec / ChromaDB** backend for embedding-based search (Phase 2).
- Plans for AI-compressed summaries via Claude, MCP integration, memory versioning/snapshots.

### 3c. r/LocalLLaMA — "3 Weeks with OpenClaw" (Multi-Agent Architecture)

**Source:** [Reddit post](https://www.reddit.com/r/LocalLLaMA/comments/1r3ro5h/) (Feb 2026)

User running 5 specialized sub-agents with two-tier memory:
- Daily logs + curated MEMORY.md (standard pattern)
- **Nightly cron job** reviews daily logs and extracts anything worth keeping
- **DECISIONS.md** — cron jobs must check this before taking external actions (prevents stale automated actions)

Biggest lesson: *"Every cron job that messages someone or takes external action needs a pre-flight check (is this still relevant?), output sanitization, and a way to abort if context changed."*

### 3d. clawvault — Obsidian-Native Memory System

**Source:** [npm package](https://www.npmjs.com/package/clawvault)

An npm package providing:
- Typed storage (entities, relationships, events)
- Knowledge graph visualization
- Context profiles
- Canvas dashboards
- Obsidian-native task views

Appears to bridge OpenClaw workspace files with Obsidian's vault system.

### 3e. Dave Swift — OpenClaw + Obsidian

**Source:** [daveswift.com](https://daveswift.com/openclaw-obsidian-memory/) (Feb 2026)

Setup for agent "Lloyd" using Obsidian vault with folders like Inbox, Projects, Thinking, Resources. Each folder has `*-guide.md` files that teach the agent how to handle that category. Key insight: the file structure itself *trains* the agent on how the user thinks.

### 3f. Agent Native — Memory Contract Pattern

**Source:** [Medium article](https://agentnativedev.medium.com/openclaw-memory-systems-that-dont-forget-qmd-mem0-cognee-obsidian-4ad96c02c9cc) (Feb 2026)

Proposes fixing OpenClaw memory at the **harness level**:
- Flush checkpoints at context thresholds
- Working-set control
- Hybrid retrieval (semantic + keyword)
- Session indexing
- **Memory contracts** — force the agent to search before acting and persist constraints

Evaluates QMD, Mem0, Cognee, and Obsidian as substrate upgrades.

### 3g. rentierdigital — Production Architecture

**Source:** [Medium](https://medium.com/@rentierdigital/the-complete-openclaw-architecture-that-actually-scales-memory-cron-jobs-dashboard-and-the-c96e00ab3f35) (Feb 2026)

Dual-VPS failover setup with structured memory, cron jobs, and dashboard. Running daily for $15/month.

---

## 4. Knowledge Graph Approaches for AI Agents

### 4a. Graphiti / Zep — Temporal Knowledge Graphs

**Sources:** [Zep paper](https://arxiv.org/abs/2501.13956) (Jan 2025), [Neo4j blog](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/), [GitHub](https://github.com/getzep/graphiti)

The most sophisticated graph-based memory system currently available.

#### Architecture
- **Neo4j** graph database backend
- **Bi-temporal model**: tracks both when an event occurred AND when it was ingested
- Every edge has validity intervals (`t_valid`, `t_invalid`)
- Automatically detects and resolves **contradictions** — when new info conflicts with existing knowledge, uses temporal metadata to invalidate (but not delete) old information

#### Key Features
- **Incremental updates** — no batch recomputation when data changes
- **Hybrid retrieval** — semantic embeddings + BM25 keyword search + graph traversal
- **P95 latency: 300ms** — no LLM calls at retrieval time
- **Custom entity types** via Pydantic models (people, preferences, business objects)
- Outperforms MemGPT on Deep Memory Retrieval benchmarks

#### Why It Matters for Agent Memory
Unlike flat-file memory or basic vector stores, Graphiti can answer:
- "What did the user prefer *last month* vs *now*?"
- "How has project X evolved over time?"
- "Which facts are still valid vs superseded?"

This is the gap between "I remember that you like coffee" and "I know you switched from coffee to tea in January."

### 4b. Mem0 — Hybrid Vector + Graph Memory

**Sources:** [Mem0 paper](https://arxiv.org/abs/2504.19413) (April 2025), [GitHub](https://github.com/mem0ai/mem0), [docs](https://docs.mem0.ai)

#### Architecture
- **Dual storage**: vector database (embeddings) + graph database (relationships)
- **Three scopes**: user, session, agent — memories are namespaced
- **Automatic extraction**: LLM-based pipeline extracts entities and relationships from every conversation
- **Entity Extractor** → identifies nodes; **Relations Generator** → infers labeled edges

#### Graph Memory Features (Mem0g)
- Two-stage LLM pipeline for extraction
- Stores embeddings in vector DB, mirrors relationships in graph backend
- Automatic deduplication and conflict resolution
- Cross-session context through hierarchical memory levels

### 4c. A-MEM — Zettelkasten for Agents

**Source:** [Paper](https://arxiv.org/abs/2502.12110) (NeurIPS 2025), [GitHub](https://github.com/WujiangXu/A-mem)

Applies the **Zettelkasten method** to AI agent memory:

#### How It Works
1. **Note Construction**: When a new memory is added, generate a structured note with:
   - Contextual description
   - Keywords
   - Tags
   - Links to related existing memories

2. **Link Generation**: Analyze historical memories to find relevant connections. Establish bidirectional links where meaningful similarities exist.

3. **Memory Evolution**: As new memories integrate, they can trigger **updates to existing memories** — the contextual representations and attributes of old memories evolve as the network grows.

#### Key Insight
Traditional memory systems are static stores. A-MEM creates a **living network** where adding new information can retroactively enrich the understanding of old information. This mirrors how humans update their mental models when learning something new that recontextualizes past experiences.

Uses **ChromaDB** for vector storage + **NetworkX** DiGraph for explicit typed edges.

### 4d. LangMem — Namespace-Scoped Memory

**Source:** [LangChain blog](https://blog.langchain.com/langmem-sdk-launch/) (May 2025), [GitHub](https://github.com/langchain-ai/langmem)

LangChain's approach to agent memory:
- **Namespace-based isolation**: `("chat", "{user_id}", "triples")` — template variables populated at runtime
- **Semantic extraction**: LLM extracts structured data (triples, profiles, facts) from conversations
- **Pluggable storage**: via LangGraph's BaseStore interface
- **Profile management**: dedicated pattern for maintaining evolving user profiles
- Supports both tool-based (agent-driven) and automatic extraction modes

### 4e. Structured vs Flat File: The Spectrum

```
Flat Files ←——————————————————→ Full Graph DB
  ↑                                      ↑
MEMORY.md                          Neo4j + Graphiti
daily notes                        Wikibase (Nathan)
  ↓                                      ↓
Simple, transparent,             Powerful queries,
no dependencies,                 temporal reasoning,
agent can read/write             complex relationships,
directly                         requires infrastructure
```

**Intermediate approaches:**
- PARA folder hierarchy (Nat/Felix) — structured files, no DB
- Obsidian with backlinks — implicit graph via `[[wiki links]]`
- SQLite-vec (s1nthagent) — embeddings in a lightweight DB
- A-MEM (ChromaDB + NetworkX) — vector + explicit graph, no heavy DB

---

## 5. Hierarchical Summarization (Daily → Weekly → Monthly → Permanent)

### Who's Doing It?

The pure daily→weekly→monthly→permanent cascade is surprisingly **rare in practice**. Most implementations use a simpler 2-3 tier model. Here's what exists:

### 5a. Nat Eliason's Nightly Consolidation
- **Daily → Knowledge Base** (nightly cron)
- No explicit weekly/monthly tiers — consolidation goes directly from daily notes into the PARA knowledge graph
- The PARA structure *is* the permanent memory

### 5b. s1nthagent/openclaw-memory
- **Daily → MEMORY.md** (every 6 hours)
- 7-day sliding window — entries older than 7 days get pruned from MEMORY.md
- Daily notes themselves persist as cold storage
- No weekly/monthly tiers

### 5c. Letta Sleep-Time Agents
- **Continuous consolidation** rather than time-bucketed
- Sleep-time agent runs between conversations and continuously refines core memory
- More like a background daemon than a scheduled batch process
- Can be configured for different frequencies

### 5d. CorpGen (Microsoft Research)
**Source:** [Microsoft Research](https://www.microsoft.com/en-us/research/blog/corpgen-advances-ai-agents-for-real-work/) (Feb 2026), [Paper](https://arxiv.org/html/2602.14229)

The closest to a true hierarchical system:
- **Tiered memory**: Working memory (intra-cycle) → Structured LTM (plans, summaries) → Semantic memory (Mem0 embeddings)
- Each day begins with structured plan + memory loaded from previous sessions
- Agent stores key outcomes at day's end for next session
- **Adaptive summarization** to manage token limits
- **Hierarchical goal decomposition** at three temporal scales

### 5e. Progressive Summarization (Tiago Forte)
**Source:** [Forte Labs](https://fortelabs.com/blog/progressive-summarization-a-practical-technique-for-designing-discoverable-notes/)

Not AI-specific, but the conceptual foundation that several agent memory systems draw on:
- **5 layers**: Original text → Bold passages → Highlighted → Mini-summary → Remix
- **Opportunistic compression** — summarize in small spurts, over time, as needed
- Only compress as much as the information deserves

This philosophy is visible in several agent systems — don't pre-summarize everything, let importance emerge through use.

### 5f. Automated Hierarchical Summarization: Does It Exist?

**Short answer: Not really as a standalone system.** The pattern that's emerged instead is:

1. **Daily raw capture** → daily log files
2. **Periodic consolidation** → extract to long-term store (nightly or every 6-8 hours)
3. **The long-term store IS the permanent memory** — there's no separate weekly/monthly tier

Why? Because:
- Weekly/monthly summaries lose the detail that makes memories useful
- The agent needs recent context (daily) and key facts (permanent), but rarely needs "a summary of last week"
- It's easier to search raw notes than navigate a hierarchy of summaries
- Time-bucketed summaries create artificial boundaries that don't match how information is actually used

**The one exception**: Nathan's Wikibase approach, where entities accumulate structured properties over time. This is effectively permanent memory that gets richer, not summarized.

---

## 6. Synthesis: Patterns & Anti-Patterns

### Common Patterns Across All Systems

1. **Two-tier minimum**: Raw capture (daily/session) + curated long-term (MEMORY.md / knowledge graph / core memory)
2. **Automated consolidation**: Cron job or sleep-time agent processes raw → curated
3. **Self-editing**: The agent manages its own memory (not an external system)
4. **Threshold-based flush**: Context window monitoring triggers emergency memory writes
5. **Separation of concerns**: What happened (logs) vs what matters (memory) vs who I am (persona)

### Anti-Patterns

1. **MEMORY.md as junk drawer** — without consolidation, it grows until it's useless
2. **No pre-flight checks** — cron jobs acting on stale context
3. **Mental notes** — anything not written to a file is lost
4. **Over-summarization** — weekly/monthly summaries that lose critical detail
5. **Monolithic context** — cramming everything into one prompt instead of tiered retrieval

### What's Missing (Opportunities)

1. **Temporal reasoning in flat-file systems** — Graphiti can answer "what changed when?" but flat files can't
2. **Cross-agent memory sharing** — sub-agents can't easily share discoveries with each other
3. **Memory validation** — no system verifies that stored memories are still accurate
4. **Forgetting** — deliberate pruning of irrelevant memories (only s1nthagent's 7-day window does this)
5. **Importance scoring** — deciding *what* to consolidate is still mostly LLM judgment, not measured importance

---

## 7. Sources & Further Reading

| Source | URL | Date |
|--------|-----|------|
| Nat Eliason / Felix tutorial | [creatoreconomy.so](https://creatoreconomy.so/p/use-openclaw-to-build-a-business-that-runs-itself-nat-eliason) | Feb 2026 |
| MemGPT paper | [arxiv.org/abs/2310.08560](https://arxiv.org/abs/2310.08560) | Oct 2023 |
| Letta sleep-time compute | [letta.com/blog/sleep-time-compute](https://www.letta.com/blog/sleep-time-compute) | Apr 2025 |
| Letta agent memory guide | [letta.com/blog/agent-memory](https://www.letta.com/blog/agent-memory) | 2025 |
| Zep/Graphiti paper | [arxiv.org/abs/2501.13956](https://arxiv.org/abs/2501.13956) | Jan 2025 |
| Graphiti + Neo4j blog | [neo4j.com/blog](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/) | Aug 2025 |
| Mem0 paper | [arxiv.org/abs/2504.19413](https://arxiv.org/abs/2504.19413) | Apr 2025 |
| A-MEM (Zettelkasten) paper | [arxiv.org/abs/2502.12110](https://arxiv.org/abs/2502.12110) | Feb 2025 |
| s1nthagent/openclaw-memory | [github.com](https://github.com/s1nthagent/openclaw-memory) | Feb 2026 |
| Nathan / Reef / Wikibase | [madebynathan.com](https://madebynathan.com/2026/02/03/everything-ive-done-with-openclaw-so-far/) | Feb 2026 |
| Dave Swift / Obsidian | [daveswift.com](https://daveswift.com/openclaw-obsidian-memory/) | Feb 2026 |
| Agent Native memory contracts | [medium.com](https://agentnativedev.medium.com/openclaw-memory-systems-that-dont-forget-qmd-mem0-cognee-obsidian-4ad96c02c9cc) | Feb 2026 |
| clawvault npm package | [npmjs.com/package/clawvault](https://www.npmjs.com/package/clawvault) | 2026 |
| CorpGen (Microsoft Research) | [microsoft.com](https://www.microsoft.com/en-us/research/blog/corpgen-advances-ai-agents-for-real-work/) | Feb 2026 |
| LangMem SDK | [langchain blog](https://blog.langchain.com/langmem-sdk-launch/) | May 2025 |
| 3 weeks with OpenClaw (Reddit) | [r/LocalLLaMA](https://www.reddit.com/r/LocalLLaMA/comments/1r3ro5h/) | Feb 2026 |
| Progressive Summarization | [fortelabs.com](https://fortelabs.com/blog/progressive-summarization-a-practical-technique-for-designing-discoverable-notes/) | 2017 |
| Velvet Shark / 50 days prompts | [gist.github.com](https://gist.github.com/velvet-shark/b4c6724c391f612c4de4e9a07b0a74b6) | 2026 |
