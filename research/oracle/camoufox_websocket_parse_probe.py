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
PROMPT = "Reply with exactly WS_PARSE_OK."


def sanitize_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}"


def extract_messages(obj, out):
    if isinstance(obj, dict):
        author = obj.get("author")
        if isinstance(author, dict):
            role = author.get("role")
            content = obj.get("content") or {}
            parts = content.get("parts") if isinstance(content, dict) else None
            text = None
            if isinstance(parts, list):
                text = "\n".join(str(p) for p in parts if p).strip()
            if role:
                out.append(
                    {
                        "role": role,
                        "status": obj.get("status"),
                        "text": text,
                        "id": obj.get("id"),
                        "metadata": (obj.get("metadata") or {}),
                    }
                )
        for v in obj.values():
            extract_messages(v, out)
    elif isinstance(obj, list):
        for v in obj:
            extract_messages(v, out)


async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    matched = [c for c in auth_cookies if _cookie_matches_url(c, CHATGPT_URL)]

    events = []
    extracted = []
    console_errors = []
    page_errors = []
    start = None

    def t_ms():
        if start is None:
            return None
        return round((time.time() - start) * 1000)

    def on_ws(ws):
        events.append({"t_ms": t_ms(), "kind": "open", "url": sanitize_url(ws.url)})

        def handle_frame(payload):
            text = payload if isinstance(payload, str) else payload.decode("utf-8", errors="replace")
            item = {"t_ms": t_ms(), "url": sanitize_url(ws.url), "rawHead": text[:1200]}
            try:
                parsed = json.loads(text)
                item["parsedType"] = type(parsed).__name__
                msgs = []
                extract_messages(parsed, msgs)
                if msgs:
                    item["messageCount"] = len(msgs)
                    item["roles"] = sorted(set(m.get("role") for m in msgs if m.get("role")))
                    # Keep a lightweight extracted record separately.
                    extracted.append({
                        "t_ms": t_ms(),
                        "url": sanitize_url(ws.url),
                        "messages": [
                            {
                                "role": m.get("role"),
                                "status": m.get("status"),
                                "text": (m.get("text") or "")[:2000],
                                "id": m.get("id"),
                                "metadata": {
                                    "initial_text": (m.get("metadata") or {}).get("initial_text"),
                                    "finished_text": (m.get("metadata") or {}).get("finished_text"),
                                    "summarization_headline": (m.get("metadata") or {}).get("summarization_headline"),
                                    "model_slug": (m.get("metadata") or {}).get("model_slug"),
                                    "message_type": (m.get("metadata") or {}).get("message_type"),
                                },
                            }
                            for m in msgs
                        ],
                    })
            except Exception as e:
                item["parseError"] = repr(e)
            events.append(item)

        try:
            ws.on("framereceived", handle_frame)
        except Exception as e:
            events.append({"t_ms": t_ms(), "kind": "ws-hook-error", "url": sanitize_url(ws.url), "error": repr(e)})

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        page.on("websocket", on_ws)
        page.on("console", lambda msg: console_errors.append({"t_ms": t_ms(), "type": msg.type, "text": msg.text}) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append({"t_ms": t_ms(), "text": str(exc)}))

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
        await asyncio.sleep(30)

        final = {
            "url": page.url,
            "title": await page.title(),
            "bodySnippet": (await page.text_content("body") or "")[:800],
            "elapsedMs": t_ms(),
        }

    print(json.dumps({
        "probe": "camoufox-websocket-parse-probe",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "matchedCookies": len(matched),
        "totalCookies": len(auth_cookies),
        "prompt": PROMPT,
        "final": final,
        "events": events[:200],
        "extracted": extracted[:50],
        "pageErrors": page_errors,
        "consoleErrors": console_errors[:30],
    }, indent=2))

asyncio.run(main())
