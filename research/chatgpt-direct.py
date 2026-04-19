#!/usr/bin/env python3
"""
chatgpt-direct — Query ChatGPT via headless Camoufox browser.

Self-contained CLI that sends prompts to ChatGPT through Camoufox (Firefox
stealth browser that bypasses Cloudflare). No Chrome CDP bridge needed.

Usage:
  chatgpt-direct --prompt "Your question"
  chatgpt-direct --prompt "Review this:" --file doc.md
  chatgpt-direct --auth-only --require-auth --require-pro --json
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
from urllib.parse import urlparse

DEFAULT_COOKIES = os.path.expanduser("~/.oracle/chatgpt-cookies.json")
DEFAULT_CHATGPT_URL = "https://chatgpt.com"


def _clean_response(text):
    """Normalize thinking prefix in response text."""
    text = (text or "").strip()
    m = re.match(
        r"^((?:Pro )?[Tt]hought for \d+ seconds?)\s*\n\s*\n(.+)",
        text,
        re.DOTALL,
    )
    if m:
        return f"{m.group(1)}\n\n{m.group(2).strip()}"
    return text


def _domain_matches(hostname, domain):
    if not hostname or not domain:
        return False
    hostname = hostname.lower()
    domain = domain.lower().lstrip(".")
    return hostname == domain or hostname.endswith(f".{domain}")


def _cookie_matches_url(cookie, url):
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path or "/"
    cookie_domain = cookie.get("domain") or ""
    cookie_path = cookie.get("path") or "/"
    if not _domain_matches(hostname, cookie_domain):
        return False
    normalized_cookie_path = cookie_path.rstrip("/") or "/"
    return path.startswith(normalized_cookie_path)


def _find_first_nested(obj, keys, max_depth=5):
    if max_depth < 0:
        return None

    if isinstance(obj, dict):
        for key in keys:
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in obj.values():
            found = _find_first_nested(value, keys, max_depth=max_depth - 1)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_first_nested(value, keys, max_depth=max_depth - 1)
            if found is not None:
                return found
    return None


def _derive_server_auth(raw):
    if not isinstance(raw, dict):
        raw = {}

    session = raw.get("data")
    session_dict = session if isinstance(session, dict) else {}

    user = session_dict.get("user")
    account = session_dict.get("account") or session_dict.get("currentAccount")
    accounts = session_dict.get("accounts")
    if not account and isinstance(accounts, list) and accounts:
        account = accounts[0]
    elif not account and isinstance(accounts, dict):
        account = accounts

    plan_type = _find_first_nested(
        session_dict,
        keys=("planType", "plan_type", "plan", "subscriptionPlan", "accountPlan"),
    )
    structure = _find_first_nested(
        session_dict,
        keys=("structure", "accountStructure", "workspaceType", "workspace_type"),
    )
    error = _find_first_nested(
        session_dict,
        keys=("error", "refreshError", "authError", "message"),
    )

    has_user = isinstance(user, dict) and bool(user)
    has_account = any(
        [
            isinstance(account, dict) and bool(account),
            isinstance(account, str) and bool(account.strip()),
            bool(plan_type),
            bool(structure),
        ]
    )

    status = raw.get("status")
    ok = bool(raw.get("ok"))

    if error and (has_user or has_account):
        state = "stale"
    elif has_user or has_account:
        state = "authenticated"
    elif ok and status == 200:
        state = "guest"
    else:
        state = "unknown"

    return {
        "state": state,
        "status": status,
        "ok": ok,
        "hasUser": has_user,
        "hasAccount": has_account,
        "planType": plan_type,
        "structure": structure,
        "error": error,
    }


def _auth_error_message(auth, require_auth=False, require_pro=False, model_info=None):
    auth = auth or {}
    server = auth.get("server") or {}
    state = server.get("state") or auth.get("state") or "unknown"
    plan_type = server.get("planType")
    server_error = server.get("error")

    if require_auth and state == "guest":
        return "Guest/free ChatGPT session detected — need fresh authenticated cookies"

    if require_auth and state == "stale":
        suffix = f" ({server_error})" if server_error else ""
        return (
            "Authenticated ChatGPT session metadata exists, but it is stale/broken "
            f"for UI use{suffix} — need fresh authenticated cookies"
        )

    if require_auth and state != "authenticated":
        return f"Unable to verify authenticated ChatGPT session (state={state})"

    if require_pro:
        model_is_pro = bool((model_info or {}).get("isPro"))
        plan_is_pro = isinstance(plan_type, str) and plan_type.lower() == "pro"
        if not model_is_pro and not plan_is_pro:
            detail = f"plan={plan_type}" if plan_type else "plan unknown"
            return f"Authenticated ChatGPT session is not Pro-capable ({detail})"

    return None


async def fetch_server_auth(page, chatgpt_url):
    raw = await page.evaluate(
        """
        async () => {
            try {
                const res = await fetch('/api/auth/session', {
                    credentials: 'include',
                    cache: 'no-store',
                    headers: {accept: 'application/json'}
                });
                const text = await res.text();
                let data = null;
                try {
                    data = text ? JSON.parse(text) : null;
                } catch (e) {
                    data = null;
                }
                return JSON.stringify({ok: res.ok, status: res.status, data});
            } catch (e) {
                return JSON.stringify({ok: false, status: null, error: String(e)});
            }
        }
        """
    )
    parsed = json.loads(raw)
    server = _derive_server_auth(parsed)
    server["cookieDomain"] = urlparse(chatgpt_url).hostname or "chatgpt.com"
    return server


async def collect_auth_state(page, chatgpt_url):
    ui_json = await page.evaluate(
        """
        () => JSON.stringify({
            hasLogin: [...document.querySelectorAll('a,button')].some((el) => /log in/i.test((el.innerText || '').trim())),
            hasSignup: [...document.querySelectorAll('a,button')].some((el) => /sign up/i.test((el.innerText || '').trim())),
            model: (document.querySelector('[data-testid="model-switcher-dropdown-button"]')?.innerText || '').trim(),
            profileAria: (document.querySelector('[aria-label*="Profile" i], [aria-label*="Account" i]')?.getAttribute('aria-label') || ''),
            welcomeModal: !!document.querySelector('[data-testid="welcome-modal"], [role="dialog"]'),
            hasPromptBox: !!document.querySelector('[id="prompt-textarea"]'),
        })
        """
    )
    auth = json.loads(ui_json)
    auth["server"] = await fetch_server_auth(page, chatgpt_url)

    server_state = auth["server"].get("state")
    if server_state == "stale":
        auth["state"] = "stale"
    elif auth.get("hasPromptBox") or server_state == "authenticated":
        auth["state"] = "authenticated"
    elif auth.get("hasLogin") and auth.get("hasSignup"):
        auth["state"] = "guest"
    else:
        auth["state"] = server_state or "unknown"

    return auth


async def ensure_pro_model(page, verbose=False):
    """Check current model and switch to Pro if available.

    Returns dict with model info: {model, isPro, quotaExhausted, evidence}.
    """
    info = await page.evaluate(
        """
        (() => {
            const btn = document.querySelector('[data-testid="model-switcher-dropdown-button"]');
            const composerPills = [...document.querySelectorAll('button, span, div')]
                .map((el) => (el.innerText || '').trim())
                .filter((text) => /^extended pro$/i.test(text) || /^pro$/i.test(text))
                .slice(0, 5);
            if (!btn) {
                return JSON.stringify({model: 'unknown', ariaLabel: '', composerPills});
            }
            return JSON.stringify({
                model: btn.innerText.trim(),
                ariaLabel: btn.getAttribute('aria-label') || '',
                composerPills,
            });
        })()
        """
    )
    data = json.loads(info)
    model = data.get("model", "unknown")
    aria = data.get("ariaLabel", "")
    composer_pills = data.get("composerPills") or []
    is_pro = (
        "pro" in model.lower()
        or "pro" in aria.lower()
        or any("pro" in pill.lower() for pill in composer_pills)
    )

    if is_pro:
        if verbose:
            print(f"Model: {model} ✅", file=sys.stderr, flush=True)
        return {
            "model": model,
            "isPro": True,
            "quotaExhausted": False,
            "evidence": {"composerPills": composer_pills},
        }

    if verbose:
        print(f"Model: {model} — attempting to switch to Pro...", file=sys.stderr, flush=True)

    btn = await page.query_selector('[data-testid="model-switcher-dropdown-button"]')
    if btn:
        try:
            await btn.click()
        except Exception:
            return {
                "model": model,
                "isPro": False,
                "quotaExhausted": False,
                "evidence": {"composerPills": composer_pills},
            }
        await asyncio.sleep(1)

        pro_option = await page.evaluate(
            """
            (() => {
                const items = document.querySelectorAll('[role="menuitem"], [role="option"], [data-testid*="model"]');
                for (const item of items) {
                    const text = (item.innerText || '').toLowerCase();
                    if (text.includes('pro') || text.includes('5.4')) {
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
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    const text = (b.innerText || '').toLowerCase();
                    if ((text.includes('pro') || text.includes('5.4')) && !text.includes('project')) {
                        return JSON.stringify({
                            found: true,
                            text: b.innerText.trim().slice(0, 80),
                            disabled: !!b.disabled,
                            exhausted: text.includes('limit') || text.includes('exhaust'),
                        });
                    }
                }
                return JSON.stringify({found: false});
            })()
            """
        )
        pro_data = json.loads(pro_option)

        if pro_data.get("found"):
            if pro_data.get("exhausted") or pro_data.get("disabled"):
                if verbose:
                    print(
                        "⚠️  Pro quota exhausted — falling back to standard model",
                        file=sys.stderr,
                        flush=True,
                    )
                await page.keyboard.press("Escape")
                return {
                    "model": model,
                    "isPro": False,
                    "quotaExhausted": True,
                    "evidence": {"composerPills": composer_pills},
                }

            clicked = await page.evaluate(
                """
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
                """
            )

            if clicked == "clicked":
                await asyncio.sleep(1)
                new_info = await page.evaluate(
                    """
                    (() => {
                        const btn = document.querySelector('[data-testid="model-switcher-dropdown-button"]');
                        const composerPills = [...document.querySelectorAll('button, span, div')]
                            .map((el) => (el.innerText || '').trim())
                            .filter((text) => /^extended pro$/i.test(text) || /^pro$/i.test(text))
                            .slice(0, 5);
                        return JSON.stringify({
                            model: btn ? btn.innerText.trim() : 'unknown',
                            composerPills,
                        });
                    })()
                    """
                )
                new_data = json.loads(new_info)
                new_model = new_data.get("model", "unknown")
                new_pills = new_data.get("composerPills") or []
                is_now_pro = "pro" in new_model.lower() or any(
                    "pro" in pill.lower() for pill in new_pills
                )
                if verbose:
                    status = "✅" if is_now_pro else "⚠️ failed"
                    print(f"Model after switch: {new_model} {status}", file=sys.stderr, flush=True)
                return {
                    "model": new_model,
                    "isPro": is_now_pro,
                    "quotaExhausted": False,
                    "evidence": {"composerPills": new_pills},
                }

        await page.keyboard.press("Escape")

    return {
        "model": model,
        "isPro": False,
        "quotaExhausted": False,
        "evidence": {"composerPills": composer_pills},
    }


async def query_chatgpt(
    prompt,
    cookies_path,
    timeout=3600,
    verbose=False,
    auth_only=False,
    require_auth=False,
    require_pro=False,
    chatgpt_url=DEFAULT_CHATGPT_URL,
):
    """Send prompt to ChatGPT via Camoufox and return response."""
    from camoufox.async_api import AsyncCamoufox

    with open(cookies_path) as f:
        auth_cookies = json.load(f)

    if not isinstance(auth_cookies, list):
        raise ValueError("Cookie jar must be a JSON array of cookie objects")

    matched_cookies = [c for c in auth_cookies if _cookie_matches_url(c, chatgpt_url)]

    if verbose:
        print("Launching Camoufox...", file=sys.stderr, flush=True)
        print(
            f"Cookie candidates for {chatgpt_url}: {len(matched_cookies)}/{len(auth_cookies)}",
            file=sys.stderr,
            flush=True,
        )

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

        if verbose:
            print(f"Loading ChatGPT: {chatgpt_url}", file=sys.stderr, flush=True)

        await page.goto(chatgpt_url, timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(8)

        title = await page.title()
        content = await page.content()

        if "Just a moment" in content or "Verify you are human" in content:
            if verbose:
                print("CF challenge detected, waiting...", file=sys.stderr, flush=True)
            await asyncio.sleep(15)
            content = await page.content()
            if "Just a moment" in content:
                return {"status": "error", "error": "Cloudflare challenge not bypassed"}

        auth = await collect_auth_state(page, chatgpt_url)

        if verbose:
            print(
                "Auth state: "
                f"ui={auth.get('state')} server={auth.get('server', {}).get('state')} "
                f"plan={auth.get('server', {}).get('planType')}",
                file=sys.stderr,
                flush=True,
            )

        if auth_only:
            early_auth_error = _auth_error_message(
                auth,
                require_auth=require_auth,
                require_pro=False,
                model_info=None,
            )
            if early_auth_error:
                return {
                    "status": "error",
                    "error": early_auth_error,
                    "auth": auth,
                }

            model_info = await ensure_pro_model(page, verbose=verbose)
            error_message = _auth_error_message(
                auth,
                require_auth=require_auth,
                require_pro=require_pro,
                model_info=model_info,
            )
            if error_message:
                return {
                    "status": "error",
                    "error": error_message,
                    "auth": auth,
                    "model": model_info,
                }
            return {
                "status": "ok",
                "text": "ORACLE_BRIDGE_OK: Browser-mode authentication is functioning correctly.",
                "elapsed": 0,
                "model": model_info,
                "auth": auth,
                "usedPro": model_info.get("isPro", False),
            }

        if "Log in" in content and "Sign up" in content:
            error_message = _auth_error_message(auth, require_auth=True)
            return {
                "status": "error",
                "error": error_message or "Session expired — need fresh cookies",
                "auth": auth,
            }

        early_auth_error = _auth_error_message(
            auth,
            require_auth=require_auth,
            require_pro=False,
            model_info=None,
        )
        if early_auth_error:
            return {
                "status": "error",
                "error": early_auth_error,
                "auth": auth,
            }

        has_box = await page.evaluate(
            '!!document.querySelector(\'[id="prompt-textarea"]\')'
        )
        if not has_box:
            return {
                "status": "error",
                "error": f"No prompt box found (title: {title})",
                "auth": auth,
            }

        if verbose:
            print(f"Authenticated: {title}", file=sys.stderr, flush=True)

        model_info = await ensure_pro_model(page, verbose=verbose)
        error_message = _auth_error_message(
            auth,
            require_auth=require_auth,
            require_pro=require_pro,
            model_info=model_info,
        )
        if error_message:
            return {
                "status": "error",
                "error": error_message,
                "auth": auth,
                "model": model_info,
            }

        el = await page.query_selector('[id="prompt-textarea"]')
        await el.focus()

        if len(prompt) > 500:
            await page.evaluate(
                """
                (text) => {
                    const el = document.querySelector('[id="prompt-textarea"]');
                    if (!el) return;
                    el.focus();
                    el.innerHTML = '';
                    document.execCommand('insertText', false, text);
                }
                """,
                prompt,
            )
            await asyncio.sleep(0.5)
        else:
            await page.keyboard.type(prompt, delay=10)
            await asyncio.sleep(0.3)

        inserted = await page.evaluate(
            "document.querySelector('[id=\"prompt-textarea\"]')?.innerText?.trim()?.length || 0"
        )
        if not inserted:
            return {"status": "error", "error": "Failed to insert prompt text", "auth": auth}

        if verbose:
            print(f"Inserted {inserted} chars, sending...", file=sys.stderr, flush=True)

        initial_turns = await page.evaluate(
            'document.querySelectorAll(\'[data-testid^="conversation-turn"]\').length'
        )
        await page.keyboard.press("Enter")
        await asyncio.sleep(1)

        submitted = await page.evaluate(
            f"""
            (() => {{
                const turns = document.querySelectorAll('[data-testid^="conversation-turn"]').length;
                const stopBtn = !!document.querySelector('[data-testid="stop-button"]');
                const textarea = document.querySelector('[id="prompt-textarea"]');
                const remaining = textarea ? (textarea.innerText || '').trim().length : 0;
                return stopBtn || turns > {initial_turns} || remaining === 0;
            }})()
            """
        )

        if not submitted:
            send_btn = await page.query_selector('[data-testid="send-button"]')
            if send_btn:
                disabled = await send_btn.get_attribute("disabled")
                if not disabled:
                    submitted = await page.evaluate(
                        """
                        (() => {
                            const btn = document.querySelector('[data-testid="send-button"]');
                            if (!btn || btn.disabled) return false;
                            btn.click();
                            return true;
                        })()
                        """
                    )
                    if submitted:
                        await asyncio.sleep(1)

        if not submitted:
            return {
                "status": "error",
                "error": "Prompt submission failed — Enter and send-button fallback both failed",
                "auth": auth,
            }

        if verbose:
            print(f"Waiting for response (timeout={timeout}s)...", file=sys.stderr, flush=True)

        start = time.time()
        last_text = ""
        stable_count = 0
        last_status_print = 0
        saw_thinking = False

        while time.time() - start < timeout:
            await asyncio.sleep(2)

            data = await page.evaluate(
                """
                (() => {
                    const turns = document.querySelectorAll('[data-testid^="conversation-turn"]');
                    if (turns.length < 2) {
                        return JSON.stringify({s: 'wait', t: '', n: turns.length});
                    }

                    const last = turns[turns.length - 1];
                    const md = last.querySelector('.markdown')
                            || last.querySelector('[data-message-content]')
                            || last.querySelector('.prose');
                    const mdText = md ? (md.innerText || '').trim() : '';

                    const details = last.querySelector('details');
                    let responseText = mdText;
                    if (details) {
                        responseText = mdText.replace((details.innerText || ''), '').trim();
                    }

                    const stopBtn = !!document.querySelector('[data-testid="stop-button"]');
                    const fullText = (last?.innerText || '').trim();

                    let status;
                    if (/something went wrong|network error|error generating/i.test(fullText)) {
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
                """
            )

            d = json.loads(data)
            elapsed = round(time.time() - start)
            status = d["s"]
            text = d["t"]

            if verbose and elapsed - last_status_print >= 10:
                snippet = (text or "(empty)")[:60]
                print(
                    f"   [{elapsed}s] {status} md={d.get('mdLen', 0)} text='{snippet}'",
                    file=sys.stderr,
                    flush=True,
                )
                last_status_print = elapsed

            if status == "thinking":
                saw_thinking = True

            if status == "error":
                return {
                    "status": "error",
                    "text": text,
                    "model": model_info,
                    "auth": auth,
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
                            "auth": auth,
                            "usedPro": saw_thinking or model_info.get("isPro", False),
                        }
                        if (
                            not saw_thinking
                            and model_info.get("isPro")
                            and len(prompt) > 200
                            and elapsed < 15
                        ):
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

        return {
            "status": "timeout",
            "text": _clean_response(last_text) if last_text else "",
            "elapsed": round(time.time() - start),
            "model": model_info,
            "auth": auth,
            "usedPro": saw_thinking,
        }


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
  %(prog)s --auth-only --require-auth --require-pro --json
        """,
    )
    parser.add_argument("--prompt", "-p", help="Prompt text")
    parser.add_argument(
        "--file",
        "-f",
        action="append",
        nargs="+",
        help="Append file contents to prompt (repeatable; one or more paths per flag)",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=3600,
        help="Response timeout in seconds (default: 3600 — GPT-5.4 Pro can think for up to an hour)",
    )
    parser.add_argument("--output", "-o", help="Write response to file")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--cookies", default=DEFAULT_COOKIES)
    parser.add_argument("--chatgpt-url", default=DEFAULT_CHATGPT_URL)
    parser.add_argument("--auth-only", action="store_true", help="Validate auth/pro state only; do not send a prompt")
    parser.add_argument("--require-auth", action="store_true", help="Fail unless the session is authenticated")
    parser.add_argument("--require-pro", action="store_true", help="Fail unless Pro appears available")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    prompt = args.prompt or ""
    if not prompt and not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()

    if args.file:
        for file_group in args.file:
            for file_path in file_group:
                with open(file_path) as fh:
                    content = fh.read()
                prompt = f"{prompt}\n\n{content}" if prompt else content

    if not args.auth_only and not prompt:
        parser.print_help(sys.stderr)
        sys.exit(1)

    try:
        result = asyncio.run(
            query_chatgpt(
                prompt,
                cookies_path=args.cookies,
                timeout=args.timeout,
                verbose=args.verbose,
                auth_only=args.auth_only,
                require_auth=args.require_auth,
                require_pro=args.require_pro,
                chatgpt_url=args.chatgpt_url,
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
