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
- fails cleanly on common direct-helper errors (for example missing token file, invalid JSON cookie jar, permission problems) instead of dumping a Python traceback
- fails cleanly on missing/invalid input (stderr error, no Python traceback)

Examples:
```bash
scripts/oracle/replace-session-token.py --token-file /tmp/session-token.txt
scripts/oracle/replace-session-token.py --token "fresh-session-token-value"
cat /tmp/session-token.txt | scripts/oracle/replace-session-token.py --stdin
```

### `install-chatgpt-cookies.py`
Safe helper to replace the local cookie jar from a **full ChatGPT cookie export**
without hand-editing JSON.

What it does:
- loads a JSON cookie export from disk or stdin (`--source -`)
- filters to ChatGPT/OpenAI-related domains only
- requires `__Secure-next-auth.session-token` by default
- writes a timestamped backup before replacing `~/.oracle/chatgpt-cookies.json`
- writes the normalized jar with restrictive permissions
- fails cleanly on common direct-helper errors (for example missing source file, invalid JSON input, wrong top-level JSON shape, permission problems) instead of dumping a Python traceback
- for wrong-shape exports it now says what the top-level JSON value was (for example object/number) and adds an explicit hint when the export is wrapped as `{ "cookies": [...] }` instead of the cookie array itself
- fails cleanly on missing/invalid input (stderr error, no Python traceback)

Examples:
```bash
scripts/oracle/install-chatgpt-cookies.py --source /tmp/chatgpt-cookies.json
scripts/oracle/install-chatgpt-cookies.py --source /tmp/export.json --cookie-file ~/.oracle/chatgpt-cookies.json
cat /tmp/chatgpt-cookies.json | scripts/oracle/install-chatgpt-cookies.py --source -
```

### `verify-after-auth-refresh.sh`
One-command runner for the full post-refresh verification sequence.

It can optionally refresh the local cookie jar first, then runs:
1. direct Camoufox auth/pro verification
2. Oracle-style wrapper auth/pro verification
3. full `check-wrapper.sh --live` verification

Supported refresh inputs:
- fresh session token (`--token-file`, `--token`, `--stdin`)
- fresh full cookie export (`--cookie-source /path/to/chatgpt-cookies.json`, or `--cookie-source -` to read from stdin)

Examples:
```bash
scripts/oracle/verify-after-auth-refresh.sh --token-file /tmp/session-token.txt
scripts/oracle/verify-after-auth-refresh.sh --cookie-source /tmp/chatgpt-cookies.json
cat /tmp/chatgpt-cookies.json | scripts/oracle/verify-after-auth-refresh.sh --cookie-source - --dry-run --json
scripts/oracle/verify-after-auth-refresh.sh --dry-run --json
scripts/oracle/verify-after-auth-refresh.sh --json
```

It stores step artifacts under `research/oracle/refresh-verify-<timestamp>/`.
In `--dry-run` mode it prints the planned sequence and artifact path **without**
changing the cookie jar or creating the artifact directory.

On failure, its JSON output now also includes:
- `failedStep` — which stage failed (`refreshInput`, `chatgptDirectAuth`, `oracleWrapperAuth`, `checkWrapperLive`)
- `failedDetail` — concrete detail extracted from the failing step artifact when available (JSON first, then stderr fallback for helper/setup failures like a missing cookie-export path)
That dry-run path now also covers pipe-based full-cookie recovery via
`--cookie-source -`.

Wrong-shape full-cookie refresh inputs (for example a top-level object like
`{"cookies": [...]}` instead of the cookie array itself) now also surface that
specific shape detail through `failedDetail`, rather than collapsing to a vague
refresh-install failure.

When `--json` is used on a failing live run, the verifier now also preserves:
- `cookieFile`
- `failedStep`
- `refreshInput`
- per-step status under `steps`

So automation can tell whether the run failed while installing auth material,
verifying `chatgpt-direct`, verifying the wrapper, or running the final live
wrapper check.

Refresh-input failures now also report `steps.refreshInput = "error"` instead of leaving the step stuck at `"running"` in failure JSON.

For large rendered bundles, wrapper JSON outputs now include the wrapper-side planning metadata below. This applies to:
- `--dry-run json`
- structured JSON refusal output on the extremely-large guard path
- successful live `--json` wrapper runs
- parsed bridge-originated JSON error outputs that the wrapper passes through after enrichment (for example auth/pro failures)
- malformed/non-JSON bridge output when the wrapper was asked for `--json` (the wrapper now emits a structured fallback error envelope instead of raw stdout)
- valid-but-non-object bridge JSON when the wrapper was asked for `--json` (for example `[]` or `"oops"`; the wrapper now emits a structured fallback error envelope instead of treating that as a successful contract match)
- object-shaped bridge JSON that still violates the wrapper contract by lacking a valid top-level `status` (`ok` / `error`) when the wrapper was asked for `--json`

