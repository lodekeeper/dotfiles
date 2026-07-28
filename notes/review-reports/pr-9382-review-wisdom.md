# Review Findings — review-wisdom — 9382

Reviewer: review-wisdom
Reviewed commit: 3534a7aa12cbe756a6deef878b8c1c3c59d2dc0b
Generated at: 2026-07-28 12:52 UTC

## Findings

### 1. packages/beacon-node/src/execution/engine/sszRestEncoding.ts:439 — Principle: keep fork-specific wire shapes type-directed

Current: `buildPayloadAttributesValue()` returns `Record<string, unknown>`, and the public encoders then pass those values into SSZ containers with `as never` casts at every serialize call. This makes the most schema-sensitive part of the transport opt out of TypeScript's field-shape checks.

Suggested: Split the versioned value construction into small typed helpers for each SSZ container, or export/use a local typed value alias per container so the serializer receives a concrete payload shape without `as never`.

Why: The SSZ-REST encoder is where future fork fields will land first. Keeping the compiler involved here makes field additions/removals easier to review, easier to unit-test in isolation, and less dependent on readers mentally matching fork branches to SSZ container definitions.

### 2. packages/beacon-node/src/execution/engine/http.ts:319 — Principle: centralize repeated control flow for transport fallback

Current: Each Engine method open-codes the same SSZ-REST control flow: check configured client, build endpoint string, await capability negotiation, log unadvertised endpoint, try SSZ request, classify network errors, log fallback, and otherwise rethrow. The same pattern appears in `notifyNewPayload`, `notifyForkchoiceUpdate`, `getPayload`, payload-bodies calls, `getBlobs`, and client-version lookup.

Suggested: Extract a small helper around "try advertised SSZ endpoint, otherwise fall through to JSON-RPC" that takes the endpoint, route label, and SSZ operation callback. Keep method-specific encoding/decoding at the call site, but put capability/fallback/error logging in one place.

Why: The fallback policy is subtle and correctness-adjacent even when each call site currently works. One helper would make the intended policy obvious, reduce review surface for future Engine endpoints/forks, and prevent small drift in logging, capability checks, or network-error handling.
