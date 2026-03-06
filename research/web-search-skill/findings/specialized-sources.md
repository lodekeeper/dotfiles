# Specialized Search Sources Research

*Compiled: 2026-03-06*

Sources that find content general search engines miss. For each: API details, auth, free tier limits, unique value, and integration complexity.

---

## 1. Code Search

### 1.1 GitHub Code Search API (REST)

- **Endpoint:** `GET https://api.github.com/search/code?q={query}`
- **Auth:** Personal Access Token required (code search endpoint *requires* authentication)
- **Rate Limits:**
  - Authenticated: **10 requests/minute** for code search (lower than other search endpoints which get 30/min)
  - Unauthenticated: Not available for code search
  - Max **1,000 results** per query
  - Queries limited to **4,000 repos** matching filters
  - Query max **256 characters** (excluding qualifiers), max 5 `AND`/`OR`/`NOT` operators
- **Result Quality:** Excellent for finding specific function names, error strings, import patterns across all public GitHub repos. Supports qualifiers: `repo:`, `org:`, `language:`, `path:`, `filename:`, `extension:`, `in:file,path`
- **Unique Content:** Searches the full text of all public GitHub repositories (hundreds of millions). No other free service covers this scope.
- **Integration Complexity:** ⭐ Very Low — simple REST GET with token header. JSON response with file path, repo, text matches with highlights.
- **Docs:** https://docs.github.com/en/rest/search/search#search-code

### 1.2 GitHub Code Search (GraphQL / New Code Search)

- **Endpoint:** GraphQL at `POST https://api.github.com/graphql` — but the new code search (cs.github.com) does NOT have a public API yet
- **Auth:** PAT with `repo` scope
- **Rate Limits:** GraphQL has a point-based system (5,000 points/hour). No dedicated code search query in GraphQL schema.
- **Result Quality:** The web-based code search at github.com/search is significantly better than the REST API (regex support, symbol search, exact string matching) but lacks API access.
- **Unique Content:** Same as REST but better ranking/regex on web UI
- **Integration Complexity:** ⭐⭐ Medium — GraphQL is more complex, and code search specifically is limited
- **Recommendation:** Use REST API for programmatic access; web UI for complex searches. Watch for API expansion.

### 1.3 Sourcegraph

