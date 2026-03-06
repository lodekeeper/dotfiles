# Research: Memory Management & Indexing Improvements for Lodekeeper

**Date:** 2026-02-28  
**Requested by:** Nico  
**Confidence:** High  
**Sources used:** OpenClaw internal memory research doc, web survey (Felix/Letta/community systems), indexing survey (hybrid retrieval literature/practice), local system audit

## Executive Summary
Your instinct is correct: the current system is usable but suboptimal for lookup quality and long-term retrieval hygiene.

The main issue is that we currently rely on a mix of flat files + a vector memory store where retrieval appears effectively vector-first. That causes noisy recall (we saw low-confidence matches returning irrelevant memories), no temporal validity model, and no robust entity/project lookup.

The recommended path is **not** a full graph DB rewrite. Best approach is an **offline-first hybrid architecture**:
1. Keep Markdown as source of truth.
2. Add structured memory bank files (typed + entity-centric).
3. Build a derived local index (SQLite FTS + metadata, optional vectors/hybrid later).
4. Add nightly "retain/reflect" consolidation and dedup.

This gives immediate gains in lookup quality while staying transparent, auditable, and easy to iterate.

## Findings

### 1) What works in top agent setups
- **Felix (Nat Eliason):** 3-layer memory (knowledge base + daily logs + tacit rules) with nightly consolidation.
- **Letta/MemGPT direction:** Separate short-term/core from long-term stores; use "sleep-time" consolidation agent.
- **OpenClaw internal research:** Recommends exactly this pattern for workspace memory: Markdown canonical + rebuildable structured index.

### 2) Why current recall quality degrades
- Pure semantic similarity often returns "topic-adjacent" but wrong memories.
- No strong metadata gating (project/type/time/status).
- No validity tracking (old/superseded facts can still rank high).
- No regular dedup + contradiction resolution.

### 3) Practical consensus from research
- For personal agent memory, **hybrid retrieval** (keyword + semantic + recency/importance) outperforms vector-only.
- **Structured file systems + good indexing** often beat overengineered memory stacks.
- Consolidation/cleanup is mandatory; memory quality decays without it.

## Recommended Architecture

## A. Canonical memory (human/audit layer)
Keep markdown as source-of-truth:

```
~/.openclaw/workspace/
  MEMORY.md                        # compact core memory (always-load subset)
  memory/
    YYYY-MM-DD.md                  # daily raw logs
  bank/
    facts.md                       # durable world/user/project facts
    decisions.md                   # explicit decisions + rationale
    preferences.md                 # user/assistant prefs w/ confidence
    lessons.md                     # durable lessons
    entities/
      people/
        nico.md
      projects/
        lodestar.md
        eip-7782.md
      prs/
        pr-8968.md
```

## B. Derived index (machine retrieval layer)
Add local rebuildable index:

```
~/.openclaw/workspace/.memory/index.sqlite
```

Tables (minimum):
- memories(id, text, type, source_path, source_line, created_at, valid_from, valid_until, importance, status)
- tags(memory_id, tag)
- entities(memory_id, entity_type, entity_slug)
- fts(memories.text)

Optional later:
- vectors (LanceDB/pgvector sidecar)
- reranker stage

## C. Retrieval strategy
1. Route query type:
   - Exact id/entity query (e.g. PR #8968) → tag/entity lookup first.
   - Broad semantic query → hybrid retrieval.
2. Pre-filter by metadata (project/type/time/status).
3. Rank with composite score:
   - keyword/BM25
   - semantic similarity (optional in phase 2)
   - recency
   - importance
4. Return top 3-7 with citations (file + line/date).

## D. Consolidation pipeline (nightly)
Nightly cron job should:
1. Read recent daily notes.
2. Extract retainable memories into typed entries.
3. Deduplicate near-duplicates.
4. Resolve contradictions by recency + confidence rules.
5. Update `bank/*` and entity pages.
6. Rebuild index.
7. Produce a short consolidation report.

## MVP Rollout Plan

### Phase 1 (1-2 sessions)
- Create `bank/` structure.
- Start entity pages for people/projects/PRs.
- Add nightly consolidation cron (rule-based + lightweight extraction).
- Build SQLite FTS index from markdown with metadata/tags.

### Phase 2
- Add query router + ranked retrieval helper.
- Add validity fields (`valid_from`, `valid_until`, supersedes links).
- Add confidence/importance scoring.

### Phase 3
- Optional semantic layer (LanceDB or pgvector hybrid search).
- Optional reranking and "sleep-time" dedicated consolidation agent.

## Why this is the right fit
- Offline/local-first
- Transparent + git-auditable
- Incremental and reversible
- Better exact lookup + better long-term consistency
- No heavy infrastructure required to get strong improvements

## Open Questions
1. Should we keep OpenClaw `memory_store/recall` as-is for lightweight preferences while moving primary retrieval to local index?
2. Preferred consolidation cadence: nightly only vs nightly + lightweight heartbeat pass?
3. Do you want PR-level entity pages auto-generated for every PR touched, or only high-importance PRs?
