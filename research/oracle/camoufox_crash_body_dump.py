import asyncio
import importlib.util
import json
import os
from camoufox.async_api import AsyncCamoufox

CHATGPT_DIRECT_PATH = "/home/openclaw/.openclaw/workspace/research/chatgpt-direct.py"
spec = importlib.util.spec_from_file_location("chatgpt_direct", CHATGPT_DIRECT_PATH)
chatgpt_direct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chatgpt_direct)
_cookie_matches_url = chatgpt_direct._cookie_matches_url

COOKIES = os.path.expanduser("~/.oracle/chatgpt-cookies.json")
CHATGPT_URL = "https://chatgpt.com"
PROMPT = "Reply with exactly CRASHDUMP_OK."
OUT = "/home/openclaw/.openclaw/workspace/research/oracle/camoufox-crash-body.txt"

async def main():
    with open(COOKIES) as f:
        auth_cookies = json.load(f)
    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        for c in auth_cookies:
            await page.context.add_cookies([{
                "name": c.get("name", ""),
                "value": c.get("value", ""),
                "domain": c.get("domain", ".chatgpt.com"),
                "path": c.get("path", "/"),
                "secure": c.get("secure", True),
                "httpOnly": c.get("httpOnly", True),
            }])
        await page.goto(CHATGPT_URL, timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(8)
        composer = page.locator('[id="prompt-textarea"]').first
        await composer.click()
        await page.keyboard.type(PROMPT, delay=10)
        await asyncio.sleep(0.3)
        await page.keyboard.press("Enter")
        await asyncio.sleep(12)
        body = await page.text_content("body") or ""
        with open(OUT, "w") as f:
            f.write(body)
        print(json.dumps({"url": page.url, "title": await page.title(), "bodyChars": len(body), "out": OUT}, indent=2))

asyncio.run(main())
