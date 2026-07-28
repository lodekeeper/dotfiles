# Review Findings — review-security — 9382

Reviewer: review-security
Reviewed commit: 3534a7aa12cbe756a6deef878b8c1c3c59d2dc0b
Generated at: 2026-07-28 12:58 UTC

## Findings

1. **packages/beacon-node/src/execution/engine/sszRestEncoding.ts:463** — Vulnerability: CWE-755, valid `INVALID_BLOCK_HASH` status is treated as an exceptional decoder failure.

   Attack vector: With `--execution.sszRest` enabled, an adversarial beacon peer can send a block whose execution payload hash fails EL block-hash validation. A spec-compliant SSZ-REST EL can return `PayloadStatusV1.status = 4` (`INVALID_BLOCK_HASH`), but `statusByteToEnum()` only accepts 0-3 and throws. Because the throw happens after the HTTP response and is not an `SszRestError`, the SSZ path does not fall back to JSON-RPC and `notifyNewPayload()` propagates an exception instead of returning the handled `ExecutionPayloadStatus.INVALID_BLOCK_HASH` case that the JSON-RPC path already supports. Repeated invalid blocks can therefore force the CL down an EL-error/exception path instead of the normal bounded invalid-block handling.

   Severity: Medium.

   Mitigation: Add byte `4 -> ExecutionPayloadStatus.INVALID_BLOCK_HASH`, keep the SSZ `notifyNewPayload()` switch aligned with the JSON-RPC branch, and add a regression test for status byte 4. Current EIP-8178 lists byte 4 as `INVALID_BLOCK_HASH` in the `PayloadStatusV1` table: https://eips.ethereum.org/EIPS/eip-8178#container-definitions

2. **packages/beacon-node/src/execution/engine/http.ts:334** — Vulnerability: CWE-362 / CWE-400, SSZ network-error fallback breaks the serialized Engine API ordering invariant.

   Attack vector: The new SSZ `newPayload` and `forkchoiceUpdated` calls are enqueued as standalone jobs, but the JSON-RPC fallback is only enqueued after that job rejects and the caller resumes. `JobItemQueue` starts the next queued job immediately after rejecting the failed job, so if an advertised SSZ endpoint is flaky or a proxy drops the SSZ request, a later `forkchoiceUpdated`/`newPayload` can run before the earlier call's JSON-RPC fallback is pushed. The surrounding comment says this queue exists because EL call order is important during sync; violating it can make the EL see FCUs before their payloads, producing unknown-payload/syncing errors and stalling block processing or proposal duties.

   Severity: Medium.

   Mitigation: Queue the whole transport attempt as one ordered unit. For queued Engine calls, the job function should try SSZ and, on network errors, call JSON-RPC before resolving/rejecting, so no later queued item can overtake the fallback. Add a concurrency regression where SSZ `newPayload` fails while a later FCU is already queued.

3. **packages/beacon-node/src/execution/engine/http.ts:228** — Vulnerability: CWE-400, SSZ transport bypasses the existing multi-URL failover and can pin the critical queue on a dead primary URL.

   Attack vector: `engine_exchangeCapabilities` is performed through the existing JSON-RPC client, which can fail over across `opts.urls`, but `SszRestClient` is always constructed from `opts.urls[0]`. If the first configured Engine URL is blackholed or slow while a later URL is healthy and advertises SSZ-REST, every advertised SSZ `newPayload`/FCU attempt targets the dead first URL, holds the single-concurrency Engine queue until `execution.timeout`, then falls back to JSON-RPC. A failing primary endpoint or network-level attacker on that endpoint can therefore repeatedly add slot-scale latency and queue pressure even though a configured backup EL is available.

   Severity: Medium.

   Mitigation: Either give SSZ-REST the same URL failover behavior as JSON-RPC, or bind negotiated capabilities to the specific URL that answered the exchange. Also consider temporary backoff/disablement of SSZ on repeated network failures so critical Engine calls do not pay the timeout every slot.

4. **packages/beacon-node/src/execution/engine/sszRestClient.ts:136** — Vulnerability: CWE-400, unbounded SSZ response buffering before size enforcement.

   Attack vector: `_fetch()` reads successful SSZ responses with `res.arrayBuffer()` before any endpoint-specific size cap is checked, and error responses are read with unbounded `res.text()` as well. SSZ type bounds only apply after the full body has already been buffered. A compromised/authenticated EL, misconfigured remote EL, or on-path proxy can stream a very large 2xx body (or large error text) within the timeout and force the beacon node to allocate it. EIP-8178's security considerations explicitly require rejecting SSZ payloads exceeding maximum sizes before full deserialization.

   Severity: Low.

   Mitigation: Add per-endpoint maximum response sizes and enforce them before buffering the full body, using `Content-Length` when present and a capped stream reader otherwise. Cap error text to the spec's `MAX_ERROR_MESSAGE_LENGTH`/log-print limit before constructing `SszRestError`.
