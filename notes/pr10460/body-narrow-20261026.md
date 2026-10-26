**Motivation**

Follow-up to #10447. On `public-hoodi-hzax41-0`, a long-running supernode, LevelDB scans over legacy data column entries that were deleted long ago slowed both startup and every archive job:

- Startup stalled about 20 minutes after `Flat file store initialized`. The reverse lookup in bucket 58 took 712 s and the wipe scan of bucket 57 took 381 s, although both buckets had no live keys. Legacy column entries deleted while long archive scans held a snapshot had stayed in the bottom LevelDB level (224.8 GB). `compactRange` never rewrites the bottom level, so the compaction from #10447 was a no-op there.
- The legacy column prune runs `keys({lt: cutoff})` from the start of bucket 58 on every archive job. The bucket is not written since flat files and only shrinks from the front, so every prune walks all deleted entries LevelDB has not compacted.

**Description**

- At startup, before the first lookup into buckets 57 and 58, check the size of the hot column bucket plus the pruned part of the legacy column archive. Above 1 GiB, write a key at each end of the range, compact, and delete the keys again. That forces the bottom files to be rewritten. On hoodi-0 the same steps took 475 s once, cut the range from 224.8 GB to 0, and startup went from 20 min to 3 ms
- Add `pruneBefore(slot)` to the legacy data column archive repository. It resumes from the slot the previous prune ended at, and the first prune of a process compacts the range it deletes from

**AI Assistance Disclosure**

Written with AI assistance (Claude), including the investigation, implementation, tests and description.
