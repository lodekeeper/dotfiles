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
PROMPT = "Reply with exactly ROUTESTATE_OK."

JS_SAMPLE = r'''
(() => {
  const body = document.body?.innerText || '';
  const routeGlobals = Object.keys(window).filter((k) => /react|router|remix/i.test(k)).sort();
  const ctx = window.__reactRouterContext;
  const safeKeys = (obj) => {
    try { return obj ? Object.keys(obj).slice(0, 20) : []; } catch { return ['<error>']; }
  };
  const safeType = (v) => {
    if (v === null) return 'null';
    if (v === undefined) return 'undefined';
    if (Array.isArray(v)) return `array:${v.length}`;
    return typeof v;
  };
  const summarize = (v) => {
    try {
      if (v === null || v === undefined) return v;
      if (typeof v === 'string') return v.slice(0, 300);
      if (typeof v === 'number' || typeof v === 'boolean') return v;
      if (Array.isArray(v)) return {type: 'array', length: v.length, firstTypes: v.slice(0, 5).map(safeType)};
      return {type: safeType(v), keys: safeKeys(v)};
    } catch (e) {
      return {error: String(e)};
    }
  };

  const rr = ctx ? {
    keys: safeKeys(ctx),
    streamControllerType: safeType(ctx.streamController),
    manifest: summarize(window.__reactRouterManifest),
    routeModules: summarize(window.__reactRouterRouteModules),
    hydration: summarize(window.__staticRouterHydrationData),
  } : null;

  const scripts = Array.from(document.scripts)
    .filter((s) => (s.textContent || '').includes('__reactRouterContext'))
    .slice(0, 3)
    .map((s) => (s.textContent || '').slice(0, 600));

  const turns = document.querySelectorAll('[data-testid^="conversation-turn"]').length;
  const lastTurnText = (() => {
    const last = turns ? document.querySelectorAll('[data-testid^="conversation-turn"]')[turns - 1] : null;
    const md = last?.querySelector('.markdown') || last?.querySelector('[data-message-content]') || last?.querySelector('.prose');
    return (md?.innerText || last?.innerText || '').trim().slice(0, 300);
  })();

  return {
    url: location.href,
    title: document.title,
    bodyHasAppError: /application error/i.test(body),
    bodyHasCFSnippet: body.includes('__CF$cv$params') || body.includes('challenge-platform'),
    bodyHasReactRouterStream: body.includes('__reactRouterContext.streamController'),
    routeGlobals,
    reactRouterContext: rr,
    reactRouterScripts: scripts,
    turns,
    lastTurnText,
  };
})();
'''

async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    matched = [c for c in auth_cookies if _cookie_matches_url(c, CHATGPT_URL)]

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()

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

        samples = []
        for _ in range(6):
            await asyncio.sleep(2)
            snap = await page.evaluate(JS_SAMPLE)
            snap["t_ms"] = round((time.time() - start) * 1000)
            samples.append(snap)
            if snap.get("bodyHasAppError"):
                break

    print(json.dumps({
        "probe": "camoufox-route-state",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "matchedCookies": len(matched),
        "totalCookies": len(auth_cookies),
        "prompt": PROMPT,
        "samples": samples,
    }, indent=2))

asyncio.run(main())
