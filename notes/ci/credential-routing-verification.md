# CI quality-gate credential routing — 2026-10-07

Nico requested repair in Telegram DM #15278.

- Native exec preflight: missing openaiApiKey; Python OpenAI package present.
- Gateway exec preflight, same script/workdir, env omitted: ready, both checks true.
- The existing credential is in the operator-managed Gateway environment; protected Secret Store list was empty. No credential values were read into chat, copied or replaced.
- Real Gateway API request on `credential-routing-proof.diff` (public merged Lodestar #10237 diff): exit 0, verdict root-cause, confidence high, should_flag false.
- CI automation 573d18ec-602c-40ba-a01a-004841c0da1a uses agent main, has no payload toolsAllow restriction, and reads scripts/ci/CRON_PROMPT.md on each run. The repaired runbook requires gateway_exec for the quality preflight and verdict request with explicit absolute paths and inherited environment.
- Independent design and final-runbook review approved.
- Verification scope: credential preflight plus actual model request. Not a full scheduled cron cycle. No scheduler/gateway config change or restart, no quality-gate bypass.
