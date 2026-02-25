# Web Scraping Benchmark Results

**Date:** 2026-02-25 22:50 UTC  
**Server:** server2 (Linux 6.8.0-45-generic x64)  
**Venv:** ~/camoufox-env  
**Tools tested:** curl_cffi (via Scrapling Fetcher), rebrowser-playwright (headless Chromium), Scrapling DynamicFetcher (rebrowser-playwright under the hood)  
**Content extraction:** Trafilatura 2.0.0

---

## Summary Table

| # | Site | curl_cffi | rebrowser-pw | DynamicFetcher |
|---|------|-----------|-------------|----------------|
| 1 | forkcast.org | ⚠️ 0.21s (shell only, 3KB) | ✅ 3.61s (42KB) | ✅ 0.91s (41KB) |
| 2 | news.ycombinator.com | ✅ 0.53s (34KB) | ✅ 4.08s (34KB) | ✅ 1.52s (34KB) |
| 3 | github.com/trending | ✅ 1.62s (596KB) | ✅ 3.93s (640KB) | ✅ 2.79s (613KB) |
| 4 | ethresear.ch | ✅ 0.56s (296KB) | ✅ 4.75s (515KB) | ✅ 1.96s (503KB) |
| 5 | npmjs.com (CF-protected) | ✅ 1.60s (532KB) | ✅ 4.58s (545KB) | ✅ 1.96s (541KB) |
| 6 | eips.ethereum.org | ✅ 0.27s (29KB) | ✅ 4.16s (54KB) | ✅ 1.80s (54KB) |
| 7 | discord.com (login-req) | ⚠️ 0.09s (SPA shell) | ⚠️ 4.12s (login page) | ⚠️ 2.37s (SPA shell) |
| 8 | beaconcha.in (CF) | ❌ 0.26s (blocked) | ❌ 3.90s (blocked) | ❌ 1.65s (blocked) |

**Legend:** ✅ = real content fetched | ⚠️ = HTTP 200 but no useful content | ❌ = blocked/failed

---

## Method Comparison

| Metric | curl_cffi (Fetcher) | rebrowser-playwright | DynamicFetcher |
|--------|--------------------|--------------------|----------------|
| **Success rate** | 5/8 real content | 6/8 real content | 6/8 real content |
| **Avg time (success)** | 0.76s | 4.19s | 1.82s |
| **JS rendering** | ❌ No | ✅ Yes | ✅ Yes |
| **CF bypass** | Partial (impersonation) | Same as normal Chrome | Same as normal Chrome |
| **Resource usage** | Minimal (no browser) | Heavy (Chromium per page) | Heavy (Chromium per page) |
| **Async compat** | ✅ Works in any context | ✅ Async native | ⚠️ Sync only (no asyncio) |

### Key Takeaway

**DynamicFetcher is the sweet spot** for general scraping: 2× faster than raw rebrowser-playwright (likely reuses browser instances), renders JS, and handles most sites. curl_cffi is king for speed on static/server-rendered pages.

---

## Per-Site Analysis

### 1. forkcast.org (Ethereum fork tracker) ⭐

| Method | Status | HTML | Trafilatura | Time |
|--------|--------|------|-------------|------|
| curl_cffi | 200 | 3,195 B | 0 B | 0.21s |
| rebrowser-pw | 200 | 41,683 B | 1,169 B | 3.61s |
| DynamicFetcher | 200 | 41,461 B | 1,169 B | 0.91s |

**Verdict:** React SPA — **requires JS execution**. curl_cffi only gets the empty shell (3KB). Browser methods render full content including fork data, EIP proposals, and upgrade timelines. Trafilatura extracts ~1.2KB of clean text.

**Content extracted:** Ethereum upgrade tracker with Hegota headliner proposals, devnet status (Live), EIP details.

### 2. news.ycombinator.com (simple HTML)

