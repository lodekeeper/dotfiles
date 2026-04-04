# Feature: GET Signed Execution Payload Envelope API

## Problem
Beacon API v5.0.0-alpha.1 defines a GET endpoint for retrieving a signed execution payload envelope by block id:

`GET /eth/v1/beacon/execution_payload_envelope/{block_id}`

Unstable currently supports only POST publish:
- `POST /eth/v1/beacon/execution_payload_envelope`

But it is missing the GET retrieval endpoint.

## Spec Reference
beacon-APIs v5.0.0-alpha.1 `apis/beacon/execution_payload/envelope_get.yaml`
- operationId: `getSignedExecutionPayloadEnvelope`
- Returns JSON or SSZ depending on `Accept` header
- Response body:
  - `version: "gloas"`
  - `execution_optimistic`
  - `finalized`
  - `data: Gloas.SignedExecutionPayloadEnvelope`
- `404` if envelope not found
- `406` for unsupported Accept

## Current State on Unstable
- Route definitions file: `packages/api/src/beacon/routes/beacon/block.ts`
- Beacon API impl: `packages/beacon-node/src/api/impl/beacon/blocks/index.ts`
- Chain already exposes helper: `chain.getSerializedExecutionPayloadEnvelope(blockSlot, blockRootHex): Promise<Uint8Array | null>`
- Chain can already resolve block response / optimistic / finalized metadata via existing block helpers

## Approach

### Route definition
Add a new endpoint next to `publishExecutionPayloadEnvelope` in `packages/api/src/beacon/routes/beacon/block.ts`:
- name: `getExecutionPayloadEnvelope`
- method: `GET`
- URL: `/eth/v1/beacon/execution_payload_envelope/{block_id}`
- req: reuse `blockIdOnlyReq`
- resp:
  - `data: ssz.gloas.SignedExecutionPayloadEnvelope`
  - `meta: ExecutionOptimisticFinalizedAndVersionCodec`

No special request wire format needed. SSZ response should work automatically via `Accept: application/octet-stream` and `context.returnBytes` in the impl.

### Impl
Add `async getExecutionPayloadEnvelope({blockId}, context)` in `packages/beacon-node/src/api/impl/beacon/blocks/index.ts`.

Implementation shape:
1. Resolve block + metadata via existing `getBlockResponse(chain, blockId)` helper
2. Check fork is post-Gloas; if not, return 404 (or maybe 400?) — spec says envelope not found, so 404 is cleaner
3. Compute block root from resolved block
4. If `context.returnBytes`:
   - call `chain.getSerializedExecutionPayloadEnvelope(block.message.slot, blockRootHex)`
   - if null → 404
   - return bytes directly with meta `{version: "gloas", executionOptimistic, finalized}`
5. Else JSON path:
   - still get bytes via `getSerializedExecutionPayloadEnvelope(...)`
   - deserialize with `ssz.gloas.SignedExecutionPayloadEnvelope.deserialize(bytes)`
   - return object with same meta

### Why use bytes helper for both paths?
- Avoids needing a second chain accessor
- Ensures hot-cache / hot-db / archive-db lookup logic stays centralized in chain
- Keeps JSON + SSZ retrieval behavior consistent

## Files to Modify
1. `packages/api/src/beacon/routes/beacon/block.ts`
2. `packages/beacon-node/src/api/impl/beacon/blocks/index.ts`
3. Possibly route tests / API tests if present

## Edge Cases
- Pre-Gloas block id → 404 envelope not found
- Known block but no stored envelope → 404
- Accept octet-stream → bytes response, same metadata headers
- Accept json → deserialized object, same metadata headers
- `head` block id should work if current head block has envelope stored
- Archive path should work for finalized blocks via `executionPayloadEnvelopeArchive`

## Test Plan
- JSON success path returns envelope + version=gloas + optimistic/finalized meta
- SSZ success path returns bytes and matching version header
- 404 when block exists but envelope missing
- 404 for pre-Gloas block
- `head` / numeric slot / root lookup path at least one coverage depending on existing test harness

## Acceptance Criteria
- [ ] GET endpoint exists at spec path
- [ ] JSON and SSZ response negotiation works
- [ ] Reuses existing chain lookup helper
- [ ] 404 behavior correct for missing envelope
- [ ] Version header/meta set to gloas
