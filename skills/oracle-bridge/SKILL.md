---
name: oracle-bridge
description: Run ChatGPT browser automation from this headless server using a hybrid Camoufox→Chromium CDP bridge. Use when `oracle --engine browser` is needed, and fall back to direct CDP CLI when Oracle UI automation is flaky.
---

# Oracle Browser Bridge Skill (v4 hybrid)

Use this when browser-mode ChatGPT access is required on the headless server.

## Current Reality (important)

- Plain headless Chromium often fails Cloudflare/Turnstile.
- **Hybrid v4 works** for authentication:
  1. Camoufox (Firefox stealth) passes CF and collects fresh cookies.
  2. Cookies are injected into rebrowser Chromium.
  3. Chromium exposes CDP for automation clients.
- Oracle CLI browser automation can still be flaky with ChatGPT UI/model-picker changes.
- A direct CDP client (`chatgpt-direct.py`) is currently the most reliable execution path.

---

## Architecture

```text
Camoufox (stealth Firefox) --passes CF--> chatgpt.com
        │
        └─extract cookies (session + cf_clearance...)
                │
                ▼
Rebrowser Chromium (CDP port 9222, authenticated tab)
        │
        ├─ Oracle CLI --engine browser --remote-chrome localhost:9222
        └─ Direct CDP CLI (chatgpt-direct)
```

---

## Prerequisites

- `~/camoufox-env` virtualenv with:
  - `camoufox`
  - `rebrowser-playwright`
  - `websocket-client`
- Oracle CLI installed (nvm node 22): `@steipete/oracle`
- Cookie file: `~/.oracle/chatgpt-cookies.json`
  - must include `__Secure-next-auth.session-token`

---

## Quick Start

## 1) Start hybrid bridge (v4)

```bash
source ~/camoufox-env/bin/activate
python3 ~/.openclaw/workspace/research/oracle-bridge-v4.py \
  --cookies ~/.oracle/chatgpt-cookies.json \
  --port 9222
```

Expected: `Oracle Bridge v4 READY` and `localhost:9222`.

## 2) Preferred query path: direct CDP CLI

Use the stable wrapper:

```bash
~/.openclaw/workspace/scripts/oracle/chatgpt-direct --prompt "Your question" --timeout 180
```

Pipe mode also works:

```bash
echo "Summarize this in 3 bullets" | ~/.openclaw/workspace/scripts/oracle/chatgpt-direct
```

## 3) Oracle browser mode (experimental)

```bash
source ~/.nvm/nvm.sh && nvm use 22
ORACLE_REUSE_TAB=1 oracle --engine browser \
  --remote-chrome localhost:9222 \
  --model gpt-5.2-pro \
  --prompt "Your question" --wait
```

If Oracle stalls on assistant capture, use the direct CDP CLI above.

---

## Output Durability Rule

For long Oracle runs, always persist output with `tee`:

```bash
oracle ... --wait 2>&1 | tee ~/research/<topic>/oracle-output.md
```

Never rely on transient stdout alone.

---

## Troubleshooting

### `backend-api/*` returns 403

- This means CF/API protection is still active for the current browser path.
- Restart the hybrid bridge and verify authenticated tab before querying.
- Validate quickly with direct CLI first (`chatgpt-direct`) before blaming Oracle.

### `Session token expired` / login page appears

- Refresh `~/.oracle/chatgpt-cookies.json` from a live ChatGPT browser session.

### Oracle says assistant timed out but prompt was sent

- Known Oracle UI-capture issue in this setup.
- Use `scripts/oracle/chatgpt-direct` for reliable completion capture.

### No ChatGPT tab found

- Bridge is not running or CDP port mismatched.
- Check bridge logs and ensure `--port` matches the client command.

---

## Key Files

- Bridge v4: `research/oracle-bridge-v4.py`
- Direct CDP client: `research/chatgpt-direct.py`
- Stable wrapper: `scripts/oracle/chatgpt-direct`
- Oracle patched files (when needed):
  - `.../oracle/dist/src/browser/index.js`
  - `.../oracle/dist/src/browser/actions/navigation.js`

If Oracle is updated, re-validate patched behavior before assuming regressions are external.
