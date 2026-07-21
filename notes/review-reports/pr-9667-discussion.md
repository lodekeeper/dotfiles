PR discussion coverage for ChainSafe/lodestar#9667
Fetched counts:
- Issue comments: 6
- Inline review comments: 8
- Review bodies: 5
Display limit: latest 20 per surface

Issue comments
- #5029826401 twoeths 2026-07-21T03:26:43Z
  https://github.com/ChainSafe/lodestar/pull/9667#issuecomment-5029826401
  @lodekeeper ready for another round of review
- #4989966692 github-actions[bot] 2026-07-21T03:22:27Z
  https://github.com/ChainSafe/lodestar/pull/9667#issuecomment-4989966692
  ## :warning: **Performance Alert** :warning:
  Possible performance regression was detected for some benchmarks.
- #5023143216 twoeths 2026-07-20T14:05:28Z
  https://github.com/ChainSafe/lodestar/pull/9667#issuecomment-5023143216
  I addressed your comments, please review again @lodekeeper
- #4998625049 twoeths 2026-07-17T03:14:56Z
  https://github.com/ChainSafe/lodestar/pull/9667#issuecomment-4998625049
  @lodekeeper please review
- #4998529001 codecov[bot] 2026-07-17T02:55:22Z
  https://github.com/ChainSafe/lodestar/pull/9667#issuecomment-4998529001
  ## [Codecov](https://app.codecov.io/gh/ChainSafe/lodestar/pull/9667?dropdown=coverage&src=pr&el=h1&utm_medium=referral&utm_source=github&utm_content=comment&utm_campaign=pr+comments&utm_term=ChainSafe) Report
  :white_check_mark: All modified and coverable lines are covered by tests.
- #4998525582 twoeths 2026-07-17T02:54:42Z
  https://github.com/ChainSafe/lodestar/pull/9667#issuecomment-4998525582
  Synced with this branch a couple of times on `feat3`, the last one was with 12h block range
  <img width="859" height="279" alt="Screenshot 2026-07-17 at 09 53 57" src="https://github.com/user-attachments/assets/3d7f81e2-b2f3-400e-8cad-42fad1de6e2b" />

Inline review comments
- #3615011881 lodekeeper 2026-07-20T14:25:07Z packages/beacon-node/src/sync/range/batch.ts:430
  https://github.com/ChainSafe/lodestar/pull/9667#discussion_r3615011881
  🔴 Peer-attributable EL `INVALID` attempts need to be excluded from immediate retry too. `routeProcessingFailure()` now marks `EXECUTION_ENGINE_INVALID` / `PAYLOAD_ERROR_EXECUTION_ENGINE_INVALID` attempts with `peerAtt...
  ```suggestion
- #3615011910 lodekeeper 2026-07-20T14:25:07Z packages/beacon-node/src/sync/range/batch.ts:707
  https://github.com/ChainSafe/lodestar/pull/9667#discussion_r3615011910
  🔴 `retainForReprocessing()` should preserve the current attempt's peer provenance. `startProcessing()` has already cleared `successfulDownloads`, and this transition keeps the retained blocks/envelopes while dropping ...
- #3600172356 lodekeeper 2026-07-17T03:25:28Z packages/beacon-node/src/sync/range/utils/hashBlocks.ts:29 reply-to=3594306888
  https://github.com/ChainSafe/lodestar/pull/9667#discussion_r3600172356
  The cheapness argument holds — `blockRootHex` is already cached, so this is strictly cheaper than the old `SignedBeaconBlock.hashTreeRoot` path.
  On signatures, I'd frame the risk differently than "same block with different signatures". BLS signing is deterministic, so an honest peer serving the same block message always produces the same signature — you're rig...
- #3600171697 lodekeeper 2026-07-17T03:25:19Z packages/beacon-node/src/sync/range/chain.ts:775 reply-to=3600093263
  https://github.com/ChainSafe/lodestar/pull/9667#discussion_r3600171697
  Confirmed, though I'd rank it below the P1. The strongest evidence is that the PR is internally inconsistent on this point: `shouldReportPeerOnBatchError` maps `MAX_EXECUTION_ENGINE_ERROR_ATTEMPTS → null` (*"If peer s...
  `onExecutionEngineError` only fires on `BlockErrorCode.EXECUTION_ENGINE_ERROR`, which is a local fault — the peer's data was never shown invalid, we just couldn't evaluate it.
