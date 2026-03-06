# Scrapling Deep-Dive — Architecture, Capabilities & Comparison

**Date:** 2026-02-25  
**Version analyzed:** v0.4 (released 2026-02-15)  
**Repo:** https://github.com/D4Vinci/Scrapling  
**Stars:** ~14.8k | **Forks:** ~980 | **Open Issues:** 9 | **Last push:** 2026-02-25

---

## 1. Fetcher Architecture — No Auto-Detection

**There is no automatic fetcher selection.** Scrapling does NOT auto-detect which fetcher to use. The user explicitly chooses one of three:

### Fetcher (HTTP-only, curl_cffi)
- **Engine:** `curl_cffi` (Python bindings for curl-impersonate)
- **File:** `scrapling/engines/static.py`
- **What it does:** HTTP requests with TLS fingerprint impersonation (Chrome, Firefox, Edge)
- **Key features:**
  - `impersonate='chrome'` — matches Chrome's TLS fingerprint, headers, HTTP/2 behavior
  - `stealthy_headers=True` — generates realistic headers via `browserforge`
  - Google search referer spoofing (makes it look like traffic came from Google)
  - HTTP/3 support via `http3=True`
  - Session support (`FetcherSession`) with context manager
  - Retry logic with configurable attempts and delay
  - Proxy rotation support (`ProxyRotator`)
- **Limitations:** No JavaScript execution. Static HTML only.
- **Our test results:** 4/6 CF sites passed

### DynamicFetcher (Playwright/Chromium)
- **Engine:** Standard `playwright` (sync + async)
- **File:** `scrapling/engines/_browsers/_controllers.py`
- **What it does:** Full browser automation with Playwright's Chromium
- **Key features:**
  - Full JS rendering, DOM waiting, network idle detection
  - `page_action` callback for custom automation
  - `wait_selector` / `wait_selector_state` for element waiting
  - `real_chrome=True` to use locally installed Chrome
  - `cdp_url` to connect to existing Chrome instances
  - Domain blocking, resource disabling for speed
  - Page pooling for concurrent sessions
- **Stealth:** Minimal. Uses standard Playwright Chromium. No special anti-detection.
- **Our test results:** 5/6 CF sites passed (rebrowser-playwright variant)

### StealthyFetcher (Patchright + stealth scripts)
- **Engine:** `patchright` (patched Playwright fork) + custom JS stealth scripts
- **File:** `scrapling/engines/_browsers/_stealth.py`
- **What it does:** Stealthy browser automation with anti-detection measures
- **Key features:**
  - Built on `patchright` (NOT regular Playwright) — patches CDP runtime detection
  - Injects 6 stealth JS scripts on page creation:
    1. `webdriver_fully.js` — removes `navigator.webdriver` traces
    2. `window_chrome.js` — fakes `window.chrome` object
    3. `navigator_plugins.js` — spoofs plugin/mime arrays
    4. `notification_permission.js` — fixes permission API
    5. `screen_props.js` — normalizes screen properties
    6. `playwright_fingerprint.js` — removes Playwright-specific fingerprints
  - **Cloudflare solver** — built-in Turnstile/Interstitial solver that:
    - Detects challenge type (non-interactive, interactive, embedded)
    - Waits for iframe, calculates captcha coordinates, clicks with randomized delay
  - Canvas fingerprint noise (`hide_canvas=True`)
  - WebRTC blocking (`block_webrtc=True`)
  - Persistent browser context with user data directory
  - `solve_cloudflare=True` — automatic CF challenge resolution
- **Our test results:** 0/6 — DNS resolution failure on our server

### Evolution History
- **Pre-v0.3:** StealthyFetcher used **Camoufox** (Firefox-based stealth browser)
- **v0.3:** Switched StealthyFetcher to **patchright** (Chromium-based), removed Camoufox dependency
- **v0.4:** Added Spider framework, proxy rotation, major refactoring

---

## 2. Internal Architecture

