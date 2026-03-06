#!/usr/bin/env python3
"""Comprehensive web scraping benchmark - tests 8 sites × 3 methods."""

import asyncio
import json
import time
import sys
import traceback
from dataclasses import dataclass, asdict
from typing import Optional

import trafilatura

# ── Sites ──────────────────────────────────────────────────────────────
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

@dataclass
class Result:
    site: str
    method: str
    success: bool = False
    status_code: Optional[int] = None
    time_s: float = 0.0
    html_size: int = 0
    text_size: int = 0
    trafilatura_size: int = 0
    content_snippet: str = ""
    error: str = ""
    is_block_page: bool = False
    notes: str = ""

RESULTS: list[Result] = []

BLOCK_INDICATORS = [
    "just a moment", "checking your browser", "cf-browser-verification",
    "challenge-platform", "ray id", "attention required",
    "enable javascript and cookies", "access denied", "please verify",
    "checking if the site connection is secure", "cf-chl-bypass",
]

def check_block(html: str) -> bool:
    lower = html[:8000].lower()
    hits = sum(1 for ind in BLOCK_INDICATORS if ind in lower)
    if hits >= 2:
        return True
    if len(html) < 8000 and hits >= 1:
        return True
    return False

def extract_with_trafilatura(html: str) -> str:
    try:
        return trafilatura.extract(html) or ""
    except Exception:
        return ""

def quality_note(html: str, traf_text: str, name: str) -> str:
    notes = []
    if len(html) < 1000:
        notes.append("very small HTML")
    if check_block(html):
        notes.append("BLOCKED (CF/challenge)")
    if not traf_text and len(html) > 5000:
        notes.append("trafilatura: nothing")
    if traf_text and len(traf_text) > 200:
        notes.append("good extraction")
    if "discord" in name.lower():
        if "login" in html.lower() or "sign in" in html.lower() or len(html) < 5000:
            notes.append("login/app page")
    return "; ".join(notes) if notes else "OK"

# ── Method A: curl_cffi via Scrapling Fetcher ─────────────────────────
def test_curl_cffi(name: str, url: str) -> Result:
    r = Result(site=name, method="curl_cffi (Fetcher)")
    start = time.monotonic()
    try:
        from scrapling import Fetcher
        fetcher = Fetcher(auto_match=False)
        resp = fetcher.get(url, timeout=30)
        r.time_s = round(time.monotonic() - start, 2)
        r.status_code = resp.status
        
        # Get HTML content
        html = str(resp.html_content) if hasattr(resp, 'html_content') and resp.html_content else ""
        if not html and hasattr(resp, 'body') and resp.body:
            html = resp.body.decode('utf-8', errors='replace') if isinstance(resp.body, bytes) else str(resp.body)
        
        r.html_size = len(html)
        r.is_block_page = check_block(html)
        
        # Text extraction
        plain_text = resp.get_all_text() if hasattr(resp, 'get_all_text') else ""
        r.text_size = len(plain_text)
        
        traf_text = extract_with_trafilatura(html)
        r.trafilatura_size = len(traf_text)
        r.content_snippet = (traf_text or plain_text)[:300].replace("\n", " ").strip()
        
        r.success = (r.status_code == 200) and not r.is_block_page
        r.notes = quality_note(html, traf_text, name)
    except Exception as e:
        r.error = f"{type(e).__name__}: {str(e)[:200]}"
        r.time_s = round(time.monotonic() - start, 2)
    return r

# ── Method B: rebrowser-playwright ────────────────────────────────────
async def test_rebrowser_pw(name: str, url: str) -> Result:
    r = Result(site=name, method="rebrowser-playwright")
    start = time.monotonic()
    try:
        from rebrowser_playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
                r.status_code = resp.status if resp else None
                html = await page.content()
                r.html_size = len(html)
                r.is_block_page = check_block(html)
                
                # Extract text directly from page
                try:
                    page_text = await page.evaluate("document.body.innerText")
                    r.text_size = len(page_text) if page_text else 0
                except:
                    r.text_size = 0
                    page_text = ""
                
                traf_text = extract_with_trafilatura(html)
                r.trafilatura_size = len(traf_text)
                r.content_snippet = (traf_text or page_text or "")[:300].replace("\n", " ").strip()
                r.success = (r.status_code == 200) and not r.is_block_page
                r.notes = quality_note(html, traf_text, name)
            finally:
                await browser.close()
        r.time_s = round(time.monotonic() - start, 2)
    except Exception as e:
        r.error = f"{type(e).__name__}: {str(e)[:200]}"
        r.time_s = round(time.monotonic() - start, 2)
    return r

