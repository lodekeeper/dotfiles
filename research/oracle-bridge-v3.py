#!/usr/bin/env python3
"""
Oracle Stealth Bridge v3 — Use Playwright CDP session for cookie injection.

Strategy: 
1. Launch Chrome with rebrowser-playwright (stealth)
2. Use Playwright's CDP session to set cookies at BROWSER level
3. Navigate to chatgpt.com in Playwright to warm the session
4. Leave the page open for Oracle to reuse
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description="Oracle Stealth Bridge v3")
    parser.add_argument("--port", type=int, default=9222)
    parser.add_argument("--cookies", required=True)
    parser.add_argument("--oneshot", action="store_true")
    parser.add_argument("--prompt", default="Say hello in one sentence")
    parser.add_argument("--model", default="gpt-5.2-pro")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    
    from rebrowser_playwright.sync_api import sync_playwright
    
    print("=" * 60)
    print("🔗 Oracle Stealth Bridge v3")
    print("=" * 60)
    
    with open(args.cookies) as f:
        cookies = json.load(f)
    print(f"📋 Loaded {len(cookies)} cookies")
    
    pw = sync_playwright().start()
    
    # Launch with CDP port AND allow origins
    browser = pw.chromium.launch(
        headless=True,
        args=[
            f"--remote-debugging-port={args.port}",
            "--remote-allow-origins=*",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
    )
    print(f"🚀 Browser launched (CDP port {args.port})")
    
    # Use browser-level CDP session to set cookies
    cdp = browser.new_browser_cdp_session()
    
    for c in cookies:
        params = {
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ".chatgpt.com"),
            "path": c.get("path", "/"),
            "secure": c.get("secure", True),
            "httpOnly": c.get("httpOnly", True),
            "url": "https://chatgpt.com",
        }
        if c.get("sameSite"):
            # CDP expects capitalized: Strict, Lax, None
            params["sameSite"] = c["sameSite"].capitalize()
        
        try:
            result = cdp.send("Storage.setCookie", {"cookie": params})
            if args.verbose:
                print(f"   Set {c['name']}: ✅")
        except Exception as e:
            if args.verbose:
                print(f"   Set {c['name']}: ❌ {e}")
            # Try alternative method
            try:
                cdp.send("Network.setCookie", params)
                if args.verbose:
                    print(f"   (fallback Network.setCookie: ✅)")
            except Exception as e2:
                if args.verbose:
                    print(f"   (fallback also failed: {e2})")
    
    print("🍪 Cookies injected via CDP")
    
    # Create a context and navigate to chatgpt.com
    # This warms the session and creates a tab Oracle can potentially reuse
    context = browser.new_context(
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720},
    )
    # Also inject cookies at context level as backup
    pw_cookies = []
    for c in cookies:
        pw_cookie = {
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ".chatgpt.com"),
            "path": c.get("path", "/"),
        }
        if c.get("secure"):
            pw_cookie["secure"] = True
        if c.get("httpOnly"):
            pw_cookie["httpOnly"] = True
        if c.get("sameSite"):
            pw_cookie["sameSite"] = c["sameSite"].capitalize()
        pw_cookies.append(pw_cookie)
    
    context.add_cookies(pw_cookies)
    
    page = context.new_page()
    print("🌐 Navigating to chatgpt.com...")
    page.goto("https://chatgpt.com", timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(5000)
    
    title = page.title()
    content = page.content()
    has_login = "Log in" in content and "Sign up" in content
    has_cf = "Just a moment" in content or "Verify you are human" in content
    
    if has_cf:
        print(f"   ⚠️  CF challenge (title: {title})")
    elif has_login:
        print(f"   ⚠️  Login page (cookies may not have worked)")
    else:
        print(f"   ✅ Logged in: {title}")
    
    # Check what Oracle will see — use CDP to query cookies
    try:
        cookie_result = cdp.send("Storage.getCookies", {"browserContextId": ""})
        session_cookies = [c for c in cookie_result.get("cookies", []) 
                         if "session-token" in c.get("name", "")]
        if session_cookies:
            print(f"   🍪 Session token visible at browser level: ✅")
        else:
            print(f"   🍪 Session token NOT at browser level")
            # List what cookies ARE there
            all_chatgpt = [c["name"] for c in cookie_result.get("cookies", []) 
                          if "chatgpt" in c.get("domain", "")]
            if args.verbose and all_chatgpt:
                print(f"   Browser-level chatgpt cookies: {all_chatgpt}")
    except Exception as e:
        if args.verbose:
            print(f"   Cookie query failed: {e}")
    
    if args.oneshot:
        print(f"\n🤖 Running Oracle...")
        cmd = (
            f"source ~/.nvm/nvm.sh && nvm use 22 > /dev/null 2>&1 && "
            f"ORACLE_REUSE_TAB=1 oracle --engine browser --remote-chrome localhost:{args.port} "
            f'--model "{args.model}" '
            f'--prompt "{args.prompt}" --wait'
        )
        try:
            result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=120)
            print(f"\n{'─' * 40}")
            if result.stdout:
                print(result.stdout)
            if result.returncode != 0 and result.stderr:
                print(f"stderr: {result.stderr[:500]}")
        except subprocess.TimeoutExpired:
            print("⏰ Oracle timed out")
        
        browser.close()
        pw.stop()
    else:
        print(f"\n✅ Bridge running:")
        print(f"   oracle --engine browser --remote-chrome localhost:{args.port} --prompt '...'")
        
        def shutdown(sig, frame):
            browser.close()
            pw.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)
        while True:
            time.sleep(1)


if __name__ == "__main__":
    main()
