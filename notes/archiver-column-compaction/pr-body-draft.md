## Problem

Data columns are written to flat files since #8899, and #10223 clears the legacy hot-column bucket during startup. The archiver still scans that bucket for every finalized canonical block. After bulk deletion, repeated scans over LevelDB tombstones can stall block archiving even when no columns are migrated.

## Changes

- Remove the obsolete canonical hot-to-cold data-column migration.
- Await compaction of the legacy hot-column range after startup deletion, including when the bucket is already empty from an earlier startup.
- Preserve legacy cold-column reads, flat-file storage, retention pruning, and noncanonical cleanup.

A restart on the fixed build performs the compaction automatically; a separate manual compaction is not required for this fix. Startup compaction can take time depending on the existing database.

## Validation

Pending local regression and lint/type checks.

## Spec compliance

Not applicable: internal database maintenance and removal of an obsolete migration. No consensus transition or wire-format changes.

Written with AI assistance.
