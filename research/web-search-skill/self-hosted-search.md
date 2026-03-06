# Self-Hosted & Open-Source Search Solutions

*Compiled from sub-agent research, 2026-03-06*

## Summary Table

| Solution | Setup Complexity | API Access | Result Quality vs Google | Rate Limits | Maintenance | Best Use Case |
|----------|-----------------|------------|-------------------------|-------------|-------------|---------------|
| **SearxNG** ⭐ | 2/5 (Docker) | JSON API (`/search?format=json`) | 85-95% (aggregates Google/Bing/DDG) | Self-managed | Low-medium | **Primary recommendation** for programmatic web search |
| **4get** | 2/5 (PHP) | Limited/unclear | 80-90% | Self-managed | Low | Lightweight alternative (200-400MB vs SearxNG ~2GB) |
| **Whoogle** | 2/5 (Docker) | Beta JSON output | 90%+ (Google only) | Google rate limits apply | ⚠️ HIGH (Google attacking it) | **NOT recommended** — Google actively breaking it since Jan 2025 |
| **YaCy** | 4/5 (Java) | REST API | 20-30% (own P2P index) | Self-managed | High | Internal/domain-specific search only |
| **LibreX** | 2/5 (PHP) | JSON API | 70-80% (3 engines only) | Self-managed | ❌ Stalled (~2023) | **NOT recommended** — effectively abandoned |
| **Meilisearch/Typesense/Zinc** | 1-3/5 | REST API | N/A (internal search) | Self-managed | Low | **NOT web search** — index your own documents |

## Detailed Findings

### 1. SearxNG ⭐ RECOMMENDED

**What it is:** Self-hosted meta-search engine that aggregates 70+ search engines (Google, Bing, DuckDuckGo, Brave, Qwant, etc.) without needing individual API keys.

**How it works:**
- Sends queries to multiple upstream engines simultaneously
- Aggregates and deduplicates results
- Exposes results via JSON API

**Setup:**
```bash
# Docker (recommended)
docker run -d --name searxng -p 8888:8080 \
  -v ./searxng:/etc/searxng \
  searxng/searxng:latest
```

**API Access:**
```
GET http://localhost:8888/search?q=query&format=json
```
- Returns: `results[]` with `title`, `url`, `content` (snippet), `engine`, `score`
- Pagination: `&pageno=2`
- Categories: `&categories=general,science,it`
- Time range: `&time_range=month`

**Configuration (`settings.yml`):**
- Enable/disable individual engines
- Set engine priorities and weights
- Configure rate limiting per engine
- Enable JSON format output (must be enabled in settings!)
- Set result language/region preferences

**Key considerations:**
- **Self-hosting is essential** — public instances often get rate-limited by upstream engines and may disable JSON format
- Google scraping can trigger CAPTCHAs under heavy load
- Mix of engines provides redundancy (if Google blocks, Bing/DDG still work)
- ~2GB RAM for comfortable operation
- Active development community, regular updates

**Verdict:** Best option for programmatic web search without API keys. Deploy self-hosted, enable JSON format, configure Google+Bing+DDG+Brave for redundancy.

### 2. 4get

**What it is:** Lightweight PHP meta-search engine with many search sources.

**Strengths:**
- Very low resource usage (200-400MB RAM)
- Many search source integrations
- Simple PHP deployment

**Weaknesses:**
- JSON API documentation is unclear/limited
- Single-developer project (bus factor of 1)
- Less mature than SearxNG

**Verdict:** Viable lightweight alternative if SearxNG is too heavy, but API integration may require more work.

### 3. Whoogle ⚠️ NOT RECOMMENDED

**What it is:** Self-hosted Google frontend — proxies Google search results.

**Critical issue:** Google has been **actively attacking Whoogle since January 2025** — blocking requests, changing markup, serving CAPTCHAs. The project is in a constant arms race with Google.

**Other issues:**
- Google-only (no fallback to other engines)
- Beta JSON output (recently added)
- High maintenance burden (frequent breakage)

**Verdict:** Unreliable for programmatic use. Google can break it at any time.

### 4. YaCy

**What it is:** P2P distributed search engine that builds its own index by crawling.

**Result quality:** Orders of magnitude worse than Google for general web search. The P2P index is tiny compared to commercial search engines.

**Use case:** Only useful for searching a specific domain/corpus you've crawled yourself.

**Verdict:** Not suitable for general web search.

### 5. LibreX

**What it is:** Minimalist PHP meta-search engine.

**Status:** Effectively stalled since ~2023. Only supports 3 engines.

**Verdict:** Use SearxNG instead.

### 6. Meilisearch / Typesense / Zinc

**What they are:** Internal document search engines — you index YOUR data and search it.

**Important:** These are **NOT web search engines**. They solve a completely different problem (searching your own documents, not the internet).

**Verdict:** Irrelevant for this skill's purpose.
