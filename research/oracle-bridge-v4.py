#!/usr/bin/env python3
"""
Oracle Stealth Bridge v4 — Hybrid Camoufox + Chrome CDP bridge.

Strategy:
1. Launch Camoufox (Firefox) to bypass Cloudflare Turnstile
2. Extract all cookies including cf_clearance
3. Launch rebrowser-playwright Chrome with those cookies on CDP port 9222
4. Oracle connects via --remote-chrome localhost:9222

This works because:
- Camoufox bypasses CF bot detection (Firefox-based stealth)
- CF clearance cookies are transferable between browsers
- Chrome exposes CDP which Oracle requires
"""

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time


async def get_cf_cookies(auth_cookie_path: str, verbose: bool = False) -> list[dict]:
    """Use camoufox to bypass CF and get authenticated cookies."""
    from camoufox.async_api import AsyncCamoufox

    print("[1/2] Bypassing Cloudflare with Camoufox...")

    with open(auth_cookie_path) as f:
        auth_cookies = json.load(f)

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()

        # Inject auth cookies
        for c in auth_cookies:
            await page.context.add_cookies([{
                "name": c.get("name", ""),
                "value": c.get("value", ""),
                "domain": c.get("domain", ".chatgpt.com"),
                "path": c.get("path", "/"),
                "secure": c.get("secure", True),
                "httpOnly": c.get("httpOnly", True),
            }])

        await page.goto("https://chatgpt.com", timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(8)

        title = await page.title()
        content = await page.content()
        has_cf = "Just a moment" in content or "Verify you are human" in content
        has_login = "Log in" in content and "Sign up" in content

        if has_cf:
            print(f"   ⚠️  CF challenge not bypassed (title: {title})")
            print("   Waiting 15s for CF to resolve...")
            await asyncio.sleep(15)
            content = await page.content()
            has_cf = "Just a moment" in content

        if has_cf:
            raise RuntimeError("Camoufox could not bypass Cloudflare Turnstile")

        if has_login:
            raise RuntimeError("Session token expired — need fresh cookie from Nico")

        print(f"   ✅ Authenticated (title: {title})")

        # Extract ALL cookies
        all_cookies = await page.context.cookies()

        cf_cookies = [c for c in all_cookies if "cf_" in c["name"].lower() or "clearance" in c["name"].lower()]
        if verbose:
            for c in cf_cookies:
                print(f"   CF cookie: {c['name']}")

        print(f"   📋 Extracted {len(all_cookies)} cookies ({len(cf_cookies)} CF-related)")
        return all_cookies


async def launch_chrome_bridge(cookies: list[dict], port: int = 9222, verbose: bool = False):
    """Launch Chrome with CF-cleared cookies and expose CDP port."""
    from rebrowser_playwright.async_api import async_playwright

    print(f"\n[2/2] Launching Chrome CDP bridge on port {port}...")

    pw = await async_playwright().__aenter__()

    browser = await pw.chromium.launch(
        headless=True,
        args=[
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
    )

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720},
    )

    # Inject all cookies
    pw_cookies = []
    for c in cookies:
        pc = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".chatgpt.com"),
            "path": c.get("path", "/"),
        }
        if c.get("secure"):
            pc["secure"] = True
        if c.get("httpOnly"):
            pc["httpOnly"] = True
        if c.get("sameSite") and c["sameSite"] != "None":
            pc["sameSite"] = c["sameSite"].capitalize()
        pw_cookies.append(pc)

    await context.add_cookies(pw_cookies)

    page = await context.new_page()
    await page.goto("https://chatgpt.com", timeout=30000)
    await page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(5)

    title = await page.title()
    content = await page.content()
    has_cf = "Just a moment" in content or "Verify you are human" in content
    has_login = "Log in" in content and "Sign up" in content

    if has_cf:
        print(f"   ⚠️  Chrome still hit CF (title: {title})")
        raise RuntimeError("CF cookies did not transfer — bridge failed")

    if has_login:
        print(f"   ⚠️  Login page (cookies may have expired)")
        raise RuntimeError("Session token expired after transfer")

    print(f"   ✅ Chrome authenticated: {title}")
    print(f"\n{'=' * 50}")
    print(f"🔗 Oracle Bridge v4 READY")
    print(f"   CDP: localhost:{port}")
    print(f"   Usage: ORACLE_REUSE_TAB=1 oracle --engine browser --remote-chrome localhost:{port} --prompt '...'")
    print(f"{'=' * 50}")

    return pw, browser, page



