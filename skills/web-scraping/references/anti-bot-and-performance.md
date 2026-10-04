# Anti-Bot and Performance Reference

Moved from `SKILL.md` (2026-10-04). The tier procedure and code stay in `SKILL.md`.

## Anti-Bot Bypass Reference

### Cloudflare Detection Layers (2026)

1. **TLS/JA4 fingerprinting** — curl_cffi handles this
2. **JS detections** — Lightweight invisible JS checks → needs a stealth browser (StealthyFetcher or Camoufox); DynamicFetcher is plain Playwright with no stealth patches
3. **JS challenge (IUAM)** — "Checking your browser" interstitial → Camoufox handles
4. **Behavioral analysis** — Mouse/scroll patterns → Camoufox `humanize=True`
5. **ML bot scoring** — Per-customer models → hard to bypass generically
6. **AI Labyrinth** — Fake honeypot pages with invisible links → don't follow unknown links

### Content Validation (Critical)

**Never trust HTTP 200 alone.** Always validate:

```python
from auto_scrape import is_cf_blocked  # scripts/auto_scrape.py

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
| discord.com | Login wall + SPA | Never scrape — OpenClaw `message` tool (`read`/`search`) |
| twitter.com/x.com | Aggressive anti-bot | Use Twitter/X API |
| linkedin.com | JS challenge + login | Use LinkedIn API |

## Performance Reference

| Method | Cold Start | Per-Page | Memory | Parallelism |
|--------|-----------|----------|--------|-------------|
| curl_cffi | ~0s | 0.1-1.6s | ~10MB | ✅ Easy (async) |
| DynamicFetcher | ~0.5s | 0.9-2.8s | ~200MB | ⚠️ Browser pool |
| Camoufox | ~2s | 5-10s | ~300MB | ⚠️ Memory-heavy |
| rebrowser-playwright | ~0.3s | 3.6-4.8s | ~200MB | ⚠️ Memory-heavy |
