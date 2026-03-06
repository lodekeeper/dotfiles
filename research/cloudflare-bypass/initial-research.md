# Cloudflare Bypass Research — Initial Findings

## Approach 1: Cookie Injection (QUICKEST TO TEST)
Oracle natively supports `--browser-inline-cookies-file ~/.oracle/cookies.json`.
Minimum cookies needed: `__Secure-next-auth.session-token` + `_account`
CF cookies (`cf_clearance`, `__cf_bm`) needed when hitting a challenge.

**Idea:** Nico exports cookies from his local browser → we inject them.
**Problem:** CF cookies expire quickly. Session token might last longer.
**Test:** Get Nico to export cookies, try injection.

## Approach 2: puppeteer-real-browser / Rebrowser
- `puppeteer-real-browser` (npm) — designed to bypass CF Turnstile
- Uses modified Chrome that passes fingerprint checks
- BUT: Oracle uses its own Chrome automation, so we'd need to either modify Oracle or use this as a bridge

## Approach 3: Stealth Chrome flags
Launch Chrome with anti-detection flags:
- Remove `HeadlessChrome` from user agent
- Set `--disable-blink-features=AutomationControlled`
- Use `--headless=new` (newer, less detectable)
- Patch navigator.webdriver

## Approach 4: Oracle's remote-chrome
Use `--remote-chrome host:port` to connect to a stealth browser
We could launch puppeteer-real-browser, let IT handle CF, then point Oracle at its DevTools port.
