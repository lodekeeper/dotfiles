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
# Simple direct query
scripts/oracle/chatgpt-direct --prompt "Your question here"

# Auth/Pro smoke test (no prompt sent)
scripts/oracle/chatgpt-direct --auth-only --require-auth --require-pro

# With file input
scripts/oracle/chatgpt-direct --prompt "Review this:" --file doc.md

# Multiple files (one or more after each --file; may be repeated)
scripts/oracle/chatgpt-direct --prompt "Review these:" --file doc.md notes.md --file diff.txt

# Pipe from stdin
echo "What is RRF?" | scripts/oracle/chatgpt-direct

# JSON output + save to file
scripts/oracle/chatgpt-direct --prompt "..." --json --output response.md

# Verbose mode (shows thinking progress)
scripts/oracle/chatgpt-direct --prompt "..." --verbose

# Oracle-style browser wrapper (preferred when someone asks for Oracle browser mode)
scripts/oracle/oracle-browser \
  --engine browser \
  --wait \
  --prompt "Review these files and give the concrete fix." \
  --file notes.md src/index.ts \
  --model gpt-5.2-pro

# Preview wrapper behavior without making a ChatGPT call
scripts/oracle/oracle-browser --prompt "Summarize these files" --file notes.md --dry-run json

# Oracle-style render aliases on the wrapper
scripts/oracle/oracle-browser --prompt "Summarize these files" --file notes.md --render

# Save preview output directly to a file
scripts/oracle/oracle-browser --prompt "Summarize these files" --file notes.md --dry-run json --write-output preview.json

# Copy preview output to the clipboard (requires a clipboard backend on the host)
scripts/oracle/oracle-browser --prompt "Summarize these files" --file notes.md --render --copy-markdown
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
| `--auth-only` | off | Validate auth/model state only; do not send a prompt |

## GPT-5.4 Pro Thinking Behavior

GPT-5.4 Pro uses **extended thinking** mode:
- Simple questions: 10-30 seconds
- Complex design reviews: 2-5 minutes
- Deep analysis: can think up to 60 minutes

### Current UI quirk (important)
ChatGPT's model button may still show the generic label **`ChatGPT`** even when **Pro** is active. On the current UI, a stronger signal is the composer pill / menu state (for example **`Extended Pro`** or the `model-switcher-gpt-5-4-pro` menu item) rather than the button text alone.

During thinking, the tool shows:
```
[10s] thinking md=0 text='(empty)'
[20s] thinking md=0 text='(empty)'
...
[192s] done md=865 text='Response starts here...'
```

The `md=0` indicates the model is still thinking. Once `md > 0`, the actual response is arriving.

## Canonical Recovery Smoke Test

After refreshing cookies/session state, use this as the first verification step:

```bash
scripts/oracle/chatgpt-direct --auth-only --require-auth --require-pro --json
```

For the Oracle-style wrapper path, the equivalent check is:

```bash
scripts/oracle/oracle-browser --auth-only --require-auth --require-pro --json
```

Expected success shape:
- `status: "ok"`
- `text: "ORACLE_BRIDGE_OK: ..."`
- `auth.state: "authenticated"`
- `auth.server.planType: "pro"`
- Pro evidence in `model.evidence.composerPills` (for example `Extended Pro`)

If the smoke test fails:
- `Guest/free ChatGPT session detected` → cookies are unauthenticated / expired / incomplete
- `stale/broken ... RefreshAccessTokenError` → auth metadata exists but refresh state is stale; replace with fresh auth material
- `GPT-5.4 Pro not available in current session` → session loaded, but Pro is not actually usable in the current UI/session

For the one-command verifier (`verify-after-auth-refresh.sh --json`), failure JSON now also includes:
- `failedStep` — which stage failed
- `failedDetail` — concrete detail extracted from the failing step artifact when available (JSON first, then stderr fallback for helper/setup failures such as a missing cookie-export path)
- `steps.refreshInput = "error"` on refresh/setup failures (instead of leaving that step at `"running"`)

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
- Increase `--timeout` (the direct bridge defaults to 21600s = 6 hours)
- For the Oracle-style wrapper path, explicitly too-short `--timeout` values on large rendered bundles are now auto-bumped to a safer floor; inspect wrapper JSON output (`--dry-run json`, successful live `--json`, structured refusal JSON, parsed bridge-originated JSON auth failures, or malformed/non-JSON bridge-output fallback envelopes) to see the top-level contract marker (`wrapper=oracle-browser-camoufox`, `wrapperSchemaVersion=1`) plus fields like `requestedTimeout`, `effectiveTimeout`, `timeoutAutoBumped`, `bundleClass`, `recommendedAction`, and `bundleGuidance`
- When the underlying `chatgpt-direct` path fails to emit valid JSON even though the wrapper was called with `--json`, the wrapper now preserves machine-readable output by emitting a structured fallback error envelope instead of raw stdout (`error.code=bridge-json-invalid`, plus `bridgeExitStatus` and a truncated `bridgeOutputExcerpt` for debugging)
- When the underlying `chatgpt-direct` path emits valid JSON but not a JSON object (for example `[]`), the wrapper also preserves machine-readable output by emitting a structured fallback error envelope instead of treating that as a successful contract match (`error.code=bridge-json-shape-invalid`)
- When the underlying `chatgpt-direct` path emits a JSON object but without a valid top-level `status` (`ok` / `error`), the wrapper also fails closed with a structured fallback error envelope instead of silently enriching contract-invalid JSON (`error.code=bridge-json-contract-invalid`)
- For extremely large rendered bundles (currently `>=100000` chars after render framing), the wrapper now refuses live sends unless the caller explicitly passes `--allow-very-large-bundle`
- If `--json` is set on that refusal path, the wrapper emits a structured error object (`error.code = very-large-bundle-refused`) so automation can react cleanly
- Some queries genuinely take GPT-5.4 Pro 10+ minutes to think through
- If consistently stuck even with generous timeout headroom, the model may have hit a generation error — retry

