@nflaig Narrowed in 0cb644cd06. The PR no longer touches blob code. dfdc06439d is reverted along with the earlier blob guard and prune changes, so the archiver's blob sidecar handling is the same as on unstable. What's left is the startup sentinel compaction of the legacy column range and `pruneBefore` on the legacy column archive. Title and description are updated.

#9957 has no file overlap with this PR. It doesn't touch `archiveBlocks.ts` or the blob archive repository, so the archiver's blob migration and prune calls remain after it lands. They can go with the rest of the blob cleanup.
