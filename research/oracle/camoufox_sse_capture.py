import asyncio
import importlib.util
import json
import os
import time
from camoufox.async_api import AsyncCamoufox

CHATGPT_DIRECT_PATH = "/home/openclaw/.openclaw/workspace/research/chatgpt-direct.py"
spec = importlib.util.spec_from_file_location("chatgpt_direct", CHATGPT_DIRECT_PATH)
chatgpt_direct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chatgpt_direct)
_cookie_matches_url = chatgpt_direct._cookie_matches_url

COOKIES = os.path.expanduser("~/.oracle/chatgpt-cookies.json")
CHATGPT_URL = "https://chatgpt.com"
PROMPT = "Reply with exactly SSE_OK."

async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    matched = [c for c in auth_cookies if _cookie_matches_url(c, CHATGPT_URL)]

    sse_bodies = []
    final = {}

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()

        async def on_response(resp):
            url = resp.url
            if "/backend-api/f/conversation" in url and not url.endswith('/prepare'):
                headers = {k.lower(): v for k, v in resp.headers.items()}
                snap = {"url": url, "status": resp.status, "contentType": headers.get("content-type")}
                try:
                    text = await resp.text()
                    snap["textHead"] = text[:12000]
                    snap["textTail"] = text[-4000:] if len(text) > 4000 else text
                    snap["len"] = len(text)
                except Exception as e:
                    snap["readError"] = repr(e)
                sse_bodies.append(snap)

        page.on("response", lambda resp: asyncio.create_task(on_response(resp)))

        for c in auth_cookies:
            await page.context.add_cookies([{
                "name": c.get("name", ""),
                "value": c.get("value", ""),
                "domain": c.get("domain", ".chatgpt.com"),
                "path": c.get("path", "/"),
                "secure": c.get("secure", True),
                "httpOnly": c.get("httpOnly", True),
            }])

        await page.goto(CHATGPT_URL, timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(8)

        composer = page.locator('[id="prompt-textarea"]').first
        await composer.click()
        await page.keyboard.type(PROMPT, delay=10)
        await asyncio.sleep(0.3)
        start = time.time()
        await page.keyboard.press("Enter")
        await asyncio.sleep(16)
        final = {"url": page.url, "title": await page.title(), "elapsedMs": round((time.time() - start) * 1000)}

    print(json.dumps({
        "probe": "camoufox-sse-capture",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "matchedCookies": len(matched),
        "totalCookies": len(auth_cookies),
        "prompt": PROMPT,
        "final": final,
        "sseBodies": sse_bodies,
    }, indent=2))

asyncio.run(main())
