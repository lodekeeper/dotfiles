# Web Search Engine APIs — Comprehensive Research

*Last updated: 2026-03-06*

## Summary Table

| API | Free Tier | Price (per 1K queries) | Own Index? | Best For | SDK |
|-----|-----------|----------------------|------------|----------|-----|
| **Google CSE** | 100/day | $5 | ✅ Google | Legacy, sunsetting Jan 2027 | REST |
| **Bing** | ❌ Retired Aug 2025 | N/A | ✅ Bing | N/A (dead) | — |
| **DuckDuckGo** | Unlimited (unofficial) | Free (scraping) | ✅ Bing+own | Quick free searches | Python (`duckduckgo-search`) |
| **Yandex** | Free tier (limited) | Usage-based (Yandex Cloud) | ✅ Yandex | Russian/Turkish web | REST (XML/JSON) |
| **Mojeek** | Trial (limited) | GBP-denominated, contact | ✅ Own crawler | Privacy, independent index | REST (JSON/XML) |
| **Brave Search** | $5/mo free credits (~1.7K queries) | ~$3 | ✅ Own (30B+ pages) | Best value, independent index | REST |
| **You.com** | $100 free credits | ~$3-5 (varies) | ✅ Own | RAG, AI agents, content extraction | Python, TypeScript |
| **Kagi** | None (requires subscription) | $25 | ✅ Aggregated | Highest quality, no SEO spam | REST |
| **Tavily** | 1,000 credits/mo | ~$4-8 (credit-based) | ❌ Aggregated | AI agents, RAG pipelines | Python, JS, REST |
| **Exa** | 1,000 req/mo | $7 (search), $12 (agentic) | ✅ Own embeddings | Semantic/neural search | Python, JS, REST |
| **Perplexity** | Tier 0 (50 RPM) | $5 (Search API) | ✅ Own | AI-grounded answers | REST (OpenAI-compatible) |
| **Serper** | 2,500 queries (one-time) | $0.30-$2 | ❌ Scrapes Google | Cheapest Google results | REST |
| **SerpAPI** | 100/mo | ~$50/5K queries | ❌ Scrapes many engines | Multi-engine, structured data | Python, Ruby, Node, REST |
| **WebSearchAPI.ai** | 100/mo | $6 (Developer) | ❌ Google-powered | Clean pre-extracted content | REST |

---

## 1. Google — Custom Search JSON API

### Status: ⚠️ SUNSETTING — Discontinued for new customers, retiring January 1, 2027

- **Endpoint:** `GET https://www.googleapis.com/customsearch/v1`
- **Auth:** API Key (via Google Cloud Console)
- **Setup:** Requires creating a Programmable Search Engine (cx ID) + API key

### Free Tier
- 100 queries/day (no charge)
- Max 10 results per query
- No commercial use restrictions explicitly, but limited

### Paid Tier
- $5 per 1,000 queries (up to 10K queries/day)
- Must enable billing in Google Cloud Console

### Result Quality
- Google-quality results (the gold standard)
- Rich snippets, metadata, structured data
- 10 results per page, paginated
- Can search entire web or specific sites

### Integration
- REST API (JSON response)
- No official SDK (use Google API client libraries)
- npm: `googleapis` (generic Google API client)
- Python: `google-api-python-client`

### Strengths
- Unmatched index quality and freshness
- Rich result types (knowledge graph, featured snippets)
- Site-restricted or whole-web search

### Weaknesses
- **Being discontinued** — no new customers, retiring Jan 1, 2027
- Low free tier (100/day)
- Requires creating a Programmable Search Engine
- Results can differ from regular Google Search
- No replacement announced (Google pushing Vertex AI Search instead)

---

## 2. Bing — Web Search API (Azure Cognitive Services)

### Status: ❌ RETIRED — Shut down August 11, 2025

- **What happened:** Microsoft retired all Bing Search APIs (Web, Image, Video, News, Custom) on August 11, 2025. Both free and paid tiers were decommissioned.
- **Replacement:** "Grounding with Bing Search" via Azure AI Agents — but this does NOT provide raw search results. It processes results through an LLM and returns synthesized answers with citations.

### Historical Pricing (for reference)
- S1: $25 per 1,000 transactions
- S6: $15 per 1,000 transactions (high volume)
- New "Grounding with Bing": $35 per 1,000 transactions (40-483% more expensive)

