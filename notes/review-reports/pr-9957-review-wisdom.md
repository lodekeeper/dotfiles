# PR #9957 review: "chore: remove blob related code" (wisdom / clean-code lens)

Reviewer: review-wisdom
Reviewed commit: 258d7d1ca8e6f170adc0c8c9330c07e1fd8a19c0

## Verdict on the regression question

**No concrete regression found for (a) post-fulu operation or (b) Gloas.**

What I checked, comparing PR head to `origin/unstable`:

- `api/impl/beacon/blocks/index.ts:133-153` publishBlockV2: the new `isDenebBlockContents && isForkPostFulu && !isForkPostGloas` branch matches the old fulu branch exactly. Gloas still gets `dataColumnSidecars = []`, and the post-publish gloas/fulu metric branches (`:384+`) are unchanged.
- `chain/blocks/verifyBlocksExecutionPayloads.ts:170-173`: versioned hashes are now computed from `body.blobKzgCommitments` instead of `BlockInputColumns.getVersionedHashes()`. For fulu blocks both come from the same commitments, so the value is identical. Gloas never gets here: `isBlockInputNoData` returns early at `:150`, and `isExecutionBlockBodyType` would also gate it.
- `chain/blocks/verifyBlocksDataAvailability.ts:45-50`: only changes `DAType.PreData` handling. Columns/NoData/OutOfRange paths are unchanged.
- `chain/seenCache/seenGossipBlockInput.ts:222-256`: branch order is still gloas -> NoData, fulu -> Columns, else PreData.
- `chain/GetBlobsTracker.ts:74-78`: post-fulu `BlockInputColumns` and `PayloadEnvelopeInput` still go to `getDataColumnSidecarsFromExecution`. The only change is that a non-columns `IBlockInput` (PreData, or a gloas `BlockInputNoData` if one ever reaches it) now returns early. Before, it was sent to a helper that immediately returned `PreFulu` and incremented `dataColumnEngineResult{result="pre_fulu"}`. That is a harmless metric difference, not a functional one.
- `sync/range/batch.ts:330-341`, `sync/utils/downloadByRange.ts:432-530`, `sync/utils/downloadByRoot.ts:194-235`: the column, envelope and parent-payload logic is the same once the blob arms are removed. The empty-`columns` guard and the gloas envelope-cache seeding (`downloadByRange.ts:162`) are kept.
- `chain/blocks/writeBlockInputToDb.ts:16-46`: the block write and the parallel column write are the same as before.
- Pure-deletion files: `git grep` on the head finds no remaining src references to `publishBlobSidecar`, `BlobSidecarsByRange/Root`, `GossipType.blob_sidecar`, `getBlobsV1`, `isBlockInputBlobs`, `DAType.Blobs` or `maxCachedBlobSidecars`. The CLI has no flag pointing at the removed chain option. Removed metrics (`beacon_get_blobs_v1_*`, `lodestar_gossip_blob_published_from_engine_total`, `lodestar_import_blobs_by_source_total`) are not used in any dashboard.

## Clean-code findings (non-blocking)

### W1. Use the existing commitments helper instead of a fork-seq check plus cast
- **File:Line**: `packages/beacon-node/src/chain/blocks/verifyBlocksExecutionPayloads.ts:170-173`
- **Severity**: low (maintainability)
- **Principle**: DRY, explicit over implicit
- **Current**: `ForkSeq[fork] >= ForkSeq.deneb ? (block.message.body as deneb.BeaconBlockBody).blobKzgCommitments.map(kzgCommitmentToVersionedHash) : undefined`. This hand-casts the body and adds a second way to read commitments by fork.
- **Suggested**: `isForkPostDeneb(fork) ? getBlobKzgCommitments(fork, block as SignedBeaconBlock<ForkPostDeneb>).map(kzgCommitmentToVersionedHash) : undefined`, reusing `util/dataColumns.ts:276`, which `writeBlockInputToDb.ts` and `gossipHandlers.ts` already use.
- **Why / scenario**: The `deneb.BeaconBlockBody` cast is only safe today because the NoData early return sits about 20 lines above it. If that guard is reordered, or a later fork moves commitments again (as gloas did into the bid), this line will read `undefined.map` and still type-check. The shared helper already knows where commitments live for each fork.

### W2. Put the type guard first in `triggerGetBlobs`, next to the right comment
- **File:Line**: `packages/beacon-node/src/chain/GetBlobsTracker.ts:72-78`
- **Severity**: low (readability)
- **Principle**: guard clauses first, fail fast
- **Current**: The comment "The request is sent right away, before block processing issues newPayload..." used to sit on the getBlobsV1 send block. It now sits on an early-return guard that sends nothing. The guard also runs after the `activeReconstructions` and `failedAttempts` checks, even though it is a pure type check.
- **Suggested**: Make `if (!(input instanceof PayloadEnvelopeInput) && !isBlockInputColumns(input)) return;` the first statement of `triggerGetBlobs`, and move the "sent right away" comment to the `getDataColumnSidecarsFromExecution(...)` call it describes.
- **Why / scenario**: A reader looking for where the request is sent "right away" lands on a `return`. A cheap guard at the top also keeps irrelevant inputs out of the retry bookkeeping.

### W3. The `PreFulu` guard and result are now duplicated
- **File:Line**: `packages/beacon-node/src/util/execution.ts:27,57-60` (with `GetBlobsTracker.ts:74`)
- **Severity**: low (maintainability)
- **Principle**: single source of truth, remove dead paths
- **Current**: `GetBlobsTracker` is the only caller of `getDataColumnSidecarsFromExecution`, and it now filters out non-column inputs itself. The helper's own `return DataColumnEngineResult.PreFulu` can no longer be reached, so the `pre_fulu` metric label is dead.
- **Suggested**: Keep the check in one place. Either drop the tracker guard and let the helper's result drive the metric as before, or narrow the helper's parameter to `BlockInputColumns | PayloadEnvelopeInput` and remove `PreFulu`.
- **Why**: Two copies of the same type gate tend to drift apart. Narrowing the parameter type also lets the compiler enforce the gate.