| Method | Status | HTML | Trafilatura | Time |
|--------|--------|------|-------------|------|
| curl_cffi | 200 | 34,141 B | 3,820 B | 0.53s |
| rebrowser-pw | 200 | 34,348 B | 4,035 B | 4.08s |
| DynamicFetcher | 200 | 34,201 B | 4,035 B | 1.52s |

**Verdict:** Classic server-rendered HTML. All methods work. **curl_cffi is 8× faster** — no benefit from browser here. Trafilatura extracts all 30 story titles and metadata cleanly.

### 3. github.com/trending (JS-rendered)

| Method | Status | HTML | Trafilatura | Time |
|--------|--------|------|-------------|------|
| curl_cffi | 200 | 595,965 B | 2,492 B | 1.62s |
| rebrowser-pw | 200 | 640,314 B | 2,492 B | 3.93s |
| DynamicFetcher | 200 | 613,289 B | 2,492 B | 2.79s |

**Verdict:** GitHub serves SSR HTML (curl_cffi gets ~596KB of content). All methods get identical trafilatura output. **curl_cffi wins** — GitHub trending doesn't need JS. Trending repos with stars/descriptions extracted.

### 4. ethresear.ch (Discourse forum)

| Method | Status | HTML | Trafilatura | Time |
|--------|--------|------|-------------|------|
| curl_cffi | 200 | 295,608 B | 2,903 B | 0.56s |
| rebrowser-pw | 200 | 515,182 B | 2,712 B | 4.75s |
| DynamicFetcher | 200 | 503,439 B | 2,712 B | 1.96s |

**Verdict:** Discourse serves initial content via SSR but loads more via JS. curl_cffi gets slightly different (but still useful) content. Browser methods get richer HTML but trafilatura actually extracts comparable content. **curl_cffi sufficient** for topic listing.

### 5. npmjs.com (Cloudflare-protected)

| Method | Status | HTML | Trafilatura | Time |
|--------|--------|------|-------------|------|
| curl_cffi | 200 | 531,507 B | 1,480 B | 1.60s |
| rebrowser-pw | 200 | 545,461 B | 1,480 B | 4.58s |
| DynamicFetcher | 200 | 541,062 B | 1,480 B | 1.96s |

**Verdict:** **All methods bypass CF successfully.** npm serves SSR content even through CF. Package metadata (@libp2p/identify) extracted including description, version, dependencies. curl_cffi's TLS impersonation is sufficient.

### 6. eips.ethereum.org (static GitHub Pages)

| Method | Status | HTML | Trafilatura | Time |
|--------|--------|------|-------------|------|
| curl_cffi | 200 | 28,555 B | 9,789 B | 0.27s |
| rebrowser-pw | 200 | 54,410 B | 9,633 B | 4.16s |
| DynamicFetcher | 200 | 53,760 B | 9,633 B | 1.80s |

**Verdict:** Static site. **Best trafilatura extraction** of all sites (~10KB clean text). Full EIP-7594 (PeerDAS) specification extracted. curl_cffi is 15× faster and gets comparable content. Browser adds JS-injected elements but same core text.

### 7. discord.com (login-required) — Expected failure

| Method | Status | HTML | Trafilatura | Time |
|--------|--------|------|-------------|------|
| curl_cffi | 200 | 4,578 B | 46 B | 0.09s |
| rebrowser-pw | 200 | 112,382 B | 365 B | 4.12s |
| DynamicFetcher | 200 | 11,406 B | 46 B | 2.37s |

**Verdict:** As expected, **no useful content without authentication**. curl_cffi gets the empty SPA shell. rebrowser-pw gets the login/app UI (112KB of React components). None return actual channel content. Would need authenticated session cookies.

### 8. beaconcha.in (Cloudflare-protected) — All blocked

| Method | Status | HTML | Trafilatura | Time |
|--------|--------|------|-------------|------|
| curl_cffi | **403** | 10,409 B | 41 B | 0.26s |
| rebrowser-pw | **403** | 32,376 B | 327 B | 3.90s |
| DynamicFetcher | **403** | 32,065 B | 327 B | 1.65s |

