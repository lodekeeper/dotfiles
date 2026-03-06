# Web Search Skill — Free vs Paid vs Account-Based Tradeoff Analysis

*Written: 2026-03-06 | Based on research in `search-engine-apis.md`, `self-hosted-search.md`, `specialized-sources.md`*

---

## Executive Summary

Building a robust AI agent search capability does NOT require paying for a single premium API. A well-architected multi-tier strategy can cover ~95% of use cases for free, with surgical paid augmentation only where quality gaps genuinely matter.

**TL;DR recommendation:**
- **Free + self-hosted:** SearxNG covers general web search with no API key, no rate limits (self-managed), and access to 70+ engines simultaneously.
- **Free accounts:** Brave (1.7K/mo), Tavily (1K/mo), GitHub PAT (code search), Stack Exchange key — cover the free-tier gaps.
- **Specialized free (no auth):** HN, Bluesky, Wikipedia, ethresear.ch, Semantic Scholar, arXiv, npm, crates.io — cover non-web domains perfectly.
- **Paid upgrade path:** Only needed above ~2K searches/month or if SearxNG maintenance is unacceptable. Brave paid (~$3/1K) is the best value jump.

---

## 1. Tier 1: Completely Free (No Key, No Account)

### What's available

| Source | Type | Rate Limit | Quality | Freshness |
|--------|------|-----------|---------|-----------|
| **DuckDuckGo** (unofficial) | General web | ~20-50 req/min (soft) | Adequate (Bing index) | Hours-days |
| **SearxNG** (self-hosted) | General web | Self-managed | Excellent (multi-engine) | Hours |
| **HN Algolia** | Tech discussions | 10,000/hr | Excellent | Minutes |
| **Bluesky API** | Social/tech | Undocumented, generous | Good, growing | Minutes |
| **Semantic Scholar** | Academic papers | ~1 req/sec (shared pool) | Excellent (214M papers) | Days-weeks |
| **arXiv API** | CS/ML preprints | 1 req/3 sec | Excellent | Hours |
| **CrossRef API** | DOI/citations | 50 req/sec (polite pool) | Excellent (150M works) | Days |
| **ethresear.ch** | Ethereum research | ~60 req/min | Excellent (niche) | Minutes |
| **Ethereum Magicians** | EIP governance | ~60 req/min | Excellent (niche) | Minutes |
| **Wikipedia API** | Factual knowledge | ~200 req/sec | Excellent | Hours |
| **npm search** | JS packages | ~5M/month | Good | Minutes |
| **crates.io search** | Rust packages | 1 req/sec (polite) | Good | Minutes |
| **grep.app** | GitHub code (unofficial) | Undocumented | Good (~1M repos) | Days |

### Notable omissions and caveats

**DuckDuckGo (unofficial library):**
- Uses the `duckduckgo-search` Python scraping library, NOT an official API
- Can and does get IP-banned without warning; rate limits are unpredictable
- Best used as a quick fallback, not a primary route
- Covers Bing's index + DuckDuckGo's own additions (privacy-focused)

**SearxNG (self-hosted) — the star of Tier 1:**
- Aggregates 70+ engines (Google, Bing, DDG, Brave, Qwant, etc.) by scraping them
- You control rate limits, engine mix, and prioritization via `settings.yml`
- Google scraping can CAPTCHA under heavy load — mix in DDG/Bing/Brave for redundancy
- JSON API at `http://localhost:8888/search?q={query}&format=json`
- **~2GB RAM for comfortable operation** — acceptable on most servers
- Active development, Docker deploy in minutes
- **Key caveat:** Must be self-hosted; public instances often disable JSON format and get severely rate-limited by upstream engines. Your own instance = no such problems.
- **Bottom line:** For an agent that needs general web search and you can afford the server resources, SearxNG is the single best free option.

**Specialized free sources are gold:**
- HN, Bluesky, Wikipedia, ethresear.ch, Ethereum Magicians, arXiv, Semantic Scholar — these are not compromises, they are purpose-built and excellent for their domains. A general search engine will never match them for academic or Ethereum-specific queries.

### Rate limit reality at Tier 1

