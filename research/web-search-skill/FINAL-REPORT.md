# Research Report: Comprehensive Web Search Skill for OpenClaw

**Date:** 2026-03-06
**Requested by:** Nico
**Duration:** ~2.5 hours
**Models used:** Claude Opus 4.6 (orchestration/synthesis), Claude Sonnet 4.6 (5 sub-agents + adversarial review)
**Confidence:** MEDIUM-HIGH (landscape survey is solid; some API sunset claims need verification)

---

## Executive Summary

We researched building a comprehensive web search skill that goes beyond our current Brave Search to find answers to arbitrary questions. Surveyed 14+ search engine APIs, 6 self-hosted solutions, 20+ specialized sources. Produced a complete architecture and built the skill.

**Key finding:** A multi-source search with query routing, parallel execution, and LLM synthesis is a genuine capability improvement. The MVP needs just 3 providers (Brave + DuckDuckGo + domain-specific routing) and can be built today at zero additional cost.

**Architecture:** `search.py` — single-file entry with provider modules. Query → classify → route → parallel search → deduplicate → rank (RRF) → optionally synthesize with citations.

**Cost:** $0/month for MVP. SearxNG self-hosted is a Phase 2 upgrade if we hit Brave rate limits (realistic: ~$0-15/month including Brave paid tier if needed).

---

## Corrections After Adversarial Review

The initial draft contained claims that need caveats:

1. **"Google CSE sunsetting Jan 2027"** — ⚠️ No credible source found for this. Google CSE may continue operating. Treat as uncertain, don't rely on this claim. Google CSE's real limitations (100/day free, $5/1K) still make it unattractive regardless.

2. **"Bing API is dead"** — ⚠️ Azure Bing Web Search v7 may still be purchasable through Azure Marketplace. The old developer portal was retired, but Azure access may persist. Worth investigating if we need Microsoft's index.

3. **SearxNG "unlimited free Google results"** — ⚠️ Google actively blocks SearxNG instances. ~60% of public instances have disabled Google. On a production server IP, Google results degrade to Bing+DDG quality within days-weeks. SearxNG is useful but not the "free Google" it's sometimes marketed as.

4. **DuckDuckGo reliability** — ⚠️ The `duckduckgo-search` library is unofficial and has triggered IP bans. Fine as an opportunistic fallback, not a load-bearing provider.

5. **"$0/month"** — API costs can be $0, but operational costs exist: SearxNG RAM (~2-3GB), maintenance (2-4 hrs/month), IP reputation risk, LLM synthesis tokens (~$5-10/month if used frequently).

---

## Search Landscape (2026)

### General Web Search APIs

| API | Free Tier | Paid (per 1K) | Quality | Status | Recommendation |
|-----|-----------|---------------|---------|--------|----------------|
| **Brave** | 1.7K/mo | $3 | Good (own 30B index) | ✅ Active | **Primary** — already integrated |
| **Serper** | 2.5K one-time | $0.30-2 | Excellent (Google) | ✅ Active | **Fallback** — cheapest Google access |
| **DuckDuckGo** | Unlimited* | Free | Adequate (Bing index) | ⚠️ Unofficial | **Opportunistic fallback** only |
| **Exa** | 1K/mo | $7-12 | Good (semantic) | ✅ Active | **Phase 2** — semantic/similar search |
| **Tavily** | 1K/mo | $4-8 | Good (AI-tuned) | ✅ Active | **Phase 2** — AI agent focused |
| **Perplexity** | 50 RPM | $5 | Good (AI answers) | ✅ Active | **Phase 2** — quick answers |
| **SearxNG** | Free (self-hosted) | $0 | Good (multi-engine†) | ✅ Active | **Phase 2** — if rate limits bite |
| Google CSE | 100/day | $5 | Excellent | ⚠️ Uncertain future | Skip |
| Bing (Azure) | Unknown | ~$3-7 | Good | ⚠️ Unclear availability | Skip for now |
| Kagi | None | $25+sub | Excellent | ✅ Active | Too expensive for programmatic use |

*Unofficial library, can break. †Degrades when Google blocks the instance.

### Specialized Sources (All Free)

| Source | Domain | Auth | Rate Limit | Unique Value |
|--------|--------|------|-----------|--------------|
| **HN Algolia** | Tech discussions | None | 10K/hr | Community sentiment, tech discourse |
| **GitHub Code Search** | Code | PAT | 10/min | All public repos |
| **Semantic Scholar** | Academic (214M papers) | Optional key | 100/sec (keyed) | Papers, citations |
| **arXiv** | CS/ML preprints | None | 1 req/3s | Latest research |
| **Stack Exchange** | Q&A | Free key | 10K/day (keyed) | Programming Q&A |
| **Wikipedia** | Factual knowledge | None | ~200/sec | Encyclopedia |
| **Bluesky** | Social/tech | None | Generous | Growing tech community |
| **ethresear.ch** | Ethereum R&D | None | ~60/min | Protocol research |
| **Ethereum Magicians** | EIP governance | None | ~60/min | EIP discussions |
| **npm/crates.io** | Packages | None | Varies | Library discovery |

