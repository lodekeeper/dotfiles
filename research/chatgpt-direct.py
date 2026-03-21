#!/usr/bin/env python3
"""
chatgpt-direct — Query ChatGPT via headless Camoufox browser.

Self-contained CLI that sends prompts to ChatGPT through Camoufox (Firefox
stealth browser that bypasses Cloudflare). No Chrome CDP bridge needed.

Usage:
  chatgpt-direct --prompt "Your question"
  chatgpt-direct --prompt "Review this:" --file doc.md
  echo "Question" | chatgpt-direct
  chatgpt-direct --prompt "Summarize" --timeout 300 --output response.md

Requires:
  - ~/camoufox-env with camoufox + playwright
  - ~/.oracle/chatgpt-cookies.json (auth cookies)
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time

DEFAULT_COOKIES = os.path.expanduser("~/.oracle/chatgpt-cookies.json")


async def get_expired_session_message(page):
    """Return expired-session modal text if ChatGPT auth has expired."""
    data = await page.evaluate("""
        (() => {
            const modal = document.querySelector('#modal-expired-session');
            if (!modal) return JSON.stringify({open: false, text: ''});
            return JSON.stringify({
                open: true,
                text: (modal.innerText || '').trim(),
            });
        })()
    """)
    parsed = json.loads(data)
    if parsed.get("open"):
        return parsed.get("text") or "Your session has expired"
    return None


async def dismiss_welcome_modal(page, verbose=False):
    """Dismiss the non-auth welcome gate if present.

    ChatGPT sometimes shows a "Welcome back" modal with a "Stay logged out"
    dismiss link even when the composer is already rendered. This is not the same
    as an expired session and should not be treated as an auth failure.
    """
    data = await page.evaluate("""
        (() => {
            const modal = document.querySelector('#modal-no-auth-login');
            const dismiss = document.querySelector('[data-testid="dismiss-welcome"]');
            return JSON.stringify({
                open: !!modal,
                text: modal ? (modal.innerText || '').trim() : '',
                canDismiss: !!dismiss,
            });
        })()
    """)
    parsed = json.loads(data)
    if not parsed.get("open"):
        return False

    if verbose:
        first_line = (parsed.get("text") or "welcome modal").splitlines()[0]
        print(f"Welcome modal detected: {first_line}", file=sys.stderr, flush=True)

    if parsed.get("canDismiss"):
        dismiss = await page.query_selector('[data-testid="dismiss-welcome"]')
        if dismiss:
            await dismiss.click()
            await asyncio.sleep(2)
            if verbose:
                print("Dismissed welcome modal via 'Stay logged out'", file=sys.stderr, flush=True)
            return True

    return False


async def get_auth_state(page):
    """Inspect whether ChatGPT is in guest/free or authenticated mode."""
    data = await page.evaluate("""
        (() => {
            const loginBtn = !!document.querySelector('[data-testid="login-button"]');
            const signupBtn = !!document.querySelector('[data-testid="signup-button"]');
            const modelBtn = document.querySelector('[data-testid="model-switcher-dropdown-button"]');
            const profileBtn = document.querySelector('[data-testid="profile-button"]');
            return JSON.stringify({
                hasLogin: loginBtn,
                hasSignup: signupBtn,
                model: modelBtn ? (modelBtn.innerText || '').trim() : '',
                profileAria: profileBtn ? (profileBtn.getAttribute('aria-label') || '') : '',
            });
        })()
    """)
    parsed = json.loads(data)
    parsed["state"] = (
        "guest" if (parsed.get("hasLogin") or parsed.get("hasSignup")) else "authenticated"
    )
    return parsed


async def ensure_pro_model(page, verbose=False):
    """Check current model and switch to Pro if available.

    Returns dict with model info: {model, isPro, quotaExhausted}.
    """
    info = await page.evaluate("""
        (() => {
            const btn = document.querySelector('[data-testid="model-switcher-dropdown-button"]');
            if (!btn) return JSON.stringify({model: 'unknown', ariaLabel: ''});
            return JSON.stringify({
                model: btn.innerText.trim(),
                ariaLabel: btn.getAttribute('aria-label') || '',
            });
        })()
    """)
    data = json.loads(info)
    model = data.get("model", "unknown")
    aria = data.get("ariaLabel", "")
    is_pro = "pro" in model.lower() or "pro" in aria.lower()

    if is_pro:
        if verbose:
            print(f"Model: {model} ✅", file=sys.stderr, flush=True)
        return {"model": model, "isPro": True, "quotaExhausted": False}

    # Not on Pro — try to switch
    if verbose:
        print(f"Model: {model} — attempting to switch to Pro...", file=sys.stderr, flush=True)

    # Click the model selector dropdown
    btn = await page.query_selector('[data-testid="model-switcher-dropdown-button"]')
    if btn:
        await btn.click()
        await asyncio.sleep(1)

        # Look for Pro option in the dropdown
        pro_option = await page.evaluate("""
            (() => {
                const items = document.querySelectorAll('[role="menuitem"], [role="option"], [data-testid*="model"]');
                for (const item of items) {
                    const text = (item.innerText || '').toLowerCase();
                    if (text.includes('pro') || text.includes('5.4')) {
                        // Check if it's disabled/exhausted
                        const disabled = item.getAttribute('aria-disabled') === 'true'
                                      || item.classList.contains('disabled')
                                      || item.querySelector('[class*="disabled"]');
                        const exhausted = text.includes('limit') || text.includes('exhaust')
                                       || text.includes('unavailable');
                        return JSON.stringify({
                            found: true,
                            text: item.innerText.trim().slice(0, 80),
                            disabled: !!disabled,
                            exhausted: !!exhausted,
                        });
                    }
                }
                // Also check buttons
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    const text = (b.innerText || '').toLowerCase();
                    if ((text.includes('pro') || text.includes('5.4'))
                        && !text.includes('project')) {
                        return JSON.stringify({
                            found: true,
                            text: b.innerText.trim().slice(0, 80),
                            disabled: b.disabled,
                            exhausted: text.includes('limit') || text.includes('exhaust'),
                        });
                    }
                }
                return JSON.stringify({found: false});
            })()
        """)
        pro_data = json.loads(pro_option)

        if pro_data.get("found"):
            if pro_data.get("exhausted") or pro_data.get("disabled"):
                if verbose:
                    print(
                        f"ℹ️  Pro option appears disabled in dropdown — trying anyway (UI may be stale)...",
                        file=sys.stderr, flush=True,
                    )
                # Don't give up — try clicking even if it appears disabled.
                # ChatGPT UI sometimes marks Pro as disabled in the dropdown
                # while it's actually the active model.

            # Click the Pro option
            clicked = await page.evaluate("""
                (() => {
                    const items = [...document.querySelectorAll(
                        '[role="menuitem"], [role="option"], [data-testid*="model"], button'
                    )];
                    for (const item of items) {
                        const text = (item.innerText || '').toLowerCase();
                        if ((text.includes('pro') || text.includes('5.4'))
                            && !text.includes('project') && !item.disabled) {
                            item.click();
                            return 'clicked';
                        }
                    }
                    return 'not_found';
                })()
            """)

            if clicked == "clicked":
                await asyncio.sleep(1)
                # Verify model switched
                new_info = await page.evaluate("""
                    (() => {
                        const btn = document.querySelector(
                            '[data-testid="model-switcher-dropdown-button"]'
                        );
                        if (!btn) return JSON.stringify({model: 'unknown', aria: ''});
                        return JSON.stringify({
                            model: btn.innerText.trim(),
                            aria: btn.getAttribute('aria-label') || '',
                        });
                    })()
                """)
                new_data = json.loads(new_info)
                new_model = new_data.get("model", "unknown")
                new_aria = new_data.get("aria", "")
                new_info = new_model
                is_now_pro = "pro" in new_model.lower() or "pro" in new_aria.lower()
                if verbose:
                    status = "✅" if is_now_pro else "ℹ️  (button still shows generic name — Pro may still be active)"
                    print(f"Model after switch: {new_info} {status}", file=sys.stderr, flush=True)
                return {
                    "model": new_info,
                    "isPro": is_now_pro,
                    "quotaExhausted": False,
                }

        # Close dropdown
        await page.keyboard.press("Escape")

    # Final check: re-read the model button — ChatGPT UI may not show "Pro"
    # explicitly in button text but the session might still be Pro
    final_info = await page.evaluate("""
        (() => {
            const btn = document.querySelector(
                '[data-testid="model-switcher-dropdown-button"]'
            );
            if (!btn) return JSON.stringify({model: 'unknown', aria: ''});
            return JSON.stringify({
                model: btn.innerText.trim(),
                aria: btn.getAttribute('aria-label') || '',
            });
        })()
    """)
    final_data = json.loads(final_info)
    final_model = final_data.get("model", model)
    final_aria = final_data.get("aria", "")
    is_final_pro = "pro" in final_model.lower() or "pro" in final_aria.lower()

    return {"model": final_model, "isPro": is_final_pro, "quotaExhausted": False}


async def query_chatgpt(
    prompt,
    cookies_path,
    timeout=3600,
    verbose=False,
    require_auth=False,
    require_pro=False,
):
    """Send prompt to ChatGPT via Camoufox and return response."""
    from camoufox.async_api import AsyncCamoufox

    with open(cookies_path) as f:
        auth_cookies = json.load(f)

    if verbose:
        print("Launching Camoufox...", file=sys.stderr, flush=True)

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

        if verbose:
            print("Loading ChatGPT...", file=sys.stderr, flush=True)

        await page.goto("https://chatgpt.com", timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(8)

        title = await page.title()
        content = await page.content()

        # Handle CF challenge
        if "Just a moment" in content or "Verify you are human" in content:
            if verbose:
                print("CF challenge detected, waiting...", file=sys.stderr, flush=True)
            await asyncio.sleep(15)
            content = await page.content()
            if "Just a moment" in content:
                return {"status": "error", "error": "Cloudflare challenge not bypassed"}

        expired_session_text = await get_expired_session_message(page)
        if expired_session_text:
            return {
                "status": "error",
                "error": (
                    "Session expired — need fresh cookies "
                    f"({expired_session_text.splitlines()[0]})"
                ),
            }

        # Dismiss non-auth "Welcome back" modal if present.
        # This overlay contains "Log in" / "Sign up" text but is NOT an auth
        # failure — it's a dismissible gate that appears even with a valid
        # session token.  Dismiss it before checking login state.
        await dismiss_welcome_modal(page, verbose=verbose)

        # Re-read content after potential modal dismissal
        content = await page.content()

        # Check login — only treat as expired if there's no prompt textarea
        # AND "Log in" / "Sign up" are present.  The welcome modal contains
        # those strings too, so we must check after dismissal.
        has_box = await page.evaluate(
            '!!document.querySelector(\'[id="prompt-textarea"]\')'
        )
        if not has_box:
            if "Log in" in content and "Sign up" in content:
                return {"status": "error", "error": "Session expired — need fresh cookies"}
            return {"status": "error", "error": f"No prompt box found (title: {title})"}

        auth_info = await get_auth_state(page)
        if verbose:
            print(
                f"Auth state: {auth_info['state']}"
                f" (login={auth_info['hasLogin']}, signup={auth_info['hasSignup']})",
                file=sys.stderr,
                flush=True,
            )
            print(f"ChatGPT loaded: {title}", file=sys.stderr, flush=True)

        if require_auth and auth_info["state"] != "authenticated":
            return {
                "status": "error",
                "error": "Guest/free ChatGPT session detected — need fresh authenticated cookies",
                "auth": auth_info,
            }

        # Ensure Pro model is selected
        model_info = await ensure_pro_model(page, verbose=verbose)

        if require_pro and not model_info.get("isPro"):
            error = "GPT-5.4 Pro not available in current session"
            if auth_info["state"] != "authenticated":
                error += " — current cookies only open guest/free ChatGPT"
            return {
                "status": "error",
                "error": error,
                "auth": auth_info,
                "model": model_info,
            }

        # Type prompt using keyboard (reliable with React)
        el = await page.query_selector('[id="prompt-textarea"]')
        await el.focus()

        # For long prompts, use fill + input event (keyboard.type is slow for >1KB)
        if len(prompt) > 500:
            await page.evaluate("""
                (text) => {
                    const el = document.querySelector('[id="prompt-textarea"]');
                    if (!el) return;
                    el.focus();
                    el.innerHTML = '';
                    document.execCommand('insertText', false, text);
                }
            """, prompt)
            await asyncio.sleep(0.5)
        else:
            await page.keyboard.type(prompt, delay=10)
            await asyncio.sleep(0.3)

        # Verify text was inserted
        inserted = await page.evaluate("""
            document.querySelector('[id="prompt-textarea"]')?.innerText?.trim()?.length || 0
        """)
        if not inserted:
            return {"status": "error", "error": "Failed to insert prompt text"}

        if verbose:
            print(f"Inserted {inserted} chars, sending...", file=sys.stderr, flush=True)

        # Click send
        send_btn = await page.query_selector('[data-testid="send-button"]')
        if send_btn:
            disabled = await send_btn.get_attribute("disabled")
            if not disabled:
                await send_btn.click()
            else:
                await page.keyboard.press("Enter")
        else:
            await page.keyboard.press("Enter")

        # Wait for response
        if verbose:
            print(f"Waiting for response (timeout={timeout}s)...", file=sys.stderr, flush=True)

        start = time.time()
        last_text = ""
        stable_count = 0
        last_status_print = 0
        saw_thinking = False  # Track if Pro thinking was observed

        while time.time() - start < timeout:
            await asyncio.sleep(2)

            data = await page.evaluate("""
                (() => {
                    const turns = document.querySelectorAll(
                        '[data-testid^="conversation-turn"]'
                    );
                    if (turns.length < 2)
                        return JSON.stringify({s:'wait', t:'', n:turns.length});

                    const last = turns[turns.length - 1];

                    // Key insight: .markdown contains the ACTUAL response.
                    // During extended thinking, .markdown exists but is EMPTY.
                    // The thinking summary text is in a sibling element.
                    const md = last.querySelector('.markdown')
                            || last.querySelector('[data-message-content]')
                            || last.querySelector('.prose');
                    const mdText = md ? (md.innerText || '').trim() : '';

                    // Strip thinking accordion if present (details/summary)
                    const details = last.querySelector('details');
                    let responseText = mdText;
                    if (details) {
                        responseText = mdText.replace(
                            (details.innerText || ''), ''
                        ).trim();
                    }

                    const stopBtn = !!document.querySelector(
                        '[data-testid="stop-button"]'
                    );

                    // Full turn text for error detection
                    const fullText = (last?.innerText || '').trim();

                    // Status logic:
                    // - stop button + empty markdown = still thinking
                    // - stop button + non-empty markdown = streaming response
                    // - no stop button + non-empty markdown = done
                    // - error keywords = error
                    let status;
                    if (/something went wrong|network error|error generating/i
                        .test(fullText)) {
                        status = 'error';
                    } else if (stopBtn && !responseText) {
                        status = 'thinking';
                    } else if (stopBtn) {
                        status = 'generating';
                    } else {
                        status = 'done';
                    }

                    return JSON.stringify({
                        s: status,
                        t: responseText,
                        n: turns.length,
                        stop: stopBtn,
                        mdLen: responseText.length,
                    });
                })()
            """)

            d = json.loads(data)
            elapsed = round(time.time() - start)
            status = d["s"]
            text = d["t"]

            if verbose and elapsed - last_status_print >= 10:
                snippet = (text or "(empty)")[:60]
                print(
                    f"   [{elapsed}s] {status} md={d.get('mdLen', 0)} "
                    f"text='{snippet}'",
                    file=sys.stderr, flush=True,
                )
                last_status_print = elapsed

            if status == "thinking":
                saw_thinking = True

            if status == "error":
                return {
                    "status": "error",
                    "text": text,
                    "model": model_info,
                    "auth": auth_info,
                }

            if status == "done" and text:
                if text == last_text:
                    stable_count += 1
                    if stable_count >= 2:
                        result = {
                            "status": "ok",
                            "text": _clean_response(text),
                            "elapsed": elapsed,
                            "model": model_info,
                            "auth": auth_info,
                            "usedPro": saw_thinking or model_info.get("isPro", False),
                        }
                        # Warn only for complex prompts that should have triggered thinking
                        if (not saw_thinking
                                and model_info.get("isPro")
                                and len(prompt) > 200
                                and elapsed < 15):
                            result["warning"] = (
                                "Pro selected but no thinking observed on complex prompt "
                                "— quota may be exhausted, response may be from standard model"
                            )
                        return result
                else:
                    stable_count = 0
                last_text = text
            elif status in ("thinking", "generating"):
                last_text = text
                stable_count = 0

        # Timeout — return whatever we have
        return {
            "status": "timeout",
            "text": _clean_response(last_text) if last_text else "",
            "elapsed": round(time.time() - start),
            "model": model_info,
            "auth": auth_info,
            "usedPro": saw_thinking,
        }


def _clean_response(text):
    """Normalize thinking prefix in response text."""
    text = text.strip()
    # "Thought for 11 seconds\n\nActual response"
    m = re.match(
        r"^((?:Pro )?[Tt]hought for \d+ seconds?)\s*\n\s*\n(.+)",
        text,
        re.DOTALL,
    )
    if m:
        return f"{m.group(1)}\n\n{m.group(2).strip()}"
    return text


def main():
    parser = argparse.ArgumentParser(
        description="Query ChatGPT via headless Camoufox browser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --prompt "Explain RRF ranking"
  %(prog)s --prompt "Review this:" --file research.md
  %(prog)s --timeout 300 --json < question.txt
  echo "Hello" | %(prog)s --output answer.md
        """,
    )
    parser.add_argument("--prompt", "-p", help="Prompt text")
    parser.add_argument("--file", "-f", help="Append file contents to prompt")
    parser.add_argument(
        "--timeout", "-t", type=int, default=3600,
        help="Response timeout in seconds (default: 3600 — GPT-5.4 Pro can think for up to an hour)",
    )
    parser.add_argument("--output", "-o", help="Write response to file")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--cookies", default=DEFAULT_COOKIES)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument(
        "--require-auth",
        action="store_true",
        help="Fail unless the session is authenticated (not guest/free mode)",
    )
    parser.add_argument(
        "--require-pro",
        action="store_true",
        help="Fail unless GPT-5.4 Pro is actually available in the current session",
    )
    args = parser.parse_args()

    # Build prompt
    prompt = args.prompt or ""
    if not prompt and not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()

    if args.file:
        with open(args.file) as fh:
            content = fh.read()
        prompt = f"{prompt}\n\n{content}" if prompt else content

    if not prompt:
        parser.print_help(sys.stderr)
        sys.exit(1)

    try:
        result = asyncio.run(
            query_chatgpt(
                prompt,
                cookies_path=args.cookies,
                timeout=args.timeout,
                verbose=args.verbose,
                require_auth=args.require_auth,
                require_pro=args.require_pro,
            )
        )

        if args.json:
            output = json.dumps(result, indent=2)
        else:
            output = result.get("text", result.get("error", ""))

        print(output)

        if args.output and result.get("text"):
            with open(args.output, "w") as fh:
                fh.write(result["text"])
            print(f"\n[Written to {args.output}]", file=sys.stderr)

        sys.exit(0 if result["status"] == "ok" else 1)

    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        if args.json:
            print(json.dumps({"status": "error", "error": str(e)}))
        else:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