For 50-200 searches/day (~1,500-6,000/month):
- **SearxNG self-hosted:** ✅ Completely sufficient (you set your own limits, no quota)
- **HN Algolia:** ✅ 10K/hr — overkill for our usage
- **DuckDuckGo unofficial:** ⚠️ Risky — could get blocked. Fine as sporadic fallback
- **arXiv:** ⚠️ 1 req/3s means 28,800/day theoretically, but sustained bulk use may hit soft limits
- **Wikipedia:** ✅ ~200 req/sec — no concern
- **Semantic Scholar:** ⚠️ 1 req/sec guaranteed (with key — see Tier 2), shared pool without key may be slower

---

## 2. Tier 2: Free with Account/API Key

### What an API key or account buys you

| Source | Free Tier | What You Get | Key Limitation | Signup Friction |
|--------|-----------|-------------|----------------|-----------------|
| **Brave Search** | ~1,667 queries/mo ($5 credit) | Independent index, rich metadata, 1 QPS | 2K/mo hard cap, 1 QPS | Credit card required (anti-fraud) |
| **Tavily** | 1,000 credits/mo | AI-agent-optimized, content extraction | Credits don't roll over, no key = no access | Email signup |
| **Exa** | 1,000 req/mo | Neural/semantic search, find-similar | Small free quota | Email signup |
| **You.com** | $100 one-time credit | Three APIs (search, contents, research) | Credits deplete, pricing opaque | Email signup |
| **Serper** | 2,500 queries (one-time) | Google results, cheapest per-query | One-time only, not monthly | Email signup |
| **Perplexity** | $0 spend threshold (50 RPM) | AI-grounded answers | Pay-as-you-go from first query, complex pricing | Email signup |
| **GitHub PAT** | Unlimited (10 req/min code search) | All public repo code search | 10 req/min rate limit | GitHub account |
| **Stack Exchange** | 10,000 req/day | Full SO/SE corpus Q&A | None at this volume | Stack Apps registration |
| **Semantic Scholar (key)** | 1 req/sec guaranteed | 214M academic papers, rich metadata | Requests per key increase requires email | API key request |
| **Libraries.io** | 60 req/min | 7M+ packages, cross-registry | 60 req/min | Email signup |
| **Reddit API** | 100 req/min (OAuth2) | Discussions, experiences, opinions | Approval process, policy changes | Developer app registration |

### Detailed assessment

**Brave Search free tier:**
- The free $5/month credit (~1,667 queries) sounds great but the **1 QPS rate limit is the real pain point** — this is what causes our current 429 errors during research sessions that fire multiple searches rapidly.
- For an agent that sends bursts of parallel searches, 1 QPS means you MUST serialize requests or get 429s.
- Brave's paid tier bumps to 50 QPS — a huge jump. This single upgrade solves most Brave-related friction.
- Independent index (30B+ pages, 100M+ daily updates) makes it the most privacy-respecting large-scale option.

**Tavily — the AI-agent darling:**
- 1,000 free credits/month is reasonable for prototyping/moderate use
- The AI-agent ecosystem (LangChain, CrewAI, AutoGPT) standardizes on Tavily — if you're already in that ecosystem, integration is trivial
- Does NOT have its own index — aggregates other engines. Less control than Brave.
- Content extraction is built-in, which is convenient (saves a separate web_fetch call)
- 1 credit = 1 basic search, 2 credits = advanced search — advanced searches eat the budget twice as fast

**Exa — uniquely powerful for discovery:**
- Neural/embedding-based search is genuinely different from keyword search
- "Find pages semantically similar to this URL" (`findSimilar`) has no equivalent elsewhere
- 1,000 free requests/month is thin for agents doing bulk search
- At $7-12/1K paid it's expensive compared to Brave ($3/1K) for raw search volume
- Best used selectively for: discovery queries, finding related resources, semantic similarity

**You.com — generous trial:**
- $100 free credit is the most generous trial in the space (no credit card)
- The three-API architecture (Search + Contents + Research) is complementary:
  - Search for result links
  - Contents to fetch and parse page text
  - Research for synthesized multi-source answers