# ── Method C: Scrapling DynamicFetcher ────────────────────────────────
def test_dynamic_fetcher(name: str, url: str) -> Result:
    r = Result(site=name, method="Scrapling DynamicFetcher")
    start = time.monotonic()
    try:
        from scrapling import DynamicFetcher
        fetcher = DynamicFetcher(headless=True, auto_match=False)
        resp = fetcher.fetch(url, timeout=30000)
        r.time_s = round(time.monotonic() - start, 2)
        r.status_code = resp.status
        
        html = str(resp.html_content) if hasattr(resp, 'html_content') and resp.html_content else ""
        if not html and hasattr(resp, 'body') and resp.body:
            html = resp.body.decode('utf-8', errors='replace') if isinstance(resp.body, bytes) else str(resp.body)
        
        r.html_size = len(html)
        r.is_block_page = check_block(html)
        
        plain_text = resp.get_all_text() if hasattr(resp, 'get_all_text') else ""
        r.text_size = len(plain_text)
        
        traf_text = extract_with_trafilatura(html)
        r.trafilatura_size = len(traf_text)
        r.content_snippet = (traf_text or plain_text)[:300].replace("\n", " ").strip()
        
        r.success = (r.status_code == 200) and not r.is_block_page
        r.notes = quality_note(html, traf_text, name)
    except Exception as e:
        r.error = f"{type(e).__name__}: {str(e)[:200]}"
        r.time_s = round(time.monotonic() - start, 2)
    return r

# ── Main ──────────────────────────────────────────────────────────────
async def main():
    print("=" * 70)
    print("WEB SCRAPING BENCHMARK — 2026-02-25")
    print("=" * 70)
    
    for i, (name, url) in enumerate(SITES):
        print(f"\n{'─' * 60}")
        print(f"[{i+1}/8] {name}: {url}")
        print(f"{'─' * 60}")
        
        # Method A: curl_cffi
        print(f"  A) curl_cffi ...", end=" ", flush=True)
        r_a = test_curl_cffi(name, url)
        RESULTS.append(r_a)
        s = "✅" if r_a.success else "❌"
        print(f"{s} {r_a.time_s}s | HTTP {r_a.status_code} | HTML={r_a.html_size:,} | traf={r_a.trafilatura_size:,} | {r_a.notes or r_a.error}")
        
        # Method B: rebrowser-playwright
        print(f"  B) rebrowser-pw ...", end=" ", flush=True)
        r_b = await test_rebrowser_pw(name, url)
        RESULTS.append(r_b)
        s = "✅" if r_b.success else "❌"
        print(f"{s} {r_b.time_s}s | HTTP {r_b.status_code} | HTML={r_b.html_size:,} | traf={r_b.trafilatura_size:,} | {r_b.notes or r_b.error}")
        
        # Method C: DynamicFetcher
        print(f"  C) DynamicFetcher ...", end=" ", flush=True)
        r_c = test_dynamic_fetcher(name, url)
        RESULTS.append(r_c)
        s = "✅" if r_c.success else "❌"
        print(f"{s} {r_c.time_s}s | HTTP {r_c.status_code} | HTML={r_c.html_size:,} | traf={r_c.trafilatura_size:,} | {r_c.notes or r_c.error}")
    
    # Dump JSON
    with open("/home/openclaw/research/web-scraping-skill/findings/benchmark-raw.json", "w") as f:
        json.dump([asdict(r) for r in RESULTS], f, indent=2)
    
    print(f"\n{'=' * 70}")
    print("SUMMARY TABLE")
    print(f"{'=' * 70}")
    print(f"{'Site':<28} {'curl_cffi':<18} {'rebrowser-pw':<18} {'DynFetcher':<18}")
    print("─" * 82)
    for name, url in SITES:
        row = [name[:27]]
        for method_prefix in ["curl_cffi", "rebrowser", "Scrapling Dynamic"]:
            matched = [r for r in RESULTS if r.site == name and method_prefix in r.method]
            if matched:
                r = matched[0]
                cell = f"{'✅' if r.success else '❌'} {r.time_s}s/{r.html_size:,}b"
            else:
                cell = "—"
            row.append(cell)
        print(f"{row[0]:<28} {row[1]:<18} {row[2]:<18} {row[3]:<18}")
    
    # Stats
    total = len(RESULTS)
    successes = sum(1 for r in RESULTS if r.success)
    print(f"\nOverall: {successes}/{total} successful ({100*successes/total:.0f}%)")
    for method in ["curl_cffi", "rebrowser", "Scrapling Dynamic"]:
        m_results = [r for r in RESULTS if method in r.method]
        m_success = sum(1 for r in m_results if r.success)
        m_total = len(m_results)
        avg_time = sum(r.time_s for r in m_results) / m_total if m_total else 0
        print(f"  {method:<25} {m_success}/{m_total} success, avg {avg_time:.1f}s")

if __name__ == "__main__":
    asyncio.run(main())
