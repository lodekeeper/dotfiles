Reviewer: review-bugs
Reviewed commit: ad32f53a527637cdf1dec599e56b32f1f6c273b9

## Findings

No functional bugs found in the reviewed areas.

The updated range-sync fault attribution now treats `PARENT_UNKNOWN` and `PARENT_PAYLOAD_UNKNOWN` at the first queued batch boundary as this-batch failures when there is no previous batch to invalidate, and `SyncChain` also falls back to `processingError()` if previous-batch invalidation is a no-op. This addresses the prior stall scenario.

Execution-engine failures are now split into local/no-verdict errors and definitive invalid verdicts. `EXECUTION_ENGINE_ERROR` / `PAYLOAD_ERROR_EXECUTION_ENGINE_ERROR` attempts are retained as non-peer-attributable and do not trigger teardown downscoring, while `EXECUTION_ENGINE_INVALID` / `PAYLOAD_ERROR_EXECUTION_ENGINE_INVALID` can still downscore only the peers that served those attempts.

`hashBlocks()` now hashes fixed-size entries containing each block message root plus proposer signature, and each available Gloas payload-envelope message root plus envelope signature, so signature-only corruption changes the attempt id for both blocks and payload envelopes.

## Verification

Ran targeted unit coverage:

```text
pnpm vitest run --project unit packages/beacon-node/test/unit/sync/range/utils/hashBlocks.test.ts packages/beacon-node/test/unit/sync/range/utils/batches.test.ts packages/beacon-node/test/unit/sync/range/batch.test.ts packages/beacon-node/test/unit/sync/range/chain.test.ts packages/beacon-node/test/unit/chain/blocks/utils/chainSegment.test.ts
```

Result: 5 test files passed, 98 tests passed. The command emitted Node engine warnings because this environment is using Node v22.19.0 while the repo requests ^24.13.0.
