# Self-Hosted & Open-Source Search Solutions

*Research compiled 2026-03-06*

## Executive Summary

For **programmatic/API web search without per-query API costs**, **SearxNG** is the clear winner. It's the most mature, actively developed, has a proper JSON API, aggregates 70+ engines, and can be deployed in 5 minutes with Docker. **4get** is a strong runner-up with a different philosophy (PHP-based, lighter weight, opinionated). **Whoogle** recently added JSON output but is Google-only and is under threat from Google's anti-scraping measures. The others (YaCy, LibreX, self-hosted index engines) are niche tools for specific use cases.

---

## 1. SearxNG ⭐ RECOMMENDED

**Repo:** https://github.com/searxng/searxng (~16k stars)
**License:** AGPL-3.0
**Language:** Python (Flask/uWSGI)
**Docker:** https://github.com/searxng/searxng-docker

### How It Works
SearxNG is a meta-search engine that sends your query to multiple upstream search engines simultaneously (Google, Bing, DuckDuckGo, Brave, Qwant, Startpage, etc.), aggregates the results, deduplicates, and ranks them. It scrapes the upstream engines' HTML responses — no API keys needed. The upstream engines see the SearxNG server's IP, not the user's.

### Installation
**Docker (recommended, ~5 min):**
```bash
cd /usr/local
git clone https://github.com/searxng/searxng-docker.git
cd searxng-docker
# Edit .env for hostname
sed -i "s|ultrasecretkey|$(openssl rand -hex 32)|g" searxng/settings.yml
docker compose up -d
```
Stack: SearxNG + Caddy (reverse proxy) + Valkey (Redis-compatible in-memory cache).

**Bare metal:** Python + uWSGI + nginx. More involved but well-documented.

### API Access (JSON)
```bash
# GET request
curl 'http://localhost:8080/search?q=ethereum+consensus&format=json'

# POST request
curl -X POST 'http://localhost:8080/search' -d 'q=ethereum+consensus&format=json'
```

**Parameters:**
- `q` — search query (required)
- `format` — `json`, `csv`, or `rss` (must be enabled in settings.yml)
- `categories` — comma-separated: `general`, `images`, `videos`, `news`, `music`, `it`, `science`, `files`, `social media`
- `engines` — comma-separated specific engines: `google`, `bing`, `duckduckgo`, `brave`, etc.
- `language` — language code
- `pageno` — page number (default 1)
- `time_range` — `day`, `month`, `year`
- `safesearch` — 0 (none), 1 (moderate), 2 (strict)

**Important:** JSON/CSV/RSS formats must be explicitly enabled in `settings.yml`:
```yaml
search:
  formats:
    - html
    - json   # Add this
    - csv    # Optional
    - rss    # Optional
```
Many public instances disable JSON format — self-hosting is essential for API use.

### Configuration (Engine Selection)
`settings.yml` controls everything:
- Which engines are active (70+ available including Google, Bing, DDG, Brave, Qwant, Wikipedia, GitHub, StackOverflow, YouTube, PubMed, arXiv, etc.)
- Rate limiting / ban times per engine
- Suspended times when engines return errors:
  - Access denied: 86400s (24h)
  - CAPTCHA: 86400s
  - Too many requests: 3600s (1h)
  - Cloudflare CAPTCHA: 1296000s (15 days!)
  - Google reCAPTCHA: 604800s (7 days)
- Language defaults, safe search, autocomplete provider

### Public Instances
Listed at https://searx.space/ — hundreds of instances worldwide. However:
- **Public instances often get rate-limited/blocked** by Google, Bing, etc. due to high traffic
- Many disable JSON/API format
- Result quality degrades under heavy load
- **Self-hosting is far superior for programmatic use**

### Result Quality
- **Good when self-hosted** — your IP isn't blacklisted by search providers
- **Varies on public instances** — heavily used instances get blocked
- Aggregation from multiple engines provides broader coverage than any single source
- Google results via SearxNG are essentially the same as direct Google (scraped HTML), but may get CAPTCHA'd
- Combining Google + Bing + DDG gives robust fallback

### Rate Limits & Reliability
- Self-hosted: Limited by upstream engine rate limits (Google is strictest)
- SearxNG has built-in engine suspension on errors (configurable timeouts)
- Using multiple engines provides resilience — if Google blocks you, Bing/DDG still work
- Valkey/Redis cache helps reduce duplicate upstream queries
- For heavy use: rotate through multiple engines, use proxy support, avoid Google-heavy configs