```
scrapling/
├── __init__.py              # Lazy imports for top-level access
├── parser.py                # Selector/Selectors — core parsing (lxml-based)
├── cli/                     # CLI tools and interactive shell
├── core/
│   ├── custom_types.py      # TextHandler, AttributesHandler, etc.
│   ├── mixins.py            # SelectorsGeneration mixin
│   ├── storage.py           # SQLiteStorageSystem for adaptive tracking
│   └── translator.py        # CSS-to-XPath translation
├── fetchers/
│   ├── requests.py          # Fetcher, AsyncFetcher (curl_cffi wrappers)
│   ├── chrome.py            # DynamicFetcher (standard Playwright)
│   └── stealth_chrome.py    # StealthyFetcher (patchright + stealth)
├── engines/
│   ├── static.py            # FetcherClient, FetcherSession (curl_cffi logic)
│   ├── constants.py         # Browser args (STEALTH_ARGS, DEFAULT_ARGS)
│   ├── toolbelt/
│   │   ├── custom.py        # BaseFetcher, Response class
│   │   ├── convertor.py     # ResponseFactory — converts raw responses to Response
│   │   ├── fingerprints.py  # Header generation via browserforge
│   │   ├── navigation.py    # JS bypass scripts, proxy helpers
│   │   └── proxy_rotation.py # ProxyRotator
│   └── _browsers/
│       ├── _base.py         # SyncSession, AsyncSession (page pooling)
│       ├── _stealth.py      # StealthySession (patchright + CF solver)
│       ├── _controllers.py  # DynamicSession (standard Playwright)
│       ├── _config_tools.py # Stealth script compilation
│       ├── _page.py         # PageInfo, PagePool
│       ├── _validators.py   # Config validation models
│       └── _types.py        # Type definitions
└── spiders/                 # Spider framework (v0.4+)
```

### Dependency Chain

| Fetcher | HTTP Library | Browser Engine | Stealth Layer |
|---------|-------------|----------------|---------------|
| `Fetcher` | `curl_cffi` | None | TLS impersonation + browserforge headers |
| `DynamicFetcher` | None | `playwright` (Chromium) | Minimal (Google referer, headers) |
| `StealthyFetcher` | None | `patchright` (Chromium) | Full (6 JS scripts + CF solver + fingerprint spoofing) |

Key dependencies:
- **lxml** — HTML parsing (core parser)
- **cssselect** — CSS selector support
- **curl_cffi** — HTTP with TLS impersonation
- **playwright** — DynamicFetcher browser engine
- **patchright** — StealthyFetcher browser engine (patched Playwright fork)
- **browserforge** — realistic header generation
- **orjson** — fast JSON serialization for storage
- **tld** — domain extraction for referer generation

---

## 3. Fingerprint Adaptation System

Scrapling's "fingerprint" system refers to **two separate things**:

### A. Browser Fingerprint Evasion (StealthyFetcher)
- Uses `browserforge.headers.HeaderGenerator` to create realistic headers matching the OS and browser
- Hardcoded browser versions: Chromium 141, Chrome 143
- OS detection matches actual host OS for consistency
- Stealth JS scripts patch: `navigator.webdriver`, `window.chrome`, plugins, permissions, screen props, Playwright fingerprint
- `patchright` itself patches CDP (Chrome DevTools Protocol) detection at the library level

### B. Adaptive Element Tracking (Parser)
This is Scrapling's unique selling point — **element relocation after website changes:**

**How it works:**
1. **Save phase:** When you use `auto_save=True` on a CSS/XPath query, Scrapling serializes the matched element's "fingerprint" to storage:
   - Tag name, text content, attributes (class, id, etc.)
   - DOM position (depth, parent info, sibling relationships)
   - Generated CSS/XPath selectors for the element
   - Stored in SQLite (thread-safe, WAL mode) keyed by (URL domain, identifier)

