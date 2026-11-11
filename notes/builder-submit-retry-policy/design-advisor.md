# Builder submit timeout/retry architecture consult

Read-only source inspection at a3ea62064abc4023be4ce3c09f24d0ed2849c366; source changes not made.

## Recommendation

Use a builder-local retry wrapper, with each API call explicitly `retries: 0`, a fresh per-call init, and one absolute deadline passed by the two API helpers already holding `chain.clock`. Add a required submit options argument `{deadlineMs: number, signal?: AbortSignal}` to the two legacy interface methods. Compute the deadline as `Date.now() - chain.clock.msFromSlot(signedBlock.slot + 1)` (or computeTimeAtSlot with clock.genesisTime), once before submission. This avoids coupling execution builder construction to chain clock and leaves getHeader, registration and post-Gloas BuilderApiClient unchanged. Required options prevent accidentally unbounded future callers; update mocks narrowly.

Do not use currentSlot or request arrival + SLOT_DURATION_MS. A signed old block must not acquire a fresh budget. Slot+1 conversion uses the existing fork-aware time implementation, including shorter slots.

Policy: initial attempt plus at most two retries, sequentially, same signed payload and byte representation. Each logical attempt gets `min(1000ms, configuredBuilderTimeout ?? 12000ms, deadlineMs - Date.now())`; a 200ms delay between retries (the actual generic default in this checkout, NOT 2 seconds). Check deadline before every dispatch and after delay, and use one abortable total deadline shared with body reads/backoff. A tiny remaining positive budget may be used rather than reserving a speculative minimum. No retries after successful response, cancellation, expired deadline, or terminal HTTP 4xx; retry HTTP 408/429 and 5xx, fetch transport errors and attempt timeout. Treat 415 as protocol negotiation via existing fallback, not an additional policy retry. Do not retry local serialization, response decoding/type validation errors indiscriminately. Keep payload reconstruction outside the transport retry wrapper.

The 1s cap is deliberately conservative to make retries useful; it is a product choice, not a protocol constant. Three 1s attempts plus two 200ms gaps can exhaust before slot end; total deadline is an upper bound, not a promise to keep trying until slot end. A last attempt allowed the full remaining budget is a viable alternative, but less simple and changes the meaning of the cap.

## Critical blocker: 415 signal leakage

Local `retries:0` is NOT sufficient for strict deadline safety on current unstable. HttpClient.requestFallbackToJson reuses init. `_request` replaces `init.signal` with its internal controller; finally removes the original signal's listener. A successful 415 then triggers JSON `_request` with the *first internal controller signal*, not the original outer deadline signal. Outer cancellation no longer reaches JSON fallback. Even if first request returned promptly, JSON fallback can continue past total deadline; per-request timeout also restarts across fallback.

Preferred: explicitly base/depend on #10526 after checking that it fixes `_request` signal mutation for BOTH ordinary retries and SSZ→JSON fallback. Do not silently claim an independent strict hard cutoff PR on unstable using retries0 alone. A Promise.race can bound the public promise but does not cancel the detached JSON request and is therefore not sufficient to promise cancellation/no later dispatch. Reimplementing wire fallback locally or wrapping fetch to enforce an outer deadline is larger than this focused change. If dependency unavailable, present the limitation and reduce the promise, rather than smuggling generic HTTP fixes into scope.

After signal fix, an attempt-specific abort controller timer must span the complete logical call including SSZ→JSON fallback, not merely each underlying fetch. This keeps the 1s cap true across fallback; pass this signal alongside timeoutMs and clear listener/timer on settle. A shared total deadline signal still spans all attempts and backoff. Recheck wall time after awaited API call before accepting a deadline-bounded result (event-loop timer lag); JS cannot preempt synchronous decode/reconstruction.

## Product ambiguity to resolve with maintainer

A hard slot-end cutoff is an implementation policy, not evidence that all later responses or submissions are useless. Existing legacy caller explicitly notes relay publishes the full block and it may already be known by gossip. Aborting HTTP does not undo relay receipt/publication. A late response can still permit local reconstruction/publishing, and an in-flight successful relay publication may occur after local deadline. Recommend explicitly confirming hard slot-end *response rejection* versus only refusing to start new retry attempts after slot end. Work on plumbing/tests can proceed meanwhile. Also confirm the arbitrary 1s attempt cap vs preserving a longer in-flight final attempt. Do not conflate local timeout with definitive proposal failure.

## Acceptance checks

- Fresh initial request, timeout then success, transport failure then success, 500 then success, max three policy calls.
- Deadline derived from signed slot, not arrival/current slot; old slot never dispatches; just-before-end call gets only remaining budget.
- Configured shorter timeout honored; 6s/custom slot timing honored using existing clock conversion.
- Deadline/caller abort during fetch headers, delayed success body, delayed error body, and backoff; no later dispatch or timers/listeners left active.
- SSZ 415→JSON succeeds with original payload; delayed JSON fallback is actually canceled at shared attempt/slot deadline; 415 near deadline never escapes budget. Count logical attempts separately from fallback wire requests.
- Successful V1 body decoding and reconstruction once; successful V2 empty response once; terminal 400/401/403/404 no retries; 408/429/5xx follow policy.
- No retry for caller abort, deadline abort, serialization/decode errors; attempt timeout may retry if time remains.
- Success before deadline cancels timers and does not schedule retries; no late rejection/unhandled promise; concurrent submits have isolated cancellation.
- Ensure unchanged getHeader tolerance, registration configuration, SSZ-support cache semantics and post-Gloas behavior.
