# Indexing & Retrieval Approaches for AI Agent Memory Systems

**Research date:** 2026-02-28  
**Focus:** Practical implementations for an AI agent personal memory system  
**Context:** We're seeing 42-59% similarity scores returning irrelevant results with pure vector search

---

## Table of Contents
1. [Vector Embeddings for Semantic Search](#1-vector-embeddings-for-semantic-search)
2. [Hybrid Search (Vector + BM25)](#2-hybrid-search-vector--bm25)
3. [Structured Indexes & Metadata](#3-structured-indexes--metadata)
4. [RAG Patterns for Personal Knowledge](#4-rag-patterns-for-personal-knowledge)
5. [Temporal Decay & Recency Weighting](#5-temporal-decay--recency-weighting)
6. [Memory Consolidation Patterns](#6-memory-consolidation-patterns)
7. [Concrete Tools & Libraries](#7-concrete-tools--libraries)
8. [Recommendations for Our System](#8-recommendations-for-our-system)

---

## 1. Vector Embeddings for Semantic Search

### How It Works
Vector databases (LanceDB, Chroma, Pinecone, Qdrant, pgvector) convert text into high-dimensional vectors using embedding models (OpenAI `text-embedding-3-small/large`, `nomic-embed-text`, Sentence Transformers). Retrieval is via approximate nearest neighbors (ANN) using cosine similarity, dot product, or L2 distance.

The typical pipeline:
1. Text → embedding model → 768-3072 dimensional vector
2. Vector stored alongside metadata in the DB
3. Query → same embedding model → query vector
4. ANN search finds top-K most similar stored vectors
5. Return chunks with similarity scores

### Why Low Similarity Scores Return Irrelevant Results

**This is the core problem we're seeing (42-59% match scores with unrelated content).** The reasons are well-documented:

1. **Semantic similarity ≠ relevance.** Embeddings capture *meaning proximity* in a general sense. "Error code 503" and "Error code 404" are semantically very close (both are server error codes) even though you need the exact one. Similarly, "I fixed a libp2p bug" and "I reviewed a networking PR" are semantically close but are completely different events.

2. **No temporal or state awareness.** Vector search treats every stored memory as equally valid. A preference from January ("I prefer Python") has the same weight as a contradicting one from March ("I switched to TypeScript"). The embeddings don't know which is current.

3. **Context pollution.** When your corpus is diverse (daily notes about Ethereum, PR reviews, personal preferences, technical decisions), semantically "vaguely close" chunks from unrelated contexts get returned. A query about "block validation" might pull chunks about "validator key management" because the embedding space puts them near each other.

4. **Embedding collapse in domain-specific text.** General-purpose embedding models compress specialized vocabulary into a smaller region of the embedding space. For a niche domain like Ethereum consensus, many technically distinct concepts (epoch, slot, attestation, beacon block) may cluster together, reducing discrimination between genuinely different topics.

5. **Chunk granularity mismatch.** If chunks are too large, the embedding averages over too much content and becomes generically "about" a topic. If too small, there's insufficient semantic signal. Either way, similarity scores cluster in the 40-60% range — exactly what we see.

### Practical Limits of Pure Vector Search

| Problem | Symptom |
|---------|---------|
| Context pollution | Query about topic A returns chunks from topic B |
| No state tracking | Old/superseded info returned alongside current |
| Token bloat | System prompt balloons with 10+ retrieved chunks |
| Black-box scoring | Can't explain *why* a result was returned |
| No exact match | Can't find "PR #8874" by ID — too short for good embeddings |

**Key insight from the field:** "Vector DBs are NOT memory" (r/AI_Agents). RAG is for static encyclopedic knowledge retrieval. Memory is dynamic state that evolves. Treating vector search as memory leads to the exact problems we're experiencing.

### Vector DB Comparison (for our use case)

| DB | Type | Strengths | Weaknesses |
|----|------|-----------|------------|
| **LanceDB** | Embedded, columnar | Zero-infra, versioned, multimodal, fast on local storage | Smaller ecosystem, newer |
| **Chroma** | Embedded | Simple API, Python-native, good for prototyping | Limited scale, basic metadata filtering |
| **pgvector** | PostgreSQL extension | SQL integration, hybrid search with tsvector, ACID | Slower ANN than specialized DBs |
| **Qdrant** | Standalone | Fast, rich filtering, payload indexing | Requires running a service |
| **Pinecone** | Cloud SaaS | Managed, scales infinitely | Vendor lock-in, cost, latency for small workloads |

**For a personal agent system:** LanceDB or pgvector are the practical choices. LanceDB gives zero-infra embedded operation. pgvector gives SQL power + native BM25 via tsvector.

---

## 2. Hybrid Search (Vector + BM25)

### The Core Idea

Combine two retrieval signals:
- **Vector/dense search:** Captures semantic meaning ("what does this mean?")
- **BM25/sparse search:** Captures exact keyword/term matches ("does this contain the word?")

This directly addresses the weakness of pure vector search for specific identifiers, technical terms, and exact phrases.

### Scoring Formula (Production Pattern)

The most commonly cited formula from production implementations:

```
FinalScore = (VectorSimilarity × α) + (BM25Score × β) + (RecencyScore × γ)
```

Typical weights:
- α = 0.5 (semantic similarity)  
- β = 0.3 (keyword match)  
- γ = 0.2 (recency)

Some implementations use **Reciprocal Rank Fusion (RRF)** instead of weighted sums:
```
RRF_score = Σ 1/(k + rank_i)  for each retrieval system i
```
where k is typically 60. RRF is more robust when score distributions differ between systems.

### Implementation Approaches

**Option A: PostgreSQL-native (pgvector + tsvector)**
```sql
SELECT *,
  (1 - (embedding <=> query_embedding)) * 0.5  -- vector similarity
  + ts_rank(tsv, plainto_tsquery('english', query)) * 0.3  -- BM25
  + EXP(-0.1 * EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400) * 0.2  -- recency decay
  AS score
FROM memories
WHERE tsv @@ plainto_tsquery('english', query)
   OR (embedding <=> query_embedding) < 0.6
ORDER BY score DESC
LIMIT 10;
```

**Option B: LanceDB with full-text search**
LanceDB supports hybrid search natively since v0.4+:
```python
results = table.search(query, query_type="hybrid")
  .limit(10)
  .to_list()
```

**Option C: Two-stage with reranking**
1. BM25 retrieves top-1000 candidates (fast, cheap)
2. Vector similarity + cross-encoder reranks top-K
3. This is Bergum's pattern — combines economic efficiency with semantic sophistication

### Does Hybrid Search Actually Help?

**Yes, significantly** — especially for:
- Technical/code-based queries where exact terms matter (PR numbers, error codes, function names)
- Queries mixing natural language + identifiers ("the libp2p identify bug from PR #8890")
- Cases where semantic similarity alone returns "vaguely related" noise

**Evidence from practitioners:**
- MemVault author: After adding BM25, exact-match queries that previously returned wrong results (e.g., "Error Code 503" returning "404" results) started working correctly
- Reddit r/Rag consensus: "If your system is QA/technical/code-based, BM25 provides better results. For enterprise/business questions, lean toward semantic."
- The memory-lancedb-pro OpenClaw plugin specifically built hybrid retrieval to fix the "remembering the right things" problem

### When Vector-Only Is Still Fine
- Broad semantic queries ("what do I know about networking?")
- Discovery/exploration ("find memories related to fork choice")
- When the corpus is small and homogeneous

---

## 3. Structured Indexes & Metadata

### Why Metadata Matters

Vector search is a **soft filter** — it finds "kind of related" things. Metadata provides **hard filters** — exact constraints that eliminate irrelevant results before similarity scoring even begins.

### Essential Metadata Fields for Agent Memory

```json
{
  "id": "mem_20260228_001",
  "text": "Reviewed PR #8890 — libp2p v3 migration, found race condition in stream handling",
  "embedding": [0.12, -0.45, ...],
  "category": "pr-review",
  "project": "lodestar",
  "importance": 0.8,
  "created_at": "2026-02-28T14:30:00Z",
  "updated_at": "2026-02-28T14:30:00Z",
  "valid_from": "2026-02-28T14:30:00Z",
  "valid_until": null,
  "source": "daily-note",
  "tags": ["libp2p", "pr-review", "networking"],
  "access_count": 3,
  "last_accessed": "2026-02-28T20:00:00Z",
  "supersedes": null,
  "superseded_by": null,
  "status": "active"
}
```

### Tag-Based Lookup Index

For fast exact-match retrieval without vector search:

```
Tag Index (inverted):
  "libp2p"      → [mem_001, mem_045, mem_089]
  "pr-review"   → [mem_001, mem_023, mem_067]
  "PR#8890"     → [mem_001]
  "fork-choice"  → [mem_012, mem_034]
```

This enables:
- Instant lookup: "What do I know about PR #8890?" → direct tag match, no vector needed
- Filtered search: "Semantic search for 'networking issues' BUT only in category=investigation"
- Aggregation: "How many PR reviews did I do this month?" → metadata query only

### Temporal Validity Modeling

The `valid_from` / `valid_until` pattern (from Tiger Data's approach) solves the state-tracking problem:

```sql
-- Only retrieve currently valid memories
WHERE valid_from <= NOW() AND (valid_until IS NULL OR valid_until > NOW())
```

When a preference changes:
1. Set `valid_until = NOW()` on the old memory
2. Create new memory with `valid_from = NOW()`, `supersedes = old_memory_id`

This preserves history while ensuring queries always get the current state.

### Pre-filtered Vector Search

The most effective pattern combines metadata filters with vector search:

```
1. Apply hard filters: category, project, date range, status=active
2. Within filtered set, run vector similarity
3. Rerank by composite score (similarity + recency + importance)
```

This dramatically reduces false positives because the vector search only operates on a relevant subset.

---

## 4. RAG Patterns for Personal Knowledge

### Chunking for Agent Memory (Not Documents)

Agent memory is fundamentally different from document RAG:
- Memories are already discrete units (conversations, decisions, events)
- They have natural boundaries (daily notes, individual interactions)
- They are shorter than documents (typically 50-500 tokens each)

**Recommendation for memory chunks:**

| Memory Type | Chunk Strategy | Size |
|-------------|---------------|------|
| Individual facts/preferences | One memory = one chunk | 20-100 tokens |
| Daily notes | Split by section/heading | 100-300 tokens |
| Investigation logs | Split by finding/step | 200-500 tokens |
| PR review summaries | One review = one chunk | 100-400 tokens |
| Conversation summaries | One conversation = one chunk | 200-500 tokens |

**Key insight:** For personal knowledge bases, the consensus best practice is 256-512 tokens per chunk with 10-20% overlap. But for discrete memories (facts, preferences, decisions), **each memory should be its own chunk** — no splitting needed.

### Metadata Enrichment at Ingestion

Every chunk should be enriched at write time:

1. **Auto-tagging:** LLM extracts entities, topics, project names from the text
2. **Importance scoring:** LLM rates 1-10 on the Park et al. scale:
   - 1 = mundane ("brushing teeth")
   - 5 = moderately important ("started a new feature branch")  
   - 10 = critical ("merged major PR", "production incident")
3. **Category classification:** LLM assigns category from fixed enum
4. **Temporal extraction:** Parse any dates/times mentioned in the text
5. **Relationship extraction:** Identify links to other memories (e.g., "this follows up on investigation X")

### Retrieval Strategy: Multi-Stage Pipeline

```
Query → [Stage 1: Route] → [Stage 2: Retrieve] → [Stage 3: Rerank] → [Stage 4: Inject]

Stage 1 - Route:
  - Is this an exact-match query? (PR number, specific date) → Tag index
  - Is this a broad semantic query? → Hybrid search
  - Is this a temporal query? ("last week") → Date filter + hybrid search

Stage 2 - Retrieve:
  - Apply metadata filters (category, project, date range, status=active)
  - Run hybrid search (vector + BM25) on filtered set
  - Fetch top-20 candidates

Stage 3 - Rerank:
  - Cross-encoder reranking (e.g., ms-marco-MiniLM or Cohere rerank)
  - Apply temporal decay weighting
  - Apply importance weighting
  - Return top-5

Stage 4 - Inject:
  - Format memories with context (date, source, importance)
  - Total token budget: ~1000-2000 tokens for memory context
  - Most recent/important first
```

### The "Reflect" Pattern (Session-End Learning)

Increasingly standard practice for personal agents:

1. At the end of a session/conversation, the agent reviews what happened
2. Extracts key facts, decisions, preferences, and lessons learned
3. Consolidates these into structured memories
4. Stores with proper metadata and embeddings

This is more effective than storing raw conversation chunks because:
- Information is pre-distilled (smaller, more focused)
- Duplicates are caught at write time
- Categories and importance are assigned with full context

---

## 5. Temporal Decay & Recency Weighting

### The Park et al. Model (Generative Agents, 2023)

The foundational work on memory scoring for AI agents. Three signals, normalized to [0,1] and combined:

```
RetrievalScore = α × Recency + β × Importance + γ × Relevance
```

Where:
- **Recency:** Exponential decay based on time since creation
  - `recency = decay_factor ^ hours_since_creation`
  - Typical decay_factor: 0.995 per hour (≈ 0.887 after 24h, 0.028 after 14 days)
- **Importance:** LLM-rated 1-10, normalized to [0,1]
  - "Brushing teeth" → 1, "Getting a divorce" → 10
- **Relevance:** Cosine similarity between query embedding and memory embedding

Typical weights: α=1, β=1, γ=1 (equal weighting) — but tunable.

### Improved Decay Functions

The simple exponential decay has a problem: important old memories fade too fast.

**Intelligent Decay (arXiv:2509.25250):**
```
utility(m) = α × recency(m) + β × relevance(m) + γ × importance(m)
```
with different decay curves for different memory types:
- Facts/preferences: Very slow decay (months-years)
- Episodic events: Moderate decay (days-weeks)
- Procedural/task context: Fast decay (hours-days)

**MemoryBank approach (Zhong et al., 2024):**
Uses Ebbinghaus forgetting curve theory — memories that are accessed more frequently decay slower (spaced repetition for AI agents).

```
retention(m) = e^(-t/S)
where S = stability (increases with each access)
```

### Practical Implementation

```python
import math
from datetime import datetime, timedelta

def compute_memory_score(
    memory,
    query_embedding,
    now: datetime,
    alpha: float = 0.3,   # recency weight
    beta: float = 0.3,    # importance weight  
    gamma: float = 0.4,   # relevance weight
    decay_rate: float = 0.1,  # per-day decay
):
    # Recency: exponential decay
    days_old = (now - memory.created_at).total_seconds() / 86400
    recency = math.exp(-decay_rate * days_old)
    
    # Importance: pre-assigned 0-1
    importance = memory.importance
    
    # Relevance: cosine similarity
    relevance = cosine_similarity(query_embedding, memory.embedding)
    
    # Access boost: memories accessed more often decay slower
    access_boost = min(memory.access_count * 0.05, 0.3)  # cap at 0.3
    
    # Category-specific decay adjustment
    if memory.category in ('preference', 'fact'):
        recency = max(recency, 0.5)  # facts don't fully decay
    
    return alpha * (recency + access_boost) + beta * importance + gamma * relevance
```

### Key Design Decisions

1. **Facts and preferences should not fully decay.** "Nico is the boss" is still true regardless of age. Use a floor value.
2. **Episodic memories should decay.** "Had a good debugging session" is less relevant after 2 weeks.
3. **Access count matters.** Frequently retrieved memories are probably important — boost them.
4. **Override decay for high-importance items.** A memory rated importance=0.9+ should resist decay.

---

## 6. Memory Consolidation Patterns

### The Problem

Without consolidation, memory stores grow unboundedly and accumulate:
- **Duplicates:** Same fact stated differently in multiple sessions
- **Contradictions:** "Prefers Python" (January) vs "Switched to TypeScript" (March)
- **Redundancy:** 10 daily notes all mentioning the same ongoing project
- **Stale info:** Completed tasks still marked as active

### Memory Lifecycle (MemOS Pattern)

```
Generated → Activated → Merged → Archived → [Deleted]

Generated:  New memory extracted from interaction
Activated:  Memory passes importance threshold, indexed for retrieval
Merged:     Related memories consolidated into unified entry
Archived:   Memory decayed below threshold, removed from active index
Deleted:    Permanently removed (rare, manual, or GDPR)
```

### Consolidation Techniques

#### A. Deduplication
At write time, check if a semantically similar memory already exists:
```
1. Embed new memory
2. Search existing memories with high similarity threshold (>0.9 cosine)
3. If match found:
   a. If same fact → skip or update timestamp
   b. If updated version → mark old as superseded, store new
   c. If contradiction → store new with supersedes link, deprecate old
```

#### B. Merging/Summarization
Periodically merge related memories into consolidated entries:
```
Input memories:
  - "Reviewed PR #8890 - found race condition" (Feb 19)
  - "PR #8890 merged after fixing stream handler" (Feb 22)
  - "Discussed libp2p v3 migration in team meeting" (Feb 24)

Consolidated memory:
  "Contributed to PR #8890 (libp2p v3 migration): identified race condition
   in stream handler, which was fixed and merged Feb 22. Discussed in team 
   meeting Feb 24."
  Tags: [libp2p, pr-review, networking, PR#8890]
  Importance: 0.7 (composite)
  Date range: Feb 19-24
```

#### C. Promotion/Demotion
- **Promotion:** If a pattern appears across multiple episodic memories, extract it as a persistent semantic fact. "I've reviewed 5 libp2p PRs this month" → fact: "Actively working on libp2p migration (Feb 2026)"
- **Demotion:** If a fact hasn't been accessed in N days and has low importance, archive it.

#### D. The "Sleep Cycle" Pattern
Inspired by human memory consolidation during sleep. Run periodically (e.g., daily or every 6 hours):

1. **Retrieve all active memories** from the past consolidation period
2. **Cluster by topic/project** using embeddings or tags
3. **Within each cluster:**
   - Merge near-duplicates
   - Resolve contradictions (most recent wins)
   - Extract cross-cutting facts
   - Summarize episodic sequences into consolidated events
4. **Update the store:**
   - Write consolidated memories
   - Archive or deprecate source memories
   - Update supersedes/superseded_by links

#### E. AWS AgentCore Consolidation Pipeline
From the AWS deep dive, their production system:
1. For each new memory, retrieve top-K similar existing memories
2. Use an LLM to compare and decide: **add** (new info), **update** (refine existing), **merge** (combine), or **skip** (duplicate)
3. Recognize cross-temporal relationships ("allergic to shellfish" in Jan + "can't eat shrimp" in Mar → same fact)
4. Respect temporal ordering — newer info takes precedence for preferences

### Implementation Considerations

- **Cost:** Consolidation requires LLM calls. Budget ~$0.002-0.01 per memory per consolidation cycle.
- **Frequency:** Daily is practical for personal agents. More frequent for high-traffic systems.
- **Conflict resolution:** "Recency wins" is the simplest and most common strategy.
- **Audit trail:** Keep supersedes links so you can trace why a memory was changed.

---

## 7. Concrete Tools & Libraries

### Dedicated Memory Frameworks

#### Mem0 (mem0ai/mem0)
- **What:** Universal memory layer for AI agents. Most popular, AWS partnership.
- **How:** LLM-powered extraction + update pipeline. Graph-based memory (Mem0g) for relational structures.
- **Backend:** Supports 24+ vector DBs (Qdrant, Chroma, pgvector, Pinecone, etc.)
- **Performance:** 26% accuracy boost, 91% lower p95 latency vs baselines
- **Catch:** Requires an LLM for operation (default: gpt-4.1-nano). Adds cost and latency.
- **Best for:** Production systems needing multi-user memory with automatic extraction/consolidation.
- **GitHub:** github.com/mem0ai/mem0 (40K+ stars)

#### Letta (formerly MemGPT)
- **What:** Stateful agent platform. Agents manage their own memory via tools.
- **How:** OS-like memory model — "core memory" (always in context, like RAM) + "archival memory" (searchable, like disk). Agent actively decides what to remember/forget.
- **Key finding:** Their LoCoMo benchmark shows a plain filesystem scores 74% — beating specialized vector-store libraries. Simplicity often wins.
- **Best for:** Agents that need to self-manage memory with full autonomy.
- **GitHub:** github.com/letta-ai/letta (18K+ stars)

#### Zep / Graphiti
- **What:** Graph-based memory + temporal knowledge graphs.
- **Graphiti:** Open-source library for building temporally-aware context graphs from chat history. Tracks how facts change over time using a knowledge graph structure.
- **How:** Extracts entities and relationships from conversations, builds a Neo4j-backed graph with temporal edges.
- **Best for:** Complex relational memory where you need to trace how knowledge evolves.
- **GitHub:** github.com/getzep/graphiti

#### Cognee
- **What:** Memory infrastructure using knowledge graphs + vector retrieval.
- **How:** Cognitive architecture inspired — processes information through a pipeline that extracts, classifies, and connects knowledge.
- **Best for:** Systems needing deep semantic understanding of interconnected information.

### Vector Databases with Memory-Relevant Features

#### LanceDB
- Embedded (no server needed), columnar storage
- Native hybrid search (vector + full-text) since v0.4
- Versioned tables — can snapshot and roll back memory state
- `memory-lancedb-pro` OpenClaw plugin: Hybrid retrieval + cross-encoder reranking + scope isolation
- **Best for:** Local/embedded agent memory with zero infrastructure

#### pgvector (PostgreSQL)
- Adds vector similarity to PostgreSQL
- Combine with native `tsvector` for BM25 keyword search
- ACID transactions, rich SQL for metadata queries
- The "obvious choice" if you already use PostgreSQL
- **Best for:** Systems needing SQL power + hybrid search + transactional guarantees

#### Chroma
- Simple Python-native embedded DB
- Good for prototyping, easy API
- Limited hybrid search — no native BM25, needs external BM25 implementation
- **Best for:** Quick experimentation, small-scale systems

### Embedding Models

| Model | Dimensions | Speed | Quality | Cost |
|-------|-----------|-------|---------|------|
| OpenAI `text-embedding-3-small` | 1536 | Fast | Good | $0.02/1M tokens |
| OpenAI `text-embedding-3-large` | 3072 | Fast | Best (OpenAI) | $0.13/1M tokens |
| `nomic-embed-text` (local) | 768 | Medium | Good | Free |
| `all-MiniLM-L6-v2` (local) | 384 | Very fast | Adequate | Free |
| Cohere `embed-v4` | 1024 | Fast | Excellent | $0.1/1M tokens |

**For personal agent use:** `nomic-embed-text` via Ollama (local, free, good quality) or OpenAI `text-embedding-3-small` (cheap, high quality, requires API).

### Reranking Models

Cross-encoder reranking dramatically improves retrieval quality by re-scoring candidates with a model that sees both query and document together:

- **Cohere Rerank v3:** Best quality, API-based
- **ms-marco-MiniLM-L-12-v2:** Open source, fast, runs locally
- **bge-reranker-v2-m3:** Multilingual, open source

### Other Notable Tools

- **LangChain LangMem:** Memory management toolkit for LangChain agents (extraction, consolidation, search)
- **MemVault:** Open-source GraphRAG platform with hybrid search, "sleep cycle" consolidation, visual dashboard
- **AgentKits Memory:** SQLite + WASM local memory for coding agents (Claude Code, Cursor, etc.)
- **Recallium:** Self-hosted memory layer via MCP protocol
- **AI Memory SDK:** Lightweight memory primitives for any agent framework

---

## 8. Recommendations for Our System

### Diagnosis of Current Problems

Our current system uses OpenClaw's built-in `memory_store`/`memory_recall` with what appears to be basic vector search. The 42-59% similarity scores returning irrelevant content indicate:

1. **Pure vector search** without keyword/metadata filtering
2. **No category separation** — all memory types in one namespace
3. **No temporal awareness** — old and new memories weighted equally
4. **No consolidation** — duplicates and contradictions accumulate
5. **Generic embeddings** not optimized for our domain

### Proposed Architecture (Incremental)

#### Phase 1: Quick Wins (File-based improvements)
Since Letta's research shows a plain filesystem scores 74% on memory benchmarks, start by improving our file-based memory:

- **Structure daily notes** with consistent headings and tags
- **Add a lookup index** file (`memory/index.json`) mapping topics/tags → file locations
- **Split MEMORY.md** into typed sections: facts, preferences, decisions, active-context
- **Add valid_from/valid_until** markers to facts that can change
- **Daily consolidation** during heartbeat: review recent notes, update MEMORY.md, archive stale entries

#### Phase 2: Hybrid Search Layer
If/when moving beyond file-based memory:

- **Use pgvector or LanceDB** as the vector store
- **Add BM25 keyword search** alongside vector similarity
- **Implement composite scoring:** `0.4 × relevance + 0.3 × keyword_match + 0.2 × recency + 0.1 × importance`
- **Pre-filter by metadata** (category, project, date range) before vector search
- **Use a cross-encoder reranker** on the top-20 candidates

#### Phase 3: Full Memory Management
- **Automatic extraction** from conversations using LLM
- **Consolidation pipeline** (daily "sleep cycle")
- **Temporal validity tracking** with supersedes chains
- **Importance scoring** with access-count boosting
- **Memory lifecycle management** (active → archived → pruned)

### Key Principles

1. **Metadata filtering > vector search alone.** Pre-filtering by category/project/date eliminates most noise.
2. **Hybrid search is table stakes.** Any production memory system needs vector + keyword + temporal signals.
3. **Consolidation is not optional.** Without it, memory quality degrades over time.
4. **Simplicity wins.** Start with structured files + good indexing before reaching for complex infra.
5. **Write-time enrichment is cheaper than read-time inference.** Invest in tagging and scoring at memory creation time.

---

## Sources & Further Reading

- Park et al. (2023). "Generative Agents: Interactive Simulacra of Human Behavior." UIST 2023.
- Packer et al. (2024). "MemGPT: Towards LLMs as Operating Systems." arXiv:2310.08560.
- Mem0 paper: "Building Production-Ready AI Agents with Scalable Long-Term Memory." arXiv:2504.19413.
- "Memory in the Age of AI Agents" survey. arXiv:2512.13564 (Dec 2025).
- "Forgetful but Faithful: A Cognitive Memory Architecture." arXiv:2512.12856.
- "Memory Management for Long-Running Low-Code Agents" (Intelligent Decay). arXiv:2509.25250.
- Letta benchmark: "Is a Filesystem All You Need?" — letta.com/blog/benchmarking-ai-agent-memory
- memory-lancedb-pro (OpenClaw plugin): github.com/win4r/memory-lancedb-pro
- MemVault hybrid search implementation: dev.to (jakops88)
- AWS AgentCore Memory deep dive: aws.amazon.com/blogs/machine-learning
- Comprehensive memory architecture gist: gist.github.com/spikelab/7551c6368e23caa06a4056350f6b2db3
