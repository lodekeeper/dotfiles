import asyncio, json, time, os, importlib.util
from playwright.async_api import async_playwright

CHATGPT_DIRECT_PATH = "/home/openclaw/.openclaw/workspace/research/chatgpt-direct.py"
spec = importlib.util.spec_from_file_location("chatgpt_direct", CHATGPT_DIRECT_PATH)
chatgpt_direct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chatgpt_direct)
_cookie_matches_url = chatgpt_direct._cookie_matches_url
collect_auth_state = chatgpt_direct.collect_auth_state
ensure_pro_model = chatgpt_direct.ensure_pro_model

COOKIES = os.path.expanduser("~/.oracle/chatgpt-cookies.json")
CHATGPT_URL = "https://chatgpt.com"
PROMPT = "Reply with exactly FIREFOX_CES_BLOCK_OK."

async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    matched = [c for c in auth_cookies if _cookie_matches_url(c, CHATGPT_URL)]
    result = {
        "probe": "playwright-firefox-block-ces",
        "chatgptUrl": CHATGPT_URL,
        "matchedCookies": len(matched),
        "totalCookies": len(auth_cookies),
        "prompt": PROMPT,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    page_errors = []
    console_errors = []
    blocked = []

    async def route_handler(route):
        url = route.request.url
        if "/ces/v1/" in url:
            blocked.append(url)
            await route.fulfill(status=204, body="", headers={"content-type": "application/json"})
        else:
            await route.continue_()

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()
        await page.route("**/*", route_handler)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on(
            "console",
            lambda msg: console_errors.append({"type": msg.type, "text": msg.text})
            if msg.type == "error"
            else None,
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
        resp = await page.goto(CHATGPT_URL, timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(8)
        result["navigation"] = {
            "status": resp.status if resp else None,
            "url": page.url,
            "title": await page.title(),
        }
        auth = await collect_auth_state(page, CHATGPT_URL)
        result["auth"] = auth
        result["model"] = await ensure_pro_model(page, verbose=False)
        result["hasPromptBox"] = await page.evaluate("!!document.querySelector('[id=\"prompt-textarea\"]')")
        initial_turns = await page.evaluate(
            "document.querySelectorAll('[data-testid^=\"conversation-turn\"]').length"
        )
        el = await page.query_selector('[id="prompt-textarea"]')
        await el.focus()
        await page.keyboard.type(PROMPT, delay=10)
        await asyncio.sleep(0.3)
        await page.keyboard.press("Enter")
        await asyncio.sleep(1)
        result["postSend"] = await page.evaluate(
            f'''(() => {{
                const turns = document.querySelectorAll('[data-testid^="conversation-turn"]').length;
                const stopBtn = !!document.querySelector('[data-testid="stop-button"]');
                return {{turns, stopBtn, submitted: stopBtn || turns > {initial_turns}, url: location.href}};
            }})()'''
        )
        samples = []
        for _ in range(10):
            await asyncio.sleep(2)
            sample = await page.evaluate(
                '''(() => {
                    const bodyText = (document.body?.innerText || '').trim();
                    const turns = document.querySelectorAll('[data-testid^="conversation-turn"]');
                    const last = turns.length ? turns[turns.length - 1] : null;
                    const md = last?.querySelector('.markdown') || last?.querySelector('[data-message-content]') || last?.querySelector('.prose');
                    const mdText = md ? (md.innerText || '').trim() : '';
                    const fullText = (last?.innerText || '').trim();
                    const stopBtn = !!document.querySelector('[data-testid="stop-button"]');
                    return {
                        url: location.href,
                        turns: turns.length,
                        stopBtn,
                        appError: /application error/i.test(bodyText),
                        lastText: (mdText || fullText).slice(0, 500),
                    };
                })()'''
            )
            samples.append(sample)
            if sample.get("appError"):
                break
            if sample.get("lastText") and not sample.get("stopBtn"):
                break
        result["samples"] = samples
        result["blockedCes"] = blocked[:50]
        result["pageErrors"] = page_errors[-10:]
        result["consoleErrors"] = console_errors[-20:]
        await browser.close()
    print(json.dumps(result, indent=2))

asyncio.run(main())
