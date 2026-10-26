fix: avoid slow LevelDB scans over deleted blob and column entries
----
**Motivation**

Follow-up to #10447. Long-running supernodes spend minutes to hours in LevelDB scans over entries that were deleted long ago:

- On `public-hoodi-hzax41-0` each archive job took about 1h45m. Both prunes run `keys({lt: cutoff})` from the start of their bucket on every job. The blob sidecar archive is not written after fulu and the legacy column archive is not written since flat files, so both buckets only shrink from the front and every scan walks all deleted entries LevelDB has not compacted.
- The same node stalled about 20 minutes on every startup after `Flat file store initialized`. The reverse lookup in bucket 58 took 712 s and the wipe scan of bucket 57 took 381 s, although both buckets had no live keys. Legacy column entries deleted while long archive scans held a snapshot had stayed in the bottom LevelDB level (224.8 GB), and `compactRange` never rewrites the bottom level, so the compaction from #10447 was a no-op there.

**Description**

- Stop migrating, pruning and deleting blob sidecars in the block archiver. Pre-fulu blob sidecars are past their retention window on every network, so these steps only walked deleted entries
- Add `pruneBefore(slot)` to the legacy data column archive repository. It resumes from the slot the previous prune ended at, and the first prune of a process compacts the range it deletes from
- At startup, before the first lookup into buckets 57 and 58, check the size of the hot column bucket plus the pruned part of the legacy column archive. Above 1 GiB, write a key at each end of the range, compact, and delete the keys again. That forces the bottom files to be rewritten. On hoodi-0 the same steps took 475 s once, cut the range from 224.8 GB to 0, and startup went from 20 min to 3 ms

**AI Assistance Disclosure**

Written with AI assistance (Claude), including the investigation, implementation, tests and description.

