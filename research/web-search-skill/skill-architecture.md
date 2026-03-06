# Web Search Skill — Architecture Design

**Author:** Lodekeeper (subagent)  
**Date:** 2026-03-06  
**Status:** Draft v1  
**Purpose:** Comprehensive multi-source search orchestrator for OpenClaw agents

---

## Table of Contents

1. [Overview & Goals](#overview)
2. [Query Classification Engine](#classification)
3. [Search Provider Abstraction Layer](#providers)
4. [Orchestration Flow](#orchestration)
5. [Result Processing Pipeline](#processing)
6. [SKILL.md Structure](#skillmd)
7. [Implementation Plan](#implementation)
8. [Rate Limit Strategy](#rate-limits)
9. [File/Script Layout](#layout)
10. [Open Questions](#open-questions)

---

## 1. Overview & Goals {#overview}

The skill transforms a natural-language question into synthesized, actionable findings by:

1. **Classifying** the query into one or more search domains
2. **Routing** to the best provider combination for that domain
3. **Querying** providers in parallel with timeout protection
4. **Aggregating** results, deduplicating by URL and semantic similarity
5. **Ranking** by a cross-source score fusion
6. **Extracting** full content from top-N URLs (optional, depth-controlled)
7. **Synthesizing** a concise answer with citations

The skill is invoked from SKILL.md by the main agent, which runs it as a sub-process via `exec`. All provider config lives in a single JSON file. The agent never needs to know which providers were used.

### Design Principles

- **Graceful degradation:** partial results are better than a hard failure
- **Modularity:** add/remove providers by editing config, no code change
- **Budget awareness:** track daily/monthly spend per provider
- **Transparency:** every result carries provenance (source + query used)
- **Fail fast on timeouts:** 8s per provider, never block the agent

---

## 2. Query Classification Engine {#classification}

### 2.1 Domain Taxonomy

```
DOMAIN              DESCRIPTION
─────────────────────────────────────────────────────────────────────
general             Anything that doesn't fit a narrower category
code                Code snippets, APIs, library usage, error messages
package             npm / crates.io / PyPI package info, versions
academic            Research papers, citations, scientific concepts
ethereum            Protocol specs, EIPs, client implementations, R&D
social_hn           Hacker News discussions, community sentiment
social_bsky         Bluesky posts (real-time, tech-leaning)
news                Recent events (< 7 days)
qa                  Stack Overflow / Stack Exchange style Q&A
encyclopedia        Wikipedia-style factual lookups
package_docs        Library documentation (MDN, ReadTheDocs, etc.)
```

### 2.2 Classification Rules

Classification is **additive** — a query can match multiple domains. The classifier runs a lightweight rule pass first; if uncertain, it asks the LLM.

#### Rule-Based Pass (fast, no LLM)

```python
PATTERNS = {
    "code": [
        r"\b(function|class|import|require|export|async|await|npm run)\b",
        r"\b(TypeError|SyntaxError|undefined is not|ENOENT|segfault)\b",
        r"`[^`]+`",                          # backtick code spans
        r"[A-Z][a-z]+Error\b",              # PascalCase errors
    ],
    "package": [
        r"\bnpm (install|i|add|remove|update)\b",
        r"\b(package\.json|Cargo\.toml|pyproject\.toml|requirements\.txt)\b",
        r"\bversion\s+\d+\.\d+",
        r"\b@[a-z][a-z0-9-]*/[a-z]",       # scoped package names
    ],
    "academic": [
        r"\b(paper|study|research|citation|doi:|arXiv|preprint)\b",
        r"\b(theorem|proof|dataset|benchmark|experiment|hypothesis)\b",
    ],
    "ethereum": [
        r"\b(EIP[-\s]\d+|ERC[-\s]\d+|beacon chain|consensus layer|execution layer)\b",
        r"\b(lodestar|prysm|lighthouse|teku|nimbus|grandine)\b",
        r"\b(solidity|vyper|ethers?\.js|web3|wagmi|viem)\b",
        r"\b(PeerDAS|ePBS|fork choice|slot|epoch|validator|attestation)\b",
        r"\bethresear\.ch\b",
    ],
    "social_hn": [
        r"\b(hacker news|HN|discuss|community reaction|show hn|ask hn)\b",
        r"\bwhat do people think\b",
    ],
    "qa": [
        r"\b(how (do|does|to|can)|why (is|does|did)|what (is|are|does))\b",
        r"\b(stack overflow|stackoverflow|stack exchange)\b",
    ],
    "news": [
        r"\b(today|yesterday|this week|breaking|just announced|latest|recent)\b",
        r"\b(2025|2026)\b",   # current years
    ],
    "encyclopedia": [
        r"\b(what is|who is|define|definition of|explain)\b",
        r"\b(history of|wikipedia|wiki)\b",
    ],
}
```

#### LLM Disambiguation Pass (only if rule pass is ambiguous / no match)

Prompt template (< 100 tokens):
```
Classify this search query into one or more of these domains: 
general, code, package, academic, ethereum, social_hn, news, qa, encyclopedia.
Respond with a JSON array of strings, most specific first.
Query: "{query}"
```

#### Output: Classified Query Object

```json
{
  "query": "how does PeerDAS batch verification work in Lodestar?",
  "domains": ["ethereum", "code", "academic"],
  "intent": "technical_explanation",
  "freshness_needed": false,
  "estimated_depth": "deep"
}
```

`estimated_depth`: shallow (facts only) | medium (with snippets) | deep (full page extraction needed)

---

## 3. Search Provider Abstraction Layer {#providers}

### 3.1 Provider Interface

Every provider module exposes a single async function:

```typescript
interface SearchProvider {
  id: string;                     // e.g. "brave", "searxng", "semantic_scholar"
  domains: string[];              // which domains this provider covers
  priority: number;               // 1 (highest) - 10 (lowest)
  rateLimit: RateLimitConfig;
  healthStatus: "healthy" | "degraded" | "down";

  search(params: SearchParams): Promise<SearchResult[]>;
  healthCheck(): Promise<boolean>;
}

interface SearchParams {
  query: string;
  domains: string[];              // hint from classifier
  maxResults: number;             // default 10
  freshness?: "day" | "week" | "month" | "any";
  timeoutMs: number;
}

interface SearchResult {
  url: string;
  title: string;
  snippet: string;
  score: number;                  // 0.0–1.0, normalized
  source: string;                 // provider id
  publishedAt?: string;           // ISO date if known
  metadata?: Record<string, unknown>;
}
```

### 3.2 Provider Catalog

```
ID                  TYPE          DOMAINS                          FREE?    PRIORITY
──────────────────────────────────────────────────────────────────────────────────────
brave               web           general, news, qa                paid     1
searxng             web           general, news, code, qa          free     2 (if self-hosted)
duckduckgo          web           general, news                    free     3
serper              web           general, news, qa                paid     2
exa                 semantic      general, academic, code          paid     3
tavily              ai-web        general, news, qa                paid     2
perplexity          ai-answer     general, news, qa                paid     1 (AI answer)
github_code         code          code, package                    free     1
semantic_scholar    academic      academic                         free     1
arxiv               academic      academic, ethereum               free     2
stack_exchange      qa            qa, code                         free     1
hn_algolia          social        social_hn                        free     1
bluesky             social        social_bsky                      free     1
wikipedia           encyclopedia  encyclopedia                     free     1
ethresearch         ethereum      ethereum                         free     1
npm_registry        package       package                          free     1
pypi                package       package                          free     2
crates_io           package       package                          free     2
```

### 3.3 Provider Configuration File

`~/.openclaw/workspace/skills/web-search/config/providers.json`

```json
{
  "brave": {
    "enabled": true,
    "apiKey": "${BRAVE_API_KEY}",
    "baseUrl": "https://api.search.brave.com/res/v1/web/search",
    "rateLimit": { "rpm": 60, "rpd": 2000, "rpm_burst": 5 },
    "costPer1k": 3.00,
    "timeoutMs": 5000,
    "priority": 1
  },
  "searxng": {
    "enabled": false,
    "baseUrl": "${SEARXNG_URL}",
    "rateLimit": { "rpm": 60, "rpd": null },
    "costPer1k": 0,
    "timeoutMs": 6000,
    "priority": 2
  },
  "duckduckgo": {
    "enabled": true,
    "apiKey": null,
    "rateLimit": { "rpm": 30, "rpd": 500 },
    "costPer1k": 0,
    "timeoutMs": 5000,
    "priority": 3
  },
  "semantic_scholar": {
    "enabled": true,
    "apiKey": "${SEMANTIC_SCHOLAR_KEY}",
    "baseUrl": "https://api.semanticscholar.org/graph/v1",
    "rateLimit": { "rpm": 100, "rpd": 5000 },
    "costPer1k": 0,
    "timeoutMs": 5000,
    "priority": 1
  },
  "github_code": {
    "enabled": true,
    "apiKey": "${GITHUB_TOKEN}",
    "baseUrl": "https://api.github.com/search/code",
    "rateLimit": { "rpm": 10, "rpd": 1000 },
    "costPer1k": 0,
    "timeoutMs": 5000,
    "priority": 1
  },
  "hn_algolia": {
    "enabled": true,
    "apiKey": null,
    "baseUrl": "https://hn.algolia.com/api/v1",
    "rateLimit": { "rpm": 600, "rpd": 10000 },
    "costPer1k": 0,
    "timeoutMs": 4000,
    "priority": 1
  }
}
```

### 3.4 Health Checking & Failover

```
CIRCUIT BREAKER per provider:
  - State: closed (healthy) → open (failed) → half-open (testing)
  - Trip: 3 consecutive failures OR latency > 2× baseline for 5 requests
  - Recovery: after 60s in open state, allow 1 probe request
  - Log all state transitions to ~/.openclaw/workspace/skills/web-search/state/health.json

FAILOVER CHAINS (ordered):
  general:    brave → duckduckgo → searxng → exa
  code:       github_code → brave → searxng → duckduckgo
  academic:   semantic_scholar → arxiv → exa → brave
  ethereum:   ethresearch → arxiv → github_code → brave
  qa:         stack_exchange → brave → duckduckgo
  social_hn:  hn_algolia → brave
  package:    npm_registry → crates_io → pypi → github_code
  news:       brave → tavily → duckduckgo → serper
  encyclopedia: wikipedia → brave
```

---

## 4. Orchestration Flow {#orchestration}

### 4.1 High-Level Pipeline

```
Agent Query
    │
    ▼
┌─────────────────────┐
│  1. Classify Query  │  (< 200ms, rule-based; LLM fallback)
└─────────────────────┘
    │  ClassifiedQuery
    ▼
┌─────────────────────┐
│  2. Route to Sources│  routing_table.json + health status check
└─────────────────────┘
    │  [ProviderPlan]
    ▼
┌─────────────────────────────────────────────┐
│  3. Parallel Search  (Promise.allSettled)   │
│     ├─ Provider A → [results]               │
│     ├─ Provider B → [results]               │
│     └─ Provider C → error (→ log + skip)    │
└─────────────────────────────────────────────┘
    │  [RawResults[]]
    ▼
┌─────────────────────┐
│  4. Aggregate       │  flatten + attach provenance
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  5. Deduplicate     │  URL exact match + domain similarity
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  6. Rank/Score      │  normalized score fusion (RRF)
└─────────────────────┘
    │  top-N results
    ▼
┌─────────────────────────────────────────────┐
│  7. Content Extract (optional, if depth=deep│
│     web_fetch(url) for top-3 results        │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────┐
│  8. Synthesize      │  LLM summarization with citations
└─────────────────────┘
    │
    ▼
  SearchResponse (answer + sources + metadata)
```

### 4.2 Routing Table

Full routing matrix — primary providers listed first, fallbacks after `|`:

```
DOMAIN         MAX_SOURCES  PRIMARY PROVIDERS                    FALLBACKS
─────────────────────────────────────────────────────────────────────────────
general        3            brave, exa                           duckduckgo, searxng
code           3            github_code, brave                   searxng, duckduckgo
package        2            npm_registry, crates_io, pypi        github_code
academic       3            semantic_scholar, arxiv              exa, brave
ethereum       4            ethresearch, arxiv, github_code      brave, exa
social_hn      2            hn_algolia                           brave
social_bsky    1            bluesky                              —
news           3            brave, tavily                        duckduckgo, serper
qa             3            stack_exchange, brave                duckduckgo
encyclopedia   2            wikipedia, brave                     duckduckgo
```

`MAX_SOURCES`: how many providers to query in parallel (budget + latency tradeoff).

### 4.3 Timeout and Circuit Breaker

```
Per-provider timeout: 8s hard limit (Promise.race with AbortController)
Total orchestration timeout: 15s (gives parallel providers 8s + 7s for processing)
Circuit breaker: trips after 3 consecutive errors, 60s cooldown
Partial success: if ≥1 provider returns results, proceed. Log failures.
Zero results: fall back to general web providers if specialized sources all fail.
```

### 4.4 Partial Failure Handling

```
Result: { ok: true, results: [...] }  → include in aggregate
Result: { ok: false, error: "timeout" } → log to health.json, mark provider degraded
                                          use next provider in failover chain

If ALL providers fail:
  → Return error with diagnostic info
  → Agent can retry with `depth=shallow` (fewer providers, faster)

If 0 results but no errors:
  → Widen query: strip quoted phrases, remove domain-specific terms
  → Retry with general fallback (brave + duckduckgo)
```

---

## 5. Result Processing Pipeline {#processing}

### 5.1 Deduplication

**Stage 1 — Exact URL match:**
```
Normalize URL: lowercase scheme+host, strip utm_* params, trailing slash
Group by normalized URL; keep result with highest score, merge source list
```

**Stage 2 — Near-duplicate detection (lightweight):**
```
If two snippets share > 80% of trigrams → consider duplicate
Keep the one with more metadata (publishedAt, longer snippet)
This catches: same article on different mirrors, Google cache vs original
```

Implementation: trigram overlap via Python `difflib.SequenceMatcher` (no ML needed).

### 5.2 Cross-Source Score Fusion

Different providers return incompatible scores (ranks, floats, boolean). Normalize using **Reciprocal Rank Fusion (RRF)**:

```
score_rrf(doc) = Σ_provider  1 / (k + rank_in_provider)
  where k = 60 (standard constant)

If provider returns raw score (0–1) instead of rank:
  rank = ceil((1 - score) * max_results)  # invert: high score → low rank
```

**Domain-specific boosts (applied after RRF):**
```
+ 0.2  if source domain matches query domain (e.g. ethereum query + ethresearch.ch result)
+ 0.1  if publishedAt within 30 days and freshness_needed=true
+ 0.1  if result is a primary source (GitHub repo, official docs, spec)
- 0.1  if result is a news aggregator / SEO farm (heuristic list)
```

### 5.3 Snippet Extraction & Summarization

**Shallow mode** (default):
- Use provider-returned snippets as-is
- Truncate to 300 chars, append `[…]`
- Include: title, url, snippet, source, score

**Deep mode** (triggered when `estimated_depth == "deep"` or `depth=full` flag):
- Fetch full content of top-3 results via `web_fetch(url)`
- Extract relevant paragraphs: chunk text → score chunks against query (BM25)
- Return top-3 chunks per page with context window

**Synthesis prompt (after ranking):**
```
You are synthesizing search results to answer a question.
Question: {query}
Top results (with content):
{results_json}

Requirements:
- Answer directly in 2–5 sentences
- Cite sources inline as [1], [2], etc.
- Note if results are conflicting or outdated
- If insufficient info, say so clearly
- Do NOT hallucinate beyond what the results say
```

### 5.4 Citation Tracking

Every result in the final output includes:
```json
{
  "id": 1,
  "url": "https://...",
  "title": "...",
  "source": "brave",
  "rank": 1,
  "score_rrf": 0.847,
  "domains": ["ethereum"],
  "fetched_content": true
}
```

The synthesis answer references `[1]`, `[2]` etc., mapped to the citations array.

---

## 6. SKILL.md Structure {#skillmd}

```markdown
# web-search

Multi-source web search orchestrator. Finds answers to any question by querying
optimal sources in parallel, deduplicating, ranking, and synthesizing results.

## When to use this skill

Use this skill when:
- You need current information beyond your training data
- You need to verify a specific fact with a source
- A question could be answered by code search, academic papers, or specialized databases
- The `web_search` tool alone is insufficient (rate limit, quality, coverage)

Do NOT use for: 
- Questions you can answer from training knowledge with high confidence
- Internal workspace file lookups (use Read/exec instead)

## How to invoke

Read this SKILL.md first. Then call the search script:

    exec: python3 ~/.openclaw/workspace/skills/web-search/search.py \
            --query "your question" \
            [--depth shallow|medium|deep] \
            [--domain ethereum|code|academic|general|...] \
            [--max-results 10] \
            [--freshness day|week|month|any] \
            [--no-synthesis]

The script prints a JSON response to stdout:

    {
      "answer": "Synthesized answer text with citations [1][2].",
      "citations": [ { "id": 1, "url": "...", "title": "...", "source": "..." } ],
      "query": { "original": "...", "domains": [...] },
      "providers_used": ["brave", "semantic_scholar"],
      "providers_failed": [],
      "latency_ms": 2340,
      "tokens_used": 800
    }

## Configuration

Edit `config/providers.json` to:
- Enable/disable providers (set `"enabled": false`)
- Update API keys (or set env vars: BRAVE_API_KEY, SERPER_KEY, etc.)
- Adjust rate limits and priorities

## Adding a new provider

1. Add entry to `config/providers.json`
2. Create `providers/<name>.py` implementing `search(params) -> list[SearchResult]`
3. Run `python3 search.py --health-check` to verify

## State files

- `state/health.json` — circuit breaker status per provider
- `state/budget.json` — daily/monthly spend tracking
- `state/provider-stats.json` — per-domain success rates (for learning)
```

---

## 7. Implementation Plan {#implementation}

### MVP (Week 1) — Core orchestrator, 4 providers

**Goal:** Working skill that improves on bare `web_search` tool.

```
Priority  Component                    Effort  Notes
────────────────────────────────────────────────────────────────────
P0        search.py entry point        S       CLI arg parsing, JSON output
P0        classifier.py (rule-based)   S       Pattern matching, no LLM
P0        providers/brave.py           S       Already have API key
P0        providers/duckduckgo.py      S       Python lib, no key
P0        providers/github_code.py     S       PAT auth, simple REST
P0        providers/hn_algolia.py      XS      Free, simple REST
P0        aggregator.py               M       RRF fusion, dedup
P0        SKILL.md                     S       Invocation docs
P1        providers.json config        S       Provider config schema
P1        state/health.json tracking   S       Circuit breaker state
```

**MVP Output:** `search.py --query "..." --depth shallow` → ranked results JSON, no synthesis.

### Phase 2 (Week 2) — Synthesis + Specialized Providers

```
Priority  Component                    Effort  Notes
────────────────────────────────────────────────────────────────────
P0        synthesizer.py              M       LLM call with citations
P0        providers/semantic_scholar  S       For academic queries
P0        providers/wikipedia.py      S       Factual queries
P0        providers/stack_exchange.py S       QA queries
P0        providers/ethresearch.py    M       Discourse API
P1        content_extractor.py        M       web_fetch integration
P1        LLM classifier (fallback)   S       For ambiguous queries
```

### Phase 3 (Week 3+) — Learning + More Providers

```
Priority  Component                    Effort  Notes
────────────────────────────────────────────────────────────────────
P1        provider_stats.py           M       Track source quality per domain
P1        providers/searxng.py        S       Self-hosted option
P1        providers/arxiv.py          S       arXiv API
P1        providers/tavily.py         S       AI-focused search
P1        providers/exa.py            S       Semantic / neural
P2        providers/perplexity.py     S       AI grounded answers
P2        providers/bluesky.py        M       AT Protocol API
P2        budget_tracker.py           M       Cost alerting
P2        npm / crates / pypi         S       Package lookups
```

### Script/Tool Breakdown

```
skills/web-search/
├── SKILL.md                    ← Agent reads this first
├── search.py                   ← Main entry point (CLI)
├── classifier.py               ← Query → domain classification
├── router.py                   ← Domains → provider selection
├── orchestrator.py             ← Parallel search + timeout
├── aggregator.py               ← Dedup + RRF fusion
├── content_extractor.py        ← web_fetch for deep mode
├── synthesizer.py              ← LLM synthesis with citations
├── config/
│   ├── providers.json          ← Provider config (keys, limits)
│   └── routing_table.json      ← Domain → provider mapping
├── providers/
│   ├── base.py                 ← Abstract provider class
│   ├── brave.py
│   ├── duckduckgo.py
│   ├── github_code.py
│   ├── hn_algolia.py
│   ├── semantic_scholar.py
│   ├── wikipedia.py
│   ├── stack_exchange.py
│   ├── ethresearch.py
│   └── [others...]
└── state/
    ├── health.json             ← Circuit breaker state (runtime)
    ├── budget.json             ← Spend tracking
    └── provider-stats.json     ← Source quality learning
```

---

## 8. Rate Limit Strategy {#rate-limits}

### 8.1 Token Bucket per Provider

Each provider has its own token bucket. Implementation uses a persistent JSON file for cross-session state (no in-memory daemon needed):

```
state/rate-limits/<provider>.json:
{
  "tokens": 45,
  "max_tokens": 60,
  "refill_rate": 1.0,   # tokens/second (= 60/min)
  "last_refill": 1709123456.789,
  "daily_used": 142,
  "daily_limit": 2000,
  "monthly_used": 1893,
  "monthly_limit": null
}
```

**Bucket logic (read-before-write with file lock):**
```python
def acquire_token(provider_id: str, n: int = 1) -> bool:
    bucket = load_bucket(provider_id)      # read + refill based on elapsed time
    if bucket.tokens >= n and bucket.daily_used + n <= bucket.daily_limit:
        bucket.tokens -= n
        bucket.daily_used += n
        save_bucket(provider_id, bucket)   # atomic write via tempfile + rename
        return True
    return False   # caller uses fallback
```

### 8.2 Fallback Chains

```
General query example:

1. Try brave (priority 1)
   → bucket full? → use it
   → bucket empty / daily limit hit? → mark degraded, try next

2. Try duckduckgo (priority 3, free)
   → no limit issues typically
   → use it

3. Try searxng (priority 2, if configured)
   → self-hosted, effectively unlimited
   → use it

4. Try exa (priority 3, 1K/mo free)
   → check monthly budget
   → use if remaining > 0

5. No providers available → return error with diagnostic
```

### 8.3 Budget Tracking

```
state/budget.json:
{
  "date": "2026-03-06",
  "month": "2026-03",
  "daily": {
    "brave": { "requests": 47, "cost_usd": 0.141 },
    "serper": { "requests": 12, "cost_usd": 0.024 }
  },
  "monthly": {
    "brave": { "requests": 892, "cost_usd": 2.676 },
    "exa": { "requests": 234, "free_tier_remaining": 766 }
  },
  "monthly_budget_usd": 10.00,
  "monthly_spent_usd": 2.70,
  "alerts": []
}
```

**Alert thresholds:**
- 80% of monthly budget → log warning in budget.json
- 95% of monthly budget → disable paid providers automatically
- Daily budget cap (configurable, default $1/day) → fallback to free providers

### 8.4 Cost-Aware Provider Selection

When multiple providers can serve a query, prefer free over paid when:
- Free provider has equivalent coverage for this domain
- Current month spend > 50% of budget
- Query is non-urgent (depth=shallow)

Use paid providers preferentially when:
- Result quality matters significantly (depth=deep)
- Free providers are rate-limited or failing
- Ethereum/academic queries where specialized APIs are critical

---

## 9. File/Script Layout (Full) {#layout}

```
~/.openclaw/workspace/skills/web-search/
├── SKILL.md
├── README.md                       ← Developer docs (adding providers, etc.)
├── search.py                       ← Main CLI entry point
├── classifier.py
├── router.py
├── orchestrator.py
├── aggregator.py
├── synthesizer.py
├── content_extractor.py
├── budget_tracker.py
├── health_checker.py
│
├── providers/
│   ├── base.py                     ← SearchProvider ABC
│   ├── brave.py
│   ├── duckduckgo.py
│   ├── github_code.py
│   ├── hn_algolia.py
│   ├── semantic_scholar.py
│   ├── arxiv.py
│   ├── wikipedia.py
│   ├── stack_exchange.py
│   ├── ethresearch.py
│   ├── npm_registry.py
│   ├── crates_io.py
│   ├── pypi.py
│   ├── bluesky.py
│   ├── exa.py
│   ├── tavily.py
│   ├── serper.py
│   ├── perplexity.py
│   └── searxng.py
│
├── config/
│   ├── providers.json              ← Per-provider config (keys via env vars)
│   ├── routing_table.json          ← Domain → provider assignment
│   └── boost_rules.json            ← Score boost/penalty rules
│
├── state/                          ← Runtime state (not in git)
│   ├── health.json
│   ├── budget.json
│   ├── provider-stats.json
│   └── rate-limits/
│       ├── brave.json
│       ├── duckduckgo.json
│       └── [...]
│
└── tests/
    ├── test_classifier.py
    ├── test_aggregator.py
    └── test_providers.py           ← Mock-based, no real API calls
```

---

## 10. Open Questions {#open-questions}

1. **SearxNG hosting:** Should we self-host a SearxNG instance? It would provide a free, unlimited general web aggregator. Requires Docker + public IP or localhost reverse proxy. Recommend: set up on the server if Docker is available.

2. **LLM for classification:** The rule-based classifier handles ~85% of queries well. For the remaining 15% (ambiguous), should we call an LLM (adds ~200ms + tokens) or just default to `general`? Recommendation: call LLM for ambiguous cases; cost is minimal.

3. **Synthesis quality vs. cost:** Synthesis requires an LLM call for every search. Should we make it opt-in (--no-synthesis flag) or always on? Recommendation: on by default for `deep`, off by default for `shallow`.

4. **Perplexity integration:** Perplexity returns AI-synthesized answers, not raw search results. It doesn't fit the standard SearchResult interface cleanly. Could bypass the pipeline and return directly when query is simple and Perplexity is available. Decision needed.

5. **Provider-stats learning:** Tracking per-domain success rate per provider enables smarter routing over time (e.g., "semantic_scholar is consistently better for ethereum academic queries than arxiv"). This requires persistent state + periodic re-weighting logic. Defer to Phase 3.

6. **Bluesky auth:** Anonymous search is possible but limited. A PAT would unlock more results. Decide whether to require Bluesky auth.

---

## Appendix: Routing Decision Examples

| Query | Classified Domains | Providers Used |
|---|---|---|
| "how does PeerDAS work" | ethereum, academic | ethresearch, arxiv, github_code |
| "npm install fails with ENOENT" | code, qa, package | github_code, stack_exchange, npm_registry, brave |
| "latest news on Ethereum Pectra upgrade" | ethereum, news | brave, ethresearch, arxiv |
| "what is Byzantine fault tolerance" | academic, encyclopedia | semantic_scholar, wikipedia |
| "best TypeScript linting setup 2026" | code, general | github_code, brave, duckduckgo |
| "HN reaction to OpenAI new model" | social_hn | hn_algolia, brave |
| "lodash clone vs structuredClone" | code, qa | stack_exchange, github_code, brave |
| "Semantic Scholar API rate limits" | academic, code | semantic_scholar, brave |

---

*Generated by Lodekeeper subagent. Architecture is a starting point — iterate as providers are integrated and real-world query patterns emerge.*