### Dead/Skip: Sourcegraph (closed), Pushshift (dead), Twitter/X ($200+/mo), Google Scholar (no API), Mastodon (no global search).

---

## Architecture

### Design Principles
1. **Value first** — synthesis (the killer feature) ships in MVP, not Phase 2
2. **Graceful degradation** — partial results beat hard failure
3. **Simple structure** — single entry point, no microservice complexity
4. **Budget-aware** — track daily spend, auto-fallback to free
5. **Cached** — same query within TTL returns cached results (highest-ROI optimization)

### Pipeline

```
Question → [Cache Check] → [Classify] → [Route] → [Parallel Search] → [Deduplicate] → [Rank] → [Synthesize] → Answer
                                                         ↓
                                                    [Cache Store]
```

**Latency Budgets:**
- `depth=shallow`: ≤4s (no synthesis, no content extraction, top-5 results)
- `depth=deep`: ≤15s (synthesis on, content extraction for top-3)
- Per-provider timeout: 4s (shallow) / 8s (deep)

### Query Classification

Two-stage: fast regex patterns (~85% of queries) → LLM fallback (15%).
**Additive** — a query can match multiple domains.

Domains: `general`, `code`, `academic`, `ethereum`, `social`, `qa`, `encyclopedia`, `news`, `package`

### Routing Table

| Domain | Primary Providers | Fallback |
|--------|------------------|----------|
| general | brave | duckduckgo |
| code | github_code, brave | duckduckgo |
| academic | semantic_scholar, arxiv | brave |
| ethereum | ethresearch, github_code | brave |
| social | hn_algolia, bluesky | brave |
| qa | stack_exchange, brave | duckduckgo |
| encyclopedia | wikipedia | brave |
| news | brave (news) | duckduckgo |
| package | npm/crates/pypi | brave |

### Score Fusion

**Reciprocal Rank Fusion (RRF):** `score(doc) = Σ 1/(k + rank_per_source)` where k=60.
- Domain boost: +0.2 if source matches query domain
- Freshness boost: +0.1 if published within 30 days and query needs freshness
- Primary source boost: +0.1 for official docs/repos
- Dedup: URL normalization + trigram similarity (>80% → merge)

### Caching (added per adversarial critique)

- SQLite with query hash key + TTL
- Default TTL: 4 hours for general, 24 hours for encyclopedia/academic
- Cache key: normalized(query + depth + domains)
- Synthesis results cached separately (expensive to regenerate)

### Rate Limiting

- SQLite-based token bucket per provider (WAL mode for concurrent access safety)
- Fallback chains when primary is exhausted
- Daily budget tracking with alerts at 80%/95%

---

## Implementation Plan (Revised per critique)

### MVP (Days 1-3) — Value First
- `search.py` CLI entry point
- 3 providers: `brave`, `duckduckgo`, `github_code`
- Rule-based query classifier
- Basic RRF ranking
- **LLM synthesis with citations** (the killer feature, not deferred)
- SQLite result cache
- SKILL.md

### Phase 2 (Week 2) — Specialized Sources
- Add: `semantic_scholar`, `wikipedia`, `stack_exchange`, `hn_algolia`, `ethresearch`
- Content extraction via `web_fetch` for deep mode
- Provider health tracking

### Phase 3 (Week 3+) — Scale
- SearxNG deployment (if hitting rate limits)
- Exa/Tavily/Perplexity providers
- Provider quality stats learning
- Budget tracker with alerts
- Query reformulation on poor results

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| DDG library gets IP-banned | Medium | Low | Brave as primary, DDG only opportunistic |
| Brave free tier insufficient | Low | Medium | $10/mo paid upgrade or SearxNG |
| LLM synthesis hallucinates | Low | High | Strict prompt + citation-only answers |
| Classification routes wrong | Medium | Low | General fallback always included |
| Server IP reputation damage | Low | High | Isolate aggressive scrapers, monitor bans |
| Provider API deprecation | Low | Medium | Modular design, easy provider swap |

---

## Sources & Detailed Findings

Full research files at `~/research/web-search-skill/findings/`:
- `search-engine-apis.md` — 14+ API detailed analysis (24KB)
- `self-hosted-search.md` — SearxNG, Whoogle, YaCy, etc. (5KB)
- `specialized-sources.md` — 20+ domain-specific sources (32KB)
- `tradeoff-analysis.md` — Free vs paid matrix with budget scenarios (16KB)
- `skill-architecture.md` — Full architecture design (28KB)
- `../drafts/critique.md` — Adversarial review and corrections (12KB)
