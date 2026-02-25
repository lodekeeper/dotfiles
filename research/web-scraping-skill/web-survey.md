# Web Scraping & Anti-Bot Bypass Survey (Feb 2026)

*Research date: 2026-02-25. Focus: free/open-source tools only.*

---

## Table of Contents

1. [Scrapling (D4Vinci/Scrapling)](#1-scrapling)
2. [Tool Comparison: Scrapling vs Playwright vs curl_cffi vs Camoufox](#2-tool-comparison)
3. [Cloudflare Bypass — State of the Art 2025-2026](#3-cloudflare-bypass)
4. [Other Anti-Bot Systems (Akamai, PerimeterX/HUMAN, DataDome)](#4-other-anti-bot-systems)
5. [Content Extraction Tools](#5-content-extraction)
6. [Novel Approaches: Fingerprinting & Evasion](#6-novel-approaches)
7. [AI Agent Scraping Tools (Firecrawl, Jina, Crawl4AI, etc.)](#7-ai-agent-tools)
8. [Recommended Architecture for Our Use Case](#8-recommended-architecture)

---

## 1. Scrapling

**Repo:** https://github.com/D4Vinci/Scrapling  
**Version:** v0.4 (Feb 2026) — 10.6k stars, 678 forks, 1,124 commits, 5 contributors  
**License:** BSD-3-Clause

### What It Is

Scrapling is an all-in-one Python web scraping framework that bundles:
- **Adaptive parser** — CSS/XPath/BS4-style selectors with smart element tracking that survives website redesigns via similarity algorithms
- **Three fetcher backends** sharing a unified response interface:
  - `Fetcher` — HTTP via httpx + curl-impersonate TLS fingerprinting, HTTP/3 support
  - `DynamicFetcher` — Playwright (Chromium/Chrome) for JS-rendered pages
  - `StealthyFetcher` — Stealth browser (patchright-based) for anti-bot bypass, Cloudflare Turnstile/Interstitial
- **Spider framework** — Scrapy-like API with concurrent crawling, multi-session support, pause/resume checkpoints, streaming mode
- **MCP server** — AI-assisted scraping integration with Claude/Cursor
- **CLI** — `scrapling extract` for code-free scraping, interactive IPython shell

### Parser Performance (from official benchmarks)

| Library | Time (ms) | vs Scrapling |
|---------|-----------|-------------|
| **Scrapling** | 2.02 | 1.0x |
| Parsel/Scrapy | 2.04 | 1.01x |
| Raw lxml | 2.54 | 1.26x |
| PyQuery | 24.17 | ~12x |
| Selectolax | 82.63 | ~41x |
| BS4 (lxml) | 1,584 | ~784x |
| BS4 (html5lib) | 3,392 | ~1,679x |

### Our Testing Results (2026-02-25)

Against 6 Cloudflare-protected sites:
- `Fetcher` (curl_cffi): 4/6 passed
- `DynamicFetcher` (rebrowser-playwright): 5/6 passed
- `StealthyFetcher` (patchright): 0/6 — DNS resolution bug on our server

### Assessment

**Strengths:** One library covers the entire pipeline. Adaptive element tracking is genuinely unique — reduces scraper maintenance when sites change incrementally. Parser is fast (on par with Parsel). Spider framework adds Scrapy-like capabilities without Scrapy's complexity. MCP server integration is forward-looking.

**Weaknesses:** Bus factor — only 5 contributors, mostly one person. Full install is heavy (Playwright + browser binaries). `StealthyFetcher` (patchright) has reliability issues. Anti-bot bypass operates in a legal gray area.

**Bottom line:** Best as an all-in-one framework for medium-complexity scraping. For maximum stealth, use its `Fetcher` (curl_cffi) tier and pair with a dedicated stealth browser (Camoufox) rather than relying on `StealthyFetcher`.

---

## 2. Tool Comparison

### HTTP-Level Tools (No JS Execution)

| Tool | TLS Fingerprint | HTTP/2 | HTTP/3 | Speed | Anti-Bot | Notes |
|------|----------------|--------|--------|-------|----------|-------|
| **curl_cffi** | ✅ Chrome/FF/Safari | ✅ | ✅ | Excellent | Good (TLS only) | Python binding for curl-impersonate. Most mature. |
| **rnet** | ✅ Chrome/FF/Safari/OkHttp | ✅ | ✅ | Superior | Good (TLS only) | Rust-powered (wreq). Newer, faster than curl_cffi. |
| **tls_client** | ✅ | ✅ | ❌ | Good | Good (TLS only) | Go-based, Python wrapper. |
| **httpx/requests** | ❌ | Partial | ❌ | Good | None | Instantly flagged by JA3/JA4. |

**Verdict:** `curl_cffi` is the current standard for Python TLS impersonation. `rnet` is emerging as a faster alternative (Rust-based, using BoringSSL). Both handle the TLS layer but cannot execute JavaScript.

### Browser Automation Tools (JS Execution + Stealth)

| Tool | Engine | Stealth Level | CF Bypass | Async | Maintenance | Notes |
|------|--------|--------------|-----------|-------|-------------|-------|
| **Camoufox** | Firefox (modified C++) | ★★★★★ | ~80-90% | Sync + async | Beta (recovering after gap) | Engine-level fingerprint spoofing. Best stealth. Only Firefox-based tool. |
| **Nodriver** | Chrome (CDP direct) | ★★★★ | ~90% | Fully async | Active | Successor to undetected-chromedriver. No WebDriver = no automation markers. |
| **Pydoll** | Chrome (CDP) | ★★★★ | ~85% | Fully async | Active | Similar to nodriver. WebDriverless. Human-like interactions. |
| **Patchright** | Chromium (Playwright fork) | ★★★☆ | ~70% | Sync + async | Active | Playwright API with stealth patches. Drop-in replacement. |
| **rebrowser-playwright** | Chromium (patched PW) | ★★★☆ | ~70% | Sync + async | Active | Patches to avoid CDP detection leaks. |
| **SeleniumBase UC Mode** | Chrome (Selenium) | ★★★☆ | ~75% | Sync | Active | Existing Selenium code compatible. Built-in CAPTCHA handling. |
| **undetected-chromedriver** | Chrome (Selenium) | ★★☆ | ~60% | Sync | Declining | Predecessor to nodriver. Being surpassed. |
| **Playwright (vanilla)** | Chromium/FF/WebKit | ★ | <20% | Sync + async | Active | Detected instantly. For testing, not scraping. |

### Key Community Sentiments (Reddit r/webscraping, late 2025-early 2026)

- **Camoufox** is the consensus "best open source option for anti-detect" (multiple threads)
- Nodriver: "faster than camoufox but not as stealthy"
- Camoufox is "the only one that consistently achieves 0% detection scores across major test suites"
- "Camoufox cause its the only one that bypass datadome anyways" (common sentiment)
- Pydoll is gaining traction — native CDP, good anti-detection
- puppeteer-stealth was deprecated in early 2026

### Our Recommended Stack

```
Tier 1: curl_cffi (or rnet) — fast HTTP with TLS impersonation
  ↓ if blocked
Tier 2: Camoufox — stealth Firefox with fingerprint rotation
  ↓ if still blocked  
Tier 3: Manual cookie bootstrap (get cf_clearance from real browser)
```

---

## 3. Cloudflare Bypass — State of the Art 2025-2026

### Cloudflare's Detection Layers (as of Jan 2026)

1. **TLS/Network fingerprinting** — JA3/JA4 hash matching, HTTP/2 frame ordering, cipher suite analysis
2. **JavaScript Detections (JSD)** — Lightweight invisible JS snippet checking browser environment properties. Issues `cf_clearance` cookie on success.
3. **JavaScript Challenge (IUAM)** — "Checking your browser" interstitial. Canvas/WebGL rendering, navigator consistency, execution timing.
4. **Behavioral analysis** — Mouse movements, scroll patterns, click timing, request sequencing
5. **ML bot scoring** — Supervised learning, bot scores 1-99, incorporates all signals + IP reputation
6. **AI Labyrinth** (NEW, March 2025) — Generates fake AI-written honeypot pages with invisible nofollow links. Bots that follow links crawl into infinite garbage data while Cloudflare maps their patterns.

### What's Working (Feb 2026)

| Method | CF Success Rate | Layer Bypassed | Notes |
|--------|----------------|---------------|-------|
| curl_cffi/rnet | 60-80% | Layer 1 only | Works for sites with basic CF (no JS challenge) |
| Camoufox (headless) | 80-90% | Layers 1-3 | Humanize mode helps with Layer 4 |
| Nodriver | ~90% | Layers 1-3 | No WebDriver artifacts |
| Pydoll | ~85% | Layers 1-3 | CDP-native, still maturing |
| SeleniumBase UC | ~75% | Layers 1-3 | Auto-CAPTCHA handling via uc_gui_click_captcha() |
| FlareSolverr | ~50% | Layers 1-2 | Based on undetected-chromedriver (outdated). Declining effectiveness. |

### What's Been Patched / Harder in 2026

- **Cloudflare per-customer ML models** — Enterprise customers get custom-trained models on their own traffic. Generic bypass tools fail more often.
- **AI Labyrinth** — Crawlers that follow links now risk falling into AI-generated garbage pages. Content validation is essential.
- **JA4 fingerprinting** — Sorts extensions alphabetically before hashing, defeating JA3 permutation attacks
- **Behavioral analysis improvements** — Session consistency tracking (fingerprint changes mid-session flagged), click precision analysis

### Critical Lesson from The Web Scraping Club (Jan 2026)

Testing Camoufox, Pydoll, and undetected-chromedriver against Harrods.com and Indeed.com:
- **Generic CF detection (searching for "checking your browser") produces false positives** — tools can return partial pages with neither CF challenges nor real content
- **Content validation is essential** — Check for site-specific elements (product names, search buttons) rather than absence of CF challenges
- Indeed.com blocks even sitemap access with 403
- Camoufox needed 2+ seconds wait after page load for CF challenges to resolve

### Practical Recommendations

1. **Always validate content** — Don't just check for HTTP 200 or absence of CF strings
2. **AI Labyrinth defense** — Only follow links you explicitly expect; validate extracted content makes sense
3. **Session persistence** — Reuse cf_clearance cookies across requests
4. **Residential IPs matter** — Even perfect fingerprints fail from datacenter IPs on aggressively protected sites
5. **Rate limiting** — Random delays (2-5s + jitter), variable timing, organic navigation patterns

---

## 4. Other Anti-Bot Systems

### Difficulty Ranking (Community Consensus, late 2025)

From hardest to easiest:
1. **Kasada** — Hardest. Heavy JS obfuscation, proof-of-work challenges
2. **Imperva/Incapsula** — Aggressive fingerprinting, difficult to bypass
3. **Cloudflare Enterprise** — Per-customer ML models
4. **PerimeterX/HUMAN** — Complex sensor data generation, dual-layered challenges  
5. **Akamai Bot Manager** — JA4 fingerprinting pioneer, but becoming easier
6. **DataDome** — Behavioral focus, but beatable with Camoufox
7. **Cloudflare Free/Pro** — Widely bypassed

### Akamai

- **Detection:** JA4 fingerprinting (they literally invented the HTTP/2 passive fingerprinting technique), behavioral analysis, device fingerprinting
- **Free bypass:** Camoufox + residential proxies works for most sites. curl_cffi with correct JA4 fingerprint for sites without JS challenges.
- **Key tool:** azuretls-client (Go) — browser-identical TLS/HTTP2/JA4 fingerprinting

### PerimeterX / HUMAN

- **Detection:** Heavyweight JS sensor (`px.js`) collecting 200+ browser properties, mouse/touch events, accelerometer data. Generates encrypted payloads sent to `collector-*.perimeterx.net`.
- **Free bypass approaches:**
  - Camoufox (best free option — passes most JS fingerprint checks)
  - Request-based bypass requires reverse-engineering sensor data generation (Go implementations exist on GitHub but are fragile and quickly patched)
  - Cookie bootstrapping from real browser sessions
- **Hardest part:** The JS sensor payload is regularly updated and requires constant reverse engineering

### DataDome

- **Detection:** Behavioral analysis primary, JS fingerprinting secondary. Tests Canvas/WebGL consistency, checks for automation patterns.
- **Free bypass:**
  - **Camoufox is the go-to** — multiple r/webscraping users report it's "the only one that bypasses DataDome"
  - undetected-chromedriver still partially works (patches TLS, HTTP, and JS fingerprints)
  - Full reverse-engineering is "the most complex" approach but most reliable
- **Notable:** DataDome is considered "a bit on the easier side" by experienced scrapers (late 2025)

### General Anti-Bot Bypass Principles

1. **TLS fingerprint must match a real browser** — curl_cffi/rnet for HTTP, stealth browsers for JS
2. **HTTP/2 settings must be browser-correct** — SETTINGS frame values, WINDOW_UPDATE, PRIORITY frames
3. **Header order matters** — Real browsers send headers in specific, consistent order
4. **Behavioral patterns must look human** — Variable timing, mouse movements, organic navigation
5. **IP reputation is a separate layer** — Datacenter IPs flagged regardless of fingerprint quality

---

## 5. Content Extraction

### Benchmark Results

#### Scrapinghub Article Extraction Benchmark (latest)

| Tool | Version | F1 | Precision | Recall |
|------|---------|------|-----------|--------|
| **go-trafilatura** | ae7ea06 | **0.960** | 0.940 | 0.980 |
| **trafilatura** | 2.0.0 | **0.958** | 0.938 | 0.978 |
| newspaper4k | 0.9.3.1 | 0.949 | 0.964 | 0.934 |
| news_please | 1.6.16 | 0.948 | 0.964 | 0.933 |
| readability_js | 0.6.0 | 0.947 | 0.914 | 0.982 |
| go_readability | 9f5bf5c | 0.934 | 0.900 | 0.971 |
| newspaper3k | 0.2.8 | 0.912 | 0.917 | 0.906 |
| readability-lxml | 0.7.1 | 0.922 | 0.913 | 0.931 |

#### Trafilatura's Own Benchmark (750 docs, 2022 — but still representative)

| Tool | Precision | Recall | F-Score |
|------|-----------|--------|---------|
| **trafilatura (precision)** | **0.930** | 0.886 | **0.907** |
| **trafilatura (recall)** | 0.893 | **0.904** | 0.898 |
| readability-lxml | 0.891 | 0.729 | 0.801 |
| news-please | 0.898 | 0.734 | 0.808 |
| goose3 | 0.934 | 0.690 | 0.793 |
| newspaper3k | 0.895 | 0.593 | 0.713 |

#### Sandia National Labs Evaluation (2024)

"While no single library outperformed the others, **Trafilatura and Readability had the highest overall performance**."

### Tool Profiles

| Tool | Best For | Speed | Maintained | Notes |
|------|----------|-------|------------|-------|
| **trafilatura** | General web content, multilingual | Fast | ✅ Active (v2.0.0) | Best overall F1. Supports metadata, dates, comments extraction. CLI available. |
| **readability-lxml** | Article cleaning | Very fast | ✅ | Mozilla Readability port. Best recall (captures most content). |
| **newspaper4k** | News articles + NLP | Moderate | ✅ | Fork of newspaper3k. NLP features (keywords, summary). Google News scraping. |
| **newspaper3k** | — | Moderate | ❌ Dead | Last updated 4+ years ago. Use newspaper4k instead. |
| **goose3** | High-precision extraction | Slow | Minimal | Most precise but worst recall. |
| **Fundus** | Academic/labeled datasets | — | ✅ | Highest accuracy on labeled benchmarks. Publisher-specific parsers. |

### Recommendation

**Trafilatura is the clear winner** for general-purpose content extraction:
- Best F1 scores across multiple independent benchmarks
- Actively maintained (v2.0.0 as of early 2026)
- Multilingual support (best for German, Greek, English, Chinese)
- Extracts metadata, dates, authors, comments — not just body text
- CLI tool (`trafilatura`) for quick extraction
- Can output text, XML, JSON, or CSV

For a **hybrid pipeline:**
```
Primary: trafilatura (best accuracy)
Fallback: readability-lxml (fast, good recall when trafilatura struggles)
Structured news: newspaper4k (when NLP features needed)
```

---

## 6. Novel Approaches: Fingerprinting & Evasion

### TLS Fingerprinting (JA3/JA4)

**What it is:** During TLS handshake, the ClientHello packet reveals cipher suites, extensions, TLS version, elliptic curves. This is hashed into JA3 (or newer JA4) fingerprints.

**Key tools:**
- **curl-impersonate / curl_cffi** — Patches curl to use BoringSSL (Chrome) or NSS (Firefox) TLS stacks. The standard for Python TLS impersonation.
- **rnet** — Rust-based (wreq), BoringSSL, claims faster than curl_cffi. Python bindings. Newer but promising.
- **azuretls-client** (Go) — Full JA3/JA4 + HTTP/2 fingerprint spoofing
- **Hazetunnel** — TLS-aware proxy that terminates TLS with browser-like profile; your scraper talks HTTP behind it

**JA4 vs JA3:** JA4 (introduced 2023) sorts TLS extensions alphabetically before hashing, making it resistant to the extension-order randomization that Chrome added to break JA3. Anti-bot systems increasingly use JA4. Tools must match JA4 specifically.

### HTTP/2 Fingerprinting

**What it is:** Beyond TLS, the HTTP/2 connection setup reveals fingerprints through:
- SETTINGS frame values (HEADER_TABLE_SIZE, MAX_CONCURRENT_STREAMS, INITIAL_WINDOW_SIZE, etc.)
- WINDOW_UPDATE frame size
- PRIORITY frames (Firefox sends these for unopened streams)
- Pseudo-header order (:method, :authority, :scheme, :path)

**Akamai pioneered** passive HTTP/2 fingerprinting (Black Hat EU 2017). They can identify browser vs library from SETTINGS alone.

**Key insight:** "Manual HTTP/2 configuration is extremely fragile and breaks with browser updates." — Use browser automation or curl-impersonate for reliable fingerprints.

### Browser Fingerprint Emulation

**Engine-level approach (Camoufox):**
- Modifies Firefox C++ source code to rewrite how the browser reports Canvas, WebGL, fonts, screen dimensions, navigator properties
- Produces internally consistent fingerprints (all surfaces agree)
- Firefox engine diversity avoids Chrome-specific ML detection models

**Patch-based approach (Patchright, rebrowser-playwright):**
- Patches Playwright/Puppeteer to avoid specific detection vectors
- Patchright: removes `--enable-automation`, patches `Runtime.enable` CDP command
- rebrowser-patches: fixes CDP leaks that reveal automation
- Less thorough than engine-level — can still leak through novel detection vectors

**CDP-avoidance approach (Nodriver, Pydoll):**
- Launches real Chrome, communicates via CDP without WebDriver
- No `navigator.webdriver` flag because there's no WebDriver
- No automation markers because no automation framework injects them
- Relies on the real browser being genuine — no fingerprint spoofing needed

### Cloudflare AI Labyrinth (NEW)

**Announced March 2025.** Instead of blocking suspected bots, CF generates fake AI-written pages as honeypots:
- Invisible links with `nofollow` tags added to real pages
- Bots following links crawl into infinite generated garbage
- Functions as "next-generation honeypot" — maps bot request patterns
- Human visitors don't see/follow the fake links

**Defense:** Only navigate to explicitly expected URLs. Validate extracted content makes semantic sense. Don't blindly follow all links.

### Header Order Fingerprinting

Real Chrome sends headers in a specific order (Accept, Accept-Language, Accept-Encoding, Sec-CH-UA, etc.). Python's `requests` sends them alphabetically or in insertion order. Header order alone can identify automated clients. curl_cffi and rnet handle this correctly when impersonating browsers.

---

## 7. AI Agent Scraping Tools

### Firecrawl

**Repo:** https://github.com/firecrawl/firecrawl  
**What:** "The Web Data API for AI" — crawls websites and converts to LLM-friendly markdown/structured data  
**Architecture:** 
- Cloud service with API (primary model)
- Self-hostable via Docker (API + worker + PostgreSQL + Redis)
- Uses Playwright internally for JS rendering
- Anti-bot bypass via their "fire-engine" (not fully open-sourced)
- `firecrawl-simple` fork exists: stripped-down, uses Ulixee Hero instead of fire-engine

**Self-hosting issues:** Community complaints that self-hosted version is intentionally degraded vs cloud (broken markdown links, etc.). `firecrawl-simple` by devflowinc is the better self-hosted option.

**Our assessment:** Useful architecture to study, but not suitable for fully free/local deployment. The anti-bot bypass is their proprietary value-add.

### Jina Reader

**Repo:** https://github.com/jina-ai/reader  
**What:** Prefix any URL with `https://r.jina.ai/` to get LLM-friendly markdown  
**Architecture:**
- Open source, self-hostable
- Uses a proxy to fetch URLs, renders in browser
- Extracts main content, converts to clean markdown
- Search mode: `https://s.jina.ai/YOUR_QUERY`
- **ReaderLM-v2** — 1.5B parameter model for HTML→markdown conversion (can run locally on Ollama)
- Supports iframes, Shadow DOM, PDF/HTML upload

**Our assessment:** Good for simple URL→markdown conversion. ReaderLM-v2 is interesting for local deployment. No serious anti-bot bypass.

### Crawl4AI

**Repo:** https://github.com/unclecode/crawl4ai — 40k+ stars  
**What:** "Open-source LLM Friendly Web Crawler & Scraper"  
**Architecture:**
- Python, async-first, **uses Playwright under the hood**
- Converts pages to LLM-friendly markdown natively
- Multiple extraction strategies (CSS, LLM-based, cosine similarity)
- Identity-based crawling (reuse browser profiles for logged-in scraping)
- Browser pool management for concurrent crawling
- Integrations with AG2, LangChain, etc.

**Our assessment:** **Best fully open-source option for AI-agent web scraping.** Playwright-based, so inherits Playwright's JS rendering + can use stealth patches. Self-hosting is production-ready. No vendor lock-in.

### ScrapeGraphAI

**Repo:** https://github.com/ScrapeGraphAI/Scrapegraph-ai  
**What:** "Python scraper based on AI" — uses LLMs to extract data via natural language prompts  
**Architecture:**
- LangChain/LangGraph pipelines
- Supports OpenAI, Ollama, local models
- No CSS selectors needed — describe what you want in English
- Visual workflow builder (ScrapeCraft)

**Our assessment:** Interesting NLP-driven approach. Works well when you don't know the page structure. Requires LLM API calls (cost for each extraction). Best for exploratory scraping, not high-volume.

### Comparison Summary

| Tool | Self-Host | Anti-Bot | JS Render | LLM Output | Volume | Best For |
|------|-----------|----------|-----------|------------|--------|----------|
| **Crawl4AI** | ✅ Full | Via Playwright | ✅ | ✅ Markdown | High | Self-hosted AI scraping |
| Firecrawl | ⚠️ Partial | Cloud only | ✅ | ✅ Markdown/JSON | High | If using cloud API |
| Jina Reader | ✅ Full | Basic | ✅ | ✅ Markdown | Medium | Simple URL→markdown |
| ScrapeGraphAI | ✅ Full | None | Via PW | ✅ NLP extraction | Low | Exploratory/unknown pages |
| Scrapling MCP | ✅ Full | ✅ (StealthyFetcher) | ✅ | Via MCP | Medium | Claude/Cursor integration |

---

## 8. Recommended Architecture for Our Use Case

Based on all research, here's the optimal free/open-source scraping stack:

### Tiered Fetching Pipeline

```
┌─────────────────────────────────────────┐
│           URL to Scrape                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Tier 1: curl_cffi / rnet               │
│  - TLS impersonation (Chrome/Firefox)   │
│  - HTTP/2 + correct headers             │
│  - Fast, low resource                   │
│  - Works for ~60-80% of sites           │
└──────────────┬──────────────────────────┘
               │ if blocked / JS required
               ▼
┌─────────────────────────────────────────┐
│  Tier 2: Camoufox (headless)            │
│  - Engine-level fingerprint spoofing    │
│  - humanize=True for behavioral evasion │
│  - OS fingerprint rotation              │
│  - Works for ~80-90% of remaining sites │
└──────────────┬──────────────────────────┘
               │ if still blocked
               ▼
┌─────────────────────────────────────────┐
│  Tier 3: Manual Cookie Bootstrap        │
│  - Get cf_clearance from real browser   │
│  - Replay cookies with curl_cffi        │
│  - Or: Nodriver with real Chrome profile│
└─────────────────────────────────────────┘
```

### Content Extraction Pipeline

```
Raw HTML → trafilatura.extract()
  ↓ (if fails or poor quality)
Raw HTML → readability-lxml → trafilatura on cleaned HTML
  ↓ (for LLM consumption)
Markdown output via trafilatura or html2text
```

### Key Libraries

| Role | Primary | Fallback |
|------|---------|----------|
| HTTP + TLS | curl_cffi (impersonate="chrome136") | rnet |
| Stealth Browser | Camoufox | Nodriver |
| Content Extraction | trafilatura | readability-lxml |
| HTML→Markdown | trafilatura (built-in) | html2text |
| Full Framework | Scrapling (if all-in-one needed) | Crawl4AI (if AI-agent integration) |
| Proxy Rotation | Scrapling ProxyRotator | Custom with free proxy lists |

### Anti-Detection Checklist

- [x] TLS fingerprint matches real browser (JA3 + JA4)
- [x] HTTP/2 SETTINGS/PRIORITY frames match browser
- [x] Header order matches browser
- [x] No `navigator.webdriver` flag
- [x] Canvas/WebGL fingerprints are consistent and non-default
- [x] Variable request timing (2-5s + random jitter)
- [x] Content validation (check for site-specific elements, not just HTTP 200)
- [x] AI Labyrinth defense (don't follow unknown links blindly)
- [x] Session consistency (don't change fingerprints mid-session)
- [ ] Residential/mobile IP (requires paid proxy — out of scope for free tools)

### Installed in Our Environment

Already installed in `~/camoufox-env` venv:
- curl_cffi
- camoufox
- rebrowser-playwright  
- patchright
- playwright-stealth
- nodriver
- websocket-client
- Scrapling v0.4

### What We Still Need

1. **trafilatura** — Not yet installed. Best content extraction tool.
2. **readability-lxml** — Fallback extractor.
3. **rnet** — Newer, faster TLS client (evaluate as curl_cffi replacement).
4. **newspaper4k** — If NLP features (keywords, summary) are needed.

---

## Sources

- Scrapling GitHub: https://github.com/D4Vinci/Scrapling
- DarkWebInformer Scrapling review (Feb 2026): https://darkwebinformer.com/scrapling-an-adaptive-web-scraping-framework/
- The Web Scraping Club — "Bypassing Cloudflare in 2026" (Jan 2026): https://substack.thewebscraping.club/p/bypassing-cloudflare-in-2026
- RoundProxies — "How to bypass Anti-Bots in 2026": https://roundproxies.com/blog/how-to-bypass-anti-bots/
- RoundProxies — "How to bypass Cloudflare in 2026": https://roundproxies.com/blog/bypass-cloudflare/
- Proxies.sx — "Camoufox vs Nodriver vs Stealth MCP (2026)": https://www.proxies.sx/blog/ai-browser-automation-camoufox-nodriver-2026
- Scrapinghub Article Extraction Benchmark: https://github.com/scrapinghub/article-extraction-benchmark
- Trafilatura evaluation: https://trafilatura.readthedocs.io/en/latest/evaluation.html
- Sandia National Labs content extraction evaluation (2024): https://www.osti.gov/servlets/purl/2429881
- Cloudflare AI Labyrinth announcement: https://blog.cloudflare.com/ai-labyrinth/
- Akamai HTTP/2 fingerprinting (Black Hat EU 2017): https://blackhat.com/docs/eu-17/materials/eu-17-Shuster-Passive-Fingerprinting-Of-HTTP2-Clients-wp.pdf
- Crawl4AI GitHub: https://github.com/unclecode/crawl4ai
- Firecrawl GitHub: https://github.com/firecrawl/firecrawl
- Jina Reader GitHub: https://github.com/jina-ai/reader
- rnet GitHub: https://github.com/0x676e67/rnet
- curl_cffi GitHub: https://github.com/lexiforest/curl_cffi
- Camoufox GitHub: https://github.com/daijro/camoufox
- Nodriver GitHub: https://github.com/ultrafunkamsterdam/nodriver
- Patchright GitHub: https://github.com/Kaliiiiiiiiii-Vinyzu/patchright
- rebrowser-patches GitHub: https://github.com/rebrowser/rebrowser-patches
- Pydoll GitHub: https://github.com/autoscrape-labs/pydoll
- Reddit r/webscraping (multiple threads, Oct 2025 — Feb 2026)
