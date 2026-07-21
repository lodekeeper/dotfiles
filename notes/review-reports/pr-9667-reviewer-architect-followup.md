Reviewer: reviewer-architect
Reviewed commit: 01fe150bed94361c8d5c979af58563c03c7a2027

## Findings

No architectural concerns - changes align with existing patterns.

## Assessment

Carrying `Attempt` through `AwaitingProcessing`, `Processing`, `AwaitingValidation`, and `retainForReprocessing()` is consistent with the `Batch` state machine. The attempt represents the provenance and content id of the completed downloaded bytes, so creating it when `downloadingSuccess()` reaches a complete batch and carrying it across process/reprocess transitions is a better fit than rebuilding it from `successfulDownloads` at processing time. It keeps retry provenance internal to `Batch` and avoids adding coupling to `SyncChain` or the peer balancer.

Including only peer-attributable `executionErrorAttempts` in `getFailedPeers()` is the right boundary. `routeProcessingFailure()` remains the place that classifies local EL malfunction versus definitive `INVALID` verdicts, while `getFailedPeers()` remains the peer-selection exclusion API used by the balancer. Local `EXECUTION_ENGINE_ERROR` attempts stay blameless because they keep `peerAttributable: false`; definitive invalid payload/block attempts are excluded from immediate retry because they carry `peerAttributable: true`.

The follow-up does not introduce abstraction leakage in range sync retry/provenance handling. `Batch` still owns downloaded-byte provenance, failed-attempt accounting, and retry exclusion; `hashBlocks()` remains a range-sync utility for attempt identity; tests exercise the retained-provenance and EL-attribution boundaries without reaching through new public abstractions. The only residual type imprecision I noticed is the pre-existing `downloadingSuccess()` return cast, which can return an `AwaitingDownload` state while typed as `DownloadSuccessState`; this delta did not create that shape, and it is not an architectural blocker for the reviewed follow-up.

Relevant changed-file anchors:
- `packages/beacon-node/src/sync/range/batch.ts:70`
- `packages/beacon-node/src/sync/range/batch.ts:433`
- `packages/beacon-node/src/sync/range/batch.ts:613`
- `packages/beacon-node/src/sync/range/batch.ts:667`
- `packages/beacon-node/src/sync/range/batch.ts:707`
- `packages/beacon-node/src/sync/range/utils/hashBlocks.ts:29`
- `packages/beacon-node/test/unit/sync/range/batch.test.ts:653`
- `packages/beacon-node/test/unit/sync/range/batch.test.ts:901`
