#!/usr/bin/env python3
"""
Test querying ChatGPT directly via Camoufox (Firefox) instead of Chrome.
If Camoufox can submit prompts successfully, the issue is Chrome-specific.
"""

import asyncio
import json
import sys
import time


async def main():
    from camoufox.async_api import AsyncCamoufox

    cookie_path = sys.argv[1] if len(sys.argv) > 1 else "/home/openclaw/.oracle/chatgpt-cookies.json"
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Reply with exactly: CAMOUFOX_OK"
    timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 120

    with open(cookie_path) as f:
        auth_cookies = json.load(f)

    print("[1] Launching Camoufox...", flush=True)
    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()

        # Inject cookies
        for c in auth_cookies:
            await page.context.add_cookies([{
                "name": c.get("name", ""),
                "value": c.get("value", ""),
                "domain": c.get("domain", ".chatgpt.com"),
                "path": c.get("path", "/"),
                "secure": c.get("secure", True),
                "httpOnly": c.get("httpOnly", True),
            }])

        print("[2] Loading ChatGPT...", flush=True)
        await page.goto("https://chatgpt.com", timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(8)

        title = await page.title()
        content = await page.content()
        if "Just a moment" in content:
            print("   ⚠️ CF challenge, waiting 15s...", flush=True)
            await asyncio.sleep(15)
            content = await page.content()
            if "Just a moment" in content:
                print("   ❌ CF not bypassed", flush=True)
                return

        print(f"   ✅ Authenticated: {title}", flush=True)

        # Check for prompt box
        has_box = await page.evaluate("!!document.querySelector('[id=\"prompt-textarea\"]')")
        print(f"   Prompt box: {has_box}", flush=True)
        if not has_box:
            print("   ❌ No prompt box", flush=True)
            return

        # Type prompt
        print(f"[3] Typing: {prompt[:50]}...", flush=True)
        el = await page.query_selector('[id="prompt-textarea"]')
        await el.focus()
        await page.keyboard.type(prompt, delay=20)
        await asyncio.sleep(0.5)

        # Check textarea content
        content = await page.evaluate(
            "document.querySelector('[id=\"prompt-textarea\"]')?.innerText?.trim() || ''"
        )
        print(f"   Textarea: '{content[:80]}' ({len(content)} chars)", flush=True)

        # Click send
        print("[4] Clicking send...", flush=True)
        send_btn = await page.query_selector('[data-testid="send-button"]')
        if send_btn:
            await send_btn.click()
            print("   ✅ Clicked send button", flush=True)
        else:
            print("   Trying Enter...", flush=True)
            await page.keyboard.press("Enter")

        # Monitor for response
        print(f"[5] Waiting for response (timeout={timeout}s)...", flush=True)
        start = time.time()
        last_text = ""
        stable = 0

        while time.time() - start < timeout:
            await asyncio.sleep(2)
            data = await page.evaluate("""
                (() => {
                    const turns = document.querySelectorAll('[data-testid^="conversation-turn"]');
                    if (turns.length < 2) return JSON.stringify({s:'wait', t:'', n:turns.length});

                    const last = turns[turns.length - 1];
                    const md = last.querySelector('.markdown') || last;
                    let text = (md?.innerText || '').trim();

                    const lines = text.split('\\n').filter(l => l.trim());
                    if (lines.length > 0 && /^chatgpt said:?$/i.test(lines[0])) lines.shift();
                    text = lines.join('\\n').trim();

                    const stop = !!document.querySelector('[data-testid="stop-button"]');
                    const thinking = /^(Pro )?thinking$/i.test(text.trim());

                    return JSON.stringify({
                        s: (stop || thinking) ? 'gen' : 'done',
                        t: text,
                        n: turns.length,
                        stop,
                    });
                })()
            """)
            d = json.loads(data)
            elapsed = round(time.time() - start)

            if d["s"] == "done" and d["t"]:
                if d["t"] == last_text:
                    stable += 1
                    if stable >= 2:
                        print(f"\n✅ Response ({elapsed}s):", flush=True)
                        print(d["t"], flush=True)
                        return
                else:
                    stable = 0
                last_text = d["t"]
            elif d["s"] == "gen":
                snippet = d["t"][:60] if d["t"] else "(empty)"
                print(f"   [{elapsed}s] generating... stop={d['stop']} text='{snippet}'", flush=True)
                last_text = d["t"]
                stable = 0
            else:
                print(f"   [{elapsed}s] waiting... turns={d['n']}", flush=True)

        print(f"\n⏰ Timeout ({timeout}s). Last text: {last_text[:200]}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
