# Oracle browser-mode / CF Turnstile — state snapshot 2026-04-23 16:55 UTC

## What exists and works today
- **Production path:** Camoufox (Firefox-based stealth) → `research/chatgpt-direct.py` → CLI `scripts/oracle/chatgpt-direct`.
  Camoufox bypasses Cloudflare Turnstile natively; Chrome/Chromium headless is blocked at the API layer (403 on `/backend-api/*`).
- **Skill doc:** `skills/oracle-bridge/SKILL.md` — quick start, flags, response detection, cookie format.
- **Auth:** `~/.oracle/chatgpt-cookies.json` refreshed 2026-04-22 11:45 UTC (full export). 9 cookies, split session token (`__Secure-next-auth.session-token.0/.1`), no `cf_clearance` (Camoufox acquires its own — per skill doc this is fine).
- **Verifier stack:** `scripts/oracle/check-wrapper.sh` (static + `--live`), `scripts/oracle/verify-after-auth-refresh.sh` (post-refresh sequence), `scripts/oracle/chatgpt-direct --auth-only --require-auth --require-pro`.

## Static checks (just re-run)
- `check-wrapper.sh --json` → `status=ok`, all static checks pass.
- `python3 -m py_compile research/chatgpt-direct.py` → ok.
- `camoufox` / `playwright` import in `~/camoufox-env` → ok.

Not running `--live` unprompted (feedback rule: no proactive wrapper checks).

