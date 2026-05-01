# Oracle auth refresh handoff

Status as of 2026-05-01:
- Local wrapper/tooling path is healthy.
- We also recovered and decrypted a fuller local ChatGPT/OpenAI cookie jar directly from `~/.oracle/stealth-profile/Default/Cookies`.
- That improved diagnosis but did **not** unblock auth: stale `cf_*` cookies were one layer of failure, but after stripping them and letting Camoufox mint fresh clearance, the underlying NextAuth session still resolves to **stale Pro auth** (`RefreshAccessTokenError`).
- The active blocker remains **stale ChatGPT auth material**, not Cloudflare bypass or missing local scripts.
- Best remaining recovery path is still a **fresh full cookie export** or a **fresh `__Secure-next-auth.session-token`**.

## What is already verified
- `scripts/oracle/check-wrapper.sh --json` is green.
- `scripts/oracle/chatgpt-direct --auth-only --require-auth --require-pro --json` works as the canonical direct auth probe.
- A recovered full local cookie jar can reach a better diagnosis path than the one-cookie jar, but only after **removing stale Cloudflare cookies** so Camoufox can mint fresh clearance.
- After that cleanup, direct auth still bottoms out at the real blocker: `server.state=stale`, `planType=pro`, `error=RefreshAccessTokenError`.
- `scripts/oracle/verify-after-auth-refresh.sh --dry-run --json` plans the exact post-refresh sequence:
  1. `chatgpt-direct --auth-only --require-auth --require-pro --cookies <cookieFile> --json`
  2. `oracle-browser --auth-only --require-auth --require-pro --cookies <cookieFile> --json`
  3. `check-wrapper.sh --live --cookie-file <cookieFile> --json`

## Preferred recovery paths

### Option A — fresh full ChatGPT cookie export (best)
Use this if a fresh browser export is available.

```bash
scripts/oracle/install-chatgpt-cookies.py --source /tmp/chatgpt-cookies.json
scripts/oracle/verify-after-auth-refresh.sh --json
```

Or pipe directly:

```bash
cat /tmp/chatgpt-cookies.json | scripts/oracle/install-chatgpt-cookies.py --source -
scripts/oracle/verify-after-auth-refresh.sh --json
```

One-command combined path:

```bash
scripts/oracle/verify-after-auth-refresh.sh --cookie-source /tmp/chatgpt-cookies.json --json
```

### Option B — fresh `__Secure-next-auth.session-token` only
Use this if only a fresh token is available.

```bash
scripts/oracle/replace-session-token.py --token-file /tmp/session-token.txt
scripts/oracle/verify-after-auth-refresh.sh --json
```

One-command combined path:

```bash
scripts/oracle/verify-after-auth-refresh.sh --token-file /tmp/session-token.txt --json
```

## Critical guardrail
Do **not** splice a fresh token into the older historical full-cookie exports.

That path was tested already and is counterproductive:
- old full-cookie exports + current/backup tokens degrade to `server.state=guest`
- the minimal one-cookie jar remains the strongest token-only base

So:
- **token-only refresh** → patch `~/.oracle/chatgpt-cookies.json` with `replace-session-token.py`
- **full-cookie refresh** → use a truly fresh full export with `install-chatgpt-cookies.py`

## Useful preflight / inspection commands

Check planned verifier steps without changing anything:

```bash
scripts/oracle/verify-after-auth-refresh.sh --dry-run --json
```

Direct auth-only probe against the active jar:

```bash
scripts/oracle/chatgpt-direct --auth-only --require-auth --require-pro --json
```

## Expected success condition
A successful refresh should make the direct auth probe stop reporting stale/guest state, after which the full verifier should pass and Oracle browser-mode queries can use the refreshed auth material.