2. **Relocate phase:** When you pass `adaptive=True` on a subsequent query:
   - Original selector is tried first
   - If it fails or returns different elements, retrieves saved fingerprint from storage
   - Scans all DOM elements and computes **multi-dimensional similarity scores**:
     - Tag name match
     - Text content similarity (using `difflib.SequenceMatcher`)
     - Attribute overlap
     - DOM path similarity
     - Parent/sibling relationships
   - Returns the highest-scoring match above a threshold

3. **Storage:** `SQLiteStorageSystem` with `lru_cache` singleton pattern, keyed by base domain (via `tld` library). Thread-safe with `RLock`.

**Practical value:** Moderate. Useful for monitoring/recurring scrapes where CSS selectors break due to design changes. Not magic — fails when the entire page structure changes radically.

---

## 4. Content Extraction Capabilities

### Selection Methods
All return `Selector` or `Selectors` objects:

| Method | Example | Notes |
|--------|---------|-------|
| CSS selectors | `page.css('.product h2::text')` | Scrapy/Parsel-compatible pseudo-elements |
| XPath | `page.xpath('//div[@class="price"]/text()')` | Full XPath 1.0 via lxml |
| `find_all()` | `page.find_all('div', class_='product')` | BeautifulSoup-style API |
| `find_by_text()` | `page.find_by_text('Price', tag='span')` | Text content search |
| Regex | Via `TextHandler.re()` / `TextHandler.re_first()` | Regex on extracted text |
| Chained selectors | `page.css('.product').css('h2::text')` | Chain for specificity |

### Navigation Methods
- `parent` — parent element
- `next_sibling` / `previous_sibling` — sibling traversal
- `children` — direct children
- `find_similar()` — find structurally similar elements
- `below_elements()` / `above_elements()` — spatial navigation

### Text Processing
- `TextHandler` wraps all text results with methods: `.clean()`, `.re()`, `.json()`, etc.
- `get_all_text(separator, strip, ignore_tags)` — concatenated text with filtering
- `prettify()` — formatted HTML output
- `html_content` — inner HTML

### Output Formats
- CSS/XPath selector auto-generation for any element
- CLI can extract to `.txt` (text), `.md` (markdown)
- Spider framework: `result.items.to_json()` / `result.items.to_jsonl()`

### What It Does NOT Do
- No built-in HTML→Markdown conversion (unlike Crawl4AI, Firecrawl, Jina Reader)
- No LLM-ready output formatting
- No structured data extraction with schemas/LLMs
- No automatic content extraction (readability-style) — you must write selectors

---

## 5. Known Limitations & Bugs

### StealthyFetcher DNS Bug (Our Server)
- **Symptom:** StealthyFetcher returns 0/6 on CF sites — DNS resolution failure
- **Root cause:** Likely `patchright` (Chromium) DNS resolution issue in our server environment
  - patchright uses Chromium's built-in DNS resolver, which may not use system DNS properly
  - Our server may have DNS configuration that standard Chromium doesn't handle
  - Camoufox (Firefox-based, used pre-v0.3) may have handled DNS differently
- **No matching issue found in Scrapling's GitHub** — suggests environment-specific problem
- **Workaround options:**
  - Use `cdp_url` to connect to an externally managed Chrome instance
  - Use `proxy` parameter (proxy handles DNS resolution)
  - Fall back to DynamicFetcher or Fetcher

### Other Known Limitations
1. **No auto-fetcher selection** — user must choose Fetcher/Dynamic/Stealthy manually
2. **Cloudflare solver is heuristic** — works on Turnstile/Interstitial but dedicated challenge pages can still block
3. **Adaptive tracking has limits** — radical page redesigns defeat similarity matching
4. **patchright dependency** — small fork project, potential maintenance risk
5. **Browser versions hardcoded** — `chromium_version = 141`, `chrome_version = 143` in fingerprints.py
6. **No built-in CAPTCHA solving** beyond Cloudflare Turnstile
7. **Heavy dependencies** — patchright + playwright + curl_cffi + lxml = large install footprint
8. **Spider framework is new** (v0.4, Feb 2026) — relatively untested in production

