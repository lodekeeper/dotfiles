# Cloudflare Bypass for Oracle Browser Mode on Headless Server

**Date:** 2026-02-25
**Status:** Research complete
**Goal:** Run Oracle CLI browser mode on headless Linux server past Cloudflare Turnstile

---

## Problem Statement

Oracle CLI's `--engine browser` automates ChatGPT via Chrome (chrome-launcher + CDP). On a headless server, Cloudflare Turnstile detects the automation and blocks it. Oracle's own docs acknowledge this:

> "When a ChatGPT folder/workspace URL is set, Cloudflare can block automation even after cookie sync. Use `--browser-keep-browser` to leave Chrome open, solve the interstitial manually, then rerun."

The core detection vectors:
1. **Headless browser fingerprinting** — Cloudflare detects `HeadlessChrome` user-agent, missing GPU, WebGL anomalies
2. **Automation signals** — CDP (Chrome DevTools Protocol) exposes `navigator.webdriver=true`, automation-related DOM properties
3. **Behavioral analysis** — No mouse movement, instant navigation, no scroll events
4. **IP reputation** — Server IPs often flagged vs residential IPs

---

## Approach 1: API Mode (✅ WORKS — recommended)

**Oracle already supports direct API access:**
```bash
oracle --engine api --model gpt-5.2-pro -p "your prompt" --file src/**/*.ts
```

**Confirmed working on our server:** GPT-5.2 Pro responded in 12.7s, $0.0945/call.

**Pros:**
- No Cloudflare issue at all — pure API
- Most reliable path (Oracle docs say so)
- Supports GPT-5.2 Pro (the most powerful model)
- Works headless by design

**Cons:**
- Costs per call (API pricing vs subscription)
- May not support all models available in ChatGPT web (e.g., certain custom GPTs)
- No access to ChatGPT-specific features (memory, projects, custom instructions)

**Verdict:** If the goal is GPT-5.2 Pro access, API mode is the answer. Already works.

---

## Approach 2: Cookie Persistence + Oracle Inline Cookies

**How it works:** Export cookies from a real browser session (including `cf_clearance`, `__cf_bm`, session tokens) and feed them to Oracle:

```bash
oracle --engine browser \
  --browser-inline-cookies-file ~/.oracle/cookies.json \
  --model "GPT-5.2 Pro" \
  -p "your prompt"
```

**Cookie format (`~/.oracle/cookies.json`):**
```json
[
  {"name": "__Secure-next-auth.session-token", "value": "<token>", "domain": "chatgpt.com", "path": "/", "secure": true, "httpOnly": true},
  {"name": "_account", "value": "personal", "domain": "chatgpt.com", "path": "/", "secure": true},
  {"name": "cf_clearance", "value": "<cf_token>", "domain": ".chatgpt.com", "path": "/", "secure": true}
]
```

**How to get cookies:**
1. Log into ChatGPT on a real browser (desktop/phone)
2. Export cookies via browser extension (e.g., "EditThisCookie", "Cookie-Editor")
3. Save as JSON array matching the CookieParam format above

**Pros:**
- Uses ChatGPT Pro subscription (no API costs)
- Works with custom GPTs, projects, etc.
- Oracle natively supports this flow

**Cons:**
- `cf_clearance` cookies expire (typically 30 min - 2 hours)
- Needs periodic manual refresh or automated cookie harvesting
- Still may trigger Cloudflare if automation fingerprint is detected on the server IP

**Verdict:** Works for occasional use. Not sustainable for automated/frequent runs unless combined with a cookie refresh mechanism.

---

## Approach 3: Xvfb + Headful Chrome on Server

**How it works:** Run a virtual X display (Xvfb) and launch Chrome in headful mode. Oracle's `--browser-headless` won't help (Cloudflare detects headless). But headful Chrome on Xvfb appears as a real browser.

```bash
# Install Xvfb if not present
sudo apt install xvfb

# Run Oracle with virtual display
xvfb-run --auto-servernum oracle --engine browser \
  --browser-manual-login \
  --browser-keep-browser \
  --model "GPT-5.2 Pro" \
  -p "your prompt"
```

**First-time setup:**
1. `--browser-manual-login` creates a persistent automation profile
2. On first run, manually log into ChatGPT via VNC/noVNC
3. Solve Cloudflare challenge once
4. Subsequent runs reuse the profile

**Pros:**
- Headful Chrome has genuine browser fingerprint
- Persistent profile means login survives restarts
- Oracle natively supports `--browser-manual-login`

**Cons:**
- Xvfb may still expose server-like characteristics
- CDP automation detection is still present
- Cloudflare may re-challenge periodically
- Requires VNC access for initial setup and re-challenges

**Verdict:** Better than pure headless. Works for semi-automated use where occasional manual intervention is acceptable.

---

## Approach 4: Camoufox Cookie Harvester

**How it works:** Use Camoufox (anti-detection Firefox) to solve Cloudflare Turnstile and harvest cookies, then feed them to Oracle.

