---
name: oracle-bridge
description: Run Oracle CLI browser mode on this headless server by connecting to a stealth Chromium CDP bridge with ChatGPT auth cookies. Use when `oracle --engine browser` is needed (GPT-5.2-pro/o-series via ChatGPT Pro), including troubleshooting bridge, token expiry, and Cloudflare/Turnstile issues.
---

# Oracle Browser Bridge Skill

Run Oracle CLI in browser mode on a headless Linux server by routing through a stealth Chromium instance that bypasses Cloudflare Turnstile.

---

## How It Works

Oracle's browser mode uses Chrome DevTools Protocol (CDP) to automate ChatGPT. On this server, two things block it:
1. **No usable Chrome** — snap chromium is blocked by AppArmor
2. **Cloudflare Turnstile** — blocks automated Chrome

The bridge solves both: it launches a stealth Chromium (rebrowser-playwright) that bypasses CF, logs into ChatGPT with auth cookies, and exposes a CDP port. Oracle connects via `--remote-chrome` and reuses the authenticated tab.

```
┌─────────────┐    CDP     ┌──────────────────┐    HTTPS    ┌──────────┐
│   Oracle    │ ─────────► │  Stealth Bridge  │ ──────────► │ ChatGPT  │
│ --remote-   │  port 9222 │  (rebrowser-pw)  │  CF bypass  │          │
│   chrome    │            │  + auth cookies   │             │          │
└─────────────┘            └──────────────────┘             └──────────┘
```

---

## Prerequisites

- **Python venv:** `~/camoufox-env` with `rebrowser-playwright` installed
- **Oracle CLI:** `@steipete/oracle` (v0.8.6+) installed globally via nvm 22
- **Oracle patch:** `ORACLE_REUSE_TAB=1` env var (patched in `chromeLifecycle.js`)
- **Auth cookies:** `~/.oracle/chatgpt-cookies.json` with ChatGPT session token

## Related Skills

- `skills/deep-research/SKILL.md` — primary consumer of this bridge (default browser-mode reasoning path).
- `skills/web-scraping/SKILL.md` — companion skill when research requires robust source collection before Oracle synthesis.

### Cookie Format

```json
[
  {
    "name": "__Secure-next-auth.session-token",
    "value": "<JWT token from Nico's browser>",
    "domain": ".chatgpt.com",
    "path": "/",
    "secure": true,
    "httpOnly": true,
    "sameSite": "Lax"
  }
]
```

**To refresh:** Ask Nico to export the cookie from chatgpt.com → DevTools → Application → Cookies.

---

## Usage

### Option 1: One-shot (recommended for single queries)

```bash
source ~/camoufox-env/bin/activate
python3 ~/.openclaw/workspace/research/oracle-bridge-v3.py \
  --cookies ~/.oracle/chatgpt-cookies.json \
  --oneshot \
  --prompt "Your question here" \
  --model gpt-5.2-pro
```

### Option 2: Persistent bridge (for multiple queries)

```bash
# Terminal 1: Start bridge (stays running)
source ~/camoufox-env/bin/activate
python3 ~/.openclaw/workspace/research/oracle-bridge-v3.py \
  --cookies ~/.oracle/chatgpt-cookies.json

# Terminal 2: Run Oracle queries
source ~/.nvm/nvm.sh && nvm use 22
ORACLE_REUSE_TAB=1 oracle --engine browser \
  --remote-chrome localhost:9222 \
  --model gpt-5.2-pro \
  --prompt "Your question here" --wait
```

### Option 3: API fallback (no bridge needed)

```bash
source ~/.nvm/nvm.sh && nvm use 22
oracle --engine api --model gpt-5.2-pro --prompt "Your question" --wait
```

---

## Error Handling

### Token Expired

**Symptom:** Bridge reports "⚠️ Not logged in (login page)" or Oracle says "Login button detected"

**Action:**
1. **Do NOT silently fall back to API mode** — alert the user
2. Message Nico: "ChatGPT session token expired — need a fresh `__Secure-next-auth.session-token` from chatgpt.com"
3. Only use `--engine api` if Nico explicitly approves the API cost

### Cloudflare Challenge

**Symptom:** Oracle says "Cloudflare challenge detected"

**Action:** This shouldn't happen with the bridge (stealth browser handles CF). If it does:
1. Check that `ORACLE_REUSE_TAB=1` is set
2. Verify the bridge is running and chatgpt.com loaded successfully
3. Kill stale chromium processes: `pkill -f "chromium.*headless"`
4. Restart the bridge

### Bridge Launch Failure

**Symptom:** Python errors about missing modules or browser binary

**Action:**
```bash
source ~/camoufox-env/bin/activate
pip install rebrowser-playwright websocket-client
python3 -m rebrowser_playwright install chromium
```

---

## Implementation Details

### Oracle Patch

The `ORACLE_REUSE_TAB=1` environment variable triggers two behaviors patched into Oracle v0.8.6:

1. **`chromeLifecycle.js`**: Skips `CDP.New()` (creating a new tab) and instead connects to the first existing target
2. **`index.js`**: Skips `navigateToChatGPT()` since the page is already loaded

Backup of original files: `*.js.bak` alongside the patched files.

**Location:** `~/.nvm/versions/node/v22.22.0/lib/node_modules/@steipete/oracle/dist/src/browser/`

**⚠️ After Oracle updates:** Re-apply the patch or check if `ORACLE_REUSE_TAB` is supported natively.

### Bridge Script

**Location:** `~/.openclaw/workspace/research/oracle-bridge-v3.py`

Key behaviors:
- Launches rebrowser-playwright Chromium with `--remote-debugging-port=9222` and `--remote-allow-origins=*`
- Injects auth cookies via Playwright context
- Navigates to chatgpt.com through the stealth browser (CF bypass)
- Keeps the tab open for Oracle to reuse

---

## Cookie Lifecycle

- **Session tokens** typically last days to weeks
- **CF clearance cookies** are handled automatically by the stealth browser (no manual refresh needed)
- When the session token expires, ChatGPT redirects to login → bridge detects this → alerts user
- **Never store multiple users' tokens** — only Nico's

---

## Notes

- Bridge uses port 9222 by default. Use `--port` to change.
- Only one bridge instance at a time (port conflict otherwise)
- Kill stale processes before restarting: `pkill -f "chromium.*remote-debugging"`
- The stealth browser profile is stored at `~/.oracle/stealth-profile/`
- API mode (`oracle --engine api`) works independently — no bridge needed, but costs per query
