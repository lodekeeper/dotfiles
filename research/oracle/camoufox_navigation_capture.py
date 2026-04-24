import asyncio
import importlib.util
import json
import os
import re
import time
from camoufox.async_api import AsyncCamoufox

CHATGPT_DIRECT_PATH = "/home/openclaw/.openclaw/workspace/research/chatgpt-direct.py"
spec = importlib.util.spec_from_file_location("chatgpt_direct", CHATGPT_DIRECT_PATH)
chatgpt_direct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chatgpt_direct)
_cookie_matches_url = chatgpt_direct._cookie_matches_url

COOKIES = os.path.expanduser("~/.oracle/chatgpt-cookies.json")
CHATGPT_URL = "https://chatgpt.com"
PROMPT = "Reply with exactly NAVCAP_OK."

async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    matched = [c for c in auth_cookies if _cookie_matches_url(c, CHATGPT_URL)]

    console_errors = []
    page_errors = []
    nav_requests = []
    nav_responses = []
    response_bodies = []
    start = None

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        page.on("console", lambda msg: console_errors.append({"type": msg.type, "text": msg.text}) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        async def on_request(req):
            if "/c/" in req.url or "/backend-api/conversation/" in req.url:
                nav_requests.append({
                    "url": req.url,
                    "method": req.method,
                    "resourceType": req.resource_type,
                    "isNavigation": req.is_navigation_request(),
                })

        async def on_response(resp):
            url = resp.url
            if "/c/" in url or "/backend-api/conversation/" in url:
                item = {
                    "url": url,
                    "status": resp.status,
                    "ok": resp.ok,
                    "headers": {k.lower(): v for k, v in resp.headers.items() if k.lower() in {"content-type", "location"}},
                }
                nav_responses.append(item)
                try:
                    if "/c/" in url or "/stream_status" in url:
                        text = await resp.text()
                        response_bodies.append({
                            "url": url,
                            "status": resp.status,
                            "textHead": text[:12000],
                        })
                except Exception as e:
                    response_bodies.append({
                        "url": url,
                        "status": resp.status,
                        "readError": repr(e),
                    })

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

        await asyncio.sleep(6)

        final = {
            "t_ms": round((time.time() - start) * 1000),
            "url": page.url,
            "title": await page.title(),
        }

    result = {
        "probe": "camoufox-navigation-capture",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "matchedCookies": len(matched),
        "totalCookies": len(auth_cookies),
        "prompt": PROMPT,
        "final": final,
        "navRequests": nav_requests,
        "navResponses": nav_responses,
        "responseBodies": response_bodies,
        "pageErrors": page_errors,
        "consoleErrors": console_errors[:20],
    }
    print(json.dumps(result, indent=2))

asyncio.run(main())
