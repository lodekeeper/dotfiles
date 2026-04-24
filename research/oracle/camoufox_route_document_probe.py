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
PROMPT = "Reply with exactly DOCCAP_OK."


def interesting_host(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(key in host for key in ["chatgpt.com", "openai.com", "oaistatic.com", "oaiusercontent.com"])


async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    matched = [c for c in auth_cookies if _cookie_matches_url(c, CHATGPT_URL)]

    send_time = None
    responses = []
    console_errors = []
    page_errors = []
    nav_events = []

    def rel_ms():
        if send_time is None:
            return None
        return round((time.time() - send_time) * 1000)

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()

        page.on(
            "console",
            lambda msg: console_errors.append({"type": msg.type, "text": msg.text}) if msg.type == "error" else None,
        )
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on(
            "framenavigated",
            lambda frame: nav_events.append({"url": frame.url, "name": frame.name, "t_ms": rel_ms()}) if frame == page.main_frame else None,
        )

        async def on_response(resp):
            nonlocal responses
            if send_time is None:
                return
            url = resp.url
            if not interesting_host(url):
                return

            request = resp.request
            resource_type = request.resource_type
            headers = {k.lower(): v for k, v in resp.headers.items()}
            content_type = headers.get("content-type", "")
            is_route_doc = resource_type == "document" and "/c/" in url
            maybe_html = "text/html" in content_type or "application/xhtml" in content_type or is_route_doc
            maybe_loader = any(x in url for x in ["/c/", "/backend-api/", "/cdn-cgi/"])
            if not (maybe_html or maybe_loader):
                return

            snap = {
                "t_ms": rel_ms(),
                "url": url,
                "status": resp.status,
                "ok": resp.ok,
                "resourceType": resource_type,
                "contentType": content_type,
            }
            if len(responses) < 40:
                try:
                    text = await resp.text()
                    if text:
                        snap["len"] = len(text)
                        snap["textHead"] = text[:6000]
                        snap["textTail"] = text[-2500:] if len(text) > 2500 else text
                        snap["hasCFSnippet"] = "__CF$cv$params" in text or "challenge-platform" in text
                        snap["hasReactRouterStream"] = "__reactRouterContext.streamController" in text
                        snap["hasApplicationError"] = "Application Error" in text
                except Exception as e:
                    snap["readError"] = repr(e)
                responses.append(snap)

        page.on("response", lambda resp: asyncio.create_task(on_response(resp)))

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
        send_time = time.time()
        await page.keyboard.press("Enter")

        samples = []
        for _ in range(8):
            await asyncio.sleep(2)
            body = await page.text_content("body") or ""
            samples.append(
                {
                    "t_ms": rel_ms(),
                    "url": page.url,
                    "title": await page.title(),
                    "bodyHasAppError": "Application Error" in body,
                    "bodyHasCFSnippet": "__CF$cv$params" in body or "challenge-platform" in body,
                    "bodyHasReactRouterStream": "__reactRouterContext.streamController" in body,
                    "bodySnippet": body[:500],
                }
            )
            if "Application Error" in body:
                break

    print(
        json.dumps(
            {
                "probe": "camoufox-route-document",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "matchedCookies": len(matched),
                "totalCookies": len(auth_cookies),
                "prompt": PROMPT,
                "navEvents": nav_events,
                "samples": samples,
                "responses": responses,
                "pageErrors": page_errors[-10:],
                "consoleErrors": console_errors[-20:],
            },
            indent=2,
        )
    )


asyncio.run(main())
