# Oracle browser-mode / Camoufox state snapshot — 2026-04-28

## Scope
Continuation of the deeper root-cause branch after the practical websocket fallback was already validated as working.

## Fresh live probes run today

### 1) `camoufox_route_state_probe.py`
Observed a failing run with the same high-level shape as 2026-04-23:
- starts healthy on `/`
- route transitions to `/c/<id>`
- flips quickly to `Application Error!`
- no live React Router globals / context visible at sample time
- embedded `__reactRouterContext.streamController.enqueue(...)` scripts still present in the HTML

Key difference vs the older theory:
- this failing run did **not** show the old Cloudflare snippet markers in `body.innerText`
- so the already-weakened “visible CF snippet in the crash body” theory looks even less central now

Interpretation: the page still looks like it dies before successful client hydration/bootstrap on the conversation route.

### 2) `camoufox_route_error_capture.py`
Observed a failing run with:
- `/c/<id>` + `Application Error!`
- **empty** JS capture surfaces:
  - no `consoleErrors` from the page’s own runtime path
  - no `windowErrors`
  - no `unhandledrejection`
  - no recorded history API events

Interpretation: the crash still does **not** present like an ordinary uncaught browser exception we can catch with standard hooks.

### 3) `camoufox_websocket_parse_probe.py`
Observed a healthy/non-crashing run in the same general environment:
- conversation route stayed up
- final page title became `WS_PARSE_OK Request`
- backend websocket delivered the completed assistant text `WS_PARSE_OK`
- same class of `Statsig` / `ces/v1/rgstr` networking errors still appeared in console

Interpretation:
- those `Statsig` / `ces` errors are **not sufficient** to explain the route crash, because they also occur on successful runs
- the failure remains **flaky / nondeterministic**, not a guaranteed consequence of the visible console noise

### 4) `trace_post_submit.py --engine camoufox`
Observed a healthy run with:
- successful submission
- route on `/c/<id>`
- no application-error transition
- websocket present
- broad asset/backend traffic looking healthy enough for end-to-end completion
- same CSP warning about blocked inline script from `sandbox eval code`
- same recurring `Statsig` / `ces` POST failures

Important nuance:
- the CSP warning references `sandbox eval code`, which is consistent with injected/evaluated probing context and is **not** currently strong evidence for the underlying ChatGPT failure itself

## Updated model

Current best explanation:
1. Camoufox can still authenticate and submit successfully.
2. The conversation route `/c/<id>` remains **flaky** under Camoufox.
3. Failing runs still look like a **route hydration/bootstrap failure** rather than a simple backend generation failure.
4. Successful runs show that the same session/cookies/browser stack can sometimes complete cleanly.
5. Repeated `Statsig` / `ces` errors correlate with the environment but are **not** the sole cause.
6. Standard JS exception hooks still do not expose the root failure directly.

## Practical status
- The production browser-mode path is still considered healthy because `research/chatgpt-direct.py` can recover through the backend websocket even when the UI route fails.
- The deeper UI-crash root cause remains unresolved.

## Best next experiments
1. **Batch crash-rate probe**: run repeated route-state / trace probes to quantify failure frequency and look for timing clusters.
2. **Network diff on fail vs success**: compare only requests that differ between a failing and successful Camoufox run, especially around route bootstrap and post-submit asset/data fetches.
3. **Reduce DOM touching further**: validate whether completely passive observation changes the crash rate materially.
4. **Try alternate starting URLs** (project/root/custom GPT) to see whether route bootstrap varies by initial app state.