- `livecrawl` parameter fetches full page content alongside search results — rare feature
- Pricing not transparently published (must use credits, run out, then renegotiate)
- Suitable for heavy evaluation/prototyping before committing to paid

**Serper — best cost for Google results:**
- 2,500 one-time queries ≠ monthly — **they expire, not renewable for free**
- Once those are gone, paying is $0.30-$2/1K (cheapest Google results in the market)
- Google's algorithm, DuckDuckGo's price? Not quite — this is a scraping service, not official API
- Fast (1-2 seconds/query), simple REST, no SDK needed
- Primary risk: Google can break scrapers. Serper has stayed stable but no guarantees.

**GitHub PAT — essential for code search:**
- Free with any GitHub account — no cost, just authentication
- 10 req/min for code search specifically (lower than other GitHub search endpoints)
- At 50-200 searches/day, hitting code search 10+ times in a minute is unlikely in normal use
- Supports powerful qualifiers: `repo:`, `org:`, `language:`, `path:`, `filename:`
- **Non-negotiable for any agent working with code**

**Stack Exchange API key:**
- 300 req/day → 10,000 req/day is a 33x multiplier just for getting an API key
- 10,000/day = 833/hr = 13/min — more than enough for any reasonable agent use
- Stack Overflow's Q&A corpus is irreplaceable for programming help
- Key is free, registration is quick — zero reason not to get this key

### Where free tiers fall short

1. **Burst/parallel search:** Brave's 1 QPS blocks parallel agent search patterns
2. **Monthly quota:** Tavily (1K), Exa (1K), Brave (~1.7K) all run out at moderate volume
3. **General web at scale:** No free tier covers >5K/month general web searches reliably
4. **News/real-time content:** Most free tiers don't include news-specific fresh content
5. **Reddit:** Approval process and policy changes make this fragile at free tier

---

## 3. Tier 3: Paid APIs

### When is paid actually worth it?

**Pay if any of these are true:**
- Agent does >5,000 general web searches/month (free tiers exhausted)
- You need >1 QPS for general web (parallel search, real-time agent loops)
- SearxNG self-hosting is not acceptable (maintenance concern, no server resources)
- You need production SLA guarantees
- Search quality in a specific domain is detectably inferior with free options

**Don't pay if:**
- SearxNG can be self-hosted (covers most general web needs)
- Searches are primarily specialized domain (Ethereum, academic, code — all free)
- Usage is under ~3K/month total

### Cost/quality comparison matrix

| API | Quality | Price (1K queries) | Own Index | Recommended? |
|-----|---------|-------------------|-----------|--------------|
| **Kagi** | ⭐⭐⭐⭐⭐ Best | $25 | Aggregated | Only if quality is paramount, budget large |
| **Brave** | ⭐⭐⭐⭐ Excellent | $3 | ✅ Own (30B+) | ✅ YES — best value/quality ratio |
| **Perplexity Sonar** | ⭐⭐⭐⭐ Excellent (AI answers) | $5 + tokens | ✅ Own | For answer synthesis, not raw results |
| **You.com** | ⭐⭐⭐ Good | ~$3-5 | ✅ Own | Good for content extraction workflow |
| **Tavily** | ⭐⭐⭐ Good | $8 (advanced) | ❌ Aggregated | If you need LangChain-native agent integration |
| **Exa** | ⭐⭐⭐⭐ Unique | $7-12 | ✅ Embeddings | For semantic search specifically |
| **Serper** | ⭐⭐⭐⭐ Google-quality | $0.30-$1 | ❌ Google scrape | ✅ YES — cheapest Google results |
| **SerpAPI** | ⭐⭐⭐⭐ Google-quality | ~$10+ | ❌ Multi scrape | Only if need multi-engine structured data |
| **Google CSE** | ⭐⭐⭐⭐⭐ Gold standard | $5 | ✅ Google | ⚠️ SUNSET Jan 2027 — don't invest |

### Budget scenarios

#### $0/month — "Pure Free" Architecture

**Feasible for: ≤50 searches/day, can self-host SearxNG**

