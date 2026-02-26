---
name: web-scraping
description: Universal web scraping for AI agents using free/open-source tools. Use when `web_fetch` is blocked or incomplete, when scraping JS-rendered SPAs, Cloudflare-protected pages, structured data, or login-gated pages. Provides tiered escalation: curl_cffi → DynamicFetcher → Camoufox → authenticated sessions.
---

# Web Scraping Skill

Universal web scraping for AI agents. Scrape any website — static, JS-rendered, or Cloudflare-protected — using free/open-source tools only.

**Try `web_fetch` first.** Only use this skill when the built-in tool fails or returns incomplete content.

---

## Prerequisites

```bash
# Activate the scraping environment
source ~/camoufox-env/bin/activate

# Verify tools
python3 -c "import curl_cffi; print('curl_cffi:', curl_cffi.__version__)"
python3 -c "import scrapling; print('scrapling OK')"
python3 -c "import trafilatura; print('trafilatura:', trafilatura.__version__)"
python3 -c "import camoufox; print('camoufox:', camoufox.__version__)"
```

**Venv location:** `~/camoufox-env` (Python 3.12)
**Installed:** curl_cffi, scrapling 0.4, camoufox 0.4.11, rebrowser-playwright, trafilatura, patchright, playwright-stealth, nodriver

## Related Skills

- `skills/deep-research/SKILL.md` — use after scraping when the task needs synthesis, tradeoff analysis, or a formal research output.
- `skills/oracle-bridge/SKILL.md` — use when Oracle browser mode is needed for ChatGPT Pro reasoning/manual Deep Research handoff.

---

## Decision Flowchart

```
Need web content?
  │
  ├─ Simple page, no anti-bot? ──→ web_fetch (built-in, no setup)
  │
  ├─ web_fetch blocked/incomplete?
  │   │
  │   ├─ Static/SSR site? ──→ Tier 1: curl_cffi (0.2-1.6s)
  │   │
  │   ├─ JS-rendered SPA? ──→ Tier 2: DynamicFetcher (0.9-2.8s)
  │   │
  │   ├─ CF-protected + JS challenge? ──→ Tier 3: Camoufox (5-10s)
  │   │
  │   ├─ Login required? ──→ Tier 4: Authenticated session
  │   │
  │   └─ Hard block (beaconcha.in-level)? ──→ Use site's API instead
  │
  └─ Need structured data extraction? ──→ See "Content Extraction" section
```

---

## Tier 1: curl_cffi (Fast HTTP with TLS Impersonation)

**Best for:** Static sites, SSR pages, APIs, sites with basic CF protection.
**Speed:** 0.2-1.6s per page. **No browser needed.**
**Success rate:** ~70% of websites including many CF-protected sites.

```python
#!/usr/bin/env python3
"""Tier 1: curl_cffi — fast HTTP with browser TLS fingerprint."""
import sys
from curl_cffi import requests as cffi_requests
import trafilatura

url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"

# Impersonate Chrome 131 (matches real browser TLS + HTTP/2 fingerprint)
resp = cffi_requests.get(
    url,
    impersonate="chrome131",
    timeout=15,
    headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    },
)

if resp.status_code != 200:
    print(f"FAILED: HTTP {resp.status_code}", file=sys.stderr)
    sys.exit(1)

html = resp.text

# Validate: not a CF challenge page
if "Checking your browser" in html or "cf-browser-verification" in html:
    print("BLOCKED: Cloudflare challenge detected", file=sys.stderr)
    sys.exit(2)

# Extract clean text
text = trafilatura.extract(html, url=url, include_links=True, include_tables=True)
if text:
    print(text)
else:
    # Fallback: raw HTML (trafilatura couldn't extract)
    print(html[:50000])
```

### When curl_cffi is enough

Sites confirmed working (from benchmarks):
- `news.ycombinator.com` — classic HTML
- `github.com/trending` — SSR
- `ethresear.ch` — Discourse forum (SSR)
- `npmjs.com` — CF-protected but TLS impersonation sufficient
- `eips.ethereum.org` — static GitHub Pages
- Most documentation sites, blogs, news outlets

### When to escalate