---

## 6. Comparison: Scrapling vs Raw curl_cffi + rebrowser-playwright

| Aspect | Scrapling | Raw curl_cffi + rebrowser-playwright |
|--------|-----------|--------------------------------------|
| **Setup complexity** | `pip install scrapling` — single package | Multiple installs, manual wiring |
| **HTTP stealth** | curl_cffi with browserforge headers | Same curl_cffi, headers are manual |
| **Browser stealth** | patchright + 6 JS scripts | rebrowser-playwright patches CDP differently |
| **CF bypass** | Built-in `solve_cloudflare=True` | Must implement solver manually |
| **DNS on our server** | StealthyFetcher broken (0/6) | rebrowser-playwright works (5/6) |
| **Parsing** | Rich Selector API, CSS/XPath/find | Must use lxml/BeautifulSoup separately |
| **Adaptive tracking** | Built-in SQLite-backed | Not available |
| **Reliability** | Depends on patchright maintenance | rebrowser-playwright actively maintained |
| **Flexibility** | Opinionated abstractions | Full control over every parameter |
| **Performance** | Lazy loading, optimized, orjson | No overhead, but no optimizations either |
| **Spider/Crawl** | Built-in Spider framework | Must build from scratch |

### Verdict for Our Use Case
**Raw curl_cffi + rebrowser-playwright is more reliable on our server** due to the StealthyFetcher DNS bug. Scrapling's value-add is the unified API and adaptive tracking, but for Oracle/CF bypass specifically, raw tools give us more control and actually work.

**Scrapling's Fetcher (curl_cffi)** is fine to use — it's just a thin wrapper and works as expected (4/6 CF sites). The issue is only with StealthyFetcher (patchright).

---

## 7. Maintenance & Community

| Metric | Value |
|--------|-------|
| Stars | ~14,800 |
| Forks | ~980 |
| Open Issues | 9 |
| Latest Release | v0.4 (2026-02-15, 10 days ago) |
| Last Push | 2026-02-25 (today) |
| Author | Karim Shoair (D4Vinci) |
| Contributors | Primarily solo developer with community PRs |
| Test Coverage | 92% claimed |
| CI | GitHub Actions, mypy + pyright type checking |
| Discord | Active (discord.gg/EMgGbDceNQ) |
| Docs | https://scrapling.readthedocs.io |
| Docker | Official image with browsers |

**Assessment:** Very actively maintained. Solo developer with strong velocity. v0.4 was a massive release (Spider framework). The project has commercial sponsors (proxy companies). Risk: bus factor of 1.

---

## 8. Comparison with Related Tools

### Crawl4AI
- **Repo:** https://github.com/unclecode/crawl4ai
- **Stars:** ~61k | **Last push:** 2026-02-25
- **Focus:** LLM-friendly web crawling — turns pages into clean Markdown
- **Engine:** Playwright (Chromium) with async-first design
- **Key differentiators vs Scrapling:**
  - **LLM-native output:** Clean Markdown, Fit Markdown (heuristic noise removal), BM25 filtering
  - **Structured extraction:** LLM-driven extraction with schemas, CSS-based extraction
  - **Chunking strategies:** Topic-based, regex, sentence-level for RAG pipelines
  - **Deep crawling:** BFS/DFS strategies, crash recovery, resume
  - **Session management:** Browser profiles, managed browser, remote CDP
  - **Cosine similarity search** for semantic content extraction
  - **Docker deployment** with REST API and WebSocket streaming
- **What Scrapling does better:** Adaptive element tracking, curl_cffi HTTP layer, CF Turnstile solver
- **What Crawl4AI does better:** Markdown generation, LLM integration, structured extraction, larger community
- **Our use case fit:** Better for "scrape and feed to LLM" workflows. Not as good for anti-detection.