```
General web:    SearxNG (self-hosted, multi-engine)
                + DuckDuckGo fallback (unofficial, risky)
Code:           GitHub Code Search (PAT, free)
Academic:       Semantic Scholar + arXiv + CrossRef (all free)
Tech discuss:   HN Algolia + Bluesky (no auth)
Ethereum:       ethresear.ch + Ethereum Magicians (Discourse JSON)
Q&A:            Stack Exchange (free key, 10K/day)
Reference:      Wikipedia API (no auth)
Packages:       npm + crates.io search (no auth)
Social:         Bluesky (no auth)
```

**Coverage:** ~80% of use cases. Gap: no official general web API, DuckDuckGo is fragile, no news aggregation.

**Monthly query capacity:** Effectively unlimited for specialized sources; general web is SearxNG (server-bound).

---

#### $10/month — "Practical Free+" Architecture

**Feasible for: ≤200 searches/day**

```
+ Brave Search (paid): $10 buys ~3,300 queries + removes 1 QPS limit → 50 QPS
OR
+ Serper.dev:          ~$5 gets ~5,000-16,000 Google queries (best per-query value)
Everything else:       Same as $0 tier
```

**Best choice at $10:** Brave ($10 = ~3,300 queries at $3/1K with 50 QPS) vs Serper ($10 = ~5,000-33K queries at $0.30-$2/1K). 

- Choose **Brave** if you want independent index + higher QPS cap
- Choose **Serper** if you need raw query volume at minimum cost

**Coverage:** ~92% of use cases. Eliminates the fragile DuckDuckGo dependency for most searches. SearxNG still handles overflow.

---

#### $50/month — "Production Ready" Architecture

**Feasible for: ≤1,000 searches/day**

```
Primary web:   Brave paid (~$30 = 10K queries, 50 QPS)
Google backup: Serper (~$10 = 10-33K queries)
Semantic:      Exa free tier (1K/mo) + paid overflow ($7/1K)
AI answers:    Perplexity PAYG (light use: ~$5)
Everything:    All $0 tier specialized sources
```

**Monthly capacity:** ~20K general web queries; ~unlimited specialized.

**Coverage:** ~96% of use cases. Multiple redundant general web options. AI answer synthesis available.

---

#### $100/month — "Full Coverage" Architecture

**Feasible for: ≤5,000 searches/day**

```
Primary web:    Brave paid (~$50 = 16K queries, 50 QPS)
Google results: Serper (~$20 = 20K-66K queries at volume)
Semantic:       Exa paid (~$10 = 1,000+ semantic searches)
AI synthesis:   Perplexity Sonar ($10 for ~2K AI answers)
News:           NewsAPI ($10 = some paid tier) OR GNews
Everything:     All specialized free sources
```

**Monthly capacity:** ~30-80K general web queries; effectively unlimited specialized.

**Coverage:** ~99% of use cases. Could handle most production agent workloads.

---

## 4. Rate Limit Reality Check

### For 50-200 searches/day (~1,500-6,000/month)

This is our actual expected range for a personal AI agent. Here's what actually works:

| Source | 50/day (1,500/mo) | 200/day (6,000/mo) | Notes |
|--------|-----------------|-----------------|-------|
| **SearxNG (self-hosted)** | ✅ ✅ | ✅ ✅ | Your own rate limits — no concerns |
| **DuckDuckGo (unofficial)** | ✅ ⚠️ | ⚠️ ❌ | IP blocking at higher volume |
| **Brave free tier** | ✅ ✅ | ⚠️ ❌ | 2K/mo cap hit at ~67/day sustained |
| **Brave paid ($3/1K)** | ✅ ✅ | ✅ ✅ | 50 QPS — handles any burst |
| **Tavily free** | ✅ ✅ | ⚠️ ❌ | 1K/mo = ~33/day; rolls over monthly |
| **Exa free** | ✅ ✅ | ⚠️ ❌ | Same as Tavily (1K/mo cap) |
| **GitHub Code Search** | ✅ ✅ | ✅ ✅ | 10 req/min = 14,400/day |
| **Stack Exchange (key)** | ✅ ✅ | ✅ ✅ | 10K/day — fine |
| **HN Algolia** | ✅ ✅ | ✅ ✅ | 10K/hr — zero concern |
| **Bluesky** | ✅ ✅ | ✅ ✅ | Generous, no auth needed |
| **Semantic Scholar (key)** | ✅ ✅ | ✅ ✅ | 1 req/sec = 86K/day |
| **arXiv** | ✅ ✅ | ✅ ⚠️ | 1 req/3s = 28K/day; sustained may soft-limit |
| **Perplexity (PAYG)** | ✅ ✅ | ✅ ✅ | 50 RPM at Tier 0; costs money per query |

