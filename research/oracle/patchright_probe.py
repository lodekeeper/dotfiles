import asyncio, json, time, os, importlib.util
from patchright.async_api import async_playwright

CHATGPT_DIRECT_PATH = "/home/openclaw/.openclaw/workspace/research/chatgpt-direct.py"
spec = importlib.util.spec_from_file_location("chatgpt_direct", CHATGPT_DIRECT_PATH)
chatgpt_direct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chatgpt_direct)
_cookie_matches_url = chatgpt_direct._cookie_matches_url
collect_auth_state = chatgpt_direct.collect_auth_state
ensure_pro_model = chatgpt_direct.ensure_pro_model

COOKIES = os.path.expanduser("~/.oracle/chatgpt-cookies.json")
CHATGPT_URL = "https://chatgpt.com"
PROMPT = "Reply with exactly PATCHRIGHT_OK."

async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    matched = [c for c in auth_cookies if _cookie_matches_url(c, CHATGPT_URL)]
    result = {
        "probe": "patchright-chatgpt-ab",
        "chatgptUrl": CHATGPT_URL,
        "matchedCookies": len(matched),
        "totalCookies": len(auth_cookies),
        "prompt": PROMPT,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    page_errors = []
    console_errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
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
        nav = {"ok": True}
        try:
            resp = await page.goto(CHATGPT_URL, timeout=30000)
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(8)
            nav["status"] = resp.status if resp else None
            nav["url"] = page.url
            nav["title"] = await page.title()
        except Exception as e:
            nav = {"ok": False, "error": repr(e), "url": page.url}
        result["navigation"] = nav
        body = (await page.text_content("body") or "")[:4000]
        result["bodySnippet"] = body
        result["cfMarkers"] = {
            "justAMoment": "Just a moment" in body,
            "verifyHuman": "Verify you are human" in body,
            "applicationError": "Application Error" in body,
        }
        auth = await collect_auth_state(page, CHATGPT_URL)
        result["auth"] = auth
        try:
            model = await ensure_pro_model(page, verbose=False)
        except Exception as e:
            model = {"error": repr(e)}
        result["model"] = model
        has_box = await page.evaluate("!!document.querySelector('[id=\"prompt-textarea\"]')")
        result["hasPromptBox"] = has_box
        result["prePromptUrl"] = page.url
        if has_box:
            initial_turns = await page.evaluate(
                "document.querySelectorAll('[data-testid^=\"conversation-turn\"]').length"
            )
            el = await page.query_selector('[id="prompt-textarea"]')
            await el.focus()
            await page.keyboard.type(PROMPT, delay=10)
            await asyncio.sleep(0.3)
            inserted = await page.evaluate(
                "document.querySelector('[id=\"prompt-textarea\"]')?.innerText?.trim()?.length || 0"
            )
            result["insertedChars"] = inserted
            await page.keyboard.press("Enter")
            await asyncio.sleep(1)
            post_send = await page.evaluate(
                f'''(() => {{
                const turns = document.querySelectorAll('[data-testid^="conversation-turn"]').length;
                const stopBtn = !!document.querySelector('[data-testid="stop-button"]');
                const textarea = document.querySelector('[id="prompt-textarea"]');
                const remaining = textarea ? (textarea.innerText || '').trim().length : 0;
                return {{turns, stopBtn, remaining, submitted: stopBtn || turns > {initial_turns} || remaining === 0, url: location.href}};
            }})()'''
            )
            result["postSend"] = post_send
            samples = []
            for _ in range(8):
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
                        bodySnippet: bodyText.slice(0, 500),
                        lastText: (mdText || fullText).slice(0, 500),
                    };
                })()'''
                )
                samples.append(sample)
                if sample.get("appError"):
                    break
            result["samples"] = samples
        result["pageErrors"] = page_errors[-10:]
        result["consoleErrors"] = console_errors[-20:]
        await browser.close()
    print(json.dumps(result, indent=2))

asyncio.run(main())