### Firecrawl
- **Repo:** https://github.com/firecrawl/firecrawl
- **Stars:** ~85.7k | **Last push:** 2026-02-25
- **Focus:** Web Data API for AI — turns websites into LLM-ready data
- **Architecture:** SaaS API (firecrawl.dev) + self-hostable monorepo
- **Key differentiators vs Scrapling:**
  - **API-first:** REST API with SDKs (Python, Node, Go, Rust)
  - **Agent mode:** AI agent that searches/navigates/extracts autonomously
  - **Structured JSON extraction** with Pydantic schemas or prompts
  - **Map:** URL discovery for entire sites
  - **Batch scraping:** Async bulk processing
  - **Actions:** Click, scroll, type before scraping
  - **Media parsing:** PDF, DOCX, image text extraction
  - **Change tracking:** Monitor website content changes
  - **Branding extraction:** Colors, fonts, typography
- **What Scrapling does better:** Free/self-hosted, adaptive tracking, CF solver, curl_cffi layer
- **What Firecrawl does better:** Everything LLM-related, scale, reliability (80%+ benchmark), community
- **Our use case fit:** Excellent for general web scraping, but API-key based. Self-hosting not fully ready.

### Jina Reader
- **Repo:** https://github.com/jina-ai/reader
- **Stars:** ~9.9k | **Last push:** 2025-05-08 (9+ months ago — possibly stale)
- **Focus:** URL → LLM-friendly text, zero setup
- **Architecture:** Hosted API — just prepend `https://r.jina.ai/` to any URL
- **Key differentiators vs Scrapling:**
  - **Zero-code:** No installation, just URL prefix
  - **Clean Markdown output** with readability filtering
  - **Search mode:** `s.jina.ai` for web search with content extraction
  - **PDF support:** Extracts text from PDFs
  - **Image captioning** (optional)
  - **Streaming mode** for SPAs with delayed content
  - **CSS targeting:** `x-target-selector` header for specific elements
  - Uses Puppeteer + headless Chrome + ReaderLM-v2 for conversion
- **What Scrapling does better:** Self-hosted, adaptive tracking, CF bypass, full automation
- **What Jina Reader does better:** Zero setup, Markdown quality, PDF/image support
- **Our use case fit:** Great for quick content extraction. Not suitable for protected pages or automation.
- **Concern:** Last commit 9 months ago — maintenance unclear.

---

## 9. Summary & Recommendations

### For Our Web Scraping Skill (Information Gathering)
1. **HTTP layer:** Use Scrapling's `Fetcher` or raw `curl_cffi` — both work, Scrapling adds nice headers/referer generation
2. **JS-rendered pages:** Use `rebrowser-playwright` directly (not Scrapling's DynamicFetcher) for better control
3. **CF-protected pages:** Our existing tiered pipeline (curl → stealth browser → manual bootstrap) is more reliable than Scrapling alone
4. **Content extraction:** For LLM feeding, consider adding Crawl4AI's Markdown generation on top of our raw fetchers
5. **Adaptive tracking:** Scrapling's adaptive feature is unique but niche — useful for long-running monitors, not one-off scrapes

### For Oracle Browser Mode (Priority)
Scrapling's StealthyFetcher is **not suitable** due to the DNS bug. Stick with our rebrowser-playwright + curl_cffi pipeline.

### Tool Selection Matrix

| Need | Best Tool |
|------|-----------|
| Quick HTTP scrape, no JS | Scrapling Fetcher or raw curl_cffi |
| JS-rendered pages, no anti-detection | Scrapling DynamicFetcher or Playwright |
| Anti-detection / CF bypass | rebrowser-playwright + custom stealth |
| URL → clean Markdown for LLM | Crawl4AI or Jina Reader |
| Structured data extraction for AI | Firecrawl (API) or Crawl4AI |
| Full website crawl | Scrapling Spider or Crawl4AI |
| Long-running monitor with selector resilience | Scrapling (adaptive tracking) |