- HTTP 403 or CF challenge page → try Tier 2 or 3
- Empty/minimal HTML (< 5KB for expected-rich page) → likely SPA, needs JS → Tier 2
- Content is just `<div id="root"></div>` → React/Vue SPA → Tier 2

---

## Tier 2: DynamicFetcher (JS Rendering)

**Best for:** SPAs (React, Vue, Angular), JS-rendered content, sites needing interaction.
**Speed:** 0.9-2.8s per page. Uses rebrowser-playwright (headless Chromium).
**Success rate:** ~85% of websites.

```python
#!/usr/bin/env python3
"""Tier 2: DynamicFetcher — JS rendering via stealth Chromium."""
import sys
from scrapling import DynamicFetcher
import trafilatura

url = sys.argv[1] if len(sys.argv) > 1 else "https://forkcast.org"

# DynamicFetcher uses rebrowser-playwright under the hood
fetcher = DynamicFetcher()
response = fetcher.fetch(
    url,
    headless=True,
    network_idle=True,  # Wait for network to settle
    timeout=30000,      # 30s timeout (ms)
)

html = response.html_content
if not html or len(html) < 500:
    print(f"FAILED: Empty or minimal response ({len(html or '')} bytes)", file=sys.stderr)
    sys.exit(1)

# CF challenge check
if "Checking your browser" in html:
    print("BLOCKED: CF challenge — escalate to Tier 3", file=sys.stderr)
    sys.exit(2)

# Extract with trafilatura
text = trafilatura.extract(html, url=url, include_links=True, include_tables=True)
if text:
    print(text)
else:
    print(html[:50000])
```

### ⚠️ DynamicFetcher caveats

- **Sync-only by default** — cannot be called from inside an `asyncio` event loop. Use `async_fetch()` for async contexts or run in a subprocess.
- Uses Scrapling v0.4 API: `.fetch()` not `.get()`. Constructor arg `auto_match` is deprecated → use `DynamicFetcher.configure(auto_match=False)`.

### When to escalate

- Still getting CF challenge (Turnstile) → Tier 3
- Site uses aggressive anti-bot (DataDome, Kasada, PerimeterX) → Tier 3
- Need fingerprint rotation → Tier 3

---

## Tier 3: Camoufox (Maximum Stealth)

**Best for:** Aggressive anti-bot protection (CF Enterprise, DataDome, Akamai).
**Speed:** 5-10s per page. Launches modified Firefox with engine-level fingerprint spoofing.
**Success rate:** ~90%+ of CF-protected sites.

```python
#!/usr/bin/env python3
"""Tier 3: Camoufox — engine-level stealth Firefox."""
import sys
from camoufox.sync_api import Camoufox
import trafilatura

url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"

with Camoufox(headless=True, humanize=True, geoip=True) as browser:
    page = browser.new_page()
    page.goto(url, timeout=30000, wait_until="networkidle")
    
    # Wait extra for CF challenge resolution if present
    import time
    time.sleep(2)
    
    html = page.content()

# CF validation
if "Checking your browser" in html or len(html) < 1000:
    print("BLOCKED: Even Camoufox couldn't bypass", file=sys.stderr)
    sys.exit(1)

text = trafilatura.extract(html, url=url, include_links=True, include_tables=True)
if text:
    print(text)
else:
    print(html[:50000])
```

### Camoufox features

- **`humanize=True`** — Simulates human-like mouse movements and interactions
- **`geoip=True`** — Rotates OS fingerprint based on GeoIP (requires MaxMind DB, installed)
- **Engine-level spoofing** — Canvas, WebGL, fonts, navigator properties modified in Firefox C++ source
- **Async API available:** `from camoufox.async_api import AsyncCamoufox`

### When Camoufox fails

- **Hard CF blocks** (beaconcha.in-level) — IP reputation based, no free bypass
- **Kasada** — Requires PoW solving, beyond free tooling
- **Solution:** Use the site's API instead, or cookie bootstrapping from a real browser session

---

## Tier 4: Authenticated Sessions

**Best for:** Login-required sites (Discord channels, private dashboards, gated content).