```python
from camoufox.sync_api import Camoufox

# On Linux headless: use virtual Xvfb display
with Camoufox(headless="virtual", humanize=True, window=(1280, 720)) as browser:
    page = browser.new_page()
    page.goto("https://chatgpt.com")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(5000)
    
    # Click Turnstile checkbox if present (~210, 290 on 1280x720)
    page.mouse.click(210, 290)
    page.wait_for_timeout(3000)
    
    # Extract cookies
    cookies = browser.contexts[0].cookies()
    import json
    with open("/home/openclaw/.oracle/cookies.json", "w") as f:
        json.dump(cookies, f)
```

**Pros:**
- Camoufox specifically designed to bypass Cloudflare
- `headless="virtual"` works on Linux servers
- `humanize=True` generates realistic mouse movements
- Can be automated as a cron job for cookie refresh

**Cons:**
- Python dependency (not Node.js ecosystem)
- Camoufox is Firefox-based, cookies may not perfectly match Chrome format
- Cookie format conversion needed (Playwright → Oracle CookieParam)
- May not stay ahead of Cloudflare updates permanently
- Adds complexity to the stack

**Verdict:** Most promising fully-automated approach. Could be combined with Approach 2 for a cookie refresh pipeline.

---

## Approach 5: FlareSolver / FlareSolverr

**How it works:** Run FlareSolverr as a Docker service that solves Cloudflare challenges and returns session cookies.

```bash
docker run -d --name flaresolverr -p 8191:8191 ghcr.io/flaresolverr/flaresolverr:latest

# Request a Cloudflare solve
curl -L -X POST 'http://localhost:8191/v1' \
  -H 'Content-Type: application/json' \
  -d '{"cmd": "request.get", "url": "https://chatgpt.com"}'
```

**Pros:**
- Docker-based, easy to deploy
- Returns cookies + user-agent after solving
- Community-maintained

**Cons:**
- FlareSolverr has been struggling with newer Cloudflare versions
- May not reliably solve Turnstile (success rate declining)
- Extra Docker service to maintain
- Cookie format conversion needed

**Verdict:** Easy to try but unreliable with modern Cloudflare.

---

## ✅ BREAKTHROUGH: Camoufox Direct Automation (Approach 6)

**Tested 2026-02-25 20:25 UTC — WORKS END-TO-END on our headless server.**

Camoufox can bypass Cloudflare AND automate ChatGPT directly, without Oracle's Chrome:

```bash
source ~/camoufox-env/bin/activate
python3 research/chatgpt-camoufox.py --prompt "your question here"
```

**Test results:**
- ✅ Cloudflare bypassed (headless=True, no Xvfb needed)
- ✅ ChatGPT loaded (anonymous/free tier auto-login)
- ✅ Prompt sent + response captured (GPT-5.2, 6s)
- ✅ Model confirmed: "GPT-5.2"

**For Pro subscription access:** Provide `--cookies` with `__Secure-next-auth.session-token` from a logged-in browser session.

**Pros:**
- Works completely headless on Linux server
- Bypasses Cloudflare Turnstile reliably
- Uses ChatGPT subscription (no API costs)
- Human-like fingerprint (mouse, typing, fingerprint rotation)
- Can be extended for model selection, file uploads, etc.

