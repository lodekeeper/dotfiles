---
name: oracle-bridge
description: Query ChatGPT Pro (whatever "Pro" model the ChatGPT picker currently offers) from this headless server using Camoufox (Firefox stealth browser). Use when Oracle browser mode is needed under Cloudflare Turnstile constraints and Chrome/Chromium headless paths fail.
---

# Oracle Browser Bridge Skill

## Architecture

```
Camoufox (headless Firefox)
├─ Bypasses CF Turnstile natively
├─ Loads ChatGPT with auth cookies
├─ Types prompt + clicks send
└─ Polls for response (handles extended thinking)
```

**Why Camoufox, not Chrome?** Cloudflare blocks Chrome/Chromium headless browsers at the API level (all `/backend-api/*` calls return 403). Camoufox (Firefox-based stealth browser) passes CF checks and allows full ChatGPT interaction.

## Prerequisites

- `~/camoufox-env` virtualenv with `camoufox` and `playwright`
- `~/.oracle/chatgpt-cookies.json` — ChatGPT auth cookies (from Nico's browser)
- No Xvfb needed (runs headless)

## Quick Start

```bash
# Simple query
scripts/oracle/chatgpt-direct --prompt "Your question here"

# With file input
scripts/oracle/chatgpt-direct --prompt "Review this:" --file doc.md

# Pipe from stdin
echo "What is RRF?" | scripts/oracle/chatgpt-direct

# JSON output + save to file
scripts/oracle/chatgpt-direct --prompt "..." --json --output response.md

# Verbose mode (shows thinking progress)
scripts/oracle/chatgpt-direct --prompt "..." --verbose
```

## Key Options

| Flag | Default | Description |
|------|---------|-------------|
| `--prompt` / `-p` | — | Prompt text |
| `--file` / `-f` | — | Append file contents to prompt |
| `--timeout` / `-t` | 3600 | Response timeout (ChatGPT Pro can think up to 1 hour) |
| `--output` / `-o` | — | Write response text to file |
| `--json` | off | JSON output with status/text/elapsed |
| `--verbose` / `-v` | off | Show progress (thinking/generating) |
| `--cookies` | `~/.oracle/chatgpt-cookies.json` | Cookie file path |
| `--chatgpt-url` | `https://chatgpt.com` | Start from a specific ChatGPT project / folder / custom GPT URL |
| `--auth-only` | off | Validate auth / Pro state only; do not send a prompt |
| `--require-auth` | off | Fail unless the session is truly authenticated (not guest/free) |
| `--require-pro` | off | Fail unless ChatGPT Pro is actually available |

With `--json`, output also carries `bridge = "chatgpt-direct"` and `bridgeSchemaVersion = 1`.

## ChatGPT Pro Thinking Behavior

The bridge is version-agnostic: it selects any model-picker entry containing "pro" (`research/chatgpt-direct.py:332`), so this follows whatever Pro model ChatGPT currently ships.

ChatGPT Pro uses **extended thinking** mode:
- Simple questions: 10-30 seconds
- Complex design reviews: 2-5 minutes
- Deep analysis: can think up to 60 minutes

During thinking, the tool shows:
```
[10s] thinking md=0 text='(empty)'
[20s] thinking md=0 text='(empty)'
...
[192s] done md=865 text='Response starts here...'
```

The `md=0` indicates the model is still thinking. Once `md > 0`, the actual response is arriving.

## Response Detection

The tool distinguishes thinking from response by checking:
1. **Stop button visible** + **empty `.markdown`** → still thinking
2. **Stop button visible** + **non-empty `.markdown`** → streaming response
3. **No stop button** + **non-empty `.markdown`** → done (stable check: 2 consecutive polls)
4. **Error keywords detected** → error. An application-error page gets a 25s grace period for websocket recovery, then the tool returns `status=error` (exit 1). There is no automatic retry.

## Troubleshooting

### "Cloudflare challenge not bypassed"
- Auth cookies may have expired → get fresh cookies from Nico's browser
- Export from browser DevTools: Application → Cookies → chatgpt.com → copy all
- Install a full export with `scripts/oracle/install-chatgpt-cookies.py --source <export.json>` (filters to ChatGPT/OpenAI domains, backs up the old jar). If you only have a fresh session token: `scripts/oracle/replace-session-token.py --token-file <file>`. Don't hand-edit the jar.

### "Session expired — need fresh cookies"
- Same fix: refresh `~/.oracle/chatgpt-cookies.json` with the helpers above

### Response times out after extended thinking
- Increase `--timeout` (default is 3600s = 1 hour)
- Some queries genuinely take ChatGPT Pro 10+ minutes to think through
- If consistently stuck, the model may have hit a generation error — retry

### "Something went wrong" error
- Transient ChatGPT error — the tool returns `status=error` (exit 1) without retrying; re-run once manually

## Verification

Static contract check (local only, sends nothing to ChatGPT):

```bash
scripts/oracle/check-wrapper.sh --json
```

`check-wrapper.sh --live` and `verify-after-auth-refresh.sh` (which ends with `--live`) send real ChatGPT traffic. Run them only when Nico explicitly asks. Coverage details: `scripts/oracle/README.md`; past changelog: `references/history.md`.

## Files

| File | Purpose |
|------|---------|
| `research/chatgpt-direct.py` | Main Camoufox-based ChatGPT client |
| `scripts/oracle/chatgpt-direct` | CLI wrapper (activates venv) |
| `scripts/oracle/oracle-browser` | Oracle-style wrapper (`-p`, `-f`, `-m`, `--write-output`, `--dry-run`); sends via the Camoufox bridge, rejects `--remote-chrome` and API-mode flags |
| `scripts/oracle/install-chatgpt-cookies.py` | Install a full cookie export into `~/.oracle/chatgpt-cookies.json` (`--source <file>` or `-`) |
| `scripts/oracle/replace-session-token.py` | Patch only the session token (`--token-file`, `--token`, `--stdin`) |
| `scripts/oracle/check-wrapper.sh` | Static contract verifier (`--live` only when Nico asks) |
| `research/oracle-bridge-v4.py` | Legacy Chrome CDP bridge (deprecated — Chrome gets 403) |
| `research/camoufox-direct.py` | Standalone test script (proof of concept) |

## Integration with OpenClaw

From agent code / skill scripts:
```bash
# Query ChatGPT Pro for research review
~/.openclaw/workspace/scripts/oracle/chatgpt-direct \
  --prompt "Review this research:" \
  --file ~/research/topic/FINAL-REPORT.md \
  --output ~/research/topic/chatgpt-pro-review.md \
  --timeout 3600
```

## Cookie Format

`~/.oracle/chatgpt-cookies.json` — array of cookie objects:
```json
[
  {"name": "__Secure-next-auth.session-token", "value": "...", "domain": ".chatgpt.com", ...},
  {"name": "cf_clearance", "value": "...", "domain": ".chatgpt.com", ...},
  ...
]
```

Export all cookies from chatgpt.com domain (including HttpOnly). The `cf_clearance` cookie is helpful but not required — Camoufox obtains its own CF clearance.
