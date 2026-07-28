# Review Findings — review-devils-advocate — 9382

Reviewer: review-devils-advocate
Reviewed commit: 3534a7aa12cbe756a6deef878b8c1c3c59d2dc0b
Generated at: 2026-07-28 12:52 UTC

## Devil's Advocate Review

### Overall Assessment

The general goal is sound as an experimental interop path, but this PR currently puts too much moving-proposal surface into Lodestar's main Engine path and makes the fallback story more optimistic than stateful Engine calls justify.

### Objections

#### 1. The implementation is pinned to a still-moving proposal surface

**Challenge:** The PR wires a full alternative Engine transport through production `ExecutionEngineHttp` (`supportedSszRestEndpoints` at `packages/beacon-node/src/execution/engine/http.ts:152`, per-method branches throughout `http.ts`, and a 753-line local SSZ schema in `sszRestEncoding.ts`) while the code still names `EIP-8161 / ethereum/execution-apis#764` (`http.ts:104`, `http.ts:238`; `sszRestEncoding.ts:19`). That proposal basis is stale/currently unsettled rather than a stable target.

**Evidence:** The current EIP page is `EIP-8178: Binary SSZ Transport for the Engine API`, created 2026-03-01, and is still marked `Draft`: https://eips.ethereum.org/EIPS/eip-8178. The older execution-apis proposal referenced by this PR, `ethereum/execution-apis#764`, is still a draft PR: https://github.com/ethereum/execution-apis/pull/764. The May 28, 2026 ACDC agenda explicitly listed two competing SSZ Engine API designs and asked for a final architectural decision between `execution-apis#764` and `execution-apis#793`: https://github.com/ethereum/pm/issues/2061.

**Counter-proposal:** Do not merge this as Lodestar's general `--execution.sszRest` implementation yet. Either (a) park it until execution-apis/EIP-8178 lands on a single canonical shape, then rebase the endpoint names, status encoding, blob versions, and nullable field model in one pass; or (b) reduce this PR to a clearly devnet-only experiment by isolating the transport behind one experimental adapter and a single small supported endpoint set needed for current interop, with comments/CLI text naming EIP-8178 rather than the stale EIP/PR number.

**Impact if ignored:** Every fork after Gloas will require touching two Engine API representations, and any spec churn before EIP-8178 stabilizes becomes Lodestar churn. Worse, users will see a hidden-but-real CLI flag whose documentation says "off until the spec stabilises" while the code has already committed to one draft endpoint vocabulary.

#### 2. Per-call JSON fallback is too broad for stateful Engine methods

**Challenge:** The PR falls back from an advertised SSZ-REST endpoint to JSON-RPC whenever `isSszRestNetworkError(e)` returns true. That happens after the SSZ request has already been issued in stateful paths like `notifyNewPayload` (`http.ts:334` -> `http.ts:357`), `notifyForkchoiceUpdate` (`http.ts:502` -> `http.ts:545`), and especially `getPayload` (`http.ts:643` -> fallback at `http.ts:654`). A timeout/abort is not proof that the EL did not process the request; it only means the CL did not receive the response.

**Evidence:** The existing `getPayload` comment in the same changed file notes that the EL "MAY stop the corresponding building process after serving this call" (`http.ts:621`-`http.ts:623`). The new SSZ client treats aborts, fetch `TypeError`s, and connection-class errors as fallbackable (`sszRestClient.ts:31`-`sszRestClient.ts:52`) even though some of those can happen after bytes were sent. The EIP's backward-compatibility story is that JSON-RPC remains available, not that one stateful Engine operation is safe to replay over a different transport after an ambiguous failure.

**Counter-proposal:** Split "fallback because endpoint is not negotiated" from "failure after using an advertised endpoint." If the endpoint is not advertised, JSON-RPC is correct. Once an advertised SSZ endpoint is selected, do not replay stateful calls through JSON-RPC after an ambiguous network error; surface the error for the current call, optionally disable SSZ for future calls after a circuit-breaker, and let subsequent forkchoice/newPayload traffic proceed on the chosen fallback transport. For read-only/stateless calls, document which ones are safe to retry across transports and keep that list explicit.

**Impact if ignored:** A proposer can lose or alter the payload path on a transient timeout: `getPayload` may have succeeded server-side and stopped the build process, then the JSON-RPC retry can return unavailable/stale/different data. For `newPayload`/`forkchoiceUpdated`, the retry also makes interop failures harder to diagnose because the EL observes both transports for one logical operation.

### Verdict

RECONSIDER — the goal is useful, but I would narrow the merge until EIP-8178/execution-apis settles and make fallback semantics conservative for advertised stateful endpoints.