```python
#!/usr/bin/env python3
"""Tier 4: Authenticated session with cookie injection."""
import sys
import json
from curl_cffi import requests as cffi_requests

url = sys.argv[1]
cookie_file = sys.argv[2]  # JSON file with cookies

# Load cookies from file
with open(cookie_file) as f:
    cookies = json.load(f)

# Build cookie dict
cookie_dict = {c["name"]: c["value"] for c in cookies}

resp = cffi_requests.get(
    url,
    impersonate="chrome131",
    cookies=cookie_dict,
    timeout=15,
)

print(resp.text[:50000])
```

For browser-based auth (preserving full session):

```python
"""Authenticated browsing with Camoufox + cookie injection."""
from camoufox.sync_api import Camoufox
import json

with Camoufox(headless=True) as browser:
    context = browser.new_context()
    
    # Inject cookies
    with open("cookies.json") as f:
        cookies = json.load(f)
    context.add_cookies(cookies)
    
    page = context.new_page()
    page.goto("https://example.com/dashboard")
    html = page.content()
```

---

## Tier 0: Discovery Sources (Before Scraping)

Before hitting a page with a browser, check for cheaper data sources:

```python
"""Check for structured data sources before scraping."""
import trafilatura

# 1. Sitemaps / RSS feeds
sitemap_urls = trafilatura.sitemaps.sitemap_search("https://example.com")

# 2. SPA hydration blobs (Next.js, Nuxt, etc.)
# Many SPAs embed full page data in script tags — no browser needed
import re, json
def extract_hydration_data(html: str) -> dict | None:
    """Extract __NEXT_DATA__ or __NUXT__ from SPA HTML."""
    # Next.js
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # Nuxt
    m = re.search(r'window\.__NUXT__\s*=\s*({.*?})\s*;?\s*</script>', html, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    return None
```

**When this helps:** Many React/Next.js/Nuxt sites embed all page data as JSON in the initial HTML. curl_cffi (Tier 1) can get this without a browser, even on SPAs.

## Structured Data Extraction (JSON-LD, Microdata, OpenGraph)

Use `extruct` to extract machine-readable structured data embedded in pages:

```python
import extruct
from w3lib.html import get_base_url

def extract_structured(html: str, url: str) -> dict:
    """Extract JSON-LD, microdata, RDFa, OpenGraph from HTML."""
    base_url = get_base_url(html, url)
    return extruct.extract(html, base_url=base_url)

# Returns dict with keys: json-ld, microdata, rdfa, opengraph, microformat, dublincore
# Example: product pages have JSON-LD with price, availability, reviews
```

**When this helps:** E-commerce, news articles, documentation — any page with structured metadata. Often gives cleaner data than DOM scraping.

---

## Content Extraction

### Trafilatura (Primary — F1 = 0.958)

Best for article text, blog posts, documentation, news. Handles multilingual content.

```python
import trafilatura

# From HTML string
text = trafilatura.extract(
    html,
    url=url,                  # Helps with relative link resolution
    include_links=True,       # Preserve hyperlinks as markdown
    include_tables=True,      # Extract tables
    include_comments=False,   # Skip user comments
    include_images=False,     # Skip image references
    favor_precision=True,     # Prefer precision over recall
    output_format="txt",      # Options: txt, xml, json, csv
)

# From URL directly (uses its own fetcher — no stealth)
text = trafilatura.fetch_url("https://example.com")
downloaded = trafilatura.fetch_url(url)
text = trafilatura.extract(downloaded)
```

### Trafilatura strengths/weaknesses

| Good at | Bad at |
|---------|--------|
| Long-form articles (F1=0.958) | Dynamic data tables |
| Documentation pages | SPA-rendered content |
| News articles | Short listings (trending repos) |
| Multilingual content | Interactive widgets |
| Metadata extraction | Login-gated content |

### Fallback: readability-lxml

When trafilatura returns None or poor results (short pages, unusual layouts):

```python
from readability import Document
import trafilatura

# Use readability to clean HTML first, then trafilatura on cleaned output
doc = Document(html)
cleaned_html = doc.summary()
title = doc.title()

text = trafilatura.extract(cleaned_html) or cleaned_html
```

### Structured Data Extraction

For tables, lists, specific elements — use CSS selectors via Scrapling's parser:

```python
from scrapling import Fetcher

fetcher = Fetcher()
response = fetcher.fetch(url)

# CSS selectors (Parsel-compatible, fast)
titles = response.css("h2.title::text")
links = response.css("a.repo-link::attr(href)")
rows = response.css("table.data tr")

for row in rows:
    cols = row.css("td::text")
    print([c.strip() for c in cols])
```

---

## Complete Auto-Tiering Script

Save as a reusable scraping utility:

```python
#!/usr/bin/env python3
"""
auto_scrape.py — Tiered web scraper with automatic escalation.

Usage:
    python3 auto_scrape.py <url> [--tier 1|2|3] [--raw] [--json]
    
Environment:
    source ~/camoufox-env/bin/activate
"""
import sys
import json
import time
import argparse
import trafilatura
from curl_cffi import requests as cffi_requests


def is_cf_blocked(html: str) -> bool:
    """Check if response is a Cloudflare challenge page."""
    indicators = [
        "Checking your browser",
        "cf-browser-verification",
        "challenges.cloudflare.com",
        "Just a moment...",
        "_cf_chl_opt",
    ]
    return any(ind in html for ind in indicators)


def is_empty_spa(html: str) -> bool:
    """Check if response is an empty SPA shell."""
    if len(html) < 5000:
        return True
    # Common SPA indicators with no rendered content
    spa_shells = ['<div id="root"></div>', '<div id="app"></div>', '<div id="__next"></div>']
    return any(shell in html for shell in spa_shells) and len(html) < 15000


def validate_content(html: str, url: str) -> bool:
    """Validate that we got real content, not a challenge or empty shell."""
    if not html or len(html) < 200:
        return False
    if is_cf_blocked(html):
        return False
    return True


def tier1_curl(url: str, timeout: int = 15) -> str | None:
    """Tier 1: curl_cffi with Chrome TLS impersonation."""
    try:
        resp = cffi_requests.get(
            url,
            impersonate="chrome131",
            timeout=timeout,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
            },
        )
        if resp.status_code == 200 and validate_content(resp.text, url):
            if not is_empty_spa(resp.text):
                return resp.text
    except Exception as e:
        print(f"Tier 1 failed: {e}", file=sys.stderr)
    return None


def tier2_dynamic(url: str, timeout: int = 30000) -> str | None:
    """Tier 2: DynamicFetcher (rebrowser-playwright)."""
    try:
        from scrapling import DynamicFetcher
        fetcher = DynamicFetcher()
        response = fetcher.fetch(url, headless=True, network_idle=True, timeout=timeout)
        html = response.html_content
        if html and validate_content(html, url):
            return html
    except Exception as e:
        print(f"Tier 2 failed: {e}", file=sys.stderr)
    return None


def tier3_camoufox(url: str, timeout: int = 30000) -> str | None:
    """Tier 3: Camoufox stealth Firefox."""
    try:
        from camoufox.sync_api import Camoufox
        with Camoufox(headless=True, humanize=True, geoip=True) as browser:
            page = browser.new_page()
            page.goto(url, timeout=timeout, wait_until="networkidle")
            time.sleep(2)  # Extra wait for CF challenge resolution
            html = page.content()
            if html and validate_content(html, url):
                return html
    except Exception as e:
        print(f"Tier 3 failed: {e}", file=sys.stderr)
    return None


def extract_content(html: str, url: str) -> str:
    """Extract readable text from HTML using trafilatura."""
    # Try precision mode first (best for articles)
    text = trafilatura.extract(
        html, url=url,
        include_links=True, include_tables=True,
        favor_precision=True,
    )
    if text and len(text) > 50:
        return text
    # Fallback: recall mode (catches more — tables, listings, forums)
    text = trafilatura.extract(
        html, url=url,
        include_links=True, include_tables=True,
        favor_recall=True,
    )
    if text and len(text) > 50:
        return text
    # Fallback: try readability + trafilatura
    try:
        from readability import Document
        doc = Document(html)
        cleaned = doc.summary()
        text = trafilatura.extract(cleaned)
        if text:
            return text
    except ImportError:
        pass
    # Last resort: return truncated HTML
    return html[:50000]


def scrape(url: str, max_tier: int = 3, raw: bool = False) -> dict:
    """Scrape URL with automatic tier escalation."""
    tiers = [
        (1, "curl_cffi", tier1_curl),
        (2, "DynamicFetcher", tier2_dynamic),
        (3, "Camoufox", tier3_camoufox),
    ]
    
    for tier_num, tier_name, tier_fn in tiers:
        if tier_num > max_tier:
            break
        t0 = time.time()
        html = tier_fn(url)
        elapsed = time.time() - t0
        if html:
            content = html if raw else extract_content(html, url)
            return {
                "url": url,
                "tier": tier_num,
                "method": tier_name,
                "time_s": round(elapsed, 2),
                "html_bytes": len(html),
                "content": content,
                "success": True,
            }
        print(f"Tier {tier_num} ({tier_name}) failed in {elapsed:.1f}s, escalating...", file=sys.stderr)
    
    return {"url": url, "success": False, "error": "All tiers exhausted"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-tiering web scraper")
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument("--tier", type=int, default=3, help="Max tier to try (1-3)")
    parser.add_argument("--raw", action="store_true", help="Return raw HTML instead of extracted text")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    args = parser.parse_args()
    
    result = scrape(args.url, max_tier=args.tier, raw=args.raw)
    
    if args.as_json:
        print(json.dumps(result, indent=2))
    elif result["success"]:
        print(result["content"])
    else:
        print(f"FAILED: {result.get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)
```