### "Something went wrong" error
- Transient ChatGPT error — tool retries automatically (new chat + resend)

## Files

| File | Purpose |
|------|---------|
| `research/chatgpt-direct.py` | Main Camoufox-based ChatGPT client |
| `scripts/oracle/chatgpt-direct` | CLI wrapper (activates venv) |
| `scripts/oracle/oracle-browser` | Simpler alias for the Oracle-style Camoufox wrapper |
| `scripts/oracle/oracle-browser-camoufox` | Oracle-compatible-ish browser wrapper: uses `oracle --render --render-plain`, then routes the rendered bundle through `chatgpt-direct` |
| `scripts/oracle/check-wrapper.sh` | Static/live verification script for the Oracle-style wrapper; supports `--json` for machine-readable summaries and checks unknown-arg rejection too |
| `research/oracle-bridge-v4.py` | Legacy Chrome CDP bridge (deprecated — Chrome gets 403) |
| `research/camoufox-direct.py` | Standalone test script (proof of concept) |

## Integration with OpenClaw

From agent code / skill scripts:
```bash
# Direct Camoufox path
~/.openclaw/workspace/scripts/oracle/chatgpt-direct \
  --prompt "Review this research:" \
  --file ~/research/topic/FINAL-REPORT.md \
  --output ~/research/topic/gpt54-review.md \
  --timeout 3600

# Direct Camoufox path, but start from a specific ChatGPT folder/project/custom-GPT URL
~/.openclaw/workspace/scripts/oracle/chatgpt-direct \
  --chatgpt-url "https://chatgpt.com/g/.../project" \
  --prompt "Continue with the project context already loaded there." \
  --timeout 3600

# Oracle-style browser path on this server
~/.openclaw/workspace/scripts/oracle/oracle-browser \
  --engine browser \
  --wait \
  --prompt "Review this research and list the concrete fixes." \
  --file ~/research/topic/FINAL-REPORT.md \
  --model gpt-5.2-pro \
  --timeout 3600

# Oracle-style path targeting a specific ChatGPT URL
~/.openclaw/workspace/scripts/oracle/oracle-browser \
  --engine browser \
  --wait \
  --chatgpt-url "https://chatgpt.com/g/.../project" \
  --prompt "Review this research and continue in that project context." \
  --file ~/research/topic/FINAL-REPORT.md \
  --model gpt-5.2-pro \
  --timeout 3600

# Wrapper verification
~/.openclaw/workspace/scripts/oracle/check-wrapper.sh --live --json

# Wrapper verification against a specific cookie jar during auth recovery
~/.openclaw/workspace/scripts/oracle/check-wrapper.sh --live --cookie-file /tmp/chatgpt-cookies.json --json

# Quick machine-readable static contract check
~/.openclaw/workspace/scripts/oracle/check-wrapper.sh --json
```

## Cookie Format

`~/.oracle/chatgpt-cookies.json` — array of cookie objects:
```json
[
  {"name": "__Secure-next-auth.session-token", "value": "...", "domain": ".chatgpt.com", ...},
  {"name": "_account", "value": "...", "domain": ".chatgpt.com", ...},
  {"name": "cf_clearance", "value": "...", "domain": ".chatgpt.com", ...},
  ...
]
```

Export all cookies from chatgpt.com domain (including HttpOnly). The `cf_clearance` cookie is helpful but not required — Camoufox obtains its own CF clearance.

### Important current auth nuance (updated 2026-04-08)
A cookie jar containing only a single `__Secure-next-auth.session-token` is **not reliably sufficient** on the current ChatGPT UI — stale single-token jars often collapse to guest/free mode after the welcome modal. However, a **freshly rotated** single `__Secure-next-auth.session-token` can work again: on 2026-04-08, replacing the stale token in `~/.oracle/chatgpt-cookies.json` with a fresh one restored authenticated Pro mode and passed both `--require-auth` and `--require-pro` checks.

