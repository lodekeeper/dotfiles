# Oracle scripts

Local Oracle/ChatGPT helpers for this headless server.

## Files

### `chatgpt-direct`
Thin wrapper around `research/chatgpt-direct.py`.

Use this when you want the **direct Camoufox ChatGPT path**:
- bypasses Cloudflare Turnstile reliably on this server
- works with authenticated Pro sessions via `~/.oracle/chatgpt-cookies.json`
- does **not** depend on Oracle's Chromium/CDP browser engine

Examples:
```bash
scripts/oracle/chatgpt-direct --prompt "Summarize this"
scripts/oracle/chatgpt-direct --prompt "Review this" --file notes.md
scripts/oracle/chatgpt-direct --prompt "Review these" --file notes.md scripts/oracle/README.md
scripts/oracle/chatgpt-direct --auth-only --require-auth --require-pro --json
scripts/oracle/chatgpt-direct --chatgpt-url "https://chatgpt.com/g/.../project" --prompt "Use this project context"
```

### `replace-session-token.py`
Safe helper to patch a fresh `__Secure-next-auth.session-token` into the local
ChatGPT cookie jar without hand-editing JSON.

What it does:
- updates the existing token in `~/.oracle/chatgpt-cookies.json`
- preserves all other cookies when present
- writes a timestamped backup before changing the jar
- can also create a minimal token-only jar when no cookie jar exists yet

Examples:
```bash
scripts/oracle/replace-session-token.py --token-file /tmp/session-token.txt
scripts/oracle/replace-session-token.py --token "fresh-session-token-value"
cat /tmp/session-token.txt | scripts/oracle/replace-session-token.py --stdin
```

Recommended post-refresh sequence:
```bash
# 1) patch the local cookie jar
scripts/oracle/replace-session-token.py --token-file /tmp/session-token.txt

# 2) verify direct Camoufox auth/pro state
scripts/oracle/chatgpt-direct --auth-only --require-auth --require-pro --json

# 3) verify the Oracle-style wrapper path
scripts/oracle/oracle-browser --auth-only --require-auth --require-pro --json

# 4) run the full wrapper verifier
scripts/oracle/check-wrapper.sh --live --json
```

### `oracle-browser-camoufox`
Compatibility wrapper for **Oracle-style browser usage** on this machine.

Alias / simpler entrypoint:
- `scripts/oracle/oracle-browser`

It preserves Oracle's prompt+file bundle flow by doing:
1. `oracle --render --render-plain ...`
2. wraps that render with a small framing prompt
3. sends the final bundle through `scripts/oracle/chatgpt-direct`

Use this when:
- you want something close to `oracle --engine browser ...`
- Oracle's stock Chromium/CDP browser path is failing due to Cloudflare or Chrome launch issues

Current caveats:
- not a full flag-for-flag replacement for Oracle
- optimized for the common prompt + file + model + timeout workflow
- preserves Oracle's render/bundle step, but the actual browser execution is ChatGPT-via-Camoufox, not Oracle's Chromium engine
- supports Oracle-style multi-path `--file` usage after a single flag
- now also accepts `--browser-attachments` and `--browser-bundle-files` as compatibility flags for browser-style invocations
- supports `--dry-run` preview modes so you can inspect the wrapper plan or final rendered prompt without making a ChatGPT call
- now also accepts Oracle-style `--render`, `--render-markdown`, and `--render-plain` aliases for full preview output
- preview/render output now also honors `--write-output` / `--output`, so you can save the generated preview bundle directly to disk
- accepts Oracle-style `--copy-markdown` for preview/render modes and fails clearly if no clipboard backend is available on the host
- now also accepts common Oracle CLI UX flags as compatibility no-ops (`--notify`, `--no-notify`, `--notify-sound`, `--no-notify-sound`, `--heartbeat`, `--force`)
- also accepts a few Oracle session/debug flags in compatibility-safe form (`--verbose-render`, `--retain-hours`, `--zombie-timeout`, `--zombie-last-activity`, `--debug-help`)
- `--browser-cookie-path` is accepted as an alias for `--cookies`, while native Oracle browser transport flags like `--remote-chrome`, `--remote-host`, `--remote-token`, and `--browser-port` now fail with wrapper-specific errors instead of generic unknown-arg noise