### Why It Matters
- Was the #2 search API by index size
- Many services (including DuckDuckGo, Yahoo) depend on Bing's index
- The replacement doesn't expose raw results — fundamentally different product

### Verdict
- **Not viable.** Dead API. Use Brave Search, Serper, or SerpAPI instead.

---

## 3. DuckDuckGo — Instant Answer API + Unofficial Libraries

### Official API
- **Endpoint:** `GET https://api.duckduckgo.com/`
- **Auth:** None required
- **Response:** JSON
- **Limitation:** This is the **Instant Answer API** only — returns topic summaries, definitions, related topics. It does NOT return web search results (organic links).

### Unofficial: `duckduckgo-search` (Python)
- **Package:** `pip install duckduckgo-search`
- **Author:** deedy5 (GitHub)
- **No API key required** — scrapes DuckDuckGo's HTML/JS search interface
- **Capabilities:** Text, images, news, videos, maps, translate, suggestions
- **Rate limits:** Undocumented, but aggressive use gets IP-blocked. Practical limit ~20-50 req/min.

### Free Tier
- Instant Answer API: Unlimited, no key needed
- `duckduckgo-search`: Unlimited (but may get rate-limited/blocked)

### Result Quality
- DuckDuckGo uses Bing's index + their own crawler
- Snippets are decent but shorter than Google's
- No structured data or rich snippets
- Good for quick lookups, privacy-focused searches

### Integration
- Official API: Simple REST, JSON — but limited to instant answers
- `duckduckgo-search`: Python only, `DDGS()` class
- No official npm package for web search results

### Strengths
- Completely free, no API key needed
- Privacy-focused (no tracking)
- Good enough for many AI agent use cases
- Python library is well-maintained

### Weaknesses
- **No official web search API** — only Instant Answer API
- Unofficial library = can break without notice
- Rate limiting is unpredictable
- Results depend partly on Bing's index (which may be affected by Bing API retirement)
- No SLA or guarantees

---

## 4. Yandex — Search API

### API Access
- **Platform:** Yandex Cloud (requires Yandex Cloud account)
- **Endpoint:** REST API via Yandex Cloud Search API service
- **Auth:** Yandex Cloud IAM token + folder ID
- **Response:** XML format (historically), JSON available on newer versions

### Free Tier
- Part of Yandex Cloud free tier (limited queries included)
- Exact free quota unclear — documentation behind CAPTCHA

### Pricing
- Usage-based via Yandex Cloud billing
- Historically: free for limited queries per day (based on domain verification)
- Paid plans via Yandex Cloud metering

### Availability Outside Russia
- **Available globally** via Yandex Cloud (which operates internationally)
- Best for: Russian-language search, Turkish search, CIS countries
- International English search quality is significantly inferior to Google/Bing/Brave
- Yandex Cloud has EU data residency options

### Result Quality
- Excellent for Russian/Turkish content
- Mediocre for English-language web
- Own crawler and index (independent from Google/Bing)

### Integration
- REST API
- Yandex Cloud SDKs (Python, Go, Java, Node.js)
- Complex setup: Yandex Cloud account → service account → API key → folder

### Strengths
- Independent index (not Google/Bing derivative)
- Best-in-class for Russian-language search
- Can be useful for geo-diversity in search results

### Weaknesses
- Aggressive CAPTCHA on documentation pages
- Complex setup via Yandex Cloud
- Poor English-language result quality
- Geopolitical concerns (Russian company)
- Documentation quality varies

---

## 5. Mojeek — Independent Search API

### API Access
- **Endpoint:** `GET https://api.mojeek.com/search`
- **Auth:** API key (obtained after signing up)
- **Response:** JSON or XML

### Free Tier
- Free trial available (limited queries, contact required)
- No self-serve free tier like Brave or Tavily

### Pricing (GBP-denominated)
| Plan | QPS | Daily Limit | Results/Request | Storage | AI Use |
|------|-----|-------------|-----------------|---------|--------|
| Basic | 1 | 2,000 | Up to 10 | ✅ | ✅ |
| Standard | 5 | 100,000 | Up to 20 | ✅ | ✅ |
| Professional | 10 | 400,000 | Up to 40 | ✅ | ✅ |
| Enterprise | Custom | No limit | Up to 100 | ✅ | ✅ |

