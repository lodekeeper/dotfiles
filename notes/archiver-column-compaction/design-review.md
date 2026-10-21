# Design review

Verdict: approve the two-part minimal design, with the test qualifications below.

## Source-verified rationale

- `BeaconNode.init` awaits `db.init()` and `db.pruneHotDb()` before runtime processing. `BeaconDb.pruneHotDb` already deletes the entire legacy hot column bucket. `LegacyDataColumnStore.putManyBinary` writes only flat files. A repository-wide source search found no production writers to the old hot repository. Removing canonical migration therefore does not change supported normal startup/upgrade behavior.
- Cold archive fallback must remain. `LegacyDataColumnStore` verifies the root-to-slot mapping using `blockArchive.getSlotByRoot` before slot-keyed archive reads. Preserve `dataColumnSidecarArchive`, `lastLegacyArchiveSlot`, its initialization, and retention pruning.
- Delete only the canonical migration call and helper. `fromAsync` becomes unused. `ProtoBlock`, `getBlobDataRetentionStartEpoch`, `finalizedPostFulu`, `PayloadStatus`, and `ForkSeq` all have other uses and must remain.
- `Db` aliases `DatabaseController<Uint8Array, Uint8Array>`. Add required `compactRange(start: K, end: K): Promise<void>` to the generic interface. The only concrete implementation found is `LevelDbController`, which already implements the method. Type checking still needs to catch structural mocks or stubs.
- The existing controller documents compaction as inclusive `[start..end]`. Ending at `encodeKey(58, empty)` can include that prefix sentinel, but real archived column keys append slot/index bytes and are strictly greater. Compaction does not delete logical records anyway and may rewrite overlapping SST files beyond the requested key interval. Do not describe the operation as physically isolated to bucket 57.
- Await compaction after `deleteBucketData(57)` resolves, unconditionally even when enumeration is empty. This covers databases pruned before this fix. It runs on every startup, not literally once; no marker is necessary for this scoped patch. It can add startup latency and does not guarantee immediate removal of every tombstone under snapshots. Make no exact performance or physical reclamation claims.

## Smallest sufficient implementation and test set

1. Three production files: `archiveBlocks.ts`, `db/beacon.ts`, and `db/controller/interface.ts`. Add a brief rationale for unconditional compaction so a future empty-bucket optimization does not undo it.
2. Extend the existing real-LevelDB `BeaconDb.pruneHotDb` test for 0/1/8 roots. Spy with real compaction passthrough. Assert exact lower/upper encoded boundaries and one call; at invocation assert bucket 57 is empty and batch deletion has finished. Existing cold-column, cold-blob, block, and flat-file preservation assertions are useful. Add an actually pre-existing tombstone case: write then delete legacy columns before invoking prune, so enumeration is already empty, and assert compaction still runs.
3. With the current one-batch inputs, assertions cannot detect compaction incorrectly placed inside a multi-batch delete loop. Prefer one additional case with >1000 keys (e.g. enough roots for 1001+ columns), or deliberately controlled deferred deletion assertions that prove compaction waits for the returned promise. Avoid sleep/timing-based tests.
4. Replace legacy-migration expectations in the existing archiver tests with Fulu and Gloas regressions: canonical processing must not invoke legacy `valuesStreamBinary`, `deleteMany`, or archive `putManyBinary`; blocks still archive, including the already-archived boundary behavior. Use no noncanonical blocks in these negative-call cases, since noncanonical cleanup legitimately calls legacy `deleteMany` through `dataColumns.deleteMany`.
5. Preserve existing noncanonical FULL/EMPTY and retention tests. For the claim that canonical flat columns remain serveable, add a real `BeaconDb` archiver regression with a stored flat column and call `dataColumns.getManyBinary` or `getAll` after archiving. A mocked `dataColumns.deleteMany` negative assertion alone proves routing, not continued serving. Keep current `dataColumnStore` cold-fallback tests unchanged and run them as the supporting upgrade regression.

Run targeted beacon prune, block archiver, and dataColumnStore tests, plus full lint and types required by repository/workspace policy. No benchmark or wall-clock assertion is needed.