### Practical burst behavior

An AI agent doing research typically fires 3-10 searches in rapid succession (parallel or near-parallel). Impact:

- **Brave free (1 QPS):** 5 parallel searches → 4 get 429. Must serialize. This is the #1 current pain point.
- **Brave paid (50 QPS):** 5 parallel searches → all succeed. Problem solved.
- **Tavily:** No documented QPS limit on free tier (quota-based not rate-based) — parallel searches OK until monthly cap.
- **SearxNG self-hosted:** You control it. Can be configured for high concurrency.

### Verdict for 50-200 searches/day

**Free-only (with SearxNG self-hosted):** Fully sufficient.
- SearxNG handles all general web searches
- Specialized sources cover domain-specific needs
- DuckDuckGo works as emergency fallback (can get blocked)

**Without self-hosting:** Free tiers (Brave + Tavily + Exa) will be exhausted at the higher end (~200/day). One of them will cap out each month.

**Minimum paid recommendation at this volume:** $10/month for Brave paid tier (removes QPS limit, adds headroom).

---

## 5. Quality Matrix

### General Web Search Result Quality Ranking

| Source | Quality Rating | Index Type | Rich Snippets | Freshness | Notes |
|--------|--------------|-----------|--------------|-----------|-------|
| **Google (CSE)** | ⭐⭐⭐⭐⭐ | Own (Google) | ✅ Full | Hours | Sunsetting Jan 2027 |
| **Kagi** | ⭐⭐⭐⭐⭐ | Aggregated | ✅ Full | Hours | Most expensive, no SEO spam |
| **Serper** (Google results) | ⭐⭐⭐⭐⭐ | Google (scraped) | ✅ Full | Hours | Cheapest Google access |
| **SerpAPI** (Google) | ⭐⭐⭐⭐⭐ | Google (scraped) | ✅ Full | Hours | More expensive, multi-engine |
| **Brave Search** | ⭐⭐⭐⭐ | Own (30B pages) | ✅ Rich | Hours | Best independent index |
| **You.com** | ⭐⭐⭐⭐ | Own + crawl | ✅ + content | Hours | Full page extraction option |
| **Exa** | ⭐⭐⭐⭐ | Own (neural) | ⭐⭐ | Days | Semantic relevance > recency |
| **Perplexity** | ⭐⭐⭐⭐ | Own | ✅ (AI answers) | Hours | Synthesized, not raw results |
| **SearxNG** | ⭐⭐⭐⭐ | Aggregated (70+) | ⭐⭐⭐ (engine-dependent) | Hours | Mix of engine qualities |
| **Tavily** | ⭐⭐⭐ | Aggregated | ⭐⭐⭐ | Days | AI-optimized but not freshest |
| **DuckDuckGo (unofficial)** | ⭐⭐⭐ | Bing + own | ⭐⭐ | Days | Decent for non-time-sensitive |
| **Yandex** | ⭐⭐ (English) | Own (Yandex) | ⭐ | Hours | Good for Russian only |

### What "rich snippets" means for agents

- **Full rich snippets (⭐⭐⭐⭐):** Title, URL, description, thumbnail, page date, author, breadcrumbs, site links, knowledge panel results
- **Moderate (⭐⭐⭐):** Title, URL, snippet, sometimes date — adequate for most agent use
- **Bare (⭐⭐):** Title + URL only, or very short snippets — may require additional web_fetch calls

**Metadata comparison — Brave vs Tavily vs Exa:**