## What "research continuation" could mean (open scope)
Prior model attempt timed out; without more direction, several sub-investigations are plausible:
1. **Cookie freshness decay model** — empirically characterize how long a full export + a token-only refresh survive before `server.state=guest`, so refresh asks can be proactive instead of reactive.
2. **Alternative stealth stacks** — patchright, undetected-chromedriver, playwright-stealth — are any more robust than Camoufox against future Turnstile changes? Fallback value only if Camoufox breaks.
3. **Automated auth refresh** — browser-side refresh loop (via Nico's machine) that periodically exports and pushes a fresh jar. Avoids manual re-export every N days.
4. **Non-browser paths** — all `/backend-api/*` Chrome calls return 403; is there a sanctioned API (e.g. Responses API via paid tier) that removes the need for the browser bridge entirely?
5. **Specific failure triage** — if there is a concrete recent error/log that triggered the continuation ask, that is the most valuable path.

## New live finding — 2026-04-23 ~17:20 UTC
- Ran a bounded Camoufox DOM probe against the exact send path with the current healthy Pro cookie jar.
- **Submission is not the bug.** Immediately after pressing Enter:
  - `turns: 2`
  - `userMsgs: 1`
  - `assistantMsgs: 1`
  - `hasStop: true`
  - URL changes to a real conversation (`/c/...`)
- So the prompt is being sent and ChatGPT creates the assistant turn shell.
- Within ~10 seconds, the page falls over into the generic **`Application Error`** screen with minified JS stack text rendered in the body.
- That means the prior `status: timeout` output was misleading: the bridge was waiting on a page that had already crashed.

## Bridge patch applied
- Updated `research/chatgpt-direct.py` so the response wait loop now:
  - detects `Application Error` screens,
  - returns `error: "ChatGPT application error after prompt submission"` instead of timing out,
  - includes `pageErrors` when Playwright surfaces them.
- Validation:
  - `python3 -m py_compile research/chatgpt-direct.py` ✅
  - `scripts/oracle/chatgpt-direct --prompt 'Reply with exactly OK.' --timeout 25 --json` now fails fast with the application-error envelope instead of a fake timeout.

## Recommendation
The problem is now narrower than "Oracle bridge timeout": **auth is good, submission is good, ChatGPT's web app crashes after submission under this headless Camoufox path.**

Best next investigations:
1. Check whether the crash is prompt-independent (same on a few trivial prompts) or tied to a specific conversation/page state.
2. Test whether starting from a truly fresh chat / forced reload changes the outcome.
3. Capture browser-side `pageerror` / console signal consistently and see whether a retry/reload workaround is viable.
4. Only after that, decide whether this needs a Camoufox/browser-stack change vs a bridge-side recovery strategy.

## Upstream signal — 2026-04-23 17:45 UTC

Non-live checks against Camoufox's own issue tracker and public commentary:
- **Camoufox is in a maintenance gap** — reported year-long slowdown in upstream maintenance; base Firefox release is aging; newly-discovered fingerprint inconsistencies have degraded detection-bypass performance in 2026.
- **Akamai-protected sites now block Camoufox headless** but pass with stock Firefox via the same Playwright protocol (`daijro/camoufox#555`). Evidence of a real post-Turnstile, inside-page detection surface that Camoufox currently fails on.
- **No issue on the Camoufox tracker mentions ChatGPT or this exact `Application Error`** — we are either alone or users aren't filing it.

Most plausible reading: the post-submit SPA `Application Error` is **not** a Turnstile failure (Turnstile already passed) and **not** an auth failure (auth already confirmed). It fits the profile of an **inside-page anti-bot detection** in ChatGPT's SPA that trips on Camoufox fingerprint once the conversation loads.

## Revised lane recommendation
- **Lane 2 (alternative stealth stack)** just got a concrete upstream-backed reason to prioritize: try **patchright** (actively maintained Playwright fork with stealth patches) or stock Firefox via Playwright (known-good on Akamai-class detectors). If either loads `/c/...` without crashing, the browser-stack swap is the fix.
- **Lane 3 (retry/reload)** is still worth keeping as a *cheap* secondary: if the crash is transient, a `page.reload()` + single retry inside the bridge might suffice without a stack swap. Low implementation cost; worth a speculative branch.
- **Lane 1 (prompt-independence)** is low-leverage now that we suspect fingerprint, not prompt state.

Handing back to Nico for scope choice between:
- (a) implement speculative retry-on-AppError in the bridge (no stack change, cheap, may not help)
- (b) stand up a parallel patchright-based bridge as an A/B alternative
- (c) both, in parallel.

## Continuation results — 2026-04-23 22:03 UTC

### 1) Patchright A/B probe (Chromium stealth fork)
- Same cookie jar, same trivial prompt, bounded probe.
- Result: **worse than Camoufox**. Navigation lands on `https://chatgpt.com/` with HTTP **403** / title `Just a moment...`; no prompt box; auth cannot be established.
- So patchright does **not** give us a viable immediate fallback here.

### 2) Camoufox reload-after-AppError probe
- Reproduced the known good pre-submit state: authenticated, Pro-capable, prompt box present, prompt inserts, send succeeds, assistant turn shell appears.
- First sample after submit again flips to the same conversation-scoped **`Application Error`** page.
- A direct `page.reload()` on that crashed `/c/...` page times out and does not restore a usable composer.
- So the cheap `reload + one retry` lane looks **unpromising** in its simplest form.

### 3) Stock Playwright Firefox probe
- Different behavior from Camoufox:
  - Initial page loads cleanly (`200`, title `ChatGPT`), prompt box present, prompt submit succeeds.
  - **No SPA crash page.**
  - But the assistant turn never materializes beyond the shell (`ChatGPT said:` with stop button staying visible).
- Console/runtime signal shows repeated failures on **`https://chatgpt.com/ces/v1/...`** endpoints (not the main page) returning Cloudflare-challenge HTML / network errors.
- So stock Firefox reaches farther than patchright and avoids the Camoufox crash, but it still does **not** complete a response.

### 4) Stock Firefox with `ces` endpoints stubbed
- Intercepted and fulfilled `chatgpt.com/ces/v1/*` requests with empty `204` responses.
- Result: response generation still **hangs at the assistant shell**; no final text arrives.
- This means the `ces` failures are **real signal** but likely **not the sole blocker**.

## Revised conclusion
The simple lane choice has changed:
- **Patchright fallback:** ruled out for now.
- **Reload-on-AppError:** low confidence / likely not enough.
- **Stock Firefox:** promising only as a diagnostic contrast, not yet a working replacement.

The useful next step is now narrower:
1. instrument the actual response path in stock Firefox (network + DOM + maybe websocket/SSE visibility) to see which request class stalls after submission, or
2. compare Camoufox vs stock Firefox request surfaces around the post-submit phase to find the first diverging blocked endpoint / codepath.

This is no longer mainly a Turnstile problem; it is a **post-auth, post-submit ChatGPT webapp runtime / network-path problem**.

## Continuation results — 2026-04-23 22:20 UTC

### 5) Sanitized Camoufox vs Firefox post-submit trace diff
Created a sanitized tracer (`research/oracle/trace_post_submit.py`) and comparison helper (`research/oracle/compare_traces.py`) that strip query strings while preserving endpoint-level shape.

#### Camoufox trace
- Pre-submit + post-submit backend path is broadly healthy:
  - many `chatgpt.com/backend-api/*` endpoints return **200**,
  - `backend-api/sentinel/chat-requirements/prepare` returns **200**,
  - `backend-api/f/conversation/prepare` returns **200**,
  - a user websocket opens: `wss://ws.chatgpt.com/...`.
- After submit, the app navigates to a real conversation URL `/c/<id>` and then collapses fast (~3.1s) into **`Application Error!`**.
- So Camoufox is **not** failing at the raw API-access layer; it gets far enough into the authenticated app/runtime to open the conversation path and websocket, then dies inside the SPA/render/runtime layer.

#### Stock Firefox trace
- Looks better at the pure page level but worse at the actual app/API layer:
  - prompt box present, submit succeeds visually,
  - assistant shell appears (`ChatGPT said:`),
  - but **no websocket opens**,
  - and a wide swath of `chatgpt.com/backend-api/*` calls return **403** instead of 200.
- Examples: `backend-api/me`, `backend-api/models`, `backend-api/conversation/init`, `backend-api/f/conversation/prepare`, `backend-api/sentinel/chat-requirements/prepare`, many more — all 403 under Firefox while 200 under Camoufox.
- `ces/v1/*` also 403s under Firefox, but the bigger finding is that Firefox is blocked at **core backend-api access**, not just telemetry/settings.

#### Most important new interpretation
There are **two distinct failure modes**, not one shared one:
1. **Firefox path:** blocked at the authenticated API layer (`backend-api/*` 403, no websocket) → assistant shell hangs because the real app/backend path never properly comes up.
2. **Camoufox path:** authenticated backend path comes up (200s + websocket), but the conversation route crashes after navigation to `/c/...` → likely an SPA/runtime/render/fingerprint-triggered failure deeper inside the loaded app.

That means the old mental model "Firefox gets farther than Camoufox" was only partially true. In reality:
- Firefox looks visually cleaner, **but is less authenticated / less functional at the backend layer**.
- Camoufox looks worse because it crashes visibly, **but it actually gets farther into the real backend conversation path first**.

## Updated next-step recommendation
The highest-value next move is no longer Firefox request diff in general — that question is now answered.

The focus should shift to **Camoufox-specific post-navigation crash diagnosis**, for example:
1. isolate the first request / console / DOM transition between successful `f/conversation` + websocket bring-up and the `/c/...` route crash,
2. test whether staying on `/` (no route transition) vs opening the conversation route changes behavior,
3. compare Camoufox page runtime features / JS errors around the `/c/...` transition rather than broad network reachability.

In short: **Firefox is a dead-end until backend-api 403 is solved; Camoufox remains the only path that actually reaches the real app backend, so that is the path worth debugging further.**

## Continuation results — 2026-04-23 22:25 UTC

### 6) Camoufox zero-touch / delayed-touch probes
I ran several narrower Camoufox probes to separate "the page is inherently broken" from "our bridge polling is making it worse".

#### a) Minimal post-submit observer (almost no DOM probing)
- `camoufox_minimal_probe.py`
- Even without the full bridge wait loop, a failing run still reached:
  - `backend-api/conversation/init` → `200`
  - `backend-api/f/conversation/prepare` → `200`
  - `backend-api/f/conversation` → `200`
  - `conversation/<id>/stream_status` → `200`
- Then the page still flipped to `Application Error!` within ~2s on that run.
- So the crash is **not purely an artifact of the bridge polling loop**.

#### b) Zero-touch navigation capture
- `camoufox_navigation_capture.py`
- A different run stayed healthy for at least ~6s with:
  - URL at `/c/<id>`
  - title `NAVCAP_OK Response`
  - `stream_status = {"status":"IS_STREAMING"}`
- This is important: Camoufox can sometimes survive the route transition long enough to look completely healthy.

#### c) Deferred-read probe
- `camoufox_deferred_read_probe.py`
- Waiting ~12s before a single read still produced a failing run (`Application Error!`), so "just wait longer before touching DOM" is **not sufficient** as a standalone fix.

#### d) Long late-failure trace
- `camoufox_late_failure_trace.py`
- Another run stayed healthy through ~14s and ended with title `Latefail OK` despite multiple `ces/v1/rgstr` network errors in the console.
- This means the Camoufox failure is at least somewhat **flaky / nondeterministic**, not a guaranteed immediate collapse.
- Repeated `ces` registration errors are therefore **correlated** but not by themselves a sufficient predictor of failure.

### 7) Crash body dump — strongest new clue so far
- `camoufox_crash_body_dump.py` → `camoufox-crash-body.txt`
- The crashed `/c/...` page body is not just a blank app shell; it contains serialized React Router error output for `routes/_conversation`, and the embedded error text includes a **Cloudflare challenge-platform snippet**:
  - hidden iframe creation
  - `window.__CF$cv$params`
  - `/cdn-cgi/challenge-platform/scripts/jsd/main.js`
- In other words, the conversation-route error surface is carrying **Cloudflare challenge HTML / JS**, not a clean JSON app payload.
- That strongly suggests that some later route-level fetch or render dependency is intermittently receiving a **Cloudflare challenge response where the app expected normal data**, and React Router is then surfacing that as the conversation-page failure.

### 8) What changed in my understanding
The new best model is:
- Camoufox gets through initial auth + conversation submission + even some real backend conversation machinery.
- After that, the `/c/...` route is **flaky**:
  - sometimes healthy for several seconds or more,
  - sometimes collapses quickly,
  - and the failure payload appears to embed **Cloudflare challenge content**.
- Our existing DOM polling loop may still be too intrusive / brittle, but it is **not** the sole root cause.

### 9) Direct next-step recommendation
Highest-value next move now:
1. capture the exact **late fetch/loader** that returns Cloudflare challenge HTML during a *failing* Camoufox run, and
2. if possible, move the bridge off live DOM polling and onto less intrusive signals (network / stream status / websocket-assisted state) to reduce self-induced fragility.

### New artifacts
- `research/oracle/camoufox_minimal_probe.py`
- `research/oracle/camoufox_route_freeze_probe.py`
- `research/oracle/camoufox_navigation_capture.py`
- `research/oracle/camoufox_deferred_read_probe.py`
- `research/oracle/camoufox_crash_body_dump.py`
- `research/oracle/camoufox_late_failure_trace.py`
- `research/oracle/camoufox_sse_capture.py`
- `research/oracle/camoufox_route_document_probe.py`
- `research/oracle/camoufox_block_challenge_after_send_probe.py`
- `research/oracle/camoufox-crash-body.txt`
- corresponding `*-current.json` outputs in `research/oracle/`

## Continuation results — 2026-04-23 23:28 UTC

### 10) Route-document probe
- `camoufox_route_document_probe.py`
- Confirmed the post-submit hop to `/c/<id>` is a **client-side route transition** (main-frame navigation event at ~2.9s after send).
- The failing run still flips to `Application Error!` around ~4.1s with:
  - React Router stream markup in the body
  - the embedded Cloudflare challenge snippet still visible in that body
- Important negative result: the probe did **not** see any separate `/c/<id>` document response or any captured post-submit backend JSON/fetch response body containing the Cloudflare snippet.
- Interpretation: the visible contamination is not obviously coming from a plain main-document fetch response that Playwright can see at the network layer.

### 11) Block late challenge-platform loads after send
- `camoufox_block_challenge_after_send_probe.py`
- Intercepted `**/cdn-cgi/challenge-platform/**` **after send only** to test whether a fresh late Cloudflare challenge load is the immediate crash trigger.
- Result in a failing run:
  - route transition still happened (`/c/<id>` at ~2.25s)
  - page still crashed to `Application Error!` at ~4.2s
  - **zero** late `challenge-platform` requests were intercepted after send
- Interpretation: a brand-new post-submit `cdn-cgi/challenge-platform` request is **not** required for the crash to happen. The challenge snippet visible in the crash body is likely surfacing from an already-loaded/in-app route/render path, not from a simple late network fetch we can trivially block.

## Continuation results — 2026-04-23 23:31 UTC

### 12) Rich JS error capture on failing route
- `camoufox_route_error_capture.py`
- Added richer in-page hooks for:
  - `console.error`
  - `window.onerror`
  - `unhandledrejection`
  - history navigation calls
- In a failing run, the page still flipped to `Application Error!` on `/c/<id>`, but the capture log contained:
  - **no** serialized console-error arguments
  - **no** `windowErrors`
  - **no** `rejections`
  - **no** recorded history events
- This is important negative signal: the failure does **not** currently present like an ordinary uncaught browser exception or promise rejection that we can grab with the usual JS hooks.

### 13) Important correction to the Cloudflare-snippet theory
- The newer route-document/block-after-send probes showed that the root page body already contains the same Cloudflare challenge snippet **before** the route crashes.
- So the mere presence of:
  - `window.__CF$cv$params`
  - `challenge-platform`
in the crash body is **not** strong enough evidence by itself that a bad challenge HTML payload was newly injected at crash time.
- That earlier interpretation was too aggressive.

## Updated conclusion
The failure is narrowing from “post-submit network weirdness” to a more specific shape:
- Camoufox reaches the real backend conversation path.
- The breakage happens around the **conversation route / framework-render error surface** after the client-side transition to `/c/<id>`.
- The latest probes argue against several simpler stories:
  - **not** a plain late main-document fetch response,
  - **not** a fresh post-send `cdn-cgi/challenge-platform` request we can trivially block,
  - **not** an ordinary uncaught JS exception/rejection visible through standard window hooks.
- The Cloudflare snippet may still be relevant context, but it is no longer safe to treat it as the direct causal payload without stronger proof.

## Continuation results — 2026-04-23 23:35 UTC

### 14) Route-state / hydration probe
- `camoufox_route_state_probe.py`
- Sampled the page after submit for:
  - visible React Router globals on `window`
  - `window.__reactRouterContext`
  - likely hydration-state globals
  - embedded router stream scripts in the HTML
- Two failing runs both showed the same shape:
  - URL already at `/c/<id>`
  - title already `Application Error!`
  - **no live React Router globals at all**
  - `window.__reactRouterContext` absent
  - no visible hydration state
  - but raw embedded `window.__reactRouterContext.streamController.enqueue(...)` scripts still present in the page HTML
- That points to a stronger hypothesis than before: the conversation page appears to die **before hydration / client bootstrap completes**, rather than only later inside a fully-hydrated route state.

## Best next move
Focus on **hydration/bootstrap boundary** rather than broad network diffs:
1. compare **healthy vs failing hydration markers** on `/c/<id>`,
2. inspect what prevents the embedded React Router stream payload from turning into live runtime globals,
3. explore whether the bridge can avoid relying on the fragile conversation-route bootstrap entirely if root-page / backend-stream observation is sufficient.
