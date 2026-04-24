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
PROMPT = "Reply with exactly LATEFAIL_OK."


def sanitize(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}"

async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    matched = [c for c in auth_cookies if _cookie_matches_url(c, CHATGPT_URL)]

    console_errors = []
    page_errors = []
    events = []
    response_snaps = []
    start = None

    def t_ms():
        if start is None:
            return None
        return round((time.time() - start) * 1000)

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        page.on("console", lambda msg: console_errors.append({"t_ms": t_ms(), "type": msg.type, "text": msg.text}) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append({"t_ms": t_ms(), "text": str(exc)}))

        async def on_request(req):
            url = req.url
            if "chatgpt.com" in url and ("backend-api" in url or "/ces/" in url or "/c/" in url):
                events.append({
                    "t_ms": t_ms(),
                    "kind": "request",
                    "url": sanitize(url),
                    "method": req.method,
                    "resourceType": req.resource_type,
                    "isNavigation": req.is_navigation_request(),
                })

        async def on_response(resp):
            url = resp.url
            if "chatgpt.com" in url and ("backend-api" in url or "/ces/" in url or "/c/" in url):
                headers = {k.lower(): v for k, v in resp.headers.items()}
                item = {
                    "t_ms": t_ms(),
                    "kind": "response",
                    "url": sanitize(url),
                    "status": resp.status,
                    "ok": resp.ok,
                    "contentType": headers.get("content-type"),
                }
                events.append(item)
                interesting = resp.status >= 400 or "/ces/" in url or (headers.get("content-type") and "text/html" in headers.get("content-type"))
                if interesting:
                    snap = {
                        "t_ms": t_ms(),
                        "url": sanitize(url),
                        "status": resp.status,
                        "contentType": headers.get("content-type"),
                    }
                    try:
                        snap["textHead"] = (await resp.text())[:5000]
                    except Exception as e:
                        snap["readError"] = repr(e)
                    response_snaps.append(snap)

        page.on("request", lambda req: asyncio.create_task(on_request(req)))
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

        await asyncio.sleep(14)
        final = {
            "t_ms": t_ms(),
            "url": page.url,
            "title": await page.title(),
        }

    result = {
        "probe": "camoufox-late-failure-trace",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "matchedCookies": len(matched),
        "totalCookies": len(auth_cookies),
        "prompt": PROMPT,
        "final": final,
        "events": events,
        "responseSnaps": response_snaps,
        "pageErrors": page_errors,
        "consoleErrors": console_errors[:30],
    }
    print(json.dumps(result, indent=2))

asyncio.run(main())