- #3600171137 lodekeeper 2026-07-17T03:25:09Z packages/beacon-node/src/sync/range/utils/batches.ts:167 reply-to=3600093261
  https://github.com/ChainSafe/lodestar/pull/9667#discussion_r3600171137
  Confirmed — this is real, and I think it's blocking. Traced end to end:
  `classifyProcessingFault` returns `PreviousBatch` whenever `firstBlockSlot === batch.startSlot`, without ever checking `prevBatch`. For the first batch of a sync chain `prevBatch` is `undefined`, and then:
- #3600093261 chatgpt-codex-connector[bot] 2026-07-17T02:59:59Z packages/beacon-node/src/sync/range/utils/batches.ts:167
  https://github.com/ChainSafe/lodestar/pull/9667#discussion_r3600093261
  **<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub> Handle first-batch parent faults as unrecoverable here**
  When this is the first queued batch in a sync chain and its first block fails with `PARENT_UNKNOWN`/`PARENT_PAYLOAD_UNKNOWN`, `prevBatch` is `undefined` but this still returns `PreviousBatch`. `processBatch()` then ca...
- #3600093263 chatgpt-codex-connector[bot] 2026-07-17T02:59:59Z packages/beacon-node/src/sync/range/chain.ts:775
  https://github.com/ChainSafe/lodestar/pull/9667#discussion_r3600093263
  **<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub> Keep execution-engine failures out of peer scoring**
  Including `executionErrorAttempts` here can downscore peers after transient local EL failures: `Batch.processingError()` records `EXECUTION_ENGINE_ERROR` separately via `onExecutionEngineError()`, and teardown intenti...
- #3594306888 twoeths 2026-07-16T09:42:17Z packages/beacon-node/src/sync/range/utils/hashBlocks.ts:29
  https://github.com/ChainSafe/lodestar/pull/9667#discussion_r3594306888
  hashing blocks + envlopes are cheap enough thanks to `cachePermanentRootStruct` option
  the downside is we don't include signatures, haven't seen an issue of same block with different signatures for range sync on any networks yet

Review bodies
- #4735819786 lodekeeper 2026-07-20T14:25:07Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9667#pullrequestreview-4735819786
  Anchoring the two open follow-up issues inline.
- #4735797009 lodekeeper 2026-07-20T14:22:33Z state=CHANGES_REQUESTED
  https://github.com/ChainSafe/lodestar/pull/9667#pullrequestreview-4735797009
  Reviewed the updated head `ad32f53a527637cdf1dec599e56b32f1f6c273b9`. The original first-batch `PARENT_UNKNOWN`/`PARENT_PAYLOAD_UNKNOWN` stall looks fixed now: the no-previous-batch path records an attempt and can tea...
  I do still see two retry/scoring issues that are worth fixing before merge:
- #4719123078 lodekeeper 2026-07-17T03:25:46Z state=CHANGES_REQUESTED
  https://github.com/ChainSafe/lodestar/pull/9667#pullrequestreview-4719123078
  Reviewed on request. The fault-localization idea is a clear improvement over tearing the whole chain down on any processing error, and splitting the boundary `PARENT_PAYLOAD_UNKNOWN` from the new mid-segment `NON_LINE...
  Requesting changes on one confirmed liveness bug. Details in-thread; summarising here plus one cross-cutting note.
- #4719031110 chatgpt-codex-connector[bot] 2026-07-17T02:59:58Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9667#pullrequestreview-4719031110
  ### 💡 Codex Review
  Here are some automated review suggestions for this pull request.
- #4711935075 gemini-code-assist[bot] 2026-07-16T08:40:23Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9667#pullrequestreview-4711935075
  ## Code Review
  This pull request introduces fault localization for sync batch processing errors to avoid tearing down the entire sync chain on any error. It adds a classification mechanism (`classifyProcessingFault`) to determine if...
