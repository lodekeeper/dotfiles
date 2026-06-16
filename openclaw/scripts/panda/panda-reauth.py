#!/usr/bin/env python3
"""Unattended panda re-auth via Camoufox + transplanted GitHub session cookies.

The panda-proxy (authentik) issues only 1h access tokens with no refresh token,
so the device flow must be re-run on expiry. authentik federates login to
lodekeeper's GitHub. This script:

  1. starts `panda auth login --no-browser` and parses the device URL + code
  2. launches headless Camoufox with the github.com session cookies loaded
  3. drives the authentik device page -> GitHub federated auth -> consent
  4. waits for the panda subprocess to re-mint the token

Run with --recon to stop after capturing screenshots/DOM at each step without
asserting success (used to learn page selectors).

Cookies: ~/.config/panda/github-cookies.json (Cookie-Editor JSON array).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

COOKIES_PATH = Path.home() / ".config" / "panda" / "github-cookies.json"
SHOT_DIR = Path("/tmp/panda-reauth-shots")
DEVICE_URL_RE = re.compile(r"https://\S+/device")
CODE_RE = re.compile(r"\b(\d{6,9})\b")


def log(msg: str) -> None:
    print(f"[panda-reauth] {msg}", file=sys.stderr, flush=True)


def load_cookies() -> list[dict]:
    data = json.loads(COOKIES_PATH.read_text())
    if not isinstance(data, list):
        raise ValueError("cookie jar must be a JSON array")
    out = []
    for c in data:
        name = c.get("name")
        value = c.get("value")
        if not name:
            continue
        domain = c.get("domain") or ".github.com"
        cookie = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": c.get("path", "/"),
            "secure": bool(c.get("secure", True)),
            "httpOnly": bool(c.get("httpOnly", False)),
        }
        exp = c.get("expirationDate") or c.get("expires")
        if isinstance(exp, (int, float)) and exp > 0:
            cookie["expires"] = int(exp)
        out.append(cookie)
    return out


async def start_device_flow():
    """Start panda auth login, return (proc, device_url, code)."""
    proc = await asyncio.create_subprocess_exec(
        "panda", "auth", "login", "--no-browser",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd="/tmp",
    )
    device_url = None
    code = None
    captured = []
    deadline = time.time() + 30
    while time.time() < deadline and (device_url is None or code is None):
        try:
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=5)
        except asyncio.TimeoutError:
            continue
        if not line:
            break
        text = line.decode(errors="replace").rstrip()
        captured.append(text)
        log(f"panda> {text}")
        m = DEVICE_URL_RE.search(text)
        if m and device_url is None:
            device_url = m.group(0)
        m2 = CODE_RE.search(text)
        if m2 and code is None and "device" not in text.lower():
            code = m2.group(1)
    if device_url is None or code is None:
        raise RuntimeError(f"could not parse device flow; got:\n" + "\n".join(captured))
    return proc, device_url, code


async def deep_click(page, predicate) -> bool:
    """Find clickable elements (incl. shadow DOM) and click the first match.

    predicate receives a dict {text, name, type} and returns bool.
    """
    elements = await page.evaluate(
        """() => {
            const acc = [];
            const walk = (root) => {
                root.querySelectorAll('button, input[type=submit], a[role=button], [role=button], a').forEach(e => acc.push(e));
                root.querySelectorAll('*').forEach(e => { if (e.shadowRoot) walk(e.shadowRoot); });
            };
            walk(document);
            return acc.map((e, i) => {
                e.setAttribute('data-reauth-idx', String(i));
                return { idx: i, text: (e.innerText||e.value||'').trim(), name: e.name||'', type: e.type||'' };
            });
        }"""
    )
    target = None
    for e in elements:
        try:
            if predicate({"text": e["text"], "name": e["name"], "type": e["type"]}):
                target = e["idx"]
                break
        except Exception:
            continue
    if target is None:
        return False
    return await page.evaluate(
        """(idx) => {
            const walk = (root) => {
                for (const e of root.querySelectorAll('[data-reauth-idx]')) {
                    if (e.getAttribute('data-reauth-idx') === String(idx)) { e.click(); return true; }
                }
                for (const e of root.querySelectorAll('*')) {
                    if (e.shadowRoot && walk(e.shadowRoot)) return true;
                }
                return false;
            };
            return walk(document);
        }""",
        target,
    )


async def dump(page, tag: str) -> None:
    try:
        await page.screenshot(path=str(SHOT_DIR / f"{tag}.png"), full_page=True)
    except Exception as e:
        log(f"screenshot {tag} failed: {e}")
    try:
        url = page.url
        title = await page.title()
        # collect inputs and buttons (incl. shadow DOM via JS)
        info = await page.evaluate(
            """() => {
                const deepQuery = (root, sel, acc) => {
                    root.querySelectorAll(sel).forEach(e => acc.push(e));
                    root.querySelectorAll('*').forEach(e => {
                        if (e.shadowRoot) deepQuery(e.shadowRoot, sel, acc);
                    });
                    return acc;
                };
                const inputs = deepQuery(document, 'input', []).map(i => ({
                    name: i.name, id: i.id, type: i.type,
                    placeholder: i.placeholder, value: (i.value||'').slice(0,20)
                }));
                const buttons = deepQuery(document, 'button, input[type=submit], [role=button]', []).map(b => ({
                    text: (b.innerText||b.value||'').trim().slice(0,40),
                    type: b.type, name: b.name
                }));
                return { inputs, buttons, bodyText: (document.body?document.body.innerText:'').slice(0,600) };
            }"""
        )
        log(f"--- {tag} ---")
        log(f"url={url}")
        log(f"title={title}")
        log(f"inputs={json.dumps(info['inputs'])}")
        log(f"buttons={json.dumps(info['buttons'])}")
        log(f"bodyText={info['bodyText']!r}")
    except Exception as e:
        log(f"dump {tag} failed: {e}")


async def run(recon: bool):
    from camoufox.async_api import AsyncCamoufox

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    cookies = load_cookies()
    log(f"loaded {len(cookies)} cookies")

    proc, device_url, code = await start_device_flow()
    log(f"device_url={device_url} code={code}")

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        await page.context.add_cookies(cookies)
        log("cookies injected")

        # Verify GitHub session first
        await page.goto("https://github.com/", timeout=45000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(3)
        await dump(page, "00-github-home")

        # Navigate to authentik device page; try code in query to pre-fill
        sep = "&" if "?" in device_url else "?"
        await page.goto(f"{device_url}{sep}code={code}", timeout=45000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(4)
        await dump(page, "01-device-page")

        if recon:
            log("recon mode: stopping after device page capture")
            proc.terminate()
            return

        # Step 1: click the authentik "GitHub" federated-login button (shadow DOM).
        clicked = await deep_click(page, lambda b: b["name"] == "source-git-hub"
                                   or b["text"].strip().lower() == "github")
        log(f"clicked GitHub source button: {clicked}")
        await asyncio.sleep(5)
        await page.wait_for_load_state("domcontentloaded")
        await dump(page, "02-after-github-click")

        # Step 2..N: resolve any GitHub OAuth authorize + authentik consent screens,
        # polling for the panda subprocess to finish re-minting the token.
        deadline = time.time() + 90
        step = 3
        while time.time() < deadline:
            try:
                await asyncio.wait_for(proc.wait(), timeout=0.1)
            except asyncio.TimeoutError:
                pass
            if proc.returncode is not None:
                break

            url = page.url
            # GitHub OAuth authorize button (first-time grant)
            if "github.com/login/oauth" in url or "github.com/sessions" in url:
                got = await deep_click(page, lambda b: b["name"] in ("authorize", "commit")
                                       or re.search(r"authorize|continue|sign in", b["text"], re.I) is not None)
                log(f"github oauth page, clicked authorize/continue: {got}")
            # authentik consent / continue screens
            elif "authentik" in url or "/if/flow/" in url or "/device" in url:
                got = await deep_click(page, lambda b: re.search(
                    r"authoriz|continue|yes|allow|accept|log in", b["text"], re.I) is not None)
                log(f"authentik page ({url[:80]}), clicked consent: {got}")

            await asyncio.sleep(4)
            try:
                await page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            await dump(page, f"{step:02d}-step")
            step += 1

            # Has panda finished?
            try:
                await asyncio.wait_for(proc.wait(), timeout=0.1)
            except asyncio.TimeoutError:
                pass

        # Drain remaining panda output.
        try:
            rest = await asyncio.wait_for(proc.stdout.read(), timeout=5)
            if rest:
                log("panda tail> " + rest.decode(errors="replace").strip())
        except Exception:
            pass
        rc = proc.returncode
        log(f"panda auth login exit code: {rc}")
        if rc != 0:
            try:
                proc.terminate()
            except Exception:
                pass
        await dump(page, "99-final")
        return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recon", action="store_true")
    args = ap.parse_args()
    rc = asyncio.run(run(args.recon))
    sys.exit(rc if isinstance(rc, int) else 0)


if __name__ == "__main__":
    main()