- Prices in GBP (not publicly listed on website — "enquire now" model)
- Pay-as-you-go credit system via Stripe

### Result Quality
- Own crawler and index (billions of pages) — truly independent
- No Bing/Google dependency
- Snippets: URL, title, query-dependent snippets
- Custom plans can access: authority scores, keyword matching scores, semantic matching scores
- Customizable snippet length, safe search, site clustering

### Integration
- Simple REST API (GET request with API key)
- JSON or XML response
- No official SDK (simple enough to use with any HTTP client)

### Strengths
- **Truly independent index** — not Google, not Bing, fully their own crawler
- Privacy-focused (UK-based company)
- AI/ML usage explicitly allowed on all plans
- Can re-rank results freely
- Can combine with other search engines' results
- No ad-tech entanglement

### Weaknesses
- Opaque pricing (must enquire)
- Smaller index than Google/Bing/Brave
- No official SDK
- Free trial requires manual contact
- English-focused (less coverage for non-English languages)

---

## 6. Brave Search API ⭐ (Currently in use)

### API Access
- **Endpoint:** `GET https://api.search.brave.com/res/v1/web/search`
- **Auth:** API key (via Brave Search API dashboard)
- **Response:** JSON

### Free Tier
- $5 in free credits every month (auto-applied)
- At $3/1K queries, this is ~1,667 free queries/month
- **Rate limit on free plan: 1 query/second, 2,000 queries/month**
- Credit card required (anti-fraud measure)

### Paid Tier
- ~$3 per 1,000 queries (credit-based)
- Answers endpoint: $4 per 1,000 requests + $5 per million tokens
- Enterprise: Custom pricing, zero data retention, custom agreements
- 50 QPS capacity on paid plans

### Current Limitations (what we experience)
- **Free tier rate limit: 1 QPS** — frequently hit 429 errors
- Free tier quota: 2,000/month
- No full-page content extraction (snippets only, up to 5 extra snippets)
- Answers endpoint costs extra