**Cons:**
- Python dependency (separate from Oracle's Node.js stack)
- Need auth cookies for Pro models
- Slower than API (~6s for simple prompts)

**Script:** `research/chatgpt-camoufox.py`

---

## Recommendation (UPDATED)

**For production use on our server:**

1. **API mode** (`oracle --engine api`) — Most reliable for programmatic use. GPT-5.2 Pro confirmed working.

2. **Camoufox direct** (`chatgpt-camoufox.py`) — For ChatGPT subscription access without API costs. Works headless, bypasses CF. Needs auth cookies for Pro tier.

3. **Cookie pipeline** — Camoufox can also just harvest CF cookies for Oracle's browser mode, if Oracle's Chrome can be unblocked from AppArmor.

4. **Not recommended:** FlareSolverr (declining reliability), pure headless Chrome (CF detects it), Oracle browser mode without CF cookies (blocked).

---

## Quick Test Commands

```bash
# Test API mode (already confirmed working)
oracle --engine api --model gpt-5.2-pro -p "Hello" --wait

# Test browser mode with inline cookies (if you have cookies)
oracle --engine browser --browser-inline-cookies-file ~/.oracle/cookies.json --model "GPT-5.2 Pro" -p "Hello"

# Test Xvfb + headful Chrome
xvfb-run --auto-servernum oracle --engine browser --browser-manual-login --browser-keep-browser -p "Hello"
```

---

## Phase 4 (General Cloudflare scraping) — 2026-02-25 20:30-20:40 UTC

Expanded testing beyond Oracle/ChatGPT to compare methods on multiple CF-protected targets.

### Test set A (6 sites)
- ChatGPT
- ScrapingCourse dedicated CF challenge page
- NowSecure
- Etherscan
- Discord
- OpenAI Platform

Results:
- **requests (control): 3/6**
- **curl-impersonate: 5/6**
- **Camoufox (headless): 6/6**

### Test set B (harder mix, 6 sites)
- ScrapingCourse CF challenge (dedicated challenge page)
- ChatGPT
- OpenAI Platform
- Coinbase
- Canva
- DeFiLlama

Results:
- **curl-impersonate: 5/6**
- **Camoufox: 5/6**
- **Playwright + stealth: 5/6**
- **nodriver: 1/6**

All tested methods were blocked on the dedicated challenge page (`scrapingcourse.com/cloudflare-challenge`) in this run.

### Key takeaways for real-world scraping

1. **Best lightweight option: `curl-impersonate`**
   - Fastest (~0.4-0.8s request time)
   - Great for static/SSR pages behind moderate CF
   - Fails on stronger Turnstile/challenge setups

2. **Best browser automation options: Camoufox or Playwright+Stealth**
   - Similar success rate in our tests (5/6 on harder set)
   - Camoufox remains strongest for ChatGPT-specific workflows
   - Both are much better than vanilla headless Chrome

3. **nodriver currently underperforms**
   - Only 1/6 on harder set
   - Not recommended as primary bypass layer for this server

4. **No universal bypass**
   - Dedicated high-friction challenge pages can still block all tested methods
   - Need a fallback strategy (retry, alternate path, cookie seeding, human-in-the-loop)

### Practical architecture recommendation

For robust scraping on this server:

- **Tier 1:** try `curl-impersonate` first (cheap/fast)
- **Tier 2:** fallback to Camoufox or Playwright+Stealth browser flow
- **Tier 3:** if still blocked, use authenticated cookie seeding and/or manual challenge solve bootstrap
- Cache `cf_clearance` + session cookies with TTL-aware refresh

### Phase 4d: Scrapling framework (per Nico's suggestion)

Tested [Scrapling](https://github.com/D4Vinci/Scrapling) v0.4 — an adaptive scraping framework with built-in CF bypass.

**Three fetchers tested:**

| Fetcher | Engine | Results | Notes |
|---------|--------|---------|-------|
| `Fetcher` | curl_cffi (HTTP/TLS impersonation) | **4/6** | Very fast (0.3-0.7s). Similar to curl-impersonate. Failed on Coinbase (503), blocked on ScrapingCourse challenge. |
| `StealthyFetcher` | patchright (stealth Chromium) | **0/6** | DNS resolution bug — `ERR_NAME_NOT_RESOLVED` on every site. Scrapling/patchright issue, not CF-related. |
| `DynamicFetcher` | rebrowser-playwright | **5/6** | Only blocked on dedicated challenge page. Slower (3-30s) but effective. |

**Key insight:** Scrapling's `Fetcher` (curl_cffi under the hood) is the best lightweight HTTP option tested — it adds automatic referer spoofing (pretends to come from Google search) which helps bypass some CF checks that curl-impersonate alone doesn't handle. The `DynamicFetcher` is competitive with our standalone Camoufox/Playwright+Stealth results.

**StealthyFetcher DNS bug:** This uses patchright (a patched Playwright fork) to run stealth Chromium. On our server, every request fails with `ERR_NAME_NOT_RESOLVED`. Likely a patchright configuration issue with DNS resolution in the sandbox environment. Not blocking — the other fetchers work.

**Scrapling advantages over raw tools:**
- Built-in referer spoofing, header rotation, retry logic
- Adaptive element tracking (survives page redesigns)
- Spider framework for crawling at scale
- MCP server for AI integration
- Single `pip install scrapling` vs assembling multiple tools

### Updated architecture recommendation

```
┌─────────────────────────────────────────────────┐
│ Tier 1: Scrapling Fetcher / curl-impersonate    │
│   Fast (0.3-0.8s), works on most CF sites       │
├─────────────────────────────────────────────────┤
│ Tier 2: Scrapling DynamicFetcher / Camoufox /   │
│         Playwright+Stealth                      │
│   Slower (3-30s), handles harder challenges     │
├─────────────────────────────────────────────────┤
│ Tier 3: Cookie seeding + manual bootstrap       │
│   For dedicated hard challenge pages            │
└─────────────────────────────────────────────────┘
```

### Consolidated results across all methods (6 hard sites)

| Method | Pass Rate | Avg Speed | Best For |
|--------|-----------|-----------|----------|
| Scrapling Fetcher | 4/6 | 0.4s | Fast scraping, most sites |
| curl-impersonate | 5/6 | 0.5s | Raw speed, no Python needed |
| Camoufox | 5/6 | 8.5s | ChatGPT automation, hardest CF |
| Playwright+Stealth | 5/6 | 7.0s | General stealth browsing |
| Scrapling Dynamic | 5/6 | 12s | Integrated scraping framework |
| nodriver | 1/6 | 6.0s | ❌ Not recommended |

Artifacts:
- `research/cf-bypass-test.py`
- `research/cf-bypass-results.json`
- `research/cf-bypass-extended.py`
- `research/cf-bypass-extended-results.json`
- `research/cf-bypass-scrapling.py`
- `research/cf-bypass-scrapling-results.json`

