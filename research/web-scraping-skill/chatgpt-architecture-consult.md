# ChatGPT Architecture Consultation (GPT-5.2-pro)

**Source:** https://chatgpt.com/c/699f7bee-883c-838c-9d49-5a7804ee7a5e
**Date:** 2026-02-25
**Requested by:** Nico

## Key Additions (not in our initial research)

### 1. Tier 0 — Discovery Sources
- Check RSS/sitemaps, `__NEXT_DATA__`/`__NUXT__` hydration blobs before even trying to render
- Many SPAs embed full page data as JSON in initial HTML

### 2. `extruct` for Structured Data
- Extract JSON-LD, microdata, RDFa, OpenGraph from any page
- Often gives cleaner data than DOM scraping (especially e-commerce, news)

### 3. Domain Profile Learning
- Remember which tier works per-domain across calls
- Bandit-like policy: start with cheapest tier that has historically worked
- Store success/failure rates per tier per domain

### 4. Network Interception
- For SPAs, capture XHR/Fetch JSON responses during page load
- Often cleaner than scraping the rendered DOM

### 5. Accessibility Tree Extraction
- Playwright ARIA snapshots as stable semantic representation
- More resilient to DOM changes than CSS selectors

### 6. First-Class Outcomes
- BLOCKED, AUTH_REQUIRED, HUMAN_REQUIRED, RATE_LIMITED as typed outcomes
- Don't silently thrash on protected pages

### 7. "Hydration" Tier
- Extract embedded state from SPAs without browser rendering
- Works for Next.js, Nuxt, and other SSR frameworks

## Architecture Recommendations (from GPT-5.2-pro)

### Recommended Stack
- **Orchestrator:** Custom tiering + outcomes + domain learning
- **HTTP tier:** httpx/curl_cffi with TLS impersonation
- **Browser tier:** Playwright for JS/auth flows
- **Structured extraction:** extruct (JSON-LD/microdata)
- **Text extraction:** Trafilatura primary + Readability fallback
- **Session vault:** Playwright storage_state + cookie bridging
- **Profile store:** SQLite (domain preferences, tier stats)

### Key Design Principle
> "Make BLOCKED/HUMAN_REQUIRED a first-class, expected outcome. For truly hardened cases, fully autonomous free-only access is not something you can guarantee without cooperation from the site."

## What We Incorporated
- [x] Tier 0 discovery (sitemaps, hydration data)
- [x] `extruct` for structured data extraction
- [x] Domain profile learning (simple JSON store)
- [x] Network interception patterns
- [ ] Accessibility tree extraction (future enhancement)
- [ ] Full SessionVault abstraction (future — our cookie injection is simpler)
- [x] First-class outcome types (already had `is_cf_blocked()`, now more explicit)