**Verdict:** **Hard CF block.** beaconcha.in uses aggressive Cloudflare protection (JS challenge + turnstile). All three methods receive 403 + challenge page. The "extracted" 327 bytes from browser methods is just the challenge page text. Would need:
- CF cookie bootstrapping
- Turnstile solver
- Residential proxy
- Or: use beaconcha.in API instead (recommended)

---

## Content Extraction Quality (Trafilatura)

| Site | HTML Size | Trafilatura | Ratio | Quality |
|------|-----------|-------------|-------|---------|
| eips.ethereum.org | 29-54 KB | ~9.7 KB | 18-34% | ⭐ Excellent — full spec text |
| news.ycombinator.com | 34 KB | ~4.0 KB | 12% | ⭐ Excellent — all stories |
| ethresear.ch | 296-515 KB | ~2.8 KB | 0.5-1% | Good — topic titles |
| github.com/trending | 596-640 KB | 2.5 KB | 0.4% | Good — repo names/descriptions |
| npmjs.com | 531-545 KB | 1.5 KB | 0.3% | OK — package metadata |
| forkcast.org | 41 KB | 1.2 KB | 3% | OK — fork headlines |
| discord.com | 5-112 KB | 46-365 B | <1% | ❌ No useful content (login wall) |
| beaconcha.in | 10-32 KB | 41-327 B | <1% | ❌ Blocked (CF challenge text) |

**Trafilatura strengths:** Long-form text (EIPs), structured lists (HN). 
**Trafilatura weaknesses:** Dynamic data tables, SPA-rendered content, short-form listings.

---

## Recommendations

### Tiered fetching strategy (fastest → most capable):

```
1. curl_cffi (Scrapling Fetcher)    → Try first (0.2-1.6s)
   Best for: static sites, SSR pages, most APIs
   
2. DynamicFetcher                   → Fallback for JS-heavy sites (1-3s)
   Best for: SPAs (forkcast.org), JS-rendered content
   Note: Cannot be used inside asyncio loops!
   
3. rebrowser-playwright (manual)    → When DynamicFetcher fails (4-5s)
   Best for: Custom wait logic, interaction needed
   
4. Authenticated session            → Login-required sites
   Need: Cookie injection or session management
```

### Site-specific notes:

- **forkcast.org**: Must use browser (React SPA). DynamicFetcher is optimal (0.91s vs 3.61s rebrowser)
- **beaconcha.in**: Use their REST API instead of scraping (hard CF block)
- **discord.com**: Use Discord API/bot, not web scraping
- **npmjs.com**: curl_cffi works despite CF — TLS fingerprint impersonation sufficient
- **ethresear.ch**: curl_cffi works, but browser gets richer content (JS-loaded topics)

### Performance budget:

| Method | Cold start | Per-page | Parallelizable |
|--------|-----------|----------|----------------|
| curl_cffi | ~0s | 0.1-1.6s | ✅ Easy (async requests) |
| DynamicFetcher | ~0.5s | 0.9-2.8s | ⚠️ Limited (browser pool) |
| rebrowser-pw | ~0.3s | 3.6-4.8s | ⚠️ Memory-heavy per browser |

---

## Technical Notes

- **DynamicFetcher uses Playwright sync API** — cannot be called from within an asyncio event loop. Must run in a separate thread/process or use `async_fetch()` method.
- **rebrowser-playwright** shows `[rebrowser-patches]` frame context errors on some sites (forkcast, github) but still works — these are non-fatal stealth patch warnings.
- **Scrapling v0.4 API changes**: `Fetcher(auto_match=False)` constructor arg is deprecated; use `Fetcher.configure(auto_match=False)` instead. `DynamicFetcher` uses `.fetch()` not `.get()`.
- **curl_cffi's TLS impersonation** successfully bypasses npm's CF protection — the `chrome_131` fingerprint matches a real browser.
- **beaconcha.in** is the only site with a **hard CF block** (Turnstile challenge) that defeats all automated methods.
