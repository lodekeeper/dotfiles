# Review Findings — review-bugs — 8899

Reviewer: review-bugs
Reviewed commit: c99107c83538666d6e65da5597bee83b6a99798d
Generated at: 2026-08-05 21:14 UTC

Reviewer: review-bugs
Reviewed commit: c99107c83538666d6e65da5597bee83b6a99798d

## Findings

### packages/beacon-node/src/chain/archiveStore/utils/archiveBlocks.ts:81

Bug: Canonical hot blocks are migrated and deleted before non-canonical flat-file sidecars are cleaned up. A crash after `migrateBlocksFromHotToColdDb()` completes but before `flatFileStore.deleteNonCanonical()` runs leaves finalized-slot sidecar files for losing roots on disk. On restart, `FlatFileStore.init()` only removes slot directories with `slot > finalizedCheckpointSlot`, so those losing roots are cached permanently even though fork choice is rebuilt from the finalized anchor and no longer has the non-canonical roots needed to retry cleanup.

Impact: Finalized by-slot range serving can return no data when the stale losing root shares a slot with the canonical root, because the existence cache sees multiple roots and refuses to choose one. If the stale root is the only sidecar file for that finalized slot, the range handler can serve sidecars for a non-canonical block.

Fix: Move non-canonical flat-file sidecar deletion before any finalized block migration/deletion that can make the losing roots unrecoverable after restart, or make startup reconcile finalized flat-file roots against canonical block archive data and remove non-canonical roots before rebuilding the authoritative cache.

### packages/beacon-node/src/network/reqresp/handlers/dataColumnSidecarsByRange.ts:106

Bug: The finalized-range path passes `blockRoot` into `handleColumnSidecarUnavailability()` for slots that are already `<= archiveMaxSlot`. That helper treats a defined `blockRoot` as unfinalized and reads `db.block.getBinary(blockRoot)`, but archived finalized blocks live in `db.blockArchive` after `archiveBlocks()` runs.

Impact: When a recent finalized block is still in fork choice and expected custody columns are missing, the handler looks in the hot block DB, fails to load the block bytes, and returns before checking the blob count. Missing finalized custody columns are not recorded in metrics or logs, and post-Gloas finalized checks also bypass the envelope-archive guard.

Fix: Do not pass `blockRoot` for finalized-range unavailability handling, or extend the helper with an explicit finalized flag and read `blockArchive` for finalized slots while using the canonical root only for the flat-file lookup.
