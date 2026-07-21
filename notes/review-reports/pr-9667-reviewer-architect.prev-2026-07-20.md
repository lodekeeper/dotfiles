Reviewer: reviewer-architect
Reviewed commit: ad32f53a527637cdf1dec599e56b32f1f6c273b9

## Findings

### P1 - Definitively invalid EL attempts are still eligible for immediate retry from the same peer

`Batch.routeProcessingFailure()` correctly marks `EXECUTION_ENGINE_INVALID` as `peerAttributable: true`, but those attempts are stored in `executionErrorAttempts`. `Batch.getFailedPeers()` only returns failed downloads and `failedProcessingAttempts`, so the batch's failed-peer set does not include peers from definitively invalid execution attempts. As a result, a peer that served a payload/block that the EL rejected as `INVALID` can be eligible for the next retry. Range sync can keep selecting the same bad peer until `MAX_EXECUTION_ENGINE_ERROR_ATTEMPTS` tears the chain down, even when another peer could have supplied valid data.

The local-EL-error path should remain retryable, but peer-attributable execution attempts should participate in `getFailedPeers()` or an equivalent retry-exclusion path.

References:
- `packages/beacon-node/src/sync/range/batch.ts:429`
- `packages/beacon-node/src/sync/range/batch.ts:752`

## Notes

The broader shape looks coherent: parent-boundary errors are separated from internal segment faults, `BlockError` and `PayloadError` now distinguish local EL failures from definitive invalid verdicts, gossip scoring follows that split, and `hashBlocks()` now covers block and envelope signatures with `ExecutionPayloadEnvelope` permanent-root caching enabled.
