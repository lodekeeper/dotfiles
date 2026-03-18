---
name: oracle-bridge
description: Query ChatGPT GPT-5.4 Pro from this headless server using Camoufox (Firefox stealth browser). Use when Oracle browser mode is needed under Cloudflare Turnstile constraints and Chrome/Chromium headless paths fail.
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
| `--timeout` / `-t` | 3600 | Response timeout (GPT-5.4 Pro can think up to 1 hour) |
| `--output` / `-o` | — | Write response text to file |
| `--json` | off | JSON output with status/text/elapsed |
| `--verbose` / `-v` | off | Show progress (thinking/generating) |
| `--cookies` | `~/.oracle/chatgpt-cookies.json` | Cookie file path |
| `--require-auth` | off | Fail unless the session is truly authenticated (not guest/free) |
| `--require-pro` | off | Fail unless GPT-5.4 Pro is actually available |

## GPT-5.4 Pro Thinking Behavior

GPT-5.4 Pro uses **extended thinking** mode:
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
4. **Error keywords detected** → error (retries once automatically)

## Troubleshooting

### "Cloudflare challenge not bypassed"
- Auth cookies may have expired → get fresh cookies from Nico's browser
- Export from browser DevTools: Application → Cookies → chatgpt.com → copy all

### "Session expired — need fresh cookies"
- Same fix: refresh `~/.oracle/chatgpt-cookies.json`

### Response times out after extended thinking
- Increase `--timeout` (default is 3600s = 1 hour)
- Some queries genuinely take GPT-5.4 Pro 10+ minutes to think through
- If consistently stuck, the model may have hit a generation error — retry

### "Something went wrong" error
- Transient ChatGPT error — tool retries automatically (new chat + resend)

## Files

| File | Purpose |
|------|---------|
| `research/chatgpt-direct.py` | Main Camoufox-based ChatGPT client |
| `scripts/oracle/chatgpt-direct` | CLI wrapper (activates venv) |
| `research/oracle-bridge-v4.py` | Legacy Chrome CDP bridge (deprecated — Chrome gets 403) |
| `research/camoufox-direct.py` | Standalone test script (proof of concept) |

## Integration with OpenClaw

From agent code / skill scripts:
```bash
# Query GPT-5.4 Pro for research review
~/.openclaw/workspace/scripts/oracle/chatgpt-direct \
  --prompt "Review this research:" \
  --file ~/research/topic/FINAL-REPORT.md \
  --output ~/research/topic/gpt54-review.md \
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