- **Brave:** `title`, `url`, `description`, `age` (publication date), `extra_snippets[]`, `favicon`, `thumbnail`, `language`, `deep_results[]`, schema-enriched objects
- **Tavily:** `title`, `url`, `content` (snippet), `score` (relevance), optional full raw_content
- **Exa:** `title`, `url`, `publishedDate`, `author`, `score`, `text` (via contents endpoint), highlights, summary

**Winner for metadata density:** Brave > Exa > Tavily

### Freshness by source

| Source | How fresh? |
|--------|-----------|
| HN Algolia | Minutes (Algolia indexes HN in near-real-time) |
| Bluesky API | Minutes (public AppView) |
| Brave Search | Hours (100M+ daily updates claimed) |
| Google/Serper | Hours (Googlebot is continuous) |
| Perplexity | Hours-days |
| Wikipedia | Hours (MediaWiki updates immediately) |
| SearxNG | Depends on upstream engines (hours for Google/Bing lanes) |
| Tavily | Days (lagging aggregated crawl) |
| Exa | Days (embedding index rebuilt periodically) |
| Semantic Scholar | Days-weeks (papers indexed within days of publication) |
| arXiv | Hours of posting (preprints appear same day) |

### Quality by use case

**General web research:**
Google (via Serper) > Brave > SearxNG > Tavily > DuckDuckGo

**Time-sensitive/news:**
Google > Brave > Perplexity > SearxNG (with news lane enabled) > HN (tech news only)

**Technical/developer queries:**
Stack Overflow API > GitHub Code Search > HN Algolia > Brave > SearxNG

**Ethereum-specific:**
ethresear.ch + Ethereum Magicians >> Brave >> SearxNG

**Academic/research:**
Semantic Scholar > arXiv > CrossRef > Google Scholar (no API) > Brave

**Social/community sentiment:**
Bluesky > HN > Reddit (OAuth2) > (Twitter/X — prohibitively expensive)

---

## 6. Recommendation Matrix

### By Use Case

#### General Web Search

| Budget | Primary | Secondary | Fallback | Expected Quality |
|--------|---------|-----------|---------|-----------------|
| $0 | SearxNG (self-hosted) | DuckDuckGo (unofficial) | — | ⭐⭐⭐⭐ (multi-engine) |
| $10 | Brave paid | SearxNG | DuckDuckGo | ⭐⭐⭐⭐ (independent index) |
| $50+ | Brave paid | Serper (Google results) | Exa (semantic) | ⭐⭐⭐⭐⭐ (multi-provider) |

**Free → Paid path:** SearxNG self-hosted → add Brave paid at $10/mo when QPS or monthly caps become limiting.

---

#### Code Search

| Priority | Source | Auth | Cost |
|----------|--------|------|------|
| Primary | GitHub Code Search | PAT (free) | $0 |
| Augment | grep.app (unofficial) | None | $0 |
| Advanced | GitHub Code Search (GraphQL) | PAT (free) | $0 |

**Notes:** For code search, paid options offer almost no advantage over GitHub's free API. The 10 req/min limit rarely matters. GitHub PAT is the correct answer here.

---

#### Academic / Research

| Priority | Source | Auth | Cost |
|----------|--------|------|------|
| Primary | Semantic Scholar API | Optional (free key) | $0 |
| Preprints | arXiv API | None | $0 |
| Citations/DOI | CrossRef API | None (polite pool) | $0 |
| Google Scholar | SerpAPI or use Semantic Scholar | Paid | $50+/mo |

**Free → Paid path:** Semantic Scholar + arXiv handles 95% of academic needs for free. Only add paid (SerpAPI for Google Scholar) if you specifically need GS citation metrics.

---

#### Social / Community Discourse

| Priority | Source | Auth | Cost |
|----------|--------|------|------|
| Primary | Bluesky API | None | $0 |
| Tech community | HN Algolia | None | $0 |
| Reddit | Reddit OAuth2 | Free developer app | $0 |
| Twitter/X | Skip | Expensive | $200+/mo |

**Notes:** Twitter/X is simply not viable at any reasonable budget for an AI agent. Bluesky is the best free alternative. HN covers tech discussions better than Twitter for most technical queries.

