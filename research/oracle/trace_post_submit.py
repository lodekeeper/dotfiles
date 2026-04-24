import argparse
import asyncio
import importlib.util
import json
import os
import time
from collections import Counter, defaultdict
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from camoufox.async_api import AsyncCamoufox

CHATGPT_DIRECT_PATH = "/home/openclaw/.openclaw/workspace/research/chatgpt-direct.py"
spec = importlib.util.spec_from_file_location("chatgpt_direct", CHATGPT_DIRECT_PATH)
chatgpt_direct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chatgpt_direct)
_cookie_matches_url = chatgpt_direct._cookie_matches_url
collect_auth_state = chatgpt_direct.collect_auth_state
ensure_pro_model = chatgpt_direct.ensure_pro_model

DEFAULT_URL = "https://chatgpt.com"
DEFAULT_COOKIES = os.path.expanduser("~/.oracle/chatgpt-cookies.json")


def sanitize_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def interesting(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(
        key in host
        for key in [
            "chatgpt.com",
            "openai.com",
            "oaistatic.com",
            "oaiusercontent.com",
        ]
    )


async def launch_engine(engine: str):
    if engine == "camoufox":
        browser = await AsyncCamoufox(headless=True).__aenter__()
        return browser, None
    if engine == "firefox":
        pw = await async_playwright().__aenter__()
        browser = await pw.firefox.launch(headless=True)
        return browser, pw
    raise ValueError(f"Unsupported engine: {engine}")


async def close_engine(engine: str, browser, pw):
    if engine == "camoufox":
        await browser.__aexit__(None, None, None)
    else:
        await browser.close()
        await pw.stop()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["camoufox", "firefox"], required=True)
    parser.add_argument("--prompt", default="Reply with exactly TRACE_OK.")
    parser.add_argument("--chatgpt-url", default=DEFAULT_URL)
    parser.add_argument("--cookies", default=DEFAULT_COOKIES)
    parser.add_argument("--observe-seconds", type=int, default=18)
    args = parser.parse_args()

    with open(args.cookies) as f:
        auth_cookies = json.load(f)

    matched = [c for c in auth_cookies if _cookie_matches_url(c, args.chatgpt_url)]
    browser, pw = await launch_engine(args.engine)
    page = await browser.new_page()

    page_errors = []
    console_errors = []
    events = []
    ws_urls = []
    send_time = None

    def rel_ms():
        if send_time is None:
            return None
        return round((time.time() - send_time) * 1000)

    def push_event(kind: str, payload: dict):
        payload = dict(payload)
        payload["kind"] = kind
        payload["t_ms"] = rel_ms()
        events.append(payload)

    async def on_request(req):
        url = req.url
        if interesting(url):
            push_event(
                "request",
                {
                    "url": sanitize_url(url),
                    "method": req.method,
                    "resourceType": req.resource_type,
                },
            )

    async def on_response(resp):
        url = resp.url
        if interesting(url):
            push_event(
                "response",
                {
                    "url": sanitize_url(url),
                    "status": resp.status,
                    "ok": resp.ok,
                },
            )

    async def on_request_failed(req):
        url = req.url
        if interesting(url):
            failure = req.failure
            push_event(
                "requestfailed",
                {
                    "url": sanitize_url(url),
                    "errorText": failure if isinstance(failure, str) else str(failure),
                    "resourceType": req.resource_type,
                },
            )

    page.on("request", lambda req: asyncio.create_task(on_request(req)))
    page.on("response", lambda resp: asyncio.create_task(on_response(resp)))
    page.on("requestfailed", lambda req: asyncio.create_task(on_request_failed(req)))
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    page.on(
        "console",
        lambda msg: console_errors.append({"type": msg.type, "text": msg.text})
        if msg.type == "error"
        else None,
    )
    page.on(
        "websocket",
        lambda ws: ws_urls.append(sanitize_url(ws.url)) if interesting(ws.url) else None,
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

    nav_resp = await page.goto(args.chatgpt_url, timeout=30000)
    await page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(8)

    auth = await collect_auth_state(page, args.chatgpt_url)
    model = await ensure_pro_model(page, verbose=False)
    has_box = await page.evaluate("!!document.querySelector('[id=\"prompt-textarea\"]')")
    if not has_box:
        result = {
            "engine": args.engine,
            "status": "no_prompt_box",
            "navigation": {
                "status": nav_resp.status if nav_resp else None,
                "url": page.url,
                "title": await page.title(),
            },
            "auth": auth,
            "model": model,
            "matchedCookies": len(matched),
            "totalCookies": len(auth_cookies),
        }
        print(json.dumps(result, indent=2))
        await close_engine(args.engine, browser, pw)
        return

    initial_turns = await page.evaluate(
        "document.querySelectorAll('[data-testid^=\"conversation-turn\"]').length"
    )
    el = await page.query_selector('[id="prompt-textarea"]')
    await el.focus()
    await page.keyboard.type(args.prompt, delay=10)
    await asyncio.sleep(0.3)
    send_time = time.time()
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

    samples = []
    for _ in range(max(1, args.observe_seconds // 2)):
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
                    bodyHasSomethingWrong: /something went wrong/i.test(bodyText),
                    lastText: (mdText || fullText).slice(0, 200),
                };
            })()'''
        )
        sample["t_ms"] = rel_ms()
        samples.append(sample)
        if sample.get("appError"):
            break
        if sample.get("lastText") and not sample.get("stopBtn"):
            break

    await asyncio.sleep(1)

    responses_by_url = defaultdict(list)
    requests_by_url = Counter()
    failures_by_url = Counter()
    for ev in events:
        if ev["kind"] == "request":
            requests_by_url[ev["url"]] += 1
        elif ev["kind"] == "response":
            responses_by_url[ev["url"]].append(ev.get("status"))
        elif ev["kind"] == "requestfailed":
            failures_by_url[ev["url"]] += 1

    summary = []
    all_urls = sorted(set(list(requests_by_url.keys()) + list(responses_by_url.keys()) + list(failures_by_url.keys())))
    for url in all_urls:
        summary.append(
            {
                "url": url,
                "requests": requests_by_url.get(url, 0),
                "responses": responses_by_url.get(url, []),
                "failures": failures_by_url.get(url, 0),
            }
        )

    result = {
        "engine": args.engine,
        "prompt": args.prompt,
        "navigation": {
            "status": nav_resp.status if nav_resp else None,
            "url": page.url,
            "title": await page.title(),
        },
        "authState": {
            "ui": auth.get("state"),
            "server": (auth.get("server") or {}).get("state"),
            "plan": (auth.get("server") or {}).get("planType"),
        },
        "model": model,
        "matchedCookies": len(matched),
        "totalCookies": len(auth_cookies),
        "postSend": post_send,
        "samples": samples,
        "websockets": sorted(set(ws_urls)),
        "pageErrors": page_errors[-10:],
        "consoleErrors": console_errors[-20:],
        "eventSummary": summary,
        "firstEvents": events[:80],
    }

    print(json.dumps(result, indent=2))
    await close_engine(args.engine, browser, pw)


if __name__ == "__main__":
    asyncio.run(main())
