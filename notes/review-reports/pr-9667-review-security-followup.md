# Security Review Findings

Reviewer: review-security
Reviewed commit: 01fe150bed94361c8d5c979af58563c03c7a2027

## Scope

Follow-up delta from `ad32f53a527637cdf1dec599e56b32f1f6c273b9` to `01fe150bed94361c8d5c979af58563c03c7a2027`, limited to:

- `packages/beacon-node/src/sync/range/batch.ts`
- `packages/beacon-node/src/sync/range/utils/hashBlocks.ts`
- `packages/beacon-node/test/unit/sync/range/batch.test.ts`

Security focus: adversarial peer retry behavior, retained-byte provenance, DoS, peer manipulation, validation bypass, and scoring evasion.

## Findings

No security issues found in the follow-up delta.

## Focus Questions

1. Malicious-peer immediate retry after peer-attributable `EXECUTION_ENGINE_INVALID`: fixed.

   `Batch.getFailedPeers()` now includes `executionErrorAttempts` only when `peerAttributable` is true (`batch.ts:427-438`). Since the retry selector excludes `batch.getFailedPeers()` before choosing another peer, a peer that served definitively invalid execution data is no longer immediately eligible for the same batch retry. Local EL failures remain retryable because non-attributable execution attempts are still excluded from `getFailedPeers()`.

2. Peer provenance across `retainForReprocessing()`: preserved.

   The attempt is now created when the batch first becomes `AwaitingProcessing`, before `successfulDownloads` is cleared (`batch.ts:613-619`). `startProcessing()` reuses that attempt and returns its peers (`batch.ts:676-680`), and `retainForReprocessing()` carries the same attempt back into `AwaitingProcessing` (`batch.ts:712-717`). Later `processingError()` / `validationError()` route the preserved attempt into scoring state (`batch.ts:723-739`, `batch.ts:756-767`), so retained bad bytes still carry the original peer set.

3. New DoS, peer manipulation, validation bypass, or scoring evasion risk: none found.

   Moving attempt hashing from `startProcessing()` to full download completion does not skip validation; blocks and payload envelopes still pass through `processChainSegment`. The hash work remains bounded by batch size. The `hashBlocks()` change to digest the entire buffer is safe because the buffer is allocated to the exact serialized size and all entries are written (`hashBlocks.ts:39-59`). The added tests cover retained-peer attribution and attributable EL-invalid retry exclusion (`batch.test.ts:653-685`, `batch.test.ts:901-930`).

## Residual Notes

The batch attempt model still attributes a failed full-batch attempt to all peers that contributed successful sub-downloads, rather than per-byte/per-column provenance. That behavior predates this follow-up and is not introduced by the reviewed delta.
