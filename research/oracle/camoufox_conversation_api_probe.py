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
PROMPT = "Reply with exactly API_OK."


def find_assistant_texts(obj):
    out = []

    def walk(v):
        if isinstance(v, dict):
            author = v.get("author")
            if isinstance(author, dict) and author.get("role") == "assistant":
                content = v.get("content") or {}
                parts = content.get("parts")
                if isinstance(parts, list):
                    text = "\n".join(str(p) for p in parts if p)
                    if text.strip():
                        out.append(text.strip())
            for vv in v.values():
                walk(vv)
        elif isinstance(v, list):
            for vv in v:
                walk(vv)

    walk(obj)
    return out


async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    matched = [c for c in auth_cookies if _cookie_matches_url(c, CHATGPT_URL)]

    console_errors = []
    page_errors = []

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        page.on("console", lambda msg: console_errors.append({"type": msg.type, "text": msg.text}) if msg.type == "error" else None)
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

        composer = page.locator('[id="prompt-textarea"]').first
        await composer.click()
        await page.keyboard.type(PROMPT, delay=10)
        await asyncio.sleep(0.3)
        start = time.time()
        await page.keyboard.press("Enter")

        conversation_id = None
        for _ in range(15):
            await asyncio.sleep(1)
            m = re.search(r'/c/([0-9a-f\-]+)', page.url)
            if m:
                conversation_id = m.group(1)
                break

        await asyncio.sleep(18)

        title = await page.title()
        body = (await page.text_content("body") or "")[:1200]
        fetch_result = None
        if conversation_id:
            raw = await page.evaluate(
                """
                async (cid) => {
                    try {
                        const res = await fetch(`/backend-api/conversation/${cid}`, {
                            credentials: 'include',
                            cache: 'no-store',
                            headers: {accept: 'application/json'}
                        });
                        const text = await res.text();
                        return JSON.stringify({ok: res.ok, status: res.status, text});
                    } catch (e) {
                        return JSON.stringify({ok: false, status: null, error: String(e)});
                    }
                }
                """,
                conversation_id,
            )
            fetch_result = json.loads(raw)

    parsed_json = None
    assistant_texts = []
    if fetch_result and fetch_result.get("text"):
        try:
            parsed_json = json.loads(fetch_result["text"])
            assistant_texts = find_assistant_texts(parsed_json)
        except Exception:
            parsed_json = None

    out = {
        "probe": "camoufox-conversation-api-probe",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "matchedCookies": len(matched),
        "totalCookies": len(auth_cookies),
        "prompt": PROMPT,
        "elapsedMs": round((time.time() - start) * 1000),
        "conversationId": conversation_id,
        "final": {
            "url": page.url,
            "title": title,
            "bodySnippet": body,
        },
        "fetch": {
            "ok": (fetch_result or {}).get("ok"),
            "status": (fetch_result or {}).get("status"),
            "error": (fetch_result or {}).get("error"),
            "textHead": ((fetch_result or {}).get("text") or "")[:4000],
        },
        "assistantTexts": assistant_texts[:10],
        "pageErrors": page_errors,
        "consoleErrors": console_errors[:30],
    }
    print(json.dumps(out, indent=2))

asyncio.run(main())