Practical guidance:
1. **Safest default:** use a **full cookie export** from a genuinely logged-in ChatGPT Pro session.
2. **Fast recovery path:** if the jar only contains `__Secure-next-auth.session-token`, try replacing it with a **fresh** value first — this may be enough.
3. If browser mode still lands in guest mode, then escalate to:
   - attaching a logged-in `chatgpt.com` tab via Browser Relay and harvesting fresh auth state, or
   - replacing `~/.oracle/chatgpt-cookies.json` with a fresh full cookie export from a live Pro session.

### Fast local token refresh helper

When only the session token changed, prefer the local helper over hand-editing the cookie jar:

```bash
scripts/oracle/replace-session-token.py --token-file /tmp/session-token.txt
```

These direct helpers now fail cleanly on common setup/input errors (missing file, invalid JSON, permission problems) instead of dumping Python tracebacks.

When you have a **full fresh cookie export**, install it safely with:

```bash
scripts/oracle/install-chatgpt-cookies.py --source /tmp/chatgpt-cookies.json

# Or pipe it directly without staging a temp file
cat /tmp/chatgpt-cookies.json | scripts/oracle/install-chatgpt-cookies.py --source -
```

For the default recovery path, prefer the one-command verifier:

```bash
scripts/oracle/verify-after-auth-refresh.sh --token-file /tmp/session-token.txt
scripts/oracle/verify-after-auth-refresh.sh --cookie-source /tmp/chatgpt-cookies.json

# Or pipe a fresh full cookie export directly into the verifier
cat /tmp/chatgpt-cookies.json | scripts/oracle/verify-after-auth-refresh.sh --cookie-source -

scripts/oracle/verify-after-auth-refresh.sh --dry-run --json
```

It stores per-step artifacts under `research/oracle/refresh-verify-<timestamp>/`.
In `--dry-run` mode it previews the planned sequence and artifact path without
changing the cookie jar or creating the artifact directory.
That dry-run path now also covers pipe-based full-cookie recovery via
`--cookie-source -`.

When `--json` is used on a failing live run, the verifier now also returns:
- `cookieFile`
- `failedStep`
- `refreshInput`
- per-step status under `steps`

That makes stale-cookie failures much easier to classify programmatically.

Manual verification sequence if you want each step separately:

```bash
scripts/oracle/chatgpt-direct --auth-only --require-auth --require-pro --json
scripts/oracle/oracle-browser --auth-only --require-auth --require-pro --json
scripts/oracle/check-wrapper.sh --live --cookie-file ~/.oracle/chatgpt-cookies.json --json
```

## Wrapper notes (current 2026-04-08 behavior)

- `scripts/oracle/oracle-browser` is the preferred entrypoint when the caller wants something Oracle-browser-like on this server.
- For large prompt/file bundles, the wrapper now preserves the direct bridge's long-thinking posture better by auto-bumping explicitly too-short timeouts to a safer heuristic floor; inspect `--dry-run json` when debugging timeout behavior.
- If a bundle crosses the extremely-large threshold, prefer narrowing the file set first; only use `--allow-very-large-bundle` when you consciously want a live send anyway.
- It is **not** a full Oracle drop-in, but it now covers the common workflow well:
  - prompt
  - multi-file `--file` usage after one flag
  - `--auth-only`
  - `--cookies` / `--browser-cookie-path`
  - `--chatgpt-url`
  - `--files-report`
  - `--dry-run summary|json|full`
  - `--render` / `--render-markdown` / `--render-plain`
  - preview/render export via `--write-output` / `--output`
  - preview/render clipboard copy via `--copy-markdown`
  - `--engine browser`
  - `--wait`
  - compatibility/no-op handling for a few browser-style / CLI UX flags, including `--notify`, `--no-notify`, `--notify-sound`, `--no-notify-sound`, `--heartbeat`, `--force`, `--verbose-render`, `--retain-hours`, `--zombie-timeout`, `--zombie-last-activity`, `--debug-help`, `--browser-attachments`, and `--browser-bundle-files`
- It rejects obvious Oracle API-only flags (`--models`, `--background`, `--base-url`, Azure API options) with clearer wrapper-specific errors instead of failing ambiguously.
- It also rejects Oracle-native Chrome/CDP / remote-browser transport flags (`--remote-chrome`, `--remote-host`, `--remote-token`, `--browser-port`) with a wrapper-specific explanation, because this path always uses the local Camoufox bridge instead.
- It also rejects unknown/unsupported leftover args explicitly instead of silently ignoring them.
- Use `scripts/oracle/check-wrapper.sh` for fast regression checks before debugging the wrapper manually; the static check now also asserts unknown-arg rejection.
- `scripts/oracle/check-wrapper.sh --json` now also covers the recovery helpers statically:
  - `verify-after-auth-refresh.sh --dry-run --json`
  - `install-chatgpt-cookies.py` mixed-domain filtering + session-token preservation

## Self-Maintenance

If any commands, file paths, URLs, or configurations in this skill are outdated or no longer work, update this SKILL.md with the correct information after completing your current task. Skills should stay accurate and self-healing — fix what you find broken.
