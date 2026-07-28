# Review Findings — reviewer-architect — 9382

Reviewer: reviewer-architect
Reviewed commit: 3534a7aa12cbe756a6deef878b8c1c3c59d2dc0b
Generated at: 2026-07-28 12:53 UTC

## Findings

### 1. SSZ-REST response containers define a private dialect instead of the Engine API wire contract

**Scope** — `packages/beacon-node/src/execution/engine/sszRestEncoding.ts` (`PayloadStatusV1`, `ForkchoiceUpdatedResponseV1`, and status decoding) affects all SSZ-REST Engine calls that return payload status or forkchoice responses.

**Issue** — The adapter models fork-independent Engine response fields as nullable SSZ lists (`latestValidHash: List[Bytes32, 1]`, `payloadId: List[Bytes8, 1]`) and decodes only status bytes 0-3. The current SSZ-REST Engine API contract uses fixed sentinel-backed vectors for these fields (`latest_valid_hash: Bytes32`, `payload_id: Bytes8`) and reserves byte 4 for `INVALID_BLOCK_HASH`. Keeping a divergent local schema in the transport adapter creates a Lodestar-specific dialect at the package boundary rather than a faithful execution-apis contract.

**Impact** — Any EL that implements the spec wire shape will serialize these responses differently than Lodestar expects, so SSZ-REST interop breaks before method-level semantics are reached. More importantly architecturally, future fork/version additions now have to reconcile two sources of truth: execution-apis and this private set of containers.

**Recommendation** — Make the SSZ containers match the spec exactly, then translate the all-zero `Bytes32` / `Bytes8` sentinels to Lodestar's `null` domain representation at the decode boundary. Add `INVALID_BLOCK_HASH` to the shared status mapping. If these Engine SSZ schemas will grow with fork support, consider centralizing them beside the Engine type definitions or generated spec bindings rather than letting ad hoc containers accumulate in `http.ts`'s helper layer.

### 2. SSZ-REST bypasses the existing Engine endpoint abstraction and binds to only the first URL

**Scope** — `packages/beacon-node/src/execution/engine/http.ts:227` through `packages/beacon-node/src/execution/engine/http.ts:238`, plus the new `SszRestClient` transport path.

**Issue** — `ExecutionEngineHttp` receives an `IJsonRpcHttpClient` that already owns URL selection, retries, auth eventing, and health/fallback behavior for `opts.urls`, but the SSZ path constructs a separate `SszRestClient` from `opts.urls?.[0]`. Capability negotiation and JSON-RPC fallback still go through the JSON-RPC client, so the two transports no longer share one coherent endpoint model.

**Impact** — Multi-EL configurations can route JSON-RPC calls across the configured URL set while SSZ calls are pinned to the first URL only. If that URL is down, lacks SSZ support, or has different capabilities from a later fallback URL, Lodestar's behavior depends on which transport a method happened to use. Long-term, every Engine transport concern (endpoint selection, per-endpoint capabilities, auth, retry/fallback, metrics) has to be kept in sync in two places.

**Recommendation** — Put SSZ-REST behind the same endpoint-selection layer as JSON-RPC, or introduce an explicit Engine transport abstraction that owns per-endpoint capabilities and can choose an SSZ or JSON-RPC request for the same configured EL target. At minimum, negotiate and store SSZ capabilities per configured URL rather than globally from the JSON-RPC exchange result plus `urls[0]`.

### 3. GLOAS `targetGasLimit` derivation now has two competing sources of truth

**Scope** — `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts:688` through `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts:697`, and the existing payload-attribute helper at `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts:905` through `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts:956`.

**Issue** — `preparePayloadAttributes()` already owns fork-specific payload attribute assembly and sets both GLOAS-only fields, including `targetGasLimit`, through `getProposerTargetGasLimit()`. This PR then mutates the prepared attributes in `prepareExecutionPayload()` with a second helper, `getTargetGasLimit()`, that uses different parent lookup and fallback rules. `getPayloadAttributesForSSE()` still uses only `preparePayloadAttributes()`, so the Engine forkchoice payload attributes and SSE payload attributes can be derived through different algorithms.

**Impact** — The fork-specific `PayloadAttributesV4` contract becomes harder to reason about because the field is no longer assembled in one place. Future fixes to dependent-root selection, empty-parent fallback, or proposer preference lookup can easily update one helper but not the other, producing drift between the payload attributes Lodestar exposes and the payload attributes it sends to the EL.

**Recommendation** — Fold the parent-block-hash-aware lookup into the existing `preparePayloadAttributes()` / `getProposerTargetGasLimit()` path, passing `parentBlockHash` if that context is required. Both block preparation and SSE construction should call the same fork-aware helper, with no post-construction mutation of spec fields in `prepareExecutionPayload()`.