### W4. Blob-only metrics and a dashboard panel are left behind
- **File:Line**: `packages/beacon-node/src/metrics/metrics/lodestar.ts:1782` (`duplicateBlobCount`), `:1796` (`createdByBlob`). Panel: `dashboards/lodestar_beacon_chain.json:346` (`lodestar_seen_block_input_cache_duplicate_blob_total`)
- **Severity**: low (maintainability, observability noise)
- **Principle**: remove dead code along with the feature it served
- **Current**: Their only increment sites (`SeenBlockInput.getByBlob`) are deleted, but the metrics are still registered and still graphed.
- **Suggested**: Remove both counters and the `duplicate_blob_{{source}}` series from that panel in this PR, which already cleans up `lodestar_block_processor.json`.
- **Why**: Panels that are always zero look like a healthy signal when they are actually stale. (Separately, and pre-existing: `metrics.gossipBlob.*` is what the data column gossip handlers record into, at `gossipHandlers.ts:384,516`. Renaming that group is a reasonable follow-up, not this PR.)

### W5. `BlockInputPreData` now means "no tracked data" rather than "before data"
- **File:Line**: `packages/beacon-node/src/chain/blocks/blockInput/blockInput.ts:189-195`, `packages/beacon-node/src/chain/blocks/verifyBlocksDataAvailability.ts:45-50`
- **Severity**: info (naming)
- **Principle**: names should match semantics
- **Current**: `DAType.PreData` now covers phase0..electra, including the deneb/electra blocks that do carry blobs. Callers have to add a fork-seq check to map it back to `DataAvailabilityStatus` (`NotRequired` vs `PreData`).
- **Suggested**: Not blocking. If more call sites start needing that fork split, consider a helper such as `getPreFuluDaStatus(forkName)` next to the class, or a JSDoc on `DAType.PreData`, so the mapping lives in one place.
- **Why**: Keeps a type's meaning and its DA-status mapping together, so the next consumer doesn't have to rediscover the deneb split.

## AGENTS.md comment-policy check (new or changed comments)

Policy: zero comments by default, only non-obvious why, no restating code, no narrating the change, no em dash, no AI-slop phrasing.

| # | File:Line (PR head) | Comment | Issue | Suggested |
|---|---|---|---|---|
| C1 | `packages/beacon-node/src/sync/utils/downloadByRange.ts:163` | "...later step can throw and abort the batch — otherwise a gloas block would sit in..." | **Em dash** on a line this PR changed | Replace the em dash with "; otherwise" or ", otherwise" |
| C2 | `packages/beacon-node/src/chain/GetBlobsTracker.ts:76` | "// getBlobs from the execution engine is only supported for post-fulu data columns" | Restates the guard above it | Delete. If W2 is applied, the guard reads on its own |
| C3 | `packages/beacon-node/src/chain/blocks/blockInput/blockInput.ts:190` | "Pre-fulu BlockInput, it only has a single state." | Awkward comma splice, reads like generated text | "Pre-fulu BlockInput has a single state: the block exists." (merge with the `- the block simply exists` bullet) |
| C4 | `packages/beacon-node/src/sync/range/batch.ts:342` | "// dataSlot will still have a value but do not create a request for pre-fulu forks" | Trailing comment after the `if`, mostly restates the `isForkPostFulu` condition | Delete |
| C5 | `packages/beacon-node/test/utils/blocksAndData.ts:142` | "/** Build legacy deneb..electra blob sidecars for test fixtures */" | Restates the function name and location | Delete, or reduce to `/** Pre-fulu only */` if the fork range matters |
| C6 | `packages/beacon-node/src/sync/utils/downloadByRange.ts:436` | "// Blocks are always required for column validation" | Restates the error message thrown a few lines below ("No blocks to validate data requests against") | Delete this line and keep the two lines below it, which explain where blocks come from |

Comments that pass the policy (they explain a non-obvious why or an invariant): `api/impl/beacon/blocks/index.ts:133-134`, `chain/blocks/verifyBlocksDataAvailability.ts:46-47`, `chain/seenCache/seenGossipBlockInput.ts:67-70` (doc list update), `sync/range/batch.ts:161,226,334`, `test/spec/utils/specTestIterator.ts:94-96` (with issue link), `test/spec/presets/fast_confirmation.test.ts:330`, `test/spec/utils/forkChoiceTestRunner.ts:448`, `cli/test/utils/crucible/utils/syncing.ts:118-119`. `index.ts:139-140` was only moved, not added.

## Informational (not findings)

- `blob_sidecars_by_range/by_root` are no longer registered at all (`ReqRespBeaconNode.ts`), so peers get protocol negotiation failure instead of an empty response. That is fine on supported networks, where FULU_FORK_EPOCH + MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS has passed. On a fresh devnet with a non-zero fulu epoch and pre-fulu blob blocks, Lodestar would not serve blobs during the window. This is consistent with the stated "follow head from Fulu only" support policy.
- `routes.events.EventType.blobSidecar` is still defined in `packages/api/src/beacon/routes/events.ts:146` but is no longer emitted anywhere. Post-fulu it was not emitted before either, so nothing changes for current users.

Code quality is otherwise solid. The removal is thorough and the post-fulu and gloas paths are untouched apart from the simplifications noted above.
