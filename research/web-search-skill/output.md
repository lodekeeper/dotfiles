# Research: Comprehensive Web Search Skill (Beyond Brave)

**Date:** 2026-03-06  
**Requested by:** Nico  
**Status:** Final synthesis after adversarial critique  
**Confidence:** Medium-High (architecture direction), Medium (cost/ops estimates pending benchmark)

## Executive Summary
A single search API (including Brave alone) is not enough for reliable “answer arbitrary internet question” behavior. The highest-leverage improvement is a **router + multi-provider orchestration skill** that:

1. Classifies query intent (general/code/academic/ethereum/etc.)
2. Routes to the best provider mix per intent
3. Executes bounded parallel retrieval with strict deadlines
4. Deduplicates/reranks across sources
5. Optionally performs deep fetch + synthesis with explicit citations

After adversarial review, the key correction is: **build reliability-first, not capability-first.**
Do not launch with a wide 10+ provider surface. Start with a small, stable core and expand based on measured marginal quality gain.

---

## 1) Problem Definition (Scoped, Measurable)

### MVP scope (in)
- Technical and research queries across:
  - general web
  - code/Q&A
  - Ethereum R&D/protocol
  - basic academic lookups

### Out of scope (v1)
- Full social-media firehose coverage
- Heavy scraping of unofficial endpoints as critical dependencies
- Always-on long-form synthesis for every query

### Success criteria (MVP)
- **Availability:** >=99% query completion with at least one citation
- **Latency:** p95 < 2.5s (fast mode), p95 < 8s (deep mode)
- **Citation integrity:** >=95% of answer claims mapped to at least one source snippet
- **Cost guardrail:** per-query hard cap + monthly budget governor

---

## 2) Evidence-Based Provider Strategy

## Tier A (must-have, stable for MVP)
1. **General primary:** Brave paid *or* self-hosted SearxNG backbone
2. **General fallback:** secondary general provider (Serper or DDG best-effort)
3. **Code source:** GitHub Code Search (official)
4. **Ethereum source:** ethresear.ch + Ethereum Magicians (Discourse JSON)

## Tier B (add after MVP metrics pass)
- Semantic Scholar / arXiv
- Stack Exchange
- Wikipedia
- HN Algolia

## Tier C (experimental / non-critical)
- Unofficial or brittle providers (e.g., wrappers without SLA)
- Keep disabled by default in production

### Why this split
Adversarial critique surfaced that broad provider fanout raises failure surface faster than reliability unless tightly constrained. Tiering gives controlled expansion and easier ops.

---

## 3) Query Routing Model

Use **multi-label routing**, not single-label classification.

Example:
- Query: “How does PeerDAS verification work in Lodestar?”
- Labels: `ethereum + code + academic`
- Route: Ethereum forums + GitHub code search + optional academic source

### Routing safeguards
- Always include one general safety-net provider
- If classifier confidence is low -> cheap broad fanout first, then refine
- Log route decisions and compute route regret (did excluded providers have better hits?)

---

## 4) Reliability Architecture (Required)

### Execution modes
- **Fast mode (default):** narrow fanout, no deep fetch, short deadline
- **Balanced mode:** moderate fanout + rerank
- **Research mode:** broader fanout + deep fetch + synthesis

### Hard budgets
- Per-provider timeout: 5-8s max
- End-to-end deadline propagation by mode
- Cancel low-value calls near deadline

### Resilience controls
- Circuit breakers + adaptive concurrency limits
- Token buckets per provider
- Degradation ladder:
  1. full synthesis
  2. retrieval-only ranked citations
  3. cached results only
  4. explicit bounded failure message

### Observability/SLOs
Track by provider and mode:
- success rate
- timeout rate
- breaker-open percentage
- p50/p95 latency
- cost/query
- citation coverage

---

## 5) Security & Compliance Controls (Non-negotiable)

## Security
- SSRF protections for deep fetch (block localhost/private/link-local ranges)
- strict content-type/size/time limits
- sandbox extraction workers
- prompt-injection hardening before synthesis (strip instructions from fetched text)

## Citation integrity
- Every synthesized claim must map to URL + extracted snippet span
- If grounding insufficient: output retrieval-only response (no speculative synthesis)

## Compliance
- Provider registry field: `official_api | unofficial_scrape | restricted`
- Unofficial sources cannot be sole dependency for critical paths
- Log retention/redaction policy for sensitive queries

---

## 6) Workload-Based Cost Model

Let:
- `Q` = queries/day
- `F` = avg provider fanout/query
- `R` = retry multiplier
- `D` = deep-fetch pages/query
- `S` = synthesis token cost/query

Then:

`cost/query ~= provider_api_cost(F * R) + fetch_cost(D) + synthesis_cost(S)`

`monthly_cost ~= cost/query * Q * 30 + infra_cost + ops_overhead`

### Practical planning bands
- **Free-first:** viable if SearxNG is hosted and deep mode is constrained
- **Low-cost (~$10-20/mo):** add Brave paid for QPS stability
- **Higher scale:** introduce additional paid providers only when benchmark proves marginal gain

**Important:** earlier optimistic fixed-dollar estimates are placeholders until benchmark data is collected.

---

## 7) Benchmark Protocol (Before Full Rollout)

Build a fixed query set (100-300 real queries) across domains.

Evaluate:
1. retrieval recall@k
2. citation precision
3. answer usefulness (human or rubric)
4. latency distribution by mode
5. cost/query distribution

Compare:
- single-provider baseline
- constrained multi-provider MVP
- expanded provider set

Promote a provider only if quality gain justifies latency/cost/maintenance overhead.

---

## 8) Recommended Build Plan

## Phase 1 — Reliability-first MVP
- Implement core orchestrator
- Enable Tier A providers only
- Fast mode default
- Retrieval-first output + citations

## Phase 2 — Controlled depth
- Add deep fetch with SSRF/sandbox controls
- Add synthesis gated by confidence/citation sufficiency
- Add Tier B providers incrementally

## Phase 3 — Optimization
- Route quality analytics (regret tracking)
- Better reranking calibration
- Adaptive cost/performance tuning

---

## 9) Immediate Decisions Needed

1. **Backbone choice now:** Brave paid first vs SearxNG-first deployment
2. **Default response policy:** retrieval-first by default, synthesis optional/gated
3. **Compliance posture:** whether unofficial providers allowed in production at all
4. **Benchmark gate:** required thresholds before expanding provider surface

---

## 10) Concrete Next Actions

1. Scaffold `skills/web-search/` with Tier A providers only
2. Add routing + timeout + fallback + citations (no deep fetch yet)
3. Implement minimal metrics (latency/success/cost/citations)
4. Run benchmark set and produce pass/fail report
5. Expand only where measured gain is clear

---

## Source Artifacts
- `findings/search-engine-apis.md`
- `findings/self-hosted-search.md`
- `findings/specialized-sources.md`
- `findings/tradeoff-analysis.md`
- `findings/skill-architecture.md`
- `drafts/v1.md`
- `drafts/critique-sonnet.md`
- `drafts/critique-opus.md`
