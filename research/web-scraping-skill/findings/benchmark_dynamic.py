#!/usr/bin/env python3
"""DynamicFetcher benchmark — runs in sync context (no asyncio loop)."""

import json
import time
import traceback
import trafilatura

SITES = [
    ("forkcast.org", "https://forkcast.org/"),
    ("news.ycombinator.com", "https://news.ycombinator.com/"),
    ("github.com/trending", "https://github.com/trending"),
    ("ethresear.ch", "https://ethresear.ch/"),
    ("npmjs.com (CF)", "https://www.npmjs.com/package/@libp2p/identify"),
    ("eips.ethereum.org", "https://eips.ethereum.org/EIPS/eip-7594"),
    ("discord.com (login)", "https://discord.com/channels/593655374469660673"),
    ("beaconcha.in", "https://beaconcha.in/validators"),
]

BLOCK_INDICATORS = [
    "just a moment", "checking your browser", "cf-browser-verification",
    "challenge-platform", "ray id", "attention required",
    "enable javascript and cookies", "access denied", "please verify",
    "checking if the site connection is secure", "cf-chl-bypass",
]

def check_block(html):
    lower = html[:8000].lower()
    hits = sum(1 for ind in BLOCK_INDICATORS if ind in lower)
    if hits >= 2:
        return True
    if len(html) < 8000 and hits >= 1:
        return True
    return False

results = []

from scrapling import DynamicFetcher

for i, (name, url) in enumerate(SITES):
    print(f"[{i+1}/8] DynamicFetcher → {name}", end=" ... ", flush=True)
    start = time.monotonic()
    try:
        fetcher = DynamicFetcher(headless=True, auto_match=False)
        resp = fetcher.fetch(url, timeout=30000)
        elapsed = round(time.monotonic() - start, 2)
        
        status = resp.status
        html = str(resp.html_content) if hasattr(resp, 'html_content') and resp.html_content else ""
        if not html and hasattr(resp, 'body') and resp.body:
            html = resp.body.decode('utf-8', errors='replace') if isinstance(resp.body, bytes) else str(resp.body)
        
        html_size = len(html)
        blocked = check_block(html)
        
        plain_text = resp.get_all_text() if hasattr(resp, 'get_all_text') else ""
        traf_text = trafilatura.extract(html) or ""
        
        success = (status == 200) and not blocked
        icon = "✅" if success else "❌"
        print(f"{icon} {elapsed}s | HTTP {status} | HTML={html_size:,} | traf={len(traf_text):,}")
        
        results.append({
            "site": name, "method": "Scrapling DynamicFetcher",
            "success": success, "status_code": status,
            "time_s": elapsed, "html_size": html_size,
            "text_size": len(plain_text), "trafilatura_size": len(traf_text),
            "content_snippet": (traf_text or plain_text)[:300].replace("\n", " ").strip(),
            "is_block_page": blocked, "error": "",
            "notes": "blocked" if blocked else ("good" if len(traf_text) > 200 else "minimal content"),
        })
    except Exception as e:
        elapsed = round(time.monotonic() - start, 2)
        print(f"❌ {elapsed}s | {type(e).__name__}: {str(e)[:150]}")
        results.append({
            "site": name, "method": "Scrapling DynamicFetcher",
            "success": False, "status_code": None,
            "time_s": elapsed, "html_size": 0,
            "text_size": 0, "trafilatura_size": 0,
            "content_snippet": "", "is_block_page": False,
            "error": f"{type(e).__name__}: {str(e)[:200]}",
            "notes": "",
        })

with open("/home/openclaw/research/web-scraping-skill/findings/benchmark-dynamic.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nDone. Results saved.")
