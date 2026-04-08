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
scripts/oracle/chatgpt-direct --auth-only --require-auth --require-pro --json
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

What it checks:
- shell syntax for `oracle-browser-camoufox`
- help output renders
- API-only flags fail clearly
- optional live auth/pro smoke test
- optional live browser-style prompt run with multi-file `--file` usage
- optional machine-readable JSON summary for automation / future health checks

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
  - custom cookie path
  - file token reporting via `--files-report`
  - a few compatibility/no-op flags (`--engine browser`, `--wait`, `--slug`, `--browser-model-strategy`, `--browser-inline-files`)
  - clearer rejection of API-only Oracle flags such as `--models`, `--background`, `--base-url`, and Azure API options
- If more Oracle flags are needed, extend the wrapper rather than patching the global Oracle install first.
