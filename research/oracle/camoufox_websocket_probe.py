import asyncio
import importlib.util
import json
import os
import time
from urllib.parse import urlparse

from camoufox.async_api import AsyncCamoufox

CHATGPT_DIRECT_PATH = "/home/openclaw/.openclaw/workspace/research/chatgpt-direct.py"
spec = importlib.util.spec_from_file_location("chatgpt_direct", CHATGPT_DIRECT_PATH)
chatgpt_direct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chatgpt_direct)
_cookie_matches_url = chatgpt_direct._cookie_matches_url

COOKIES = os.path.expanduser("~/.oracle/chatgpt-cookies.json")
CHATGPT_URL = "https://chatgpt.com"
PROMPT = "Reply with exactly WS_OK."


def sanitize_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}"


def short_text(text, limit=1200):
    if text is None:
        return None
    text = str(text)
    return text[:limit]


async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    matched = [c for c in auth_cookies if _cookie_matches_url(c, CHATGPT_URL)]

    websocket_events = []
    console_errors = []
    page_errors = []
    start = None

    def t_ms():
        if start is None:
            return None
        return round((time.time() - start) * 1000)

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        page.on("console", lambda msg: console_errors.append({"t_ms": t_ms(), "type": msg.type, "text": msg.text}) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append({"t_ms": t_ms(), "text": str(exc)}))

        def on_ws(ws):
            entry = {"t_ms": t_ms(), "kind": "open", "url": sanitize_url(ws.url)}
            websocket_events.append(entry)
            try:
                ws.on("framesent", lambda payload: websocket_events.append({
                    "t_ms": t_ms(),
                    "kind": "framesent",
                    "url": sanitize_url(ws.url),
                    "text": short_text(payload),
                }))
                ws.on("framereceived", lambda payload: websocket_events.append({
                    "t_ms": t_ms(),
                    "kind": "framereceived",
                    "url": sanitize_url(ws.url),
                    "text": short_text(payload),
                }))
                ws.on("close", lambda _: websocket_events.append({
                    "t_ms": t_ms(),
                    "kind": "close",
                    "url": sanitize_url(ws.url),
                }))
            except Exception as e:
                websocket_events.append({"t_ms": t_ms(), "kind": "ws-hook-error", "url": sanitize_url(ws.url), "error": repr(e)})

        page.on("websocket", on_ws)

        for c in auth_cookies:
            await page.context.add_cookies([
                {
                    "name": c.get("name", ""),
                    "value": c.get("value", ""),
                    "domain": c.get("domain", ".chatgpt.com"),
                    "path": c.get("path", "/"),
                    "secure": c.get("secure", True),
                    "httpOnly": c.get("httpOnly", True),
                }
            ])

        await page.goto(CHATGPT_URL, timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(8)

        composer = page.locator('[id="prompt-textarea"]').first
        await composer.click()
        await page.keyboard.type(PROMPT, delay=10)
        await asyncio.sleep(0.3)
        start = time.time()
        await page.keyboard.press("Enter")

        await asyncio.sleep(20)

        final = {
            "url": page.url,
            "title": await page.title(),
            "bodySnippet": (await page.text_content("body") or "")[:1000],
            "elapsedMs": t_ms(),
        }

    print(json.dumps({
        "probe": "camoufox-websocket-probe",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "matchedCookies": len(matched),
        "totalCookies": len(auth_cookies),
        "prompt": PROMPT,
        "final": final,
        "websocketEvents": websocket_events[:200],
        "pageErrors": page_errors,
        "consoleErrors": console_errors[:30],
    }, indent=2))

asyncio.run(main())
