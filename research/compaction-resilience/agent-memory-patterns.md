# Agent Memory Patterns: How AI Frameworks Handle Context Limits

> Research compiled 2026-02-26. Focus: practical patterns for file-based memory systems.

---

## Table of Contents

1. [The Core Problem](#the-core-problem)
2. [Framework-by-Framework Analysis](#framework-by-framework-analysis)
3. [Memory Type Taxonomy](#memory-type-taxonomy)
4. [Pattern 1: Tiered Memory (MemGPT/Letta)](#pattern-1-tiered-memory-memgptletta)
5. [Pattern 2: Context Compaction (Claude Code)](#pattern-2-context-compaction-claude-code)
6. [Pattern 3: Structured Scratchpads (Anthropic Multi-Agent)](#pattern-3-structured-scratchpads)
7. [Pattern 4: Memory Bank (Cline)](#pattern-4-memory-bank-cline)
8. [Pattern 5: Repository Maps (Aider)](#pattern-5-repository-maps-aider)
9. [Pattern 6: Session Resume (Codex CLI)](#pattern-6-session-resume-codex-cli)
10. [Pattern 7: Conversation Summary Buffer (LangChain)](#pattern-7-conversation-summary-buffer-langchain)
11. [Pattern 8: Checkpointing (LangGraph)](#pattern-8-checkpointing-langgraph)
12. [Pattern 9: Multi-Layer Memory (CrewAI)](#pattern-9-multi-layer-memory-crewai)
13. [Pattern 10: File-Based Memory ("Convergent Evolution")](#pattern-10-file-based-memory)
14. [Pattern 11: Progressive Summarization for Agents](#pattern-11-progressive-summarization)
15. [Pattern 12: Memory Extraction & Consolidation (Mem0)](#pattern-12-memory-extraction-mem0)
16. [Pattern 13: Self-Learning Feedback Loops](#pattern-13-self-learning-feedback-loops)
17. [Comparative Analysis](#comparative-analysis)
18. [Practical Recommendations for OpenClaw](#practical-recommendations-for-openclaw)
19. [Key Academic Papers](#key-academic-papers)
20. [Sources](#sources)

---

## The Core Problem

LLMs have fixed context windows (working memory). As conversations grow, older information gets truncated, summarized, or silently dropped. This creates three failure modes (per Drew Breunig):

- **Context Poisoning**: Hallucinations make it into context and persist
- **Context Distraction**: Too much context overwhelms the training signal
- **Context Confusion**: Irrelevant context influences responses
- **Context Rot**: As token count increases, recall accuracy decreases (per Chroma research)

Anthropic frames it as **attention scarcity**: transformers use n² pairwise attention, so every token added depletes the "attention budget." Context engineering = optimizing token utility against these constraints.

> "Context engineering is the delicate art and science of filling the context window with just the right information for the next step." — Andrej Karpathy

---

## Framework-by-Framework Analysis

| Framework | Primary Strategy | Persistence Level | Best For |
|-----------|-----------------|-------------------|----------|
| **LangChain** | Modular (Buffer, Summary, Entity) | Manual (connect DB) | Diverse RAG workflows |
| **LangGraph** | Graph Checkpointing | Built-in (thread-level) | Complex cyclical tasks |
| **CrewAI** | Unified Multi-Layer (STM, LTM, Entity) | Built-in (SQLite/Chroma) | Multi-agent collaboration |
| **MemGPT/Letta** | OS-inspired tiered memory | Built-in (hierarchical) | Extended context illusion |
| **Claude Code** | Compaction + CLAUDE.md files | File-based (Markdown) | Coding sessions |
| **Codex CLI** | Session resume + AGENTS.md | File-based + session store | Coding automation |
| **Aider** | Repository maps + chat history | In-session (tree-sitter) | Codebase navigation |
| **Cline** | Memory Bank (structured MD files) | File-based (Markdown) | Project continuity |
| **Cursor** | Rules + Skills + auto-memories | File-based + IDE state | IDE-integrated coding |
| **Manus** | Three-file pattern | File-based (Markdown) | Long-running agent tasks |
| **Mem0** | Extract-Consolidate-Retrieve | Vector DB + graph | Cross-session personalization |
| **OpenAI Agents SDK** | SummarizingSession | In-memory | Short-term compression |

---

## Memory Type Taxonomy

From the research, agent memory types map to cognitive analogs:

| Memory Type | Duration | Implementation | Purpose |
|-------------|----------|----------------|---------|
| **Short-Term** | Minutes | Context window / buffer | Current conversation thread |
| **Working** | Seconds–minutes | Scratchpad / state object | Intermediate reasoning (CoT) |
| **Long-Term** | Indefinite | Files / DB / vector store | Facts, preferences, decisions |
| **Procedural** | Permanent | Action recipes / learned rules | "How to" knowledge |
| **Episodic** | Variable | Session logs / transcripts | Past interaction examples |
| **Semantic** | Permanent | Knowledge base / entities | Structured facts & relationships |

---

## Pattern 1: Tiered Memory (MemGPT/Letta)

**Source**: MemGPT paper (UC Berkeley, 2023), Letta framework  
**Paper**: [arxiv.org/abs/2310.08560](https://arxiv.org/abs/2310.08560)

### Concept

Inspired by OS virtual memory. The LLM's context window = RAM, external storage = disk. The agent manages its own memory via function calls, paging data in and out.

### Architecture

```
┌─────────────────────────────────┐
│  Main Context (RAM)             │
│  ┌───────────┐  ┌─────────┐    │
│  │ Core      │  │ Message │    │
│  │ Memory    │  │ Buffer  │    │
│  │ (blocks)  │  │ (FIFO)  │    │
│  └───────────┘  └─────────┘    │
└────────────┬────────────────────┘
             │ page in/out via tools
┌────────────▼────────────────────┐
│  External Storage (Disk)        │
│  ┌──────────┐  ┌────────────┐  │
│  │ Recall   │  │ Archival   │  │
│  │ Memory   │  │ Memory     │  │
│  │ (search) │  │ (vector DB)│  │
│  └──────────┘  └────────────┘  │
└─────────────────────────────────┘
```

### Key Components

- **Core Memory**: In-context blocks (persona, user info, goals). Editable by the agent itself via `core_memory_replace` and `core_memory_append` tools
- **Recall Memory**: Searchable conversation history (stored on disk, retrieved via `conversation_search`)
- **Archival Memory**: Vector-indexed knowledge store for explicitly saved information (`archival_memory_insert` / `archival_memory_search`)

### Eviction Strategy

When context fills up, 70% of messages are evicted. Evicted messages undergo recursive summarization — summarized along with existing summaries. Older messages have progressively less influence.

### File-Based Adaptation for OpenClaw

```
workspace/
├── MEMORY.md              # Core memory (always loaded, ~150 lines)
├── memory/
│   ├── 2026-02-26.md      # Recall memory (daily logs)
│   ├── 2026-02-25.md
│   └── archive/           # Archival memory (searchable)
│       ├── decisions.md
│       ├── architecture.md
│       └── entities.md
```

Core memory = `MEMORY.md` (always in context). Recall = daily notes (loaded on demand). Archival = structured files searched when needed.

---

## Pattern 2: Context Compaction (Claude Code)

**Source**: Anthropic Claude Code, Claude API Compaction docs

### How It Works

Claude Code manages context automatically. When approaching the window limit (~75% of 200K tokens = ~150K), it triggers compaction:

1. **Clears older tool outputs first** (highest token waste)
2. **Summarizes the conversation** if still over limit
3. **Preserves**: user requests, key code snippets, CLAUDE.md content
4. **Loses**: detailed instructions from early in the session

### The Compaction Buffer

For a 200K context window, compaction triggers around 167K tokens. The remaining 33K buffer is used for the summarization process itself — Claude needs working space to create the summary.

### CLAUDE.md Hierarchy (Compaction-Resilient)

```
~/.claude/CLAUDE.md           # Global (all projects)
~/project/CLAUDE.md           # Project-level
~/project/.claude/CLAUDE.md   # Project settings
```

These files are **re-read after every compaction**, making them compaction-resilient. Anything in CLAUDE.md survives context resets.

### Hooks for Memory Persistence

Claude Code's hook system enables memory capture at critical moments:

```json
{
  "hooks": {
    "PreCompact": ["./scripts/save-state.sh"],
    "Stop": ["./scripts/extract-memories.sh"],
    "SessionEnd": ["./scripts/consolidate.sh"]
  }
}
```

### Community Pattern: Structured State to Disk

From r/ClaudeAI (247 upvotes): Instead of relying on conversation memory, write structured state to disk. The CLAUDE.md instructs Claude to maintain a state file:

```markdown
## Working State
Before each major step, update `.claude/state.md` with:
- Current objective
- Completed steps
- Key decisions made
- File paths being modified
- Numbers/values computed
```

**Key insight**: Context survives compaction because state is in files, not conversation history.

---

## Pattern 3: Structured Scratchpads

**Source**: Anthropic multi-agent research system, LangChain context engineering guide

### Concept

Agents write notes to a "scratchpad" — a persistent storage area outside the context window. The scratchpad is read back when needed, similar to a human taking notes during complex problem-solving.

### Anthropic's Multi-Agent Researcher

> "The LeadResearcher begins by thinking through the approach and saving its plan to Memory to persist the context, since if the context window exceeds 200,000 tokens it will be truncated and it is important to retain the plan."

### Implementation Approaches

**1. File-based scratchpad** (simplest, works with OpenClaw):
```markdown
# .scratchpad.md — Working Memory

## Current Task
Refactoring the validator client API layer

## Plan
1. ✅ Identify all affected endpoints
2. 🔄 Update type definitions
3. ⬜ Modify handler functions
4. ⬜ Update tests

## Key Findings
- 14 endpoints affected (list in docs/endpoints.md)
- Breaking change: attestation format changed in Electra

## Decisions Made
- Use adapter pattern for backward compat (decided 2026-02-26)
- Keep old endpoints as deprecated, not removed
```

**2. State object** (runtime, not file-based):
```python
# LangGraph state-based scratchpad
class AgentState(TypedDict):
    messages: list[BaseMessage]
    scratchpad: str           # Persisted between steps
    plan: str                 # Current plan
    completed_steps: list[str]
```

**3. Extended thinking as scratchpad** (Claude-specific):
Using extended thinking mode as a "controllable scratchpad" where Claude reasons through its approach before acting.

---

## Pattern 4: Memory Bank (Cline)

**Source**: Cline (formerly Cline Bot), community-developed pattern

### Concept

A structured documentation system using Markdown files that the agent reads at the start of **every** task. Treats the agent's memory reset as a feature, not a bug — it forces perfect documentation.

### File Structure

```
memory-bank/
├── projectbrief.md      # Foundation: core requirements and goals
├── productContext.md     # Why the project exists, UX goals
├── activeContext.md      # Current focus, recent changes, next steps
├── systemPatterns.md     # Architecture, design patterns
├── techContext.md        # Tech stack, setup, constraints
└── progress.md           # What works, what's left, known issues
```

### Key Design Principles

1. **Hierarchical**: Files build on each other (brief → context → patterns → progress)
2. **Always read**: Agent MUST read ALL files at task start — non-optional
3. **Frequently updated**: `activeContext.md` changes every session
4. **Concise**: Each file ~1 page. Details go in linked docs
5. **Human-editable**: Plain Markdown, version-controllable

### Session Management Commands

- `"initialize memory bank"` — Create initial structure
- `"update memory bank"` — Full review and update after milestones
- `"follow your custom instructions"` — Read bank and resume work

### Context Window Integration

When the context window fills:
1. Ask agent to "update memory bank" (captures current state)
2. Start new conversation
3. Agent reads memory bank files → has full context again

### Adaptation for OpenClaw

This pattern maps almost 1:1 to OpenClaw's architecture:

| Cline Memory Bank | OpenClaw Equivalent |
|-------------------|---------------------|
| `projectbrief.md` | `AGENTS.md` (project instructions) |
| `activeContext.md` | Today's daily note (`memory/YYYY-MM-DD.md`) |
| `progress.md` | `MEMORY.md` (curated knowledge) |
| `systemPatterns.md` | `TOOLS.md` + project-specific files |

---

## Pattern 5: Repository Maps (Aider)

**Source**: Aider (aider.chat)

### Concept

Instead of loading entire files, Aider builds a **compact repository map** showing classes, methods, and function signatures from the entire codebase. This gives the LLM enough context to navigate without exhausting the window.

### How It Works

1. Uses **tree-sitter** to parse all files → extract identifiers
2. Builds a **graph** of references between identifiers
3. Applies **PageRank** to prioritize which identifiers are most important
4. Generates a compact map within a configurable token budget (`--map-tokens`)
5. Map is **task-aware**: analyzed "in light of the current chat" to include relevant symbols

### Example Repo Map

```
src/validator/index.ts
│ class ValidatorClient
│   - constructor(config: ValidatorConfig)
│   - async proposeBlock(slot: Slot): Promise<SignedBeaconBlock>
│   - async submitAttestation(attestation: Attestation): void
│
src/api/routes.ts
│ function registerRoutes(server: FastifyInstance)
│   - GET /eth/v1/validator/duties/proposer/:epoch
│   - POST /eth/v1/validator/duties/attester/:epoch
```

### Key Insight for File-Based Memory

The repo map is essentially a **structured index** — a compressed representation of the codebase that fits in the context window. This same principle can be applied to memory:

```markdown
# memory-index.md — Compact Map of All Memory Files

## Daily Notes (recent)
- 2026-02-26: Worked on compaction research, spawned sub-agents
- 2026-02-25: PR #8874 reviews, lazy slasher refinements
- 2026-02-24: EIP-8025 implementation started

## Key Decisions (memory/decisions/)
- Use adapter pattern for backward compat (Feb 26)
- Merge strategy: never force-push (standing rule)

## Active Tasks
- Compaction resilience research (this task)
- PR #8874 lazy slasher (awaiting review)
```

---

## Pattern 6: Session Resume (Codex CLI)

**Source**: OpenAI Codex CLI

### How It Works

Codex stores **full session transcripts** locally (`~/.codex/sessions/`). You can resume any previous session with all context intact:

```bash
# Resume most recent session
codex resume --last

# Resume with new instructions
codex exec resume --last "Fix the race conditions you found"

# Resume specific session
codex resume 7f9f9a2e-1b3c-4c7a-9b0e-...
```

Each resumed run keeps:
- Original transcript
- Plan history
- Approval records
- Working directory state

### AGENTS.md (Codex's Equivalent of CLAUDE.md)

```
~/.codex/AGENTS.md              # Global instructions
~/project/AGENTS.md             # Project-level
~/project/subdir/AGENTS.md      # Directory-level
```

Loaded at session start, provides persistent instructions across sessions.

### Memory Slash Commands

Codex has added `/memory` commands for managing persistent knowledge that survives session boundaries.

### File-Based Takeaway

The session resume pattern = **checkpointing the full conversation**. For a file-based system, the analog is saving session summaries:

```markdown
# memory/sessions/2026-02-26-compaction-research.md

## Session Summary
- Task: Research agent memory patterns
- Duration: ~45 minutes
- Status: Complete

## Key Outputs
- Created ~/research/compaction-resilience/findings/agent-memory-patterns.md
- Searched 15+ sources on agent memory architecture

## Decisions Made
- Focus on file-based patterns over DB-based
- Include practical code examples

## Resume Context
If continuing this work, read the findings document first.
The next step would be applying patterns to OpenClaw's architecture.
```

---

## Pattern 7: Conversation Summary Buffer (LangChain)

**Source**: LangChain framework

### Concept

A hybrid of buffer and summarization. Recent messages stay in full. Older messages are compressed into a running summary. Uses token count (not message count) to decide when to compress.

### Implementation

```python
from langchain.memory import ConversationSummaryBufferMemory
from langchain.llms import OpenAI

memory = ConversationSummaryBufferMemory(
    llm=OpenAI(temperature=0),
    max_token_limit=2000,  # Keep last 2000 tokens verbatim
)

# Recent messages: kept in full
# Older messages: summarized into running summary
# Result: summary + recent = complete context
```

### LangChain Memory Types

| Type | How It Works | Token Cost |
|------|-------------|------------|
| `ConversationBufferMemory` | Store everything | O(n) — grows unbounded |
| `ConversationBufferWindowMemory` | Keep last k messages | O(k) — fixed, but loses old context |
| `ConversationSummaryMemory` | Summarize everything | O(1) — constant, but lossy |
| `ConversationSummaryBufferMemory` | Summary + recent buffer | O(k+s) — best balance |
| `ConversationEntityMemory` | Track entities mentioned | O(e) — scales with entities |
| `VectorStoreRetrieverMemory` | RAG over past messages | O(r) — retrieval-based |

### File-Based Adaptation

```markdown
# memory/conversation-summary.md

## Running Summary (auto-updated)
The agent has been working on Lodestar consensus client. Key areas:
validator API refactoring (adapter pattern chosen), lazy slasher
implementation (PR #8874), and EIP-8025 optional proofs. The user
prefers TypeScript strict mode, conventional commits, and no force-push.

## Recent Context (last session)
- Reviewed PR feedback on lazy slasher from nflaig
- Fixed type narrowing issue in slasher/index.ts
- Next: address bot reviewer comments (Gemini, Codex)
```

---

## Pattern 8: Checkpointing (LangGraph)

**Source**: LangChain/LangGraph framework

### Concept

Save the **complete graph state** at every execution step ("superstep"). Enables:
- **Resume**: Pick up where you left off after crash/restart
- **Time travel**: Roll back to any previous state
- **Human-in-the-loop**: Pause for human approval, resume later
- **Debugging**: Replay exact execution sequence

### Implementation

```python
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph

# Create checkpointer (persists to SQLite)
checkpointer = SqliteSaver.from_conn_string("checkpoint.db")

# Build graph with checkpointer
graph = StateGraph(AgentState)
graph.add_node("research", research_node)
graph.add_node("write", write_node)
app = graph.compile(checkpointer=checkpointer)

# Every invocation saves state to DB
# Resume with same thread_id to continue
result = app.invoke(
    {"messages": [HumanMessage(content="Research X")]},
    config={"configurable": {"thread_id": "session-123"}}
)
```

### File-Based Adaptation

Instead of SQLite, checkpoint to Markdown:

```markdown
# memory/checkpoints/task-2026-02-26-refactor.md

## Checkpoint: Step 3 of 5
- Timestamp: 2026-02-26T14:30:00Z
- Status: IN_PROGRESS

## Completed Steps
1. ✅ Identified affected files (14 files, listed below)
2. ✅ Updated type definitions in types/api.ts
3. 🔄 Modifying handler functions (7/14 done)

## Current State
- Working on: src/api/handlers/attestation.ts
- Blocked by: Nothing
- Files modified: [list]

## Next Steps
4. ⬜ Update remaining 7 handlers
5. ⬜ Run test suite, fix failures

## Rollback Info
- Git commit before changes: abc1234
- Branch: feat/api-refactor
```

---

## Pattern 9: Multi-Layer Memory (CrewAI)

**Source**: CrewAI framework

### Architecture

CrewAI uses four memory types simultaneously:

1. **Short-Term Memory**: ChromaDB + RAG for current session context
2. **Long-Term Memory**: SQLite3 for task results across sessions
3. **Entity Memory**: RAG to track people, places, concepts
4. **Contextual Memory**: Combines above for agent reasoning

### Enabling Memory

```python
from crewai import Crew, Agent, Task

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    memory=True,  # Enables all memory types
    # Storage: platform-specific app data directory
)
```

### Key Insight

CrewAI's multi-agent architecture means memory serves **coordination** — agents share context about what other agents have done. In a single-agent system (OpenClaw), this maps to:
- Short-term = current session context window
- Long-term = MEMORY.md (curated insights)
- Entity = tracking of people, repos, PRs mentioned
- Contextual = daily notes (what happened today)

---

## Pattern 10: File-Based Memory ("Convergent Evolution")

**Source**: Manus ($2B acquisition), OpenClaw, Claude Code — independent convergence

### The Convergence

Three independent high-value projects converged on the same solution: **plain Markdown files for memory**:

| System | Files Used |
|--------|-----------|
| **Manus** | `task_plan.md` (goals/progress), `notes.md` (research), deliverable output |
| **OpenClaw** | `MEMORY.md` (curated), `memory/YYYY-MM-DD.md` (daily), `SOUL.md` (personality) |
| **Claude Code** | `CLAUDE.md` hierarchy, `.claude/MEMORY.md` (auto-captured learnings) |

### Why Files Beat Databases for Agent Memory

1. **Persistent**: Survives crashes, restarts, updates (decoupled from process lifecycle)
2. **Transparent**: Open in any text editor, read exactly what agent "knows"
3. **Editable**: Fix hallucinated memories by editing the file
4. **Versionable**: Git tracks changes over time
5. **Portable**: No database to migrate, backup, or corrupt
6. **Human-readable**: Markdown renders nicely everywhere
7. **Holistic context**: Full document > fragmented vector similarity results

### File-Based RAG Alternative

From Bas Nijholt's `agent-cli` project:
- Documents in a folder → auto-indexed with ONNX embeddings
- Memories as Markdown files with Git versioning
- OpenAI-compatible proxy → works with any tool (Cursor, Cline, etc.)
- Two-stage retrieval: embedding similarity → cross-encoder reranking

```
~/my-docs/          # Drop files here → auto-indexed
~/.agent/memories/  # Markdown files with Git versioning
```

### The Reconciliation Loop

When memories accumulate, a reconciliation step merges duplicates:
1. Extract new facts from conversation
2. Compare against existing memories (Jaccard similarity)
3. If >60% overlap → supersede old entry
4. Every N extractions → LLM consolidation pass
5. Confidence decay: progress fades (7-day half-life), architecture never decays

---

## Pattern 11: Progressive Summarization for Agents

**Source**: Tiago Forte's Progressive Summarization, adapted for AI agents

### Original Concept (Forte)

Five layers of increasing compression:

1. **L1**: Original notes (captured)
2. **L2**: Bold the important parts
3. **L3**: Highlight within the bold
4. **L4**: Executive summary in your own words
5. **L5**: Remix into new creative output

Each layer is created **just-in-time** when the note is revisited — not preemptively.

### Agent Adaptation

Apply progressive summarization to session logs and daily notes:

```markdown
# memory/2026-02-26.md

## L1: Raw Session Log (auto-captured)
[Full session transcript — details of every action taken]

## L2: Key Points (end-of-session extraction)
- Researched agent memory patterns across 15+ frameworks
- Found convergent evolution pattern: Manus, OpenClaw, Claude Code all use Markdown
- **MemGPT's tiered memory (RAM/disk analogy) is most applicable**
- **Cline's Memory Bank pattern maps directly to OpenClaw architecture**

## L3: Essence (weekly review)
- **Tiered memory + structured Markdown files = optimal pattern for OpenClaw**
- **Three mechanisms prevent memory bloat: dedup, consolidation, confidence decay**

## L4: Executive Summary (monthly distillation → MEMORY.md)
File-based tiered memory with progressive summarization is the proven pattern.
```

### Recursive Summarization for Context Compaction

```
Session 1 transcript → Summary 1
Session 2 transcript → Summary 2
Summary 1 + Summary 2 → Combined summary
Session 3 transcript → Summary 3
Combined summary + Summary 3 → New combined summary
...
```

Each summarization pass progressively distills, so older sessions have less detail but key decisions and facts persist.

---

## Pattern 12: Memory Extraction & Consolidation (Mem0)

**Source**: Mem0 paper ([arxiv.org/abs/2504.19413](https://arxiv.org/abs/2504.19413))

### Architecture

Mem0 dynamically extracts, consolidates, and retrieves salient information:

```
Conversation → Extract → Consolidate → Store → Retrieve
                  │           │                    │
                  ▼           ▼                    ▼
            Identify      Merge with          Similarity
            key facts     existing memories   search at
            from new      (dedup, update,     query time
            messages      resolve conflicts)
```

### Mem0g (Graph-Enhanced)

Extends flat memory with a knowledge graph:
- Nodes = entities, facts, preferences
- Edges = relationships between them
- Enables traversal-based retrieval (not just similarity)

### Consolidation Strategies

1. **Deduplication**: Jaccard similarity check on incoming memories
2. **Supersession**: New info replaces outdated info (with timestamp)
3. **Contradiction resolution**: Flag conflicting memories
4. **Periodic garbage collection**: LLM reviews all memories, merges/prunes

### File-Based Adaptation

```markdown
# memory/entities/lodestar.md

## Lodestar
- **Type**: Ethereum consensus client (TypeScript)
- **Repo**: ~/lodestar (main), worktrees for features
- **Build**: pnpm build | test: pnpm test:unit | lint: pnpm lint
- **Updated**: 2026-02-26

## Key Decisions
- [2026-02-20] Use adapter pattern for backward compat in API changes
- [2026-02-15] Never force-push — use merge strategy
- [2026-01-10] Node v24 via nvm

## Known Gotchas
- Browser automation breaks after ~5 consecutive writes
- Must use .js extension for relative TS imports
- Don't run pnpm install unless told to
```

---

## Pattern 13: Self-Learning Feedback Loops

**Source**: Context Studios production AI agent architecture

### Architecture

```
EXECUTION → MEMORY → FEEDBACK → STRATEGY → EXECUTION
```

### Three Feedback Loops

**Loop 1: Engagement Metrics → Strategy**
```
measure previous results → analyze patterns →
  if confidence > 0.7: update strategy files →
    adjust next execution
```

**Loop 2: Human Corrections → Learned Rules**
```markdown
# content-rules-learned.md
## Tone & Voice
- [2026-02-10] Scripts should feel "messy" and natural

## Structure
- [2026-02-03] ALL language versions must have SAME section count

## Images
- [2026-02-09] Hero images MUST be specific to article topic
```

Every human correction is appended with a timestamp. The agent reads this file before every run. **The system literally cannot make the same mistake twice.**

**Loop 3: Failure Detection → Recovery**
Every pipeline step writes outputs to disk before proceeding. Partial completion is detected and resumed on next run.

### File-Based Implementation

```
memory/
├── MEMORY.md                    # Long-term (distilled insights)
├── learned-rules.md             # Procedural (accumulated corrections)
├── 2026-02-26.md               # Daily log (raw session data)
└── feedback/
    ├── engagement-metrics.md    # What worked
    └── error-patterns.md       # What failed and why
```

---

## Comparative Analysis

### Context Management Strategy Comparison

| Strategy | Survives Compaction? | Cross-Session? | Human-Editable? | Token Cost |
|----------|---------------------|----------------|-----------------|------------|
| Conversation buffer | ❌ | ❌ | ❌ | High |
| Summary buffer | Partial | ❌ | ❌ | Medium |
| CLAUDE.md / AGENTS.md | ✅ | ✅ | ✅ | Low (fixed) |
| Memory Bank (Cline) | ✅ | ✅ | ✅ | Medium (6 files) |
| Scratchpad files | ✅ | ✅ | ✅ | Low |
| Session resume | N/A | ✅ | ❌ | Full replay |
| Vector DB (RAG) | ✅ | ✅ | ❌ | Variable |
| Checkpointing | ✅ | ✅ | ❌ | Full state |

### When to Use What

- **Single long session**: Compaction + scratchpad files
- **Multi-session project**: Memory Bank + daily notes
- **Learning from mistakes**: Feedback loops + learned-rules file
- **Large codebase navigation**: Repository maps (Aider-style)
- **Cross-session personalization**: Mem0-style extraction + consolidation

---

## Practical Recommendations for OpenClaw

Based on this research, here are concrete patterns for OpenClaw's file-based architecture:

### 1. Tiered Memory Structure (Already Mostly Exists)

```
workspace/
├── AGENTS.md              # Tier 0: Identity (always loaded)
├── MEMORY.md              # Tier 1: Core memory (always loaded, ~150 lines)
├── TOOLS.md               # Tier 1: Capabilities (always loaded)
├── memory/
│   ├── 2026-02-26.md      # Tier 2: Daily context (loaded on demand)
│   ├── 2026-02-25.md
│   └── ...
└── .scratchpad.md          # Tier 1.5: Working memory (task-specific)
```

### 2. Compaction-Resilient Working State

Add a `.scratchpad.md` or `STATE.md` that the agent updates before compaction:

```markdown
# STATE.md — Current Working State
Last updated: 2026-02-26T00:45:00Z

## Active Task
Research agent memory patterns for compaction resilience

## Plan
1. ✅ Search 15+ sources on agent memory
2. ✅ Read and extract key patterns
3. 🔄 Write findings document
4. ⬜ Apply to OpenClaw architecture

## Key Data
- 13 patterns identified
- File: ~/research/compaction-resilience/findings/agent-memory-patterns.md

## Decisions
- Focus on file-based patterns (not DB-based)
- Use Cline Memory Bank as primary template
```

### 3. Progressive Daily Note Summarization

```
Daily note (L1) → Weekly summary (L2) → Monthly distillation (L3) → MEMORY.md (L4)
```

Implement via a cron job or session-end hook that:
1. At end of day: Extract key points from daily note
2. At end of week: Summarize the week's daily notes
3. At end of month: Distill into MEMORY.md updates

### 4. Learned Rules File

```markdown
# memory/learned-rules.md
# Rules accumulated from human corrections (never auto-deleted)

## Git
- [2026-01-15] Never force push — breaks reviewer history tracking
- [2026-01-20] Always use conventional commits: feat:, fix:, chore:

## Code Style
- [2026-02-01] Use double quotes, not single quotes
- [2026-02-05] Use .js extension for relative imports in TypeScript

## Workflow
- [2026-02-10] Always run tests before pushing
- [2026-02-15] Read ALL review comments before responding
```

### 5. Memory Consolidation Process

Periodically (weekly/monthly), run a consolidation:
1. Scan all daily notes for the period
2. Extract facts, decisions, patterns
3. Deduplicate against existing MEMORY.md entries
4. Update MEMORY.md with new consolidated knowledge
5. Archive old daily notes (keep, but deprioritize)

### 6. Confidence Decay

Not all memories are equal. Consider tagging memory entries:

```markdown
## Active Decisions [permanent]
- Use adapter pattern for backward compat

## Current Context [decays after 30 days]
- Working on EIP-8025 implementation
- PR #8874 in review

## Recent Progress [decays after 7 days]
- Fixed type narrowing in slasher/index.ts
- Addressed Gemini reviewer comments
```

---

## Key Academic Papers

1. **MemGPT: Towards LLMs as Operating Systems** (2023)
   - UC Berkeley. Tiered memory inspired by OS virtual memory.
   - [arxiv.org/abs/2310.08560](https://arxiv.org/abs/2310.08560)

2. **Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory** (2025)
   - Dynamic extraction, consolidation, retrieval. 26% accuracy improvement.
   - [arxiv.org/abs/2504.19413](https://arxiv.org/abs/2504.19413)

3. **Memory Management and Contextual Consistency for Long-Running Low-Code Agents** (2025)
   - Addresses finite context window bottleneck for extended-duration agents.
   - [arxiv.org/pdf/2509.25250](https://arxiv.org/pdf/2509.25250)

4. **Reflexion: Language Agents with Verbal Reinforcement Learning** (2023)
   - Self-reflection and memory reuse across agent turns.
   - [arxiv.org/abs/2303.11366](https://arxiv.org/abs/2303.11366)

5. **Generative Agents: Interactive Simulacra of Human Behavior** (2023)
   - Memory synthesis from collections of past agent feedback.
   - [arxiv.org/abs/2304.03442](https://arxiv.org/abs/2304.03442)

6. **Memory in the Age of AI Agents: A Survey** (2026)
   - Comprehensive paper list: [github.com/Shichun-Liu/Agent-Memory-Paper-List](https://github.com/Shichun-Liu/Agent-Memory-Paper-List)

7. **Zep: A Temporal Knowledge Graph Architecture for Agent Memory** (2025)
   - Graph-based memory with temporal awareness.

---

## Sources

1. [Letta Blog: Agent Memory](https://www.letta.com/blog/agent-memory) — MemGPT/Letta architecture deep dive
2. [LangChain: Context Engineering for Agents](https://rlancemartin.github.io/2025/06/23/context_engineering/) — Lance Martin's categorization (write/select/compress/isolate)
3. [Anthropic: Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — Context as finite resource, attention budget concept
4. [Anthropic: Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system) — Scratchpad and memory persistence patterns
5. [Claude Code Docs: How It Works](https://code.claude.com/docs/en/how-claude-code-works) — Compaction mechanics
6. [Claude Code Docs: Memory](https://code.claude.com/docs/en/memory) — CLAUDE.md hierarchy
7. [Cline Memory Bank Docs](https://docs.cline.bot/features/memory-bank) — Structured Markdown memory
8. [Aider: Repository Map](https://aider.chat/docs/repomap.html) — Tree-sitter based codebase mapping
9. [Codex CLI Features](https://developers.openai.com/codex/cli/features/) — Session resume, AGENTS.md
10. [DEV.to: When Markdown Files Are All You Need](https://dev.to/imaginex/ai-agent-memory-management-when-markdown-files-are-all-you-need-5ekk) — Convergent evolution analysis
11. [Bas Nijholt: File-Based RAG & Memory](https://www.nijho.lt/post/file-based-rag-memory/) — Git-versioned memories without databases
12. [Context Studios: Self-Learning Agent Architecture](https://www.contextstudios.ai/blog/how-to-build-a-self-learning-ai-agent-system-our-actual-architecture) — Feedback loops and learned rules
13. [DEV.to: Persistent Memory Architecture for Claude Code](https://dev.to/suede/the-architecture-of-persistent-memory-for-claude-code-17d) — Two-tier memory with hooks
14. [CrewAI Memory Docs](https://docs.crewai.com/en/concepts/memory) — Multi-layer memory (STM/LTM/Entity)
15. [LangGraph Persistence Docs](https://docs.langchain.com/oss/python/langgraph/persistence) — Checkpointing architecture
16. [Pinecone: LangChain Conversational Memory](https://www.pinecone.io/learn/series/langchain/langchain-conversational-memory/) — Summary buffer memory
17. [Mem0 Paper](https://arxiv.org/abs/2504.19413) — Memory extraction and consolidation
18. [VentureBeat: GAM Dual-Agent Memory](https://venturebeat.com/ai/gam-takes-aim-at-context-rot-a-dual-agent-memory-architecture-that) — Context rot and dual-agent approach
