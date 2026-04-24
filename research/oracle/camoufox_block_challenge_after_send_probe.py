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
PROMPT = "Reply with exactly NOCHALLENGE_OK."


async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    matched = [c for c in auth_cookies if _cookie_matches_url(c, CHATGPT_URL)]

    send_time = None
    blocked = []
    console_errors = []
    page_errors = []
    nav_events = []
    samples = []

    def rel_ms():
        if send_time is None:
            return None
        return round((time.time() - send_time) * 1000)

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()

        async def route_handler(route):
            url = route.request.url
            if send_time is not None and "/cdn-cgi/challenge-platform/" in url:
                blocked.append({"t_ms": rel_ms(), "url": url, "resourceType": route.request.resource_type})
                await route.fulfill(status=204, body="")
                return
            await route.continue_()

        await page.route("**/*", route_handler)

        page.on(
            "console",
            lambda msg: console_errors.append({"type": msg.type, "text": msg.text}) if msg.type == "error" else None,
        )
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on(
            "framenavigated",
            lambda frame: nav_events.append({"url": frame.url, "name": frame.name, "t_ms": rel_ms()}) if frame == page.main_frame else None,
        )

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

        for _ in range(8):
            await asyncio.sleep(2)
            body = await page.text_content("body") or ""
            last_text = await page.evaluate(
                '''(() => {
                    const turns = document.querySelectorAll('[data-testid^="conversation-turn"]');
                    const last = turns.length ? turns[turns.length - 1] : null;
                    const md = last?.querySelector('.markdown') || last?.querySelector('[data-message-content]') || last?.querySelector('.prose');
                    const fullText = (md?.innerText || last?.innerText || '').trim();
                    return fullText.slice(0, 400);
                })()'''
            )
            samples.append(
                {
                    "t_ms": rel_ms(),
                    "url": page.url,
                    "title": await page.title(),
                    "bodyHasAppError": "Application Error" in body,
                    "bodyHasCFSnippet": "__CF$cv$params" in body or "challenge-platform" in body,
                    "bodyHasReactRouterStream": "__reactRouterContext.streamController" in body,
                    "lastTurnText": last_text,
                    "bodySnippet": body[:500],
                }
            )
            if "Application Error" in body:
                break

    print(
        json.dumps(
            {
                "probe": "camoufox-block-challenge-after-send",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "matchedCookies": len(matched),
                "totalCookies": len(auth_cookies),
                "prompt": PROMPT,
                "blocked": blocked,
                "navEvents": nav_events,
                "samples": samples,
                "pageErrors": page_errors[-10:],
                "consoleErrors": console_errors[-20:],
            },
            indent=2,
        )
    )


asyncio.run(main())
