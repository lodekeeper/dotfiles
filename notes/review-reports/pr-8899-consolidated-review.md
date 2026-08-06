## Review — flat file storage for blobs and data columns (`c99107c8`)

Full pass over the new `flatFileStore` backend, the archive/migration path, and the reqresp range handlers. Nice work overall — atomic writes, the existence cache, and the Gloas EMPTY/FULL shared-root handling in `deleteNonCanonical` are all handled carefully. Three things worth a look, roughly in order of how much they matter. None are merge-blockers for a draft.

### 1. Crash between canonical migration and non-canonical sidecar deletion can permanently orphan sidecars at finalized slots

`archiveBlocks()` migrates + deletes canonical hot blocks first (`archiveBlocks.ts:81`), then deletes non-canonical flat-file sidecars (`archiveBlocks.ts:144`). The line-143 comment ("Delete sidecars first so their block roots remain available to retry cleanup after a failure or crash") covers the sidecar-vs-block ordering *within* the non-canonical cleanup — but there's a wider window between line 81 and line 144.

If the process crashes in that window (widened by the `persistOrphanedBlocks` disk loop when enabled), non-canonical sidecar files for losing roots at finalized slots stay on disk, and the retry doesn't happen on restart because:

- fork choice is rebuilt from the finalized anchor, so those sub-anchor losing roots are never re-imported → the next `archiveBlocks` run doesn't see them in `finalizedNonCanonicalBlocks`, so `deleteNonCanonical` is never called for them again;
- `FlatFileStore.init()` only removes slot dirs with `slot > finalizedCheckpointSlot` (`flatFileStore.ts:45-46`), so finalized-slot files are kept;
- `existenceCache.rebuildFromDisk()` re-registers every on-disk root, so the stale root re-enters the presence map.

Downstream this bites the by-slot serve path: `getDataColumnsBinaryBySlot` → `getUniqueColumnRootForSlot` returns a root only when exactly one is known (`existenceCache.ts:83`). A stale losing root sharing a finalized slot with the canonical root → the slot serves nothing; if the stale root is the *only* file there → it serves non-canonical columns. Narrow trigger (crash in-window + a reorged FULL block at/below the finalized slot), but the state is permanent once it lands.

Worth confirming the retry-on-restart assumption actually holds. If it doesn't, the robust fix is startup reconciliation — have `init()` keep only the canonical root per finalized slot (cross-referenced against `blockArchive`) rather than pruning purely by `slot > finalized`.

### 2. Finalized-boundary missing-column detection is routed to the hot block DB

In the finalized/archive loop, `handleColumnSidecarUnavailability` is called with `blockRoot: canonicalBlock ? fromHex(canonicalBlock.blockRoot) : undefined` (`dataColumnSidecarsByRange.ts:106`). For the boundary slots where fork choice still lists the block (`slot >= oldestForkChoiceSlot`), `canonicalBlock` is defined — but that block has already been migrated to `blockArchive` and deleted from hot db.

The helper does `blockRoot ? db.block.getBinary(blockRoot) : db.blockArchive.getBinary(slot)` (`dataColumnResponseValidation.ts:47`), so a defined root sends it to the hot DB, `getBinary` returns null, and it early-returns — `metrics.dataColumns.missingCustodyColumns` is never incremented and the log reads "unfinalized block not found." The post-Gloas envelope-archive guard just above is likewise gated on `blockRoot === undefined`, so it's skipped for the boundary case too.

Low impact (observability only — the available columns are still served correctly), but it means a genuine DA gap at the finalized-boundary slot is silently swallowed. An explicit `finalized` flag — or just not passing the root on the finalized path and reading `blockArchive` by slot — would fix it.

### 3. Fork-choice walk is materialized before the range needs it (perf / DoS hardening)

`onDataColumnSidecarsByRange` builds `getAllAncestorBlocks(head)` + the `canonicalBlocksBySlot` Map unconditionally (`dataColumnSidecarsByRange.ts:61-63`), before the `startSlot <= archiveMaxSlot` branch; same shape in `blobSidecarsByRange`. A peer requesting a single finalized slot still pays O(hot-fork-choice-window), and under prolonged non-finality that window is unbounded while the rate limiter only charges the requested sidecar count. Consider deferring the walk/Map until the request actually intersects the non-finalized range (or the bounded finalized-boundary window that needs root disambiguation), and serving purely-archived ranges straight from the slot cache.

Happy to dig into any of these deeper or open a follow-up if useful.