- **Status:** ⚠️ **No longer publicly available.** Sourcegraph went closed-source in Aug 2024. The public sourcegraph.com code search was discontinued.
- **Self-hosted:** Requires enterprise license for most features
- **API:** GraphQL API at `/.api/graphql` (requires Sourcegraph instance + access token)
- **Alternative:** [Sourcebot](https://github.com/sourcebot-dev/sourcebot) — open-source Sourcegraph alternative (self-hosted, uses Zoekt)
- **Integration Complexity:** ⭐⭐⭐⭐ High — requires self-hosting or enterprise subscription
- **Recommendation:** Skip unless self-hosting is an option. Use GitHub Code Search or grep.app instead.

### 1.4 grep.app (by Vercel)

- **Endpoint:** `GET https://grep.app/api/search?q={query}` (undocumented/unofficial)
- **Auth:** None required (public)
- **Rate Limits:** Undocumented; community tools report ~1000 max results per query. No official API docs.
- **Result Quality:** Excellent for quick regex/literal searches across ~1M+ public GitHub repos. Supports: regex, case-sensitive, repo filter, path filter, language filter.
- **Unique Content:** Fast, instant-result code search. Returns first 1000 matches. Great for finding usage patterns, error messages, specific function calls.
- **Integration Complexity:** ⭐⭐ Low-Medium — API is undocumented, may break. Several MCP servers and CLI tools wrap it (e.g., `grep_app_mcp`, `grepgithub.py`). Returns JSON with repo, file path, line matches.
- **Caveats:** Unofficial API. No SLA. May get rate-limited without warning. Covers ~1M repos (not all of GitHub).
- **Recommendation:** Great for quick searches. Don't rely on it for production. Use alongside GitHub Code Search.

---

## 2. Discussion Forums

### 2.1 Reddit API (Official)

- **Endpoint:** `GET https://oauth.reddit.com/search?q={query}` (and `/r/{subreddit}/search`)
- **Auth:** OAuth2 required. Register app at https://www.reddit.com/prefs/apps
- **Rate Limits:**
  - OAuth authenticated: **100 requests/minute** (was 60, increased)
  - Unauthenticated: **10 requests/minute**
  - Free tier for non-commercial use with <100 QPS
  - As of Nov 2025: new "Responsible Builder Policy" — apps need approval for API access
- **Result Quality:** Decent for finding discussions, experiences, opinions. Reddit search is notoriously mediocre at relevance ranking. Sorting options: relevance, hot, top, new, comments.
- **Unique Content:** Massive trove of real human discussions, opinions, experiences, troubleshooting. Unmatched for "has anyone tried X" or "what's the best Y" queries.
- **Integration Complexity:** ⭐⭐ Medium — OAuth2 flow adds setup overhead. Use PRAW (Python) for easiest integration.
- **Docs:** https://www.reddit.com/dev/api/

### 2.2 Pushshift / Alternatives (Reddit Archive)

- **Status:** ⚠️ **Pushshift is effectively dead** for public use as of mid-2023. Reddit revoked access.
- **Alternatives:**
  - **Arctic Shift:** Community archive, limited availability
  - **Unddit/Reveddit:** Web-only, no API
  - **PullPush.io:** Some Pushshift data mirrored, unreliable
- **Recommendation:** Use official Reddit API. For historical data, look for academic data dumps on archive.org or academic datasets.

### 2.3 Hacker News (Algolia HN API)

- **Endpoints:**
  - Search: `GET http://hn.algolia.com/api/v1/search?query={query}` (relevance-sorted)
  - Search by date: `GET http://hn.algolia.com/api/v1/search_by_date?query={query}` (date-sorted)
  - Item details: `GET http://hn.algolia.com/api/v1/items/{id}`
  - User details: `GET http://hn.algolia.com/api/v1/users/{username}`
- **Auth:** None required (fully public)
- **Rate Limits:** ~10,000 requests/hour (Algolia's generous free tier). Max **1,000 results** per search (pagination via `page` param, 20 results/page).
- **Result Quality:** Excellent. Full-text search across all HN stories, comments, polls. Supports filters: `tags` (story, comment, ask_hn, show_hn, front_page), `numericFilters` (created_at_i, points, num_comments).
- **Unique Content:** The premier source for tech industry discussions, launches, and opinions. Comments contain enormous technical knowledge not found elsewhere.
- **Integration Complexity:** ⭐ Very Low — simple GET requests, JSON response, no auth. One of the easiest APIs to integrate.
- **Docs:** https://hn.algolia.com/api (brief), https://github.com/algolia/hn-search (detailed)

### 2.4 Stack Overflow / Stack Exchange API

- **Endpoint:** `GET https://api.stackexchange.com/2.3/search?order=desc&sort=relevance&intitle={query}&site=stackoverflow`
  - Advanced: `GET /2.3/search/advanced` (supports body search, tags, date ranges)
  - Full-text: `GET /2.3/search/excerpts` (searches title + body)
- **Auth:** Optional but recommended. Register app for API key at https://stackapps.com/
- **Rate Limits:**
  - Without API key: **300 requests/day** per IP
  - With API key: **10,000 requests/day**
  - Hard limit: **30 concurrent requests/second** per IP (instant ban)
  - Heavy caching — identical requests should not be made more than once/minute
  - `backoff` field in response: must wait N seconds before same method again
- **Result Quality:** Very high for programming Q&A. Answers are community-curated and ranked by votes. Supports filtering by tags, answer count, accepted answers, date range.
- **Unique Content:** Best source for solved programming problems. Answers include code examples, explanations, edge cases. Covers 180+ Stack Exchange sites (not just SO).
- **Integration Complexity:** ⭐⭐ Low-Medium — gzip-compressed responses by default. JSON with wrapper object. Client libraries available in many languages.
- **Docs:** https://api.stackexchange.com/docs

### 2.5 Discourse Forums API (Generic)

- **Endpoint:** `GET https://{discourse-instance}/search.json?q={query}`
- **Auth:** API key + username in headers (`Api-Key`, `Api-Username`). Some endpoints work without auth.
- **Rate Limits:** Instance-dependent. Default Discourse rate limits:
  - 60 requests/minute for most endpoints
  - Higher for read-only operations
- **Result Quality:** Varies by instance. Search supports filters: `#category`, `@username`, `in:title`, `status:open`, `order:latest`, date ranges.
- **Unique Content:** Each Discourse instance is a distinct community. Combined, they cover enormous breadth (Ruby, Rust, Julia, Kubernetes forums etc.).
- **Integration Complexity:** ⭐ Very Low — simple JSON API, consistent across all Discourse instances.
- **Docs:** https://docs.discourse.org/

---

## 3. Academic / Research

### 3.1 Semantic Scholar API

- **Endpoints:**
  - Paper search: `GET https://api.semanticscholar.org/graph/v1/paper/search?query={query}`
  - Paper details: `GET /graph/v1/paper/{paper_id}`
  - Author search: `GET /graph/v1/author/search?query={query}`
  - Recommendations: `POST /recommendations/v1/papers/`
  - Bulk access: Dataset downloads available
- **Auth:** Optional API key (request at https://www.semanticscholar.org/product/api#api-key-form)
- **Rate Limits:**
  - Unauthenticated: **1,000 requests/second** shared among ALL unauthenticated users (effectively much lower per client)
  - Authenticated (API key): **1 request/second** guaranteed per key (can request higher)
  - Bulk dataset downloads available for offline analysis
- **Result Quality:** Excellent for academic papers. 214M+ papers, 2.49B citations, 79M authors. Returns: title, abstract, authors, venue, year, citation count, references, SPECTER2 embeddings, PDF URLs, TLDRs.
- **Unique Content:** AI-powered paper discovery, citation graphs, paper recommendations, SPECTER embeddings. Much richer metadata than Google Scholar. Open access PDF links. TL;DR summaries.
- **Integration Complexity:** ⭐ Very Low — clean REST API, excellent documentation, Python client available.
- **Docs:** https://api.semanticscholar.org/api-docs/

### 3.2 arXiv API

- **Endpoint:** `GET http://export.arxiv.org/api/query?search_query={query}`
- **Auth:** None required (fully public)
- **Rate Limits:**
  - **1 request every 3 seconds** (enforced)
  - Single connection at a time
  - Max **2,000 results per page** (use `start` + `max_results` for pagination)
  - No hard cap on total results
- **Result Quality:** Good for physics, math, CS, stats, quant-bio, quant-fin. Search fields: `ti:` (title), `au:` (author), `abs:` (abstract), `co:` (comment), `jr:` (journal ref), `cat:` (category), `all:` (all fields). Supports boolean operators (AND, OR, ANDNOT).
- **Unique Content:** 2.4M+ preprints. Many papers appear here months before journal publication. The primary source for cutting-edge CS/ML/physics research.
- **Integration Complexity:** ⭐ Very Low — simple GET, returns Atom/XML feed. Python wrapper: `pip install arxiv`. Well-documented.
- **Caveats:** Response is Atom XML (not JSON). Slow rate limit means bulk queries take time.
- **Docs:** https://info.arxiv.org/help/api/user-manual.html

### 3.3 Google Scholar

- **Status:** ⚠️ **No official API.** Google has never provided a Scholar API.
- **Alternatives:**
  - **SerpAPI:** Scrapes Google Scholar results. $50/month for 5,000 searches. Good quality.
  - **ScrapingBee/ScrapingDog:** Similar SERP scraping services.
  - **scholarly** (Python): Unofficial scraping library, breaks frequently.
  - **Semantic Scholar:** Best free alternative for most use cases.
- **Recommendation:** Use Semantic Scholar API for programmatic access. Use Google Scholar web UI for manual searches. SerpAPI if you need Google Scholar specifically and can pay.

### 3.4 CrossRef API

- **Endpoint:** `GET https://api.crossref.org/works?query={query}`
- **Auth:** None required. "Polite pool" recommended: include `mailto:your@email.com` in query params for faster responses.
- **Rate Limits:**
  - Anonymous: **50 requests/second** (subject to throttling)
  - Polite pool (with mailto): Higher priority, faster responses
  - Plus membership: Higher rate limits + snapshot access
- **Result Quality:** Excellent for DOI resolution, bibliographic metadata, funder data. 150M+ works. Supports filters: `from-pub-date`, `type`, `has-full-text`, `is-referenced-by-count`, ISSN, DOI prefix.
- **Unique Content:** The authoritative DOI metadata source. Funder data (who funded what), license info, reference lists, citation counts. Covers most published academic literature.
- **Integration Complexity:** ⭐ Very Low — simple REST API, JSON responses, excellent documentation, no auth needed.
- **Docs:** https://api.crossref.org/ (Swagger), https://github.com/CrossRef/rest-api-doc

---

## 4. Ethereum / Crypto Specific

### 4.1 ethresear.ch (Ethereum Research Forum)

- **Endpoint:** `GET https://ethresear.ch/search.json?q={query}`
- **Auth:** None for read-only search. API key needed for write operations.
- **Rate Limits:** Standard Discourse limits (~60 req/min). Instance may have custom limits.
- **Result Quality:** High for Ethereum research topics. Topics include: sharding, rollups, MEV, PBS, ePBS, PeerDAS, VDFs, proof systems.
- **Unique Content:** The primary forum for Ethereum protocol research discussions. Posts from Vitalik, Dankrad, Justin Drake, and other core researchers. Proposals often appear here before becoming EIPs.
- **Integration Complexity:** ⭐ Very Low — standard Discourse API. Append `.json` to any URL for JSON.
- **Search URL pattern:** `https://ethresear.ch/search.json?q=PeerDAS`
- **Additional endpoints:** `/latest.json`, `/categories.json`, `/t/{topic_id}.json`

### 4.2 EIPs Repository Search

- **Endpoint:** GitHub Code Search against `repo:ethereum/EIPs`
  - `GET https://api.github.com/search/code?q={query}+repo:ethereum/EIPs`
  - Or local clone: `~/consensus-specs` / search EIP markdown files
- **Auth:** GitHub PAT (for API), none for local clone
- **Rate Limits:** GitHub Code Search limits (10 req/min)
- **Result Quality:** Definitive for EIP content. Every EIP is a markdown file with structured metadata (status, type, category, author, created date).
- **Unique Content:** The canonical source for all Ethereum Improvement Proposals. Not available via general search with the same structured metadata.
- **Integration Complexity:** ⭐ Very Low — clone repo + grep is fastest. API works too.
- **Better approach:** Clone `ethereum/EIPs` locally, use `grep -r` or `rg` for instant results.

### 4.3 Ethereum Magicians Forum

- **Endpoint:** `GET https://ethereum-magicians.org/search.json?q={query}`
- **Auth:** None for read-only. Same Discourse API as ethresear.ch.
- **Rate Limits:** Standard Discourse limits
- **Result Quality:** High for EIP discussions, governance, working group coordination. More implementation-focused than ethresear.ch.
- **Unique Content:** EIP discussion threads (linked from EIP headers), All Core Devs meeting notes discussions, working group coordination. The "town hall" of Ethereum governance.
- **Integration Complexity:** ⭐ Very Low — standard Discourse API.

### 4.4 Consensus Specs Discussions

- **Endpoint:** GitHub Discussions API on `ethereum/consensus-specs`
  - `GET https://api.github.com/repos/ethereum/consensus-specs/discussions` (via GraphQL)
  - Issues: `GET https://api.github.com/search/issues?q=repo:ethereum/consensus-specs+{query}`
- **Auth:** GitHub PAT
- **Rate Limits:** Standard GitHub API limits
- **Result Quality:** Specific to consensus layer spec discussions and issues.
- **Unique Content:** Direct spec-level discussions that don't appear on forums. PR review comments, design decisions.
- **Integration Complexity:** ⭐⭐ Low-Medium — GitHub GraphQL needed for Discussions; REST for Issues.

---

## 5. Social Media

### 5.1 Twitter/X API

- **Endpoint:** `GET https://api.x.com/2/tweets/search/recent?query={query}`
  - Recent search: last 7 days (Basic+)
  - Full archive search: `/2/tweets/search/all` (Pro+)
- **Auth:** OAuth 2.0 Bearer Token required
- **Pricing (as of 2025-2026):**
  - **Free tier:** Write-only (500 posts/month). **NO search access.**
  - **Basic ($200/month):** 10,000 read requests/month, recent search only (7 days)
  - **Pro ($5,000/month):** 1M read requests/month, full archive search
  - **Enterprise:** Custom pricing, higher limits
  - Pay-per-use beta launched Nov 2025 (invite-only)
- **Result Quality:** Good for real-time discourse, announcements, hot takes. Supports: keyword, hashtag, @mention, from:user, has:links, lang:, place:, etc.
- **Unique Content:** Real-time reactions, breaking news, community sentiment. Crypto/Ethereum community heavily uses Twitter. Many protocol announcements appear here first.
- **Integration Complexity:** ⭐⭐ Medium — OAuth2 setup, pagination via tokens, complex query syntax
- **Recommendation:** Too expensive for most use cases. Use Bluesky API (free) as alternative. For specific needs, Nitter instances may provide read-only access (legal gray area).
- **Docs:** https://developer.x.com/en/docs/x-api

### 5.2 Bluesky (AT Protocol) API

- **Endpoints:**
  - Search posts: `GET https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q={query}`
  - Search actors: `GET https://public.api.bsky.app/xrpc/app.bsky.actor.searchActors?q={query}`
  - Get posts: `GET /xrpc/app.bsky.feed.getPosts`
- **Auth:** Public endpoints work without auth! Authenticated access via user PDS.
- **Rate Limits:** Not strictly documented. Public AppView is rate-limited but generous.
- **Result Quality:** Growing. Bluesky has attracted significant tech/research community. Supports: keyword search, author filter, date range, language, domain filter, mentions.
- **Unique Content:** Many researchers and developers who left Twitter are on Bluesky. Growing Ethereum community presence. Open protocol means data is inherently accessible.
- **Integration Complexity:** ⭐ Very Low — public endpoints, no auth needed for search, JSON responses.
- **Docs:** https://docs.bsky.app/docs/api/app-bsky-feed-search-posts
- **Recommendation:** ⭐ HIGHLY RECOMMENDED — Free, open, no auth needed, growing community. Best Twitter alternative for API access.

### 5.3 Mastodon API

- **Endpoint:** `GET https://{instance}/api/v2/search?q={query}&type=statuses`
  - Types: `accounts`, `hashtags`, `statuses`
- **Auth:** OAuth2 app token (needed for full search). Some instances allow unauthenticated hashtag search.
- **Rate Limits:**
  - Default: **300 requests per 5 minutes** per endpoint
  - Per-IP: **7,500 requests per 5 minutes**
  - Instance-configurable (varies)
- **Result Quality:** Limited — **federated search only covers the local instance + known federated content**. No global search across all instances.
- **Unique Content:** Decentralized tech community discussions. Strong presence in open-source, privacy, and some academic circles.
- **Integration Complexity:** ⭐⭐ Medium — OAuth2 required for full search, must target specific instances, fragmented data across federation.
- **Caveats:** No global search. Must query each instance separately. Consider aggregators or specialized indices.
- **Docs:** https://docs.joinmastodon.org/methods/search/

---

## 6. Documentation / Knowledge Bases

### 6.1 MDN Web Docs

- **Endpoint:** No official REST API for search. Content is on GitHub:
  - Repo: `github.com/mdn/content` (markdown files)
  - Build output: `https://developer.mozilla.org/api/v1/search?q={query}`
  - Alternative: `https://developer.mozilla.org/en-US/search?q={query}` (HTML, can scrape)
- **Auth:** None
- **Rate Limits:** Undocumented. Be polite.
- **Result Quality:** Definitive for web platform docs (HTML, CSS, JS, Web APIs, HTTP).
- **Unique Content:** The authoritative web platform reference. Browser compatibility tables, examples, specifications links.
- **Integration Complexity:** ⭐⭐ Medium — no official search API. Best approach: clone `mdn/content` repo and search locally.
- **Recommendation:** Clone repo for local search. Use web_fetch on specific pages when needed.

### 6.2 DevDocs.io

- **Endpoint:** No public API. Content served via static JSON docs:
  - Index: `https://devdocs.io/docs/{docset}/index.json`
  - Entries: `https://devdocs.io/docs/{docset}/db.json`
- **Auth:** None
- **Rate Limits:** N/A (static files)
- **Result Quality:** Pre-indexed, fast. Covers 100+ documentation sets.
- **Unique Content:** Aggregated, searchable documentation across many languages/frameworks in one place.
- **Integration Complexity:** ⭐⭐⭐ Medium-High — no search API; must download JSON index and implement client-side search.
- **Recommendation:** Not great for programmatic search. Better to query individual documentation sources directly.

### 6.3 Wikipedia API (MediaWiki Action API)

- **Endpoint:** `GET https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&format=json`
  - Page content: `action=parse&page={title}&format=json`
  - REST API (newer): `GET https://en.wikipedia.org/api/rest_v1/page/summary/{title}`
- **Auth:** None required
- **Rate Limits:**
  - Unauthenticated: ~200 requests/second generally tolerated
  - User-Agent header required (with contact info)
  - MaxLag parameter recommended for write operations
- **Result Quality:** Excellent for factual queries, definitions, entity information. Returns snippets with highlighting.
- **Unique Content:** The world's largest encyclopedia. Structured data, infoboxes, citations, cross-language links.
- **Integration Complexity:** ⭐ Very Low — simple REST API, well-documented, many client libraries.
- **Docs:** https://www.mediawiki.org/wiki/API:Action_API

### 6.4 Wikidata SPARQL

- **Endpoint:** `GET https://query.wikidata.org/sparql?query={SPARQL_QUERY}&format=json`
  - Interactive: https://query.wikidata.org/
- **Auth:** None required
- **Rate Limits:**
  - Queries timeout at **60 seconds**
  - Concurrent request limits per IP (not precisely documented)
  - Rate limit exceeded (429) if too many queries from same IP
  - ~5 queries/second seems safe
- **Result Quality:** Excellent for structured/relational queries. "All cities with population > 1M", "All Ethereum-related software projects", etc.
- **Unique Content:** Structured knowledge graph with 100M+ items. Relationships, properties, qualifiers. Unmatched for entity-relationship queries.
- **Integration Complexity:** ⭐⭐⭐ Medium-High — requires SPARQL knowledge. Powerful but steep learning curve.
- **Docs:** https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service

---

## 7. News / Blog Aggregators

### 7.1 Hacker News (Algolia)

*See section 2.3 above.*

### 7.2 Lobste.rs

- **Endpoint:** Minimal JSON API via URL patterns:
  - Homepage: `GET https://lobste.rs/hottest.json`
  - Newest: `GET https://lobste.rs/newest.json`
  - By tag: `GET https://lobste.rs/t/{tag}.json`
  - User: `GET https://lobste.rs/u/{username}.json`
  - **No search endpoint** — must scrape or use site search
- **Auth:** None for read-only JSON
- **Rate Limits:** Undocumented. Be polite.
- **Result Quality:** High quality tech content, curated community (invite-only). Tags: rust, go, networking, distributed, security, etc.
- **Unique Content:** More niche/technical than HN. Invite-only community means higher signal-to-noise. Strong systems programming focus.
- **Integration Complexity:** ⭐ Very Low — append `.json` to pages. But **no search** is a major limitation.
- **Recommendation:** Good for monitoring latest content by tag. Not useful for historical search. Use HN Algolia for search instead.

### 7.3 NewsAPI.org

- **Endpoints:**
  - Everything: `GET https://newsapi.org/v2/everything?q={query}&apiKey={key}`
  - Top headlines: `GET https://newsapi.org/v2/top-headlines?q={query}&apiKey={key}`
  - Sources: `GET https://newsapi.org/v2/top-headlines/sources`
- **Auth:** API key required (free registration)
- **Rate Limits / Pricing:**
  - **Free (Developer):** 100 requests/day, 1-month article history, development only (cannot use in production!)
  - **Business ($449/month):** 250,000 requests/month, production use
  - **Enterprise:** Custom
- **Result Quality:** Good. 150,000+ sources, 80+ countries. Filters: sources, domains, language, date range, sort by relevance/popularity/publishedAt.
- **Unique Content:** Aggregated news from major outlets worldwide. Good for monitoring tech news, crypto news.
- **Integration Complexity:** ⭐ Very Low — simple REST API, JSON, well-documented.
- **Caveats:** Free tier is development-only (legally cannot use in production). No full article content (only title, description, URL).
- **Docs:** https://newsapi.org/docs

### 7.4 GNews API

- **Endpoints:**
  - Search: `GET https://gnews.io/api/v4/search?q={query}&apikey={key}`
  - Top headlines: `GET https://gnews.io/api/v4/top-headlines?apikey={key}`
- **Auth:** API key required (free registration)
- **Rate Limits / Pricing:**
  - **Free:** 100 requests/day, 10 articles/request, 12-hour delay, 30 days history
  - **Essential (€49.99/mo):** 1,000 requests/day, 25 articles/request, real-time, history from 2020
  - **Business (€99.99/mo):** 5,000/day
  - **Enterprise (€249.99/mo):** 25,000/day
- **Result Quality:** Similar to NewsAPI. Supports: language, country, date range, in: (title, description, content).
- **Unique Content:** Slightly different source coverage than NewsAPI. Offers full content on paid tiers.
- **Integration Complexity:** ⭐ Very Low — simple REST, JSON.
- **Recommendation:** Free tier is more restrictive than NewsAPI. Consider as backup.
- **Docs:** https://gnews.io/docs/v4

### 7.5 RSS Feed Aggregation (DIY)

- **Endpoint:** N/A — assemble your own feed reader
- **Auth:** N/A
- **Tools:** `feedparser` (Python), `rss-parser` (Node.js), Miniflux, FreshRSS
- **Result Quality:** Depends entirely on curated feed list. Can be excellent for niche topics.
- **Unique Content:** Many blogs and projects only publish via RSS (no API). Ethereum client blogs, personal researcher blogs, project changelogs.
- **Integration Complexity:** ⭐⭐ Low-Medium — parse XML feeds, handle various RSS/Atom formats, polling schedule.
- **Recommendation:** ⭐ RECOMMENDED for monitoring specific sources (Ethereum blog, client team blogs, Week in Ethereum). Pair with a search index for historical queries.

---

## 8. Package Registries

### 8.1 npm Registry Search

- **Endpoint:** `GET https://registry.npmjs.org/-/v1/search?text={query}`
- **Auth:** None required for search
- **Rate Limits:**
  - ~5,000,000 requests/month considered acceptable
  - Search queries must be ≥3 characters
  - No hard documented rate limit per minute
- **Result Quality:** Good. Returns: package name, version, description, keywords, links, publisher, maintainers, npm score (quality/popularity/maintenance).
- **Unique Content:** 2M+ JavaScript packages. Dependency graphs, download counts, quality scores. Package README content.
- **Integration Complexity:** ⭐ Very Low — simple GET, JSON response.
- **Package details:** `GET https://registry.npmjs.org/{package}` (full metadata)
- **Docs:** https://github.com/npm/registry/blob/main/docs/REGISTRY-API.md

### 8.2 PyPI (Python Package Index)

- **Endpoint:**
  - Package info: `GET https://pypi.org/pypi/{package}/json`
  - Package version: `GET https://pypi.org/pypi/{package}/{version}/json`
  - Simple index: `GET https://pypi.org/simple/` (all package names)
  - **No search endpoint!** XML-RPC search was deprecated.
- **Auth:** None
- **Rate Limits:** Undocumented but reasonable use expected.
- **Result Quality:** N/A — cannot search by keyword via API. Can only look up known package names.
- **Unique Content:** 500K+ Python packages. Full metadata, release history, download URLs.
- **Integration Complexity:** ⭐ Very Low for lookups, but ⭐⭐⭐⭐ impossible for search.
- **Workaround for search:** Use `pip search` (deprecated) or third-party tools:
  - `pip-search` package
  - Libraries.io API: `GET https://libraries.io/api/search?q={query}&platforms=pypi&api_key={key}`
  - PyPI BigQuery dataset for analytics
- **Docs:** https://docs.pypi.org/api/

### 8.3 crates.io (Rust Package Registry)

- **Endpoint:** `GET https://crates.io/api/v1/crates?q={query}`
- **Auth:** None required for search
- **Rate Limits:**
  - **1 request/second** recommended (crawler policy)
  - `crates_io_api` Rust crate has built-in rate limiter
  - User-Agent header required (with contact info)
  - Sparse index (`https://index.crates.io/`) has no rate limits
- **Result Quality:** Good. Returns: crate name, description, downloads, recent downloads, max version, homepage, repository, keywords, categories.
- **Unique Content:** 150K+ Rust crates. Download statistics, version history, dependency tree, feature flags.
- **Integration Complexity:** ⭐ Very Low — simple REST API, JSON. Rust client: `crates_io_api`.
- **Database dump:** Full database dump available for offline analysis.
- **Docs:** https://crates.io/data-access

### 8.4 Libraries.io (Cross-Registry)

- **Endpoint:** `GET https://libraries.io/api/search?q={query}&api_key={key}`
  - Supports: `platforms=` (npm, pypi, rubygems, etc.), `sort=`, `languages=`
- **Auth:** API key required (free registration)
- **Rate Limits:** 60 requests/minute
- **Result Quality:** Good for cross-platform package discovery. 7M+ packages across 40+ registries.
- **Unique Content:** Cross-registry search. SourceRank scoring. Dependency analysis across ecosystems.
- **Integration Complexity:** ⭐ Very Low
- **Docs:** https://libraries.io/api

---

## Summary: Top Recommendations

### Highest Value (Free, Easy to Integrate)

| Source | Unique Strength | Auth | Complexity |
|--------|----------------|------|-----------|
| **HN Algolia** | Tech discussions, no auth | None | ⭐ |
| **Bluesky API** | Social/tech discourse, open | None | ⭐ |
| **Semantic Scholar** | Academic papers, 214M+ | Optional | ⭐ |
| **arXiv API** | CS/ML preprints | None | ⭐ |
| **CrossRef API** | DOI/citation metadata | None | ⭐ |
| **ethresear.ch** | Ethereum research | None | ⭐ |
| **Ethereum Magicians** | EIP governance | None | ⭐ |
| **Wikipedia API** | Factual knowledge | None | ⭐ |
| **GitHub Code Search** | Code in all public repos | PAT | ⭐ |
| **Stack Exchange API** | Programming Q&A | Optional | ⭐⭐ |
| **npm search** | JS package discovery | None | ⭐ |
| **crates.io search** | Rust package discovery | None | ⭐ |

### Worth Investing In (Auth/Cost Required)

| Source | Unique Strength | Cost | Notes |
|--------|----------------|------|-------|
| **Reddit API** | Human experiences/opinions | Free (OAuth2) | Requires app registration |
| **NewsAPI/GNews** | Aggregated news | Free tier limited | Production use costs $$ |
| **RSS aggregation** | Niche blogs/changelogs | Free (DIY) | Requires curation |
| **Libraries.io** | Cross-registry packages | Free (API key) | 60 req/min |

### Skip / Low Value

| Source | Reason |
|--------|--------|
| **Sourcegraph** | Closed source, no public access |
| **Pushshift** | Dead |
| **Twitter/X API** | $200+/month for read access |
| **Google Scholar** | No API, scraping services expensive |
| **Mastodon search** | No global search, fragmented |
| **DevDocs** | No search API |
| **PyPI search** | Search endpoint deprecated |

---

## Integration Priority for Web Search Skill

1. **Phase 1 (Quick wins):** HN Algolia, Bluesky, ethresear.ch, Ethereum Magicians, Wikipedia, GitHub Code Search, npm, crates.io
2. **Phase 2 (Medium effort):** Semantic Scholar, arXiv, CrossRef, Stack Exchange, Reddit, grep.app
3. **Phase 3 (Advanced):** NewsAPI, RSS aggregation, Wikidata SPARQL, Libraries.io
4. **Skip:** Sourcegraph, Pushshift, Twitter/X, Google Scholar, Mastodon, DevDocs

All Phase 1 sources are free, require no or minimal auth, and return JSON. Total integration time: ~2 hours for basic wrappers.