async def _close_bridge(browser=None, pw=None):
    if browser is not None:
        try:
            for ctx in list(browser.contexts):
                try:
                    await ctx.close()
                except Exception:
                    pass
            await browser.close()
        except Exception:
            pass
    if pw is not None:
        try:
            # Prefer explicit stop() when available to fully tear down driver tasks.
            if hasattr(pw, "stop"):
                await pw.stop()
            else:
                await pw.__aexit__(None, None, None)
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Oracle Stealth Bridge v4 (Camoufox + Chrome)")
    parser.add_argument("--port", type=int, default=9222)
    parser.add_argument("--cookies", required=True, help="Path to chatgpt-cookies.json")
    parser.add_argument("--oneshot", action="store_true", help="Run a single query then exit")
    parser.add_argument("--prompt", default="Say hello in one sentence")
    parser.add_argument("--model", default="gpt-5.2-pro")
    parser.add_argument(
        "--browser-model-strategy",
        choices=["select", "current", "ignore"],
        default="current",
        help="Oracle browser model picker strategy for oneshot mode",
    )
    parser.add_argument("--oracle-timeout", type=int, default=300, help="Oracle oneshot timeout in seconds")
    parser.add_argument(
        "--no-direct-fallback",
        action="store_true",
        help="Disable direct CDP fallback when Oracle oneshot times out/fails",
    )
    parser.add_argument(
        "--direct-timeout",
        type=int,
        default=120,
        help="Direct CDP fallback timeout in seconds",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("=" * 50)
    print("🔗 Oracle Stealth Bridge v4 (Camoufox + Chrome)")
    print("=" * 50)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    pw = None
    browser = None

    try:
        # Phase 1: Get CF cookies via Camoufox
        cookies = loop.run_until_complete(get_cf_cookies(args.cookies, args.verbose))

        # Phase 2: Launch Chrome with those cookies
        pw, browser, _page = loop.run_until_complete(
            launch_chrome_bridge(cookies, args.port, args.verbose)
        )

        if args.oneshot:
            print("\n🤖 Running Oracle...")
            cmd = (
                f"source ~/.nvm/nvm.sh && nvm use 22 > /dev/null 2>&1 && "
                f"ORACLE_REUSE_TAB=1 oracle --engine browser --remote-chrome localhost:{args.port} "
                f"--browser-model-strategy {args.browser_model_strategy} "
                f'--model "{args.model}" '
                f'--prompt "{args.prompt}" --wait --force'
            )

            oracle_ok = False
            try:
                result = subprocess.run(
                    ["bash", "-c", cmd],
                    capture_output=True,
                    text=True,
                    timeout=args.oracle_timeout,
                )
                print(f"\n{'─' * 40}")
                if result.stdout:
                    print(result.stdout)
                if result.returncode != 0 and result.stderr:
                    print(f"stderr: {result.stderr[:1000]}")
                oracle_ok = result.returncode == 0
            except subprocess.TimeoutExpired:
                print("⏰ Oracle timed out")

            if (not oracle_ok) and (not args.no_direct_fallback):
                print("\n↪ Falling back to direct CDP client...")
                direct_cmd = [
                    sys.executable,
                    os.path.expanduser("~/.openclaw/workspace/research/chatgpt-direct.py"),
                    "--port",
                    str(args.port),
                    "--timeout",
                    str(args.direct_timeout),
                    "--prompt",
                    args.prompt,
                ]
                direct_result = subprocess.run(direct_cmd, capture_output=True, text=True)
                print(f"\n{'─' * 40}")
                if direct_result.stdout:
                    print(direct_result.stdout)
                if direct_result.returncode != 0 and direct_result.stderr:
                    print(f"direct stderr: {direct_result.stderr[:1000]}")

            loop.run_until_complete(_close_bridge(browser, pw))
            browser = None
            pw = None
        else:
            stop_requested = False

            async def keepalive(page, interval=30):
                """Ping Chrome periodically to prevent idle connection death."""
                while True:
                    try:
                        await asyncio.sleep(interval)
                        title = await page.title()
                        if args.verbose:
                            print(f"   ♥ keepalive: {title}")
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        print(f"   ⚠️ Keepalive failed: {e}")
                        break

            def shutdown(_sig, _frame):
                nonlocal stop_requested
                if stop_requested:
                    return
                stop_requested = True
                print("\n🛑 Shutting down bridge...")
                loop.call_soon_threadsafe(loop.stop)

            signal.signal(signal.SIGINT, shutdown)
            signal.signal(signal.SIGTERM, shutdown)

            ka_task = asyncio.ensure_future(keepalive(_page), loop=loop)
            loop.run_forever()
            ka_task.cancel()
            loop.run_until_complete(_close_bridge(browser, pw))
            browser = None
            pw = None

    except Exception as e:
        print(f"\n❌ Bridge failed: {e}")
        try:
            loop.run_until_complete(_close_bridge(browser, pw))
        except Exception:
            pass
        sys.exit(1)
    finally:
        loop.close()


if __name__ == "__main__":
    main()
