# oracle-bridge — history

Changelog prose moved out of `SKILL.md` on 2026-10-04. Current verifier coverage is documented in `scripts/oracle/README.md` (sections "verify-after-auth-refresh.sh" and "Verification").

## Verification / regression guard (as of 2026-04)

Use the local verifier to lock the wrapper + direct-path contract in place:

```bash
scripts/oracle/check-wrapper.sh --json
scripts/oracle/check-wrapper.sh --live --json
```

(`--live` sends real ChatGPT traffic. Since 2026-04-24 it runs only when Nico explicitly asks.)

`verify-after-auth-refresh.sh --json` now also emits a stable verifier marker for automation:
- `verifier = "verify-after-auth-refresh"`
- `verifierSchemaVersion = 1`

The static verifier now also asserts that `scripts/oracle/chatgpt-direct` still exposes the repaired auth-check interface:
- `--chatgpt-url`
- `--auth-only`
- `--require-auth`
- `--require-pro`
- plus `python3 -m py_compile research/chatgpt-direct.py`

It also now locks the valid bridge-JSON pass-through path in place: when `chatgpt-direct` emits a valid structured JSON success or error envelope, the wrapper must preserve those direct-tool fields while adding wrapper metadata, and it must preserve the direct-tool exit-status semantics for valid structured bridge JSON.
