#!/usr/bin/env python3
"""
auto_scrape.py — Tiered web scraper with automatic escalation.

Usage:
    python3 auto_scrape.py <url> [--tier 1|2|3] [--raw] [--json]

Environment:
    source ~/camoufox-env/bin/activate

Tiers:
    1: curl_cffi (TLS impersonation, 0.2-1.6s, no JS)
    2: DynamicFetcher (rebrowser-playwright, 0.9-2.8s, JS rendering)
    3: Camoufox (stealth Firefox, 5-10s, max anti-bot bypass)
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
    """Check if response is an empty SPA shell needing JS."""
    # If it has hydration data, it's NOT empty — we can extract from script tags
    if extract_hydration_data(html) is not None:
        return False
    if len(html) < 5000:
        return True
    spa_shells = ['<div id="root"></div>', '<div id="app"></div>', '<div id="__next"></div>']
    return any(shell in html for shell in spa_shells) and len(html) < 15000


def extract_hydration_data(html: str) -> dict | None:
    """Extract __NEXT_DATA__ or __NUXT__ embedded state from SPA HTML."""
    import re
    # Next.js
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Nuxt
    m = re.search(r'window\.__NUXT__\s*=\s*(\{.*?\})\s*;?\s*</script>', html, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


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
            else:
                print(f"Tier 1: SPA shell detected ({len(resp.text)} bytes)", file=sys.stderr)
        elif resp.status_code != 200:
            print(f"Tier 1: HTTP {resp.status_code}", file=sys.stderr)
        else:
            print(f"Tier 1: Content validation failed", file=sys.stderr)
    except Exception as e:
        print(f"Tier 1 error: {e}", file=sys.stderr)
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
        else:
            print(f"Tier 2: Content validation failed ({len(html or '')} bytes)", file=sys.stderr)
    except Exception as e:
        print(f"Tier 2 error: {e}", file=sys.stderr)
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
            else:
                print(f"Tier 3: Content validation failed ({len(html or '')} bytes)", file=sys.stderr)
    except Exception as e:
        print(f"Tier 3 error: {e}", file=sys.stderr)
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
    # Fallback: recall mode (catches more content like HN, tables)
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
                "content_bytes": len(content),
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
        # Truncate content in JSON output to avoid huge prints
        out = {**result}
        if "content" in out and len(out["content"]) > 10000:
            out["content"] = out["content"][:10000] + f"\n\n... [truncated, {len(result['content'])} total chars]"
        print(json.dumps(out, indent=2))
    elif result["success"]:
        print(result["content"])
    else:
        print(f"FAILED: {result.get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)