Examples:
```bash
scripts/oracle/oracle-browser \
  --prompt "Review this code and give the concrete fix." \
  --file "src/**/*.ts" \
  --model gpt-5.2-pro \
  --timeout 300

scripts/oracle/oracle-browser-camoufox \
  --prompt "Review this code and give the concrete fix." \
  --file "src/**/*.ts" \
  --model gpt-5.2-pro \
  --timeout 300

# Oracle-ish browser invocation style
scripts/oracle/oracle-browser \
  --engine browser \
  --wait \
  --prompt "Summarize these files." \
  --file notes.md scripts/oracle/README.md \
  --model gpt-5.2-pro

# Auth/Pro smoke test via wrapper
scripts/oracle/oracle-browser --auth-only --require-auth --require-pro --json

# Preview the wrapper plan without sending anything to ChatGPT
scripts/oracle/oracle-browser --prompt "Summarize these files." --file notes.md --dry-run
scripts/oracle/oracle-browser --prompt "Summarize these files." --file notes.md --dry-run json
scripts/oracle/oracle-browser --prompt "Summarize these files." --file notes.md --dry-run full

# Oracle-style render aliases (mapped to full wrapper preview output)
scripts/oracle/oracle-browser --prompt "Summarize these files." --file notes.md --render
scripts/oracle/oracle-browser --prompt "Summarize these files." --file notes.md --render-plain

# Save preview output to a file instead of only stdout
scripts/oracle/oracle-browser --prompt "Summarize these files." --file notes.md --dry-run json --write-output preview.json
scripts/oracle/oracle-browser --prompt "Summarize these files." --file notes.md --render --output preview.md

# Copy preview output to the clipboard (requires pbcopy, wl-copy, xclip, or xsel)
scripts/oracle/oracle-browser --prompt "Summarize these files." --file notes.md --render --copy-markdown

# Start from a specific ChatGPT project/folder/custom-GPT URL
scripts/oracle/oracle-browser \
  --chatgpt-url "https://chatgpt.com/g/.../project" \
  --prompt "Continue in this project context" \
  --file notes.md

# File token usage during the Oracle render phase
scripts/oracle/oracle-browser --files-report --prompt "Summarize these files." --file notes.md scripts/oracle/README.md
```

## Verification

Quick static verification:
```bash
scripts/oracle/check-wrapper.sh
scripts/oracle/check-wrapper.sh --json
```

Full static + live smoke checks:
```bash
scripts/oracle/check-wrapper.sh --live
scripts/oracle/check-wrapper.sh --live --json
```

If live auth has gone stale, the JSON/error output now includes the concrete reason
(for example `RefreshAccessTokenError`, `state=stale`, `plan=pro`) instead of only
reporting a generic wrapper smoke-test failure.

What it checks:
- shell syntax for `oracle-browser-camoufox`
- help output renders
- API-only flags fail clearly
- unknown unsupported args fail clearly
- optional live auth/pro smoke test
- optional live browser-style prompt run with multi-file `--file` usage
- optional machine-readable JSON summary for automation / future health checks

## Wrap-up reference

If you need the single-file handoff summary for this work, see:
- `research/oracle/WRAPUP-2026-04-08.md`

## Why this exists

On this server:
- **Camoufox direct works**
- **Oracle Chromium/CDP browser mode is unreliable**
  - local launch path can fail before CDP attach
  - remote headless Chromium path reaches ChatGPT but hits Cloudflare anti-bot

So the practical production answer is:
- use `chatgpt-direct` for direct ChatGPT automation
- use `oracle-browser-camoufox` when you want Oracle-style prompt/file ergonomics

## Notes

- The wrapper is **not** a full drop-in replacement for every Oracle flag.
- It currently focuses on the common browser-mode workflow:
  - prompt
  - file attachments / globs (including Oracle-style `--file path1 path2 ...` after a single flag)
  - model hint
  - timeout
  - JSON output
  - write-output
  - auth-only checks
  - custom cookie path (including `--browser-cookie-path` as an alias)
  - custom `--chatgpt-url` targets (projects / folders / custom GPT entry URLs)
  - file token reporting via `--files-report`
  - wrapper preview via `--dry-run summary|json|full`
  - Oracle-style render aliases via `--render`, `--render-markdown`, `--render-plain`
  - preview/render export via `--write-output` / `--output`
  - preview/render clipboard copy via `--copy-markdown`
  - a few compatibility/no-op flags (`--engine browser`, `--wait`, `--slug`, `--notify`, `--no-notify`, `--notify-sound`, `--no-notify-sound`, `--heartbeat`, `--force`, `--verbose-render`, `--retain-hours`, `--zombie-timeout`, `--zombie-last-activity`, `--debug-help`, `--browser-model-strategy`, `--browser-attachments`, `--browser-inline-files`, `--browser-bundle-files`)
  - clearer rejection of API-only Oracle flags such as `--models`, `--background`, `--base-url`, and Azure API options
  - explicit rejection of unknown/unsupported leftover args instead of silently ignoring them
- If more Oracle flags are needed, extend the wrapper rather than patching the global Oracle install first.
