# Research Plan: Universal Web Scraping Skill

## Goal
Build a skill for reliable web scraping/information gathering that works on virtually all websites, including CF-protected, JS-heavy, and authenticated sites. Free/open-source only.

## Sub-questions

### Q1: Best general-purpose scraping stack
- Scrapling (D4Vinci/Scrapling) — auto-detection, multiple backends
- Raw Playwright/rebrowser-playwright — stealth patches
- curl_cffi / curl-impersonate — fast, TLS fingerprint mimicry
- Camoufox — anti-detect Firefox
- httpx + beautifulsoup — simple static sites
- Custom tiered approach combining multiple tools

### Q2: Anti-bot protection landscape (2025-2026)
- Cloudflare Turnstile (most common)
- Akamai Bot Manager
- PerimeterX/HUMAN
- DataDome
- hCaptcha / reCAPTCHA
- What works against each? What's the state of the art?

### Q3: Optimal tiered architecture
- Tier selection: how to detect which tier is needed
- Fast path (curl-based) vs slow path (browser-based)
- Cookie persistence and session management
- Retry/fallback logic

### Q4: Authenticated scraping
- Cookie injection for logged-in sessions
- OAuth/API token approaches
- GitHub, Discord archives, forums

### Q5: Content extraction quality
- Trafilatura (academic, precision-focused)
- Mozilla Readability / @mozilla/readability
- Scrapling's auto-extraction
- BeautifulSoup manual parsing
- Structured data: tables, JSON-LD, microdata
- What gives the best output for AI consumption?

## Existing Data
- Phase 4 CF bypass results (6 tools × 12 sites)
- curl-impersonate 5/6, Camoufox 5-6/6, Playwright+Stealth 5/6
- Scrapling Fetcher 4/6, DynamicFetcher 5/6, StealthyFetcher 0/6 (DNS bug)
- Dedicated CF challenge page blocks everything tested

## Constraints
- Headless Linux server (Ubuntu 22.04)
- Python-based (~/camoufox-env venv)
- Free/open-source only — no paid CAPTCHA solvers, proxies, or APIs
- Must work autonomously (no human-in-the-loop)
- Target: 95%+ success rate on typical websites
