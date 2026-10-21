# Hoodi archiver stall after manual compaction

Source: Adrian (abienkow), Discord #lodestar-private, 2026-10-20 21:31 UTC, message1562216686013259827; diagnostic post1562216467963973776.

## Observed versus inferred

- Adrian reports bucket57 compaction333ms, buckets57+58 compaction27.9s, followed by a persistent epoch131029 archiver stall after `Migrated blobSidecars`. One libuv worker has accumulated CPU and was observed in D state; no recent bucket57/58 metric activity. No live host access or native capture supplied to this investigation.
- Downloaded the attached CPU profile using its Discord attachment URL (curl; urllib received403). Kept original bytes in `main_thread.cpuprofile`. Weighted `samples` by `timeDeltas`: duration31.354745s, sampled time31.354513s, idle90.3747%. Unweighted sample count would misleadingly give94.7%. No sampled archive/iterator frame; one classic-level `_put` node has zero self time.
- This supports investigating asynchronous/native work, not a JS CPU loop. It does not identify which native operation belongs to the pending archive promise, nor prove a deadlock or disk fault.

## Source verification

Read local v1.50.0 tag ba0d575a0527ef4c39b29691c519429fb3f0e021; main checkout has unrelated untracked work and was not changed.

1. `packages/beacon-node/src/chain/archiveStore/utils/archiveBlocks.ts:136–153`: after blob migration log, post-Fulu canonical work enters `migrateDataColumnSidecarsFromHotToColdDb`. Its qualifying blocks await `fromAsync(db.dataColumnSidecar.valuesStreamBinary(root))`; each batch also awaits `db.dataColumnSidecar.deleteMany(...)`. Empty streams do not establish cheap seeks.
2. `packages/db/src/abstractPrefixedRepository.ts`: valuesStreamBinary wraps entriesStream with root-prefixed bounds. deleteMany first enumerates keys for each root, then submits a batch deletion.
3. `packages/db/src/controller/level.ts:198–222`: metricsAll/metricsIterator increment read requests once at entry; read items only after full completion. A request started before a60s window can be stuck with zero rate and zero returned-item increments. Metrics are logical requests/results, not physical SST reads or tombstones traversed. Bucket labels are names, not numeric IDs.
4. classic-level1.4.1 `binding.cc`: NextWorker invokes SeekToRange and ReadMany asynchronously. SeekToRange first calls LevelDB Seek; the binding checks the upper bound afterwards in Valid(). A query's logical bucket does not bound all native seek work.
5. Bundled LevelDB1.20 `db/db_iter.cc`: DBIter::FindNextUserEntry skips tombstones/hidden versions until a live user entry or end. POSIX `util/env_posix.cc` defaults to mmap for up to1000 files on64-bit. SST page faults can cause I/O without read/pread64 syscalls; a quiet strace is not proof of no DB reading.

## Diagnostic recommendation

Use the HOST TID of the busy libuv-worker belonging to the actual Node process (not a container-namespace TID or tini PID). As an account already permitted to inspect that process:

```bash
ps -L -p "$BEACON_PID" -o tid,pcpu,stat,wchan:30,comm
perf record -e cpu-clock -F 99 -t "$BEACON_TID" --call-graph dwarf -o /tmp/archiver-native.perf -- sleep 15
perf report --stdio -i /tmp/archiver-native.perf
```

Native iterator frames (`NextWorker`, `DBIter::Seek`, `DBIter::FindNextUserEntry`) distinguish a scanning path from write/compaction (`DBImpl::Write`, `MakeRoomForWrite`) or filesystem work. These are candidates to look for, not a guarantee of available symbols. CPU-clock sampling only captures on-CPU activity; few samples require off-CPU evidence, not a deadlock conclusion.

Optional paired syscall capture (briefly attaches, bounded15s):

```bash
timeout -s INT 15s strace -ttT -yy -p "$BEACON_TID" -e trace=pread64,read,write,pwrite64,fdatasync,fsync,futex -o /tmp/archiver-native.strace
```

Slow SST reads, sync waits and futex waits discriminate mechanisms; mmap caveat applies. Resolved paths/mappings can also verify the live DB matches the manually compacted mount. Use kernel wchan/stack evidence if mostly blocked; that may require the host operator's existing privileges.

## Outcome and limits

Earlier local tombstone reproduction remains a real performance issue addressed by PR10447, but it is NOT a confirmed cause of this live stall after manual compaction. Do not suggest more compaction/restarts without native evidence. Beacon image/version confirmation was requested and remains pending; source-specific conclusions are conditional on stockv1.50.0. No host actions, DB changes, deployment, new source patch or GitHub write performed.

Independent native reviewer approved source interpretation and command syntax, including perf --dry-run validation. Final response reviewed before delivery.