---

## Usage from the Agent

### Quick scrape (inline)

```bash
source ~/camoufox-env/bin/activate
python3 {baseDir}/scripts/auto_scrape.py "https://example.com" --json
```

### In a sub-agent task

```
sessions_spawn task:"Scrape https://forkcast.org for current Ethereum fork status.
Use: source ~/camoufox-env/bin/activate && python3 ~/.openclaw/workspace/skills/web-scraping/scripts/auto_scrape.py 'https://forkcast.org' --json
Write findings to ~/research/<topic>/scraped-data.md"
```

### Batch scraping

```python
"""Scrape multiple URLs efficiently."""
import sys
sys.path.insert(0, "/home/openclaw/.openclaw/workspace/skills/web-scraping/scripts")
from auto_scrape import scrape

urls = [
    "https://news.ycombinator.com",
    "https://ethresear.ch",
    "https://forkcast.org",
]

for url in urls:
    result = scrape(url, max_tier=2)  # Cap at Tier 2 for speed
    if result["success"]:
        print(f"✅ {url} — Tier {result['tier']} in {result['time_s']}s")
        # Process result["content"]...
    else:
        print(f"❌ {url} — failed")
```

---

## Advanced Techniques

### Network Interception (Browser Tier)

For SPAs, the cleanest data is often in XHR/Fetch JSON responses, not the DOM:

```python
"""Capture API responses during page load."""
from rebrowser_playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    
    captured = []
    def on_response(response):
        if "application/json" in (response.headers.get("content-type") or ""):
            try:
                captured.append({"url": response.url, "data": response.json()})
            except: pass
    
    page.on("response", on_response)
    page.goto("https://example-spa.com", wait_until="networkidle")
    
    # captured[] now has all JSON API responses — often cleaner than DOM scraping
    for c in captured:
        print(f"API: {c['url'][:80]} → {len(str(c['data']))} chars")
```

### Domain Profile Learning

For repeated scraping of the same domains, remember which tier works:

```python
"""Simple domain profile store — remember what works."""
import json, os
from urllib.parse import urlparse

PROFILE_PATH = os.path.expanduser("~/camoufox-env/domain-profiles.json")

def load_profiles() -> dict:
    if os.path.isfile(PROFILE_PATH):
        with open(PROFILE_PATH) as f:
            return json.load(f)
    return {}

def save_profile(url: str, tier: int, success: bool):
    domain = urlparse(url).netloc
    profiles = load_profiles()
    profiles.setdefault(domain, {"successes": {}, "failures": {}})
    key = "successes" if success else "failures"
    profiles[domain][key][str(tier)] = profiles[domain][key].get(str(tier), 0) + 1
    with open(PROFILE_PATH, "w") as f:
        json.dump(profiles, f, indent=2)

def best_tier(url: str) -> int:
    """Return the cheapest tier that has succeeded for this domain."""
    domain = urlparse(url).netloc
    profiles = load_profiles()
    if domain in profiles:
        for tier in [1, 2, 3]:
            if profiles[domain]["successes"].get(str(tier), 0) > 0:
                return tier
    return 1  # default: try cheapest first
```