---

#### Ethereum / Protocol Specific

| Priority | Source | Auth | Cost |
|----------|--------|------|------|
| Research forum | ethresear.ch Discourse API | None | $0 |
| EIP governance | Ethereum Magicians Discourse | None | $0 |
| EIP text | GitHub Code Search (`repo:ethereum/EIPs`) | PAT | $0 |
| Spec discussions | GitHub Issues (`repo:ethereum/consensus-specs`) | PAT | $0 |
| Lodestar code | GitHub Code Search (`repo:ChainSafe/lodestar`) | PAT | $0 |
| General Ethereum | Brave (Ethereum topics trend well) | Free key | $0-$3/1K |

**Paid upgrade:** Unnecessary. All Ethereum sources are free and excellent.

---

#### News / Current Events

| Priority | Source | Auth | Cost |
|----------|--------|------|------|
| General news | SearxNG news lane | None | $0 (self-hosted) |
| Crypto/tech news | HN Algolia + Bluesky | None | $0 |
| Curated sources | RSS feeds (Ethereum blog, client blogs) | None | $0 |
| Full news coverage | NewsAPI (100/day dev) / GNews | Free key | $0 (limited) |
| Production news | NewsAPI Business | Paid | $449/mo |

**Notes:** NewsAPI's production tier is absurdly expensive. For AI agent news use cases, RSS aggregation + HN + Bluesky covers most tech/Ethereum news very well.

---

### The "Sweet Spot" Configuration

For a personal AI agent doing 50-200 searches/day with mixed use cases (general research, code, Ethereum, academic):

#### Recommended Configuration (< $15/month)

**General Web:**
- SearxNG (self-hosted, Docker, 2GB RAM) — primary, zero query cost
- Brave paid tier (~$10/mo, ~3,300 queries, 50 QPS) — API-grade when SearxNG is unavailable or for structured metadata

**Code:**
- GitHub Code Search with PAT — free, definitive

**Academic:**
- Semantic Scholar API (free key) — primary
- arXiv API (no auth) — preprints
- CrossRef (no auth) — DOI/citations

**Ethereum-specific:**
- ethresear.ch + Ethereum Magicians (Discourse JSON, no auth)
- GitHub search on ethereum/* repos (PAT)

**Social/Community:**
- HN Algolia (no auth)
- Bluesky API (no auth)

**Reference:**
- Wikipedia API (no auth)
- Stack Exchange API (free key)

**Packages:**
- npm + crates.io search (no auth)

**Free tier buffers (sign up once, use when needed):**
- Tavily (1,000/mo) — overflow or LangChain-native workflows
- Exa (1,000/mo) — semantic search queries
- You.com ($100 one-time) — evaluation + full content extraction

#### Cost estimate

| Item | Monthly Cost | Queries Covered |
|------|-------------|-----------------|
| SearxNG server (shared) | ~$5 (VPS RAM) | Unlimited |
| Brave paid tier | ~$10 | ~3,300 web queries |
| Everything else | $0 | Effectively unlimited |
| **Total** | **~$15/mo** | **Full coverage** |

---

## Summary Decision Table

| Question | Answer |
|---------|--------|
| Can we do this for $0? | Yes, if self-hosting SearxNG is acceptable |
| What's the minimum paid spend worth it? | ~$10/mo (Brave paid, removes QPS bottleneck) |
| Should we use multiple providers? | Yes — route by domain, not just one universal search |
| What's the fastest win from our current broken state? | Upgrade Brave to paid tier → fixes 429 errors |
| What about Google CSE? | Skip — sunsetting Jan 2027, not worth investing |
| What about Kagi? | Only if quality is the #1 priority and budget is available; $25/1K is hard to justify |
| Is self-hosting SearxNG really viable? | Yes — Docker, 2GB RAM, 30min setup, then zero marginal cost forever |
| What do we lose by not paying at all? | QPS limits on Brave, fragile DuckDuckGo, possible monthly cap hits — but SearxNG patches these gaps |

---

*Analysis by Lodekeeper subagent — 2026-03-06*
