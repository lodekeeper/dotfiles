Reviewer: review-bugs
Reviewed commit: 01fe150bed94361c8d5c979af58563c03c7a2027

## Findings

No functional bugs found in the follow-up delta.

## Focus Questions

1. Yes. The new head fixes the immediate-retry issue for peer-attributable EL `INVALID` results. `Batch.getFailedPeers()` now includes only `executionErrorAttempts` whose `peerAttributable` flag is true, while `routeProcessingFailure()` tags `EXECUTION_ENGINE_INVALID` / `PAYLOAD_ERROR_EXECUTION_ENGINE_INVALID` attempts as peer-attributable before storing them in `executionErrorAttempts`. Local `EXECUTION_ENGINE_ERROR` attempts remain retryable.

2. Yes. The new head preserves peer provenance across `retainForReprocessing()`. `downloadingSuccess()` now creates the `Attempt` before `successfulDownloads` is cleared, `startProcessing()` carries that attempt into `Processing`, and `retainForReprocessing()` carries the same attempt back to `AwaitingProcessing`. A later retained-byte validation failure therefore still has the original peer list.

3. I did not find a concrete regression in batch retry, provenance, or hash behavior. The normal processing path still uses the same successful-peer set, the retained/reprocessed path now keeps that attempt instead of rebuilding it from an empty `successfulDownloads`, and `hashBlocks()` now digests the exact allocated buffer. Because the buffer length is computed from the same fixed-size block/envelope entry count that advances `offset`, switching from `digest(buf.subarray(0, offset))` to `digest(buf)` does not add an unwritten tail.

## Verification

Static review of the provided follow-up artifacts:

- `/home/openclaw/.openclaw/workspace/notes/review-reports/pr-9667-followup/delta-ad32f53-to-01fe150.diff`
- `/home/openclaw/.openclaw/workspace/notes/review-reports/pr-9667-followup/delta-files.txt`
- `/home/openclaw/.openclaw/workspace/notes/review-reports/pr-9667-followup/batch-01fe150.ts`

I did not run the Lodestar test suite for this follow-up review.
