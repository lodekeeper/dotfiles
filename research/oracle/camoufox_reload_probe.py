import asyncio, json, time, os, importlib.util
from camoufox.async_api import AsyncCamoufox

CHATGPT_DIRECT_PATH = "/home/openclaw/.openclaw/workspace/research/chatgpt-direct.py"
spec = importlib.util.spec_from_file_location("chatgpt_direct", CHATGPT_DIRECT_PATH)
chatgpt_direct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chatgpt_direct)
_cookie_matches_url = chatgpt_direct._cookie_matches_url
collect_auth_state = chatgpt_direct.collect_auth_state
ensure_pro_model = chatgpt_direct.ensure_pro_model

COOKIES = os.path.expanduser("~/.oracle/chatgpt-cookies.json")
CHATGPT_URL = "https://chatgpt.com"
PROMPT = "Reply with exactly CAMOUFOX_RELOAD_OK."

async def run_attempt(page, label):
    data = {"label": label}
    auth = await collect_auth_state(page, CHATGPT_URL)
    data["auth"] = auth
    try:
        data["model"] = await ensure_pro_model(page, verbose=False)
    except Exception as e:
        data["model"] = {"error": repr(e)}
    has_box = await page.evaluate("!!document.querySelector('[id=\"prompt-textarea\"]')")
    data["hasPromptBox"] = has_box
    data["urlBeforeSend"] = page.url
    if not has_box:
        data["result"] = "no_prompt_box"
        data["bodySnippet"] = (await page.text_content("body") or "")[:800]
        return data

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
    data["insertedChars"] = inserted
    await page.keyboard.press("Enter")
    await asyncio.sleep(1)
    data["postSend"] = await page.evaluate(
        f'''(() => {{
            const turns = document.querySelectorAll('[data-testid^="conversation-turn"]').length;
            const stopBtn = !!document.querySelector('[data-testid="stop-button"]');
            const textarea = document.querySelector('[id="prompt-textarea"]');
            const remaining = textarea ? (textarea.innerText || '').trim().length : 0;
            return {{turns, stopBtn, remaining, submitted: stopBtn || turns > {initial_turns} || remaining === 0, url: location.href}};
        }})()'''
    )

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
            data["result"] = "app_error"
            data["samples"] = samples
            return data
        if sample.get("lastText") and not sample.get("stopBtn"):
            data["result"] = "response_done"
            data["samples"] = samples
            return data
    data["result"] = "timeout"
    data["samples"] = samples
    return data

async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    matched = [c for c in auth_cookies if _cookie_matches_url(c, CHATGPT_URL)]
    result = {
        "probe": "camoufox-reload-retry",
        "chatgptUrl": CHATGPT_URL,
        "matchedCookies": len(matched),
        "totalCookies": len(auth_cookies),
        "prompt": PROMPT,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    page_errors = []
    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
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
        result["attempt1"] = await run_attempt(page, "attempt1")
        if result["attempt1"].get("result") == "app_error":
            try:
                await page.reload(timeout=30000)
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(8)
                result["reload"] = {"ok": True, "url": page.url, "title": await page.title()}
            except Exception as e:
                result["reload"] = {"ok": False, "error": repr(e), "url": page.url}
            result["attempt2"] = await run_attempt(page, "attempt2")
        result["pageErrors"] = page_errors[-10:]
    print(json.dumps(result, indent=2))

asyncio.run(main())