All of those JSON shapes now also include a top-level contract marker:
- `wrapper = "oracle-browser-camoufox"`
- `wrapperSchemaVersion = 1`

For malformed bridge-output fallback envelopes, the top-level `error` object now also carries:
- `code = "bridge-json-invalid"`
- `bridgeExitStatus`
- `bridgeOutputBytes`
- `bridgeOutputExcerpt`
- `bridgeOutputTruncated`

For valid-but-non-object bridge JSON fallback envelopes, the top-level `error` object uses:
- `code = "bridge-json-shape-invalid"`
- the same `bridgeExitStatus` / `bridgeOutput*` diagnostics as above

For object-shaped-but-contract-invalid bridge JSON fallback envelopes, the top-level `error` object uses:
- `code = "bridge-json-contract-invalid"`
- the same `bridgeExitStatus` / `bridgeOutput*` diagnostics as above

Included fields:
- `requestedTimeout`
- `effectiveTimeout`
- `timeoutHeuristicFloor`
- `timeoutAutoBumped`
- `timeoutAdjustment`
- `bundleClass`
- `recommendedAction`
- `bundleGuidance`
- `veryLargeBundle`
- `allowVeryLargeBundle`

This makes it easy to see when the wrapper raised an explicitly too-short timeout before handing off to `chatgpt-direct`, and also surfaces human-readable guidance + recommended next action when a bundle is large enough that extended thinking time is expected.

Recommended post-refresh sequence:
```bash
# One command for the full refresh + verification flow from a fresh token
scripts/oracle/verify-after-auth-refresh.sh --token-file /tmp/session-token.txt

# One command for the full refresh + verification flow from a full cookie export
scripts/oracle/verify-after-auth-refresh.sh --cookie-source /tmp/chatgpt-cookies.json

# Same flow, but pipe the export directly instead of staging a temp file
cat /tmp/chatgpt-cookies.json | scripts/oracle/verify-after-auth-refresh.sh --cookie-source -

# Or run the checks only if the cookie jar is already updated
scripts/oracle/verify-after-auth-refresh.sh --json
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
- if a caller passes an explicitly short `--timeout` for a very large rendered bundle, the wrapper now auto-bumps it to a safer floor instead of blindly preserving a timeout that is too short for Extended Pro thinking
- for extremely large rendered bundles (currently `>=100000` chars after render framing), the wrapper refuses live sends by default unless the caller explicitly passes `--allow-very-large-bundle`
- if `--json` is set on that refusal path, the wrapper now emits a structured error object (`error.code = very-large-bundle-refused`) instead of forcing callers to scrape stderr
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

# Large rendered bundles: dry-run JSON now shows requested/effective timeout,
# and the wrapper auto-bumps too-short explicit timeouts to a safer floor.
scripts/oracle/oracle-browser \
  --prompt "Review these large files carefully." \
  --file AGENTS.md USER.md \
  --timeout 180 \
  --dry-run json

# Extremely large bundles require explicit opt-in for a live send
scripts/oracle/oracle-browser \
  --prompt "Review these very large files carefully." \
  --file tmp/oracle-huge-bundle.txt \
  --allow-very-large-bundle

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

# Override the cookie jar being verified
scripts/oracle/check-wrapper.sh --live --cookie-file /tmp/chatgpt-cookies.json --json
```

If live auth has gone stale, the JSON/error output now includes the concrete reason
(for example `RefreshAccessTokenError`, `state=stale`, `plan=pro`) instead of only
reporting a generic wrapper smoke-test failure.

What it checks:
- shell syntax for `oracle-browser-camoufox`
- help output renders
- API-only flags fail clearly
- unknown unsupported args fail clearly
- recovery helpers stay healthy too:
  - `verify-after-auth-refresh.sh --dry-run --json`
  - refresh-input failure classification in `verify-after-auth-refresh.sh` (missing path + wrong-top-level-shape cookie export)
  - `install-chatgpt-cookies.py` mixed-domain filtering + session-token preservation
  - direct helper failure UX for missing-path, malformed-JSON, and wrong-top-level-shape cookie exports
- optional live auth/pro smoke test
- optional live browser-style prompt run with multi-file `--file` usage
- optional custom cookie-jar verification via `--cookie-file <path>` for refresh/recovery flows
- optional machine-readable JSON summary for automation / future health checks

## Wrap-up reference

If you need the single-file handoff summary for this work, see:
- `research/oracle/WRAPUP-2026-04-08.md`

## Why this exists

On this server:
- **Camoufox direct works**
- **Oracle Chromium/CDP browser mode is unreliable**
  - upstream expects Linux browser runs to stay headful and to have a compositor / virtual display available
  - this host currently has no Xvfb / virtual display installed, so the intended headful path is unavailable here
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