### Setup Complexity: 2/5
Docker setup is straightforward. Configuration tuning takes some experimentation.

### Maintenance Burden: LOW-MEDIUM
- Docker image updates: `docker compose pull && docker compose up -d`
- Occasional engine breakage when upstream sites change (community fixes quickly)
- Monitor for engine suspensions/blocks
- Active development, ~weekly updates

### Best Use Case
**Primary web search aggregator for agents/automation.** The JSON API is purpose-built for programmatic access. Best when self-hosted with multiple engines configured for redundancy.

---

## 2. 4get

**Repo:** https://git.lolcat.ca/lolcat/4get
**License:** AGPL
**Language:** PHP
**Official instance:** https://4get.ca

### How It Works
Similar to SearxNG — a meta-search proxy that scrapes upstream engines. But with a distinctly different philosophy: lightweight, minimal, no third-party libraries. Written entirely in PHP with focus on minimal resource usage (~200-400MB RAM vs SearxNG's ~2GB).

### Supported Search Sources
**Web:** DuckDuckGo, Brave, Yandex, Google, Startpage, Qwant, Ghostery, Yep, Greppr, Crowdview, Mwmbl, Mojeek, Baidu, Marginalia, wiby, Curlie
**Images:** DDG, Brave, Yandex, Google, Startpage, Qwant, Yep, Baidu, Pinterest, 500px, VSCO, Imgur, FindThatMeme
**Videos:** YouTube, Sepia Search, DDG, Brave, Yandex, Google, Startpage, Qwant, Baidu, Coc Coc
**News:** DDG, Brave, Google, Startpage, Qwant, Mojeek, Baidu
**Music:** SoundCloud
**Autocomplete:** Brave, DDG, Yandex, Google, Startpage, Kagi, Qwant, Ghostery, Yep, Marginalia, YouTube, SoundCloud

### Installation
Requires Apache2 or Nginx + PHP. Docker supported.
```bash
# Docker
docker pull lolcat/4get
docker run -p 8080:80 lolcat/4get
```
Docs for Apache2, Nginx, Caddy, Docker, and Tor available.

### API/Programmatic Access
4get supports API access. The URL structure is:
```
https://4get.ca/web?s=<query>
```
The LibreX comparison table on their README shows 4get does not explicitly list an API column, but LibreX claims both LibreX and SearxNG have APIs. 4get scraper results can be accessed programmatically via URL parameters. For structured JSON output: **unclear/limited** — the primary interface is HTML. May need HTML scraping for programmatic use unless a JSON mode exists in configuration.

### Key Features
- Per-scraper rotating proxy support
- Search filters (which SearxNG lacks in some areas)
- Bot protection
- No JavaScript required
- Favicon fetcher with caching
- Image proxy
- Encrypted `npt` (next page token) — queries stored temporarily in RAM, encrypted, deleted after 15 min

### Setup Complexity: 3/5
Requires PHP + web server setup. Docker simplifies it but less polished than SearxNG's Docker setup.

### Result Quality
Good — uses same upstream engines as SearxNG. More opinionated about which scrapers to use and maintains them actively.

### Rate Limits & Reliability
- RAM: 200-400MB (much lighter than SearxNG)
- Same upstream rate limit issues as SearxNG
- Author maintains scrapers actively — "shit breaks all the time but I repair it all the time too"
- Smaller community = fixes depend on one main dev

### Maintenance Burden: MEDIUM
- Single-developer project (lolcat) — bus factor of 1
- Scrapers need updating when upstream sites change
- Less automated than SearxNG's community-driven engine fixes

### Best Use Case
Lightweight self-hosted search when SearxNG feels too heavy. Good for personal use. Less ideal for programmatic API access compared to SearxNG.

---

## 3. Whoogle

**Repo:** https://github.com/benbusby/whoogle-search (~10k+ stars)
**License:** MIT
**Language:** Python (Flask)

### How It Works
Whoogle is a **Google-only** proxy. It sends your query to Google, scrapes the JavaScript-free HTML results, strips tracking/ads/AMP links, and serves clean results. It does NOT aggregate multiple engines — it's purely a Google frontend.

### How It Differs from SearxNG
| Aspect | SearxNG | Whoogle |
|--------|---------|---------|
| Sources | 70+ engines | Google only |
| Approach | Aggregation | Single-source proxy |
| Complexity | Moderate | Simple |
| Resource usage | ~2GB | Very light |
| API | JSON/CSV/RSS | JSON (recent, beta) |
| Customization | Extensive | Basic |

### ⚠️ CRITICAL: Google Breakage (Jan 2025+)
**Since January 16, 2025, Google has been attacking the ability to perform search queries without JavaScript.** This is a fundamental part of how Whoogle works. The project warns this may be a breaking change. Workarounds are ongoing but reliability is compromised.

### API Access
- **Recent beta (Shoogle):** JSON results via content negotiation — `Accept: application/json` header
- Historically: no API, HTML-only. The JSON feature was added in a recent beta release (httpx refactor)
- Not as mature or well-documented as SearxNG's API

### Installation
```bash
# Docker (simplest)
docker run --publish 5000:5000 --restart unless-stopped benbusby/whoogle-search:latest

# pip
pip install whoogle-search
whoogle-search --port 5000
```

### Result Quality
- **Identical to Google** (when working) — it's literally proxied Google results
- When Google blocks it: **no results at all** (single point of failure)
- No fallback to other engines

### Setup Complexity: 1/5
Easiest of all options. Single Docker command.

### Rate Limits & Reliability: ⚠️ HIGH RISK
- **Google is actively fighting this tool** (Jan 2025 onwards)
- Relies 100% on Google's willingness to serve JS-free results
- Gets blocked by Google more easily than SearxNG (all traffic goes to one provider)
- No engine fallback — when Google blocks you, you get nothing
- BYOK mode (Google Custom Search API key) available but defeats the "no API key" purpose

### Maintenance Burden: LOW (when working), HIGH (breakage events)
- Simple to update: `docker pull && docker run`
- But Google's anti-scraping measures cause periodic total breakage
- Development is reactive to Google's changes

### Best Use Case
Quick personal Google proxy when you just want ad-free Google. **NOT recommended for programmatic/API use** due to reliability concerns and Google's active countermeasures.

---

## 4. YaCy

**Repo:** https://github.com/yacy/yacy_search_server
**License:** GPL-2.0
**Language:** Java
**Website:** https://yacy.net

### How It Works
YaCy is fundamentally different — it builds its **own search index** via a peer-to-peer distributed crawling network. Each YaCy peer independently crawls the web, indexes pages, and shares its index with other peers via DHT (Distributed Hash Table). No central server.

### Key Characteristics
- **P2P architecture** — decentralized, censorship-resistant
- **Own index** — doesn't scrape other search engines
- **Crawling-based** — you (and the network) crawl websites to build the index
- Can also run in "intranet mode" for internal document search
- Java-based, resource-heavy

### Practicality Assessment
- **Index quality is poor for general web search** — the P2P network indexes only a tiny fraction of the web compared to Google/Bing
- **Relevance ranking is basic** — nowhere near Google's sophistication
- **Resource-heavy** — Java, needs significant RAM and disk for the index
- **Slow** — crawling and indexing takes time; real-time web search is not feasible
- **Useful for:** Internal/intranet search, domain-specific crawling, academic/research exploration
- **Not useful for:** General-purpose web search replacement

### Setup Complexity: 3/5
Java application, Docker available. Configuration is complex (crawling settings, DHT, etc.)

### API Access
REST API available for searching the local/network index. JSON output supported.

### Result Quality: POOR for general web search
Orders of magnitude worse than Google/Bing for general queries. Acceptable for domain-specific crawled content.

### Rate Limits: N/A (self-indexed)
No external rate limits since it uses its own index. But crawling and indexing are slow.

### Maintenance Burden: HIGH
- Crawling management, index maintenance, P2P network health
- Java updates, memory management
- Crawling can generate significant outbound traffic

### Best Use Case
**Internal/intranet document search**, domain-specific research indexes, academic projects. NOT for general web search.

---

## 5. LibreX

**Repo:** https://github.com/hnhx/librex
**License:** AGPL-3.0
**Language:** PHP (no frameworks, no third-party libs)

### How It Works
Meta-search engine similar to SearxNG but written in minimal PHP with zero dependencies. Scrapes Google, Qwant, Ahmia (Tor), and popular torrent sites.

### Features
- No JavaScript required
- Privacy frontend redirects (routes to Invidious, Nitter, etc.)
- Torrent search results
- API endpoint available
- Zero third-party libraries
- TOR and I2P support

### Comparison to SearxNG
| Aspect | LibreX | SearxNG |
|--------|--------|---------|
| Engine count | ~3 (Google, Qwant, Ahmia) | 70+ |
| Dependencies | Zero | Many Python packages |
| JS required | No | Not user-friendly without JS |
| API | Yes | Yes |
| Privacy redirects | Yes (built-in) | Host-configurable only |
| Torrent results | Yes | Yes |
| Activity | Low (last meaningful update ~2023) | Very active |

### Public Instances
Multiple listed on the GitHub README, including .onion and I2P addresses. Many appear offline or poorly maintained.

### Setup Complexity: 2/5
PHP + web server. Very simple, lightweight.

### API Access
Has an API endpoint. Minimal documentation.

### Result Quality: LIMITED
Only queries ~3 search engines. Far less comprehensive than SearxNG. Google results are the main source, subject to same blocking issues.

### Rate Limits & Reliability
Same upstream Google rate-limit issues. Very few engines = no redundancy.

### Maintenance Burden: HIGH (effectively abandoned)
- Development appears largely stalled (last major work ~2023)
- Richard Stallman uses it (mentioned on stallman.org) but community is tiny
- Few engines means any breakage has outsized impact

### Best Use Case
Minimalist, zero-dependency PHP search for extreme lightweight scenarios. Not recommended over SearxNG for serious use.

---

## 6. Self-Hosted Search with Own Index

### Meilisearch
- **Purpose:** Full-text search engine for YOUR data (documents, products, etc.)
- **NOT for web search** — requires you to feed it a pre-existing dataset
- **Excellent at:** Typo-tolerant, fast, developer-friendly API
- **Irrelevant for:** Searching the internet

### Typesense
- **Purpose:** Same as Meilisearch — search over your own data
- **NOT for web search** — no crawling, no external data aggregation
- **Excellent at:** Real-time search, geo-search, faceting
- **Irrelevant for:** Searching the internet

### Zinc (now ZincSearch/ZincObserve/OpenObserve)
- **Purpose:** Log search / document search (Elasticsearch alternative)
- **NOT for web search** — designed for ingested data
- **Irrelevant for:** Searching the internet

### SOSSE (Self-hosted Open-Source Search Engine)
- Worth mentioning: Actually crawls and indexes web pages (like a mini-YaCy but simpler)
- Still impractical for general web search — index is tiny
- Useful for: Indexing specific sites/domains

### Assessment
These tools (Meilisearch, Typesense, Zinc) are **internal/document search engines** — they require you to provide the data. They are NOT web search engines and cannot replace Google/Bing/SearxNG. They solve a completely different problem (searching your own content).

---

## Comparison Matrix

| Solution | Setup (1-5) | API Quality | Web Result Quality | Reliability | Maintenance | Best For |
|----------|:-----------:|:-----------:|:------------------:|:-----------:|:-----------:|----------|
| **SearxNG** ⭐ | 2 | Excellent (JSON/CSV/RSS) | Good (multi-engine) | High (redundancy) | Low-Med | Programmatic web search |
| **4get** | 3 | Limited (HTML mainly) | Good (multi-engine) | Medium | Medium | Lightweight personal search |
| **Whoogle** | 1 | Recent/Beta (JSON) | Excellent (= Google) | ⚠️ LOW (Google fighting it) | Variable | Quick personal Google proxy |
| **YaCy** | 3 | Good (REST/JSON) | Poor (own index) | High (self-reliant) | High | Internal/domain search |
| **LibreX** | 2 | Basic | Limited (~3 engines) | Low | High (stale) | Minimalist PHP search |
| **Meilisearch** | 2 | Excellent | N/A (not web search) | High | Low | Internal document search |
| **Typesense** | 2 | Excellent | N/A (not web search) | High | Low | Internal document search |

---

## Recommendation for OpenClaw Web Search Skill

**SearxNG self-hosted** is the clear choice:

1. **JSON API** purpose-built for programmatic access
2. **70+ engines** with configurable fallback
3. **No API keys needed** — scrapes upstream engines directly
4. **Docker deployment** in 5 minutes
5. **Active community** — engines fixed quickly when upstream changes
6. **Configurable** — choose which engines, set rate limits, tune timeouts
7. **Resilient** — if Google blocks you, Bing/DDG/Brave still work

**Deployment plan:**
```bash
# Deploy on the same server as OpenClaw
git clone https://github.com/searxng/searxng-docker.git /opt/searxng
cd /opt/searxng
# Configure settings.yml:
#   - Enable json format
#   - Select engines: google, bing, duckduckgo, brave, qwant
#   - Tune rate limits for API usage
#   - Disable Caddy if already behind reverse proxy
docker compose up -d
```

**Usage from skill:**
```bash
curl 'http://localhost:8080/search?q=ethereum+PeerDAS+specification&format=json&engines=google,bing,duckduckgo'
```

**Estimated resources:** ~500MB-2GB RAM depending on load.
