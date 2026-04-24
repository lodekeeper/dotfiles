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
PROMPT = "Reply with exactly ERRCAP_OK."

INIT_SCRIPT = r'''
(() => {
  const log = {
    consoleErrors: [],
    windowErrors: [],
    rejections: [],
    nav: [],
  };

  const seen = new WeakSet();
  function safeSerialize(value, depth = 0) {
    if (depth > 2) return {type: typeof value, note: 'max-depth'};
    if (value === null || value === undefined) return value;
    const t = typeof value;
    if (t === 'string' || t === 'number' || t === 'boolean') return value;
    if (t === 'function') return {type: 'function', name: value.name || '(anonymous)'};
    if (value instanceof Error) {
      return {
        type: value.constructor?.name || 'Error',
        name: value.name,
        message: value.message,
        stack: value.stack,
        cause: safeSerialize(value.cause, depth + 1),
        keys: Object.keys(value).reduce((acc, k) => {
          try { acc[k] = safeSerialize(value[k], depth + 1); } catch {}
          return acc;
        }, {}),
      };
    }
    if (typeof Response !== 'undefined' && value instanceof Response) {
      return {
        type: 'Response',
        status: value.status,
        statusText: value.statusText,
        url: value.url,
        redirected: value.redirected,
      };
    }
    if (typeof Request !== 'undefined' && value instanceof Request) {
      return {
        type: 'Request',
        method: value.method,
        url: value.url,
        mode: value.mode,
        destination: value.destination,
      };
    }
    if (typeof value === 'object') {
      if (seen.has(value)) return {type: value.constructor?.name || 'Object', note: 'circular'};
      seen.add(value);
      const out = {
        type: value.constructor?.name || 'Object',
        keys: {},
      };
      for (const k of Object.keys(value).slice(0, 20)) {
        try {
          out.keys[k] = safeSerialize(value[k], depth + 1);
        } catch (e) {
          out.keys[k] = {type: 'error', message: String(e)};
        }
      }
      try {
        if (typeof value.message === 'string' && !out.message) out.message = value.message;
        if (typeof value.stack === 'string' && !out.stack) out.stack = value.stack;
      } catch {}
      return out;
    }
    return {type: t, string: String(value)};
  }

  const origConsoleError = console.error.bind(console);
  console.error = (...args) => {
    try {
      log.consoleErrors.push({t: Date.now(), args: args.map((a) => safeSerialize(a))});
    } catch {}
    return origConsoleError(...args);
  };

  window.addEventListener('error', (event) => {
    try {
      log.windowErrors.push({
        t: Date.now(),
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: safeSerialize(event.error),
      });
    } catch {}
  });

  window.addEventListener('unhandledrejection', (event) => {
    try {
      log.rejections.push({
        t: Date.now(),
        reason: safeSerialize(event.reason),
      });
    } catch {}
  });

  const origPush = history.pushState.bind(history);
  history.pushState = function(state, title, url) {
    try { log.nav.push({kind: 'pushState', t: Date.now(), url: String(url)}); } catch {}
    return origPush(state, title, url);
  };
  const origReplace = history.replaceState.bind(history);
  history.replaceState = function(state, title, url) {
    try { log.nav.push({kind: 'replaceState', t: Date.now(), url: String(url)}); } catch {}
    return origReplace(state, title, url);
  };

  Object.defineProperty(window, '__routeErrCap', {value: log, configurable: false});
})();
'''


async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    matched = [c for c in auth_cookies if _cookie_matches_url(c, CHATGPT_URL)]

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        await page.add_init_script(INIT_SCRIPT)

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
        for _ in range(8):
            await asyncio.sleep(2)
            body = await page.text_content("body") or ""
            samples.append(
                {
                    "t_ms": round((time.time() - start) * 1000),
                    "url": page.url,
                    "title": await page.title(),
                    "bodyHasAppError": "Application Error" in body,
                    "lastText": await page.evaluate(
                        '''(() => {
                            const turns = document.querySelectorAll('[data-testid^="conversation-turn"]');
                            const last = turns.length ? turns[turns.length - 1] : null;
                            const md = last?.querySelector('.markdown') || last?.querySelector('[data-message-content]') || last?.querySelector('.prose');
                            const fullText = (md?.innerText || last?.innerText || '').trim();
                            return fullText.slice(0, 250);
                        })()'''
                    ),
                }
            )
            if "Application Error" in body:
                break

        cap = await page.evaluate("window.__routeErrCap")

    print(
        json.dumps(
            {
                "probe": "camoufox-route-error-capture",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "matchedCookies": len(matched),
                "totalCookies": len(auth_cookies),
                "prompt": PROMPT,
                "samples": samples,
                "capture": cap,
            },
            indent=2,
        )
    )


asyncio.run(main())