### Result Quality
- **Own independent index** (30B+ pages, 100M+ updates/day)
- On par with Google/Bing in blinded tests (per Brave's claims)
- Rich metadata: favicons, thumbnails, page age, deep results
- Up to 5 extra alternate snippets per result
- Goggles: custom re-ranking and filtering
- Schema-enriched results (movies, recipes, wikis)

### Available Endpoints
- Web Search, Image Search, Video Search, News Search
- Suggest (autocomplete), Spellcheck
- Answers (AI-generated, citation-grounded)
- LLM Context endpoint (optimized for AI consumption)

### Integration
- REST API (simple GET/POST)
- No official SDK, but trivially consumed by any HTTP client
- Available on AWS Marketplace
- SOC 2 Type II attested

### Strengths
- **Only independent index at scale** besides Google
- Best price/quality ratio for independent search
- Privacy-first (zero data retention option)
- Goggles for custom result filtering
- LLM-optimized context endpoint
- MCP integration leader (Claude MCP)

### Weaknesses
- **Free tier QPS is very low** (1/sec) — causes 429s in our setup
- No full-page content extraction (just snippets)
- Results can lean towards privacy/tech community content
- Less coverage for non-English languages vs Google
- Answers endpoint is separate cost

---

## 7. You.com — Search API

### API Access
- **Endpoint:** `GET https://ydc-index.io/v1/search` (Search), `POST https://ydc-index.io/v1/contents` (Contents), `POST https://api.you.com/v1/research` (Research)
- **Auth:** API key via `X-API-Key` header
- **Response:** JSON

### Free Tier
- **$100 in complimentary credits** on signup (no credit card required)
- Very generous for evaluation

### Pricing
- Search API: Pay-per-use (credit-based)
- Contents API: Separate pricing
- Research API: Separate pricing
- Exact per-query pricing not publicly documented (credit-based system)

### Three Core APIs
1. **Search API** — Structured web/news results, LLM-ready JSON. Supports `livecrawl` parameter for full-page content.
2. **Contents API** — Give URLs, get clean Markdown/HTML. Like a scraping service.
3. **Research API** — Multi-search synthesized answers with citations. Configurable depth (`lite` to `exhaustive`).

### Result Quality
- Own index + web crawling
- `livecrawl` mode: fetches full page content per result as clean Markdown
- Structured results: URL, title, description, snippets, page age, authors, favicons
- News search included

### Integration
- **Python SDK:** `pip install youdotcom`
- **TypeScript SDK:** `@youdotcom-oss/sdk`
- REST API
- MCP Server available
- LangChain, LlamaIndex, Vercel AI SDK, n8n integrations
- OpenAI GPT OSS integration (powers default web browsing)

### Strengths
- **$100 free credits** — most generous free tier
- Three complementary APIs (search, contents, research)
- `livecrawl` for full-page content extraction alongside search
- Excellent SDK support (Python + TypeScript)
- Wide integration ecosystem
- Citation tracking built-in

### Weaknesses
- Pricing not transparently published (credit-based)
- Relatively new API — less battle-tested at scale
- Contents API pricing may add up for heavy content extraction
- Research API latency can be high for complex queries

---

## 8. Kagi — Search API

### API Access
- **Endpoint:** `GET https://kagi.com/api/v0/search`
- **Auth:** API key (requires Kagi subscription — Business or higher plan)
- **Response:** JSON

### Free Tier
- **None.** Requires a Kagi subscription to access the API.
- Kagi subscription: $5/mo (Starter, 300 searches), $10/mo (Professional, unlimited)

### Pricing
- **$25 per 1,000 queries** (2.5¢ per search)
- On top of the Kagi subscription cost
- This is among the most expensive options

### Result Quality
- **Highest quality search results** — Kagi is widely praised for relevance
- Aggregates from multiple sources (Google, Brave, Mojeek, Yandex, own crawler)
- No SEO spam, no ads, no tracking
- Personalization features (domain blocking, boosting, etc.)
- Lenses (topical filters)

### Integration
- REST API (simple GET)
- No official SDK
- Straightforward JSON response

### Strengths
- **Best result quality** — widely regarded as the best search engine for quality
- No SEO spam filtering
- Privacy-focused (no tracking, no ads)
- Personalized ranking (block/boost domains)
- Good for research and technical queries

### Weaknesses
- **Most expensive** option ($25/1K + subscription)
- Requires Kagi subscription (can't just use API standalone)
- No free tier
- No official SDK
- Small user base means less community support
- API is secondary to their consumer search product

---

## 9. Tavily — AI-Focused Search API

### API Access
- **Endpoint:** `POST https://api.tavily.com/search` (Search), `POST https://api.tavily.com/extract` (Extract)
- **Auth:** API key
- **Response:** JSON

### Free Tier
- **1,000 API credits/month** (no credit card required)
- 1 credit = 1 basic search, 2 credits = 1 advanced search
- Free for students

### Pricing
| Plan | Credits/mo | Price |
|------|-----------|-------|
| Researcher (Free) | 1,000 | $0 |
| Pay-as-you-go | Unlimited | $0.008/credit |
| Project | 4,000-100,000 | $24-$500/mo |
| Enterprise | Custom | Custom |

- Credits don't roll over
- Basic search: 1 credit, Advanced search: 2 credits
- Extract (page content): separate credit cost

### Result Quality
- Aggregated results (uses multiple search engines underneath)
- AI-optimized: returns relevance-scored results
- Can return raw content from pages
- Designed specifically for RAG pipelines
- Topic-level search depth control

### Integration
- REST API
- **Python SDK:** `pip install tavily-python`
- **JavaScript SDK:** `npm install tavily`
- LangChain integration (official)
- CrewAI, AutoGPT integrations
- MCP integration

### Strengths
- **Purpose-built for AI agents** — most popular in the AI agent ecosystem
- 1,000 free credits/month (good for prototyping)
- Content extraction included
- LangChain-native integration
- Simple API (one endpoint does it all)
- Advanced search mode for deeper results

### Weaknesses
- No own index — aggregated from other engines
- Credits don't roll over
- Advanced search uses 2 credits (effectively doubles cost)
- $0.008/credit PAYG can add up quickly at scale
- Less customization than Brave or Kagi
- Occasional stale results compared to Google/Brave

---

## 10. Exa (formerly Metaphor) — Neural/Semantic Search API

### API Access
- **Endpoints:**
  - `POST https://api.exa.ai/search` — Embedding-based search
  - `POST https://api.exa.ai/contents` — Get page contents
  - `POST https://api.exa.ai/findSimilar` — Find similar pages to a URL
  - `POST https://api.exa.ai/answer` — Direct answers with citations
  - `POST https://api.exa.ai/research` — Autonomous deep research
- **Auth:** API key via header
- **Response:** JSON

### Free Tier
- **1,000 free requests/month**

### Pricing
| Operation | Cost |
|-----------|------|
| Search (1-10 results) | $7 per 1,000 requests |
| Search (additional results beyond 10) | +$1 per additional result |
| Agentic Search | $12 per 1,000 requests |
| Agentic Search + reasoning | +$3 per 1,000 |
| Contents | $1 per 1,000 pages |
| Answer | $5 per 1,000 answers |
| Research (agent operations) | $5 per 1K ops |
| Research (page reads) | $5 per 1K reads |
| Research reasoning tokens | $5 per 1M tokens |

### Result Quality
- **Embedding-based search** — understands semantic meaning, not just keywords
- Can search by meaning ("articles about X that have a skeptical tone")
- Real-time crawled index
- Contents endpoint provides clean, parsed HTML/text
- Find-similar is unique: "pages like this URL"
- Structured output support on Agentic Search

### Integration
- **Python SDK:** `pip install exa-py`
- **TypeScript/JS SDK:** available
- REST API
- LangChain, LlamaIndex integrations
- SOC 2 compliant, zero data retention option

### Strengths
- **Unique semantic/neural search** — no other API does this
- Find-similar is powerful for discovery
- Agentic search for multi-step research
- Clean content extraction included
- Good free tier (1K/mo)
- Enterprise-grade security

### Weaknesses
- More expensive than keyword-based search APIs ($7/1K vs $3/1K Brave)
- Semantic search is great for discovery but can miss keyword-exact matches
- Smaller index than Google/Brave
- Newer company — less proven at massive scale
- Complex pricing (multiple dimensions)

---

## 11. Perplexity — Search API & Sonar API

### API Access
- **Search API:** `POST https://api.perplexity.ai/search`
- **Sonar API:** `POST https://api.perplexity.ai/chat/completions` (OpenAI-compatible)
- **Auth:** API key (`Authorization: Bearer KEY`)
- **Response:** JSON (OpenAI-compatible for Sonar)

### Three Products
1. **Search API** — Raw web search results with filtering ($5/1K requests)
2. **Sonar API** — AI-grounded answers using web search (token + request pricing)
3. **Agent API** — Third-party model access with web search tools

### Free Tier
- Tier 0: No minimum spend required
- Sonar: 50 RPM, Search: 50 QPS
- No free credits — pay-as-you-go from first query

### Pricing
| Product | Price |
|---------|-------|
| **Search API** | $5 per 1,000 requests |
| **Sonar** | $1/1M input + $1/1M output + $5-12/1K requests (context-dependent) |
| **Sonar Pro** | $3/1M input + $15/1M output + $6-14/1K requests |
| **Sonar Reasoning Pro** | $2/1M input + $8/1M output + $6-14/1K requests |
| **Sonar Deep Research** | $2/1M input + $8/1M output + citations + reasoning tokens + search queries |
| **Agent API web_search tool** | $0.005 per invocation |
| **Agent API fetch_url tool** | $0.0005 per invocation |

### Tier Progression (rate limits scale with spend)
| Tier | Cumulative Spend | Sonar RPM |
|------|-----------------|-----------|
| Tier 0 | $0 | 50 |
| Tier 1 | $50+ | 150 |
| Tier 2 | $250+ | 500 |
| Tier 3 | $500+ | 1,000 |
| Tier 4 | $1,000+ | 4,000 |
| Tier 5 | $5,000+ | 4,000 |

### Result Quality
- Own search index + web crawling
- Sonar models provide grounded, cited answers
- Deep Research does multi-step investigation
- High-quality citations with source URLs
- Search context size control (low/medium/high)

### Integration
- REST API (OpenAI SDK compatible for Sonar)
- Python: `pip install perplexity` (official SDK)
- OpenAI Python/JS SDK compatible
- MCP integration

### Strengths
- **AI-native search answers** — not just links, but grounded responses
- OpenAI SDK compatible (drop-in replacement)
- Multiple depth levels (basic to deep research)
- Dedicated Search API for raw results
- Growing ecosystem

### Weaknesses
- Complex pricing (tokens + requests + context size)
- No free credits
- Raw Search API is $5/1K (expensive for just search results)
- Sonar quality can vary by topic
- Rate limits tied to cumulative spend

---

## 12. Additional APIs Discovered

### Serper.dev — Google SERP API
- **What:** Scrapes Google search results and returns structured JSON
- **Endpoint:** `POST https://google.serper.dev/search`
- **Auth:** API key
- **Free tier:** 2,500 queries (one-time, not monthly)
- **Pricing:** $50 for 50K queries ($1.00/1K), down to $0.30/1K at higher volumes
- **Speed:** 1-2 seconds per query (among the fastest)
- **Strengths:** Cheapest Google results, fast, simple API, pay-as-you-go
- **Weaknesses:** Scraping-based (can break), no own index, depends on Google
- **SDKs:** REST API, LangChain integration

### SerpAPI — Multi-Engine SERP API
- **What:** Scrapes Google, Bing, Yahoo, Yandex, DuckDuckGo, Baidu, and more
- **Endpoint:** `GET https://serpapi.com/search`
- **Auth:** API key
- **Free tier:** 100 queries/month
- **Pricing:** $75/mo (5K searches), $150/mo (15K), $300/mo (30K), up to $250/mo (50K) enterprise
- **Strengths:** Most engines supported (~30+), structured data, Google AI Overview/Mode
- **Weaknesses:** Expensive per query, scraping-based, slower than Serper
- **SDKs:** Python, Ruby, Node.js, Java, Go, PHP, Rust, C#

### WebSearchAPI.ai
- **What:** Google-powered search with pre-extracted content
- **Endpoint:** REST API
- **Free tier:** 100 searches/month
- **Pricing:** $30/mo (5K searches), $189/mo (50K), enterprise custom
- **Strengths:** Pre-extracted clean content, RAG-optimized, Google quality
- **Weaknesses:** Small company, limited track record

### Felo Search
- **What:** Budget AI-driven search with multilingual support
- **Pricing:** $14.99/mo premium, free tier available
- **Strengths:** Very affordable, strong multilingual, AI summarization
- **Weaknesses:** Newer, fewer integrations

---

## Recommendations for Our Use Case

### Current Setup
We use **Brave Search API** (free tier) via OpenClaw's built-in `web_search` tool. Main pain point: **1 QPS rate limit causes frequent 429 errors** during research sessions.

### Best Options to Augment/Replace

#### For Cost-Effective Web Search
1. **Brave Search (paid)** — Upgrade from free to paid. $3/1K queries, 50 QPS. Best independent index. Already integrated.
2. **Serper.dev** — $0.30-$1/1K for Google results. Cheapest per-query. Good for bulk research.
3. **DuckDuckGo (unofficial)** — Free, no API key. Good backup/fallback. Risk of breakage.

#### For AI Agent Integration
1. **Tavily** — 1,000 free/month, purpose-built for AI agents, LangChain native.
2. **Exa** — 1,000 free/month, semantic search is unique. Best for discovery/research.
3. **You.com** — $100 free credits, three complementary APIs, content extraction.

#### For Highest Quality
1. **Kagi** — Best result quality, but expensive ($25/1K + subscription).
2. **Google CSE** — Still the gold standard, but sunsetting Jan 2027.

#### For Independent/Privacy-First
1. **Brave Search** — Best independent index at scale.
2. **Mojeek** — Truly independent (own crawler), privacy-focused, but opaque pricing.

### Recommended Architecture
A multi-provider search skill should:
1. **Primary:** Brave Search (paid tier, ~$3/1K, independent index, 50 QPS)
2. **Fallback/Augment:** Serper ($0.30-$1/1K, Google results when Brave misses)
3. **Semantic search:** Exa (neural search for discovery, find-similar)
4. **Deep research:** Perplexity Sonar or You.com Research API
5. **Free tier for dev/testing:** DuckDuckGo (`duckduckgo-search` library)

Cost estimate for moderate agent use (~10K searches/month):
- Brave only: ~$30/month
- Brave + Serper fallback: ~$20-25/month
- Multi-provider (Brave + Serper + Exa): ~$40-50/month
