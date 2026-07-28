# Review Findings — review-bugs — 9382

Reviewer: review-bugs
Reviewed commit: 3534a7aa12cbe756a6deef878b8c1c3c59d2dc0b
Generated at: 2026-07-28 13:01 UTC

## Findings

1. **packages/beacon-node/src/execution/engine/http.ts:812** — SSZ `getBlobsV1` misassigns compact partial responses by index.

   **Bug:** The v1 SSZ response decoder returns a flat list of found blobs, then this line pads it against the original request positions with `found[i] ?? null`. For a request like `[A, B, C]` where the EL has only `A` and `C`, the flat response `[A, C]` is decoded as `[A, C, null]`; the blob/proof for `C` is treated as the response for missing `B` because `BlobAndProofV1` carries no versioned hash or availability marker.

   **Impact:** The pre-Fulu engine-fetch path can add and publish a blob sidecar at the wrong blob index. If the remaining blobs arrive later, Lodestar can mark the block's blob data available while one cached engine sidecar does not correspond to the block commitment/versioned hash at that index, producing incorrect local DA accounting and bad sidecars on gossip.

   **Fix:** Do not positionally pad compact v1 SSZ responses. Either use a response shape with per-request availability/nullability, or only accept SSZ v1 responses whose decoded length exactly matches the request length; when it is shorter, fall back to JSON-RPC `engine_getBlobsV1` so the exact null positions are preserved, or treat the whole response as unavailable.