---

## Anti-Bot Bypass Reference

### Cloudflare Detection Layers (2026)

1. **TLS/JA4 fingerprinting** — curl_cffi handles this
2. **JS detections** — Lightweight invisible JS checks → DynamicFetcher handles
3. **JS challenge (IUAM)** — "Checking your browser" interstitial → Camoufox handles
4. **Behavioral analysis** — Mouse/scroll patterns → Camoufox `humanize=True`
5. **ML bot scoring** — Per-customer models → hard to bypass generically
6. **AI Labyrinth** — Fake honeypot pages with invisible links → don't follow unknown links

### Content Validation (Critical)

**Never trust HTTP 200 alone.** Always validate:

```python
def validate_scrape(html: str, expected_indicators: list[str] = None) -> bool:
    """Validate scraped content is real, not a challenge page or honeypot."""
    # 1. Not a CF challenge
    if is_cf_blocked(html):
        return False
    # 2. Has reasonable content
    if len(html) < 1000:
        return False
    # 3. Site-specific validation (if provided)
    if expected_indicators:
        return any(ind in html for ind in expected_indicators)
    return True
```

### AI Labyrinth Defense

Cloudflare generates fake pages as honeypots. Defense:
- **Only follow links you explicitly expect** — don't blindly crawl
- **Validate content makes semantic sense** for the expected page
- **Check for `nofollow` on discovered links** before following

### Known Hard Blocks (No Free Bypass)

| Site | Protection | Workaround |
|------|-----------|------------|
| beaconcha.in | CF Enterprise + Turnstile | Use their REST API |
| discord.com | Login wall + SPA | Use Discord bot API |
| twitter.com/x.com | Aggressive anti-bot | Use Twitter/X API |
| linkedin.com | JS challenge + login | Use LinkedIn API |

---

## Troubleshooting

### DynamicFetcher: "cannot be used in async context"

DynamicFetcher uses Playwright's sync API. If called from asyncio:
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=2)
loop = asyncio.get_event_loop()
html = await loop.run_in_executor(executor, lambda: tier2_dynamic(url))
```

### Camoufox: browser binary not found

```bash
source ~/camoufox-env/bin/activate
python3 -m camoufox fetch  # Re-download browser binary
```

### rebrowser-playwright: frame context errors

`[rebrowser-patches]` warnings are non-fatal — stealth patch noise. Content is still fetched correctly.

### curl_cffi: SSL errors

Update impersonation target. Browser versions evolve:
```python
# Try newer versions if chrome131 starts failing
resp = cffi_requests.get(url, impersonate="chrome136")
```

### Scrapling API changes (v0.4)

- Use `.fetch()` not `.get()`
- Constructor `auto_match=False` is deprecated → `DynamicFetcher.configure(auto_match=False)`

---

## Performance Reference

| Method | Cold Start | Per-Page | Memory | Parallelism |
|--------|-----------|----------|--------|-------------|
| curl_cffi | ~0s | 0.1-1.6s | ~10MB | ✅ Easy (async) |
| DynamicFetcher | ~0.5s | 0.9-2.8s | ~200MB | ⚠️ Browser pool |
| Camoufox | ~2s | 5-10s | ~300MB | ⚠️ Memory-heavy |
| rebrowser-playwright | ~0.3s | 3.6-4.8s | ~200MB | ⚠️ Memory-heavy |

---

## Notes

- **Budget:** Free/open-source tools only. No paid CAPTCHA solvers, proxies, or services.
- **Legal:** Respect robots.txt and ToS. This skill is for legitimate information gathering.
- **Rate limiting:** Always add delays between requests (2-5s + random jitter for anti-bot sites).
- **Session reuse:** For multiple pages on the same site, reuse the browser instance (Camoufox/Playwright context).
- **Trafilatura is the default extractor.** Only skip it when you need raw HTML or structured CSS-selector extraction.
- **Test new sites at Tier 1 first** — most sites don't need a full browser.
