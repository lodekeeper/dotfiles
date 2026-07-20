# Security Review Findings

Reviewer: review-security
Reviewed commit: ad32f53a527637cdf1dec599e56b32f1f6c273b9

## Findings

### 1. Peer-attributable INVALID payload attempts are still eligible for immediate retry

`Batch.routeProcessingFailure()` stores `EXECUTION_ENGINE_INVALID` / `PAYLOAD_ERROR_EXECUTION_ENGINE_INVALID` attempts in `executionErrorAttempts` with `peerAttributable: true`, but `getFailedPeers()` only returns download failures and `failedProcessingAttempts`. Because range retry peer selection excludes peers through `getFailedPeers()`, a peer that just served a definitively invalid payload remains eligible for the same batch. That peer can be selected repeatedly, consume `MAX_BATCH_PROCESSING_ATTEMPTS`, and tear down the `SyncChain` even when other peers could have supplied the valid batch.

Relevant code: `packages/beacon-node/src/sync/range/batch.ts:429` and `packages/beacon-node/src/sync/range/batch.ts:759`

Suggested fix: include only peer-attributable `executionErrorAttempts` in `getFailedPeers()` so local EL errors remain blameless, but definitive invalid payload senders are avoided on retries.

### 2. Retained batches lose peer provenance before signature failures are scored

When a batch is classified as `PreviousBatch`, `retainForReprocessing()` moves it back to `AwaitingProcessing` without preserving the current `attempt`, and `startProcessing()` has already cleared `successfulDownloads`. On the later reprocess, `startProcessing()` builds a new attempt with an empty peer list. If the retained bytes then fail with `INVALID_SIGNATURE` or a forged envelope signature after the previous batch is repaired, the new signature-inclusive attempt hash differs from the eventual honest attempt, but there are no peers to report.

Relevant code: `packages/beacon-node/src/sync/range/batch.ts:663` and `packages/beacon-node/src/sync/range/batch.ts:704`

Suggested fix: carry the original attempt/peer provenance across `retainForReprocessing()` so any later peer-attributable failure of the retained data can still be scored.

## Notes

I did not find a remaining first-batch parent/payload fault that would silently stall forever; the first-batch `PARENT_UNKNOWN` / `PARENT_PAYLOAD_UNKNOWN` no-previous-batch path now records attempts and eventually tears down instead of retaining with nothing to invalidate.
