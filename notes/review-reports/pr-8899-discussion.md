PR discussion coverage for ChainSafe/lodestar#8899
Fetched counts:
- Issue comments: 4
- Inline review comments: 22
- Review bodies: 3
Display limit: latest 20 per surface

Issue comments
- #3893812751 github-actions[bot] 2026-08-04T20:29:16Z
  https://github.com/ChainSafe/lodestar/pull/8899#issuecomment-3893812751
  ## Performance Report
  ✔️ no performance regression detected
- #3965027169 twoeths 2026-02-26T08:42:13Z
  https://github.com/ChainSafe/lodestar/pull/8899#issuecomment-3965027169
  > > Store all DataColumnSidecars per block
  >
- #3958316872 nflaig 2026-02-25T10:35:05Z
  https://github.com/ChainSafe/lodestar/pull/8899#issuecomment-3958316872
  > Store all DataColumnSidecars per block
  leaning towards this and mitigate cons by implementing `fd.read()` with offset/length
- #3893724238 gemini-code-assist[bot] 2026-02-12T22:25:45Z
  https://github.com/ChainSafe/lodestar/pull/8899#issuecomment-3893724238
  ## Summary of Changes
  Hello @wemeetagain, I'm Gemini Code Assist[^1]! I'm currently reviewing this pull request and will post my feedback shortly. In the meantime, here's a summary to help you and other reviewers quickly get up to speed!

Inline review comments
- #3715946086 wemeetagain 2026-08-04T20:29:33Z packages/beacon-node/src/db/flatFileStore/existenceCache.ts:30 reply-to=2801370208
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r3715946086
  Uses fork choice for finalized data now
- #3715941478 wemeetagain 2026-08-04T20:28:54Z packages/beacon-node/src/chain/chain.ts:809 reply-to=2801370204
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r3715941478
  no fallback
- #3715916310 lodekeeper 2026-08-04T20:24:54Z packages/beacon-node/src/chain/blocks/writeBlockInputToDb.ts:101 reply-to=3715553403
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r3715916310
  Checked this on current head: the flat-file path still batches the whole custody-column set in one call via `putDataColumnsBinary(slot, root, binaryColumns)`. That flows into `ColumnStore.putColumnsBinary(...)`, which...
- #3715916313 lodekeeper 2026-08-04T20:24:54Z packages/beacon-node/src/chain/blocks/writeBlockInputToDb.ts:60 reply-to=3715522784
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r3715916313
  Done in 5804ec1af3: `writeBlockInputToDb` now passes the `blobSidecars` value directly to `flatFileStore.putBlobSidecars(...)`, and `FlatFileStore` owns the wrapper serialization internally.
- #3715916315 lodekeeper 2026-08-04T20:24:54Z docs/design-flat-file-storage.md:1 reply-to=3715502860
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r3715916315
  Done in 5804ec1af3: the standalone design doc was removed from the PR.
- #3715916325 lodekeeper 2026-08-04T20:24:54Z packages/beacon-node/src/db/flatFileStore/atomicWrite.ts:1 reply-to=3715568702
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r3715916325
  Done in 5804ec1af3: `atomicWrite.ts` now imports the promise APIs directly from `node:fs/promises`.
- #3715916330 lodekeeper 2026-08-04T20:24:54Z packages/beacon-node/src/db/flatFileStore/metrics.ts:1 reply-to=3715616079
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r3715916330
  Done in 5804ec1af3: `dashboards/lodestar_vm_host.json` now has a Flat file storage row covering operation duration p95, operation errors, read/write throughput, file count, pruned directories, startup duration/errors,...
- #3715502860 wemeetagain 2026-08-04T19:37:23Z docs/design-flat-file-storage.md:1
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r3715502860
  delete this file. If anything, some of the description can go into a module-level comment near the code.
- #3715522784 wemeetagain 2026-08-04T19:37:23Z packages/beacon-node/src/chain/blocks/writeBlockInputToDb.ts:60
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r3715522784
  maybe putBlobSidecars should pass blobSidecars directly, and serialize inside.
- #3715553403 wemeetagain 2026-08-04T19:37:23Z packages/beacon-node/src/chain/blocks/writeBlockInputToDb.ts:101
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r3715553403
  there should be a batch put, like the prior implementation
- #3715568702 wemeetagain 2026-08-04T19:37:23Z packages/beacon-node/src/db/flatFileStore/atomicWrite.ts:1
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r3715568702
  just import from `"node:fs/promises"`
- #3715616079 wemeetagain 2026-08-04T19:37:23Z packages/beacon-node/src/db/flatFileStore/metrics.ts:1
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r3715616079
  we need all of these new metrics exposed in a dashboard
- #2863196707 lodekeeper 2026-02-27T08:39:20Z packages/beacon-node/src/db/flatFileStore/dcolFormat.ts:209 reply-to=2863181635
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r2863196707
  The code looks correct to me. `popcount(bitmap, index)` counts set bits in `[0, index)` — that's the number of columns **before** `index`, which gives the right offset table position `p`.
  Trace with columns 0, 3, 7 present → offset table: `[off_col0, off_col3, off_col7, sentinel]`
- #2863181635 twoeths 2026-02-27T08:35:07Z packages/beacon-node/src/db/flatFileStore/dcolFormat.ts:209
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r2863181635
  `index` start from 0 but `popcount` expect it's upper bound exclusive
- #2863044956 twoeths 2026-02-27T07:56:24Z packages/beacon-node/src/db/flatFileStore/dcolFormat.ts:149
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r2863044956
  is this use for testing only? if yes drop a comment
- #2863040827 twoeths 2026-02-27T07:55:04Z packages/beacon-node/src/db/flatFileStore/dcolFormat.ts:120
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r2863040827
  we always read slot as 4 bytes in `sszBYtes.ts`, maybe make it consistent everywhere?
  ```typescript
- #2863028730 twoeths 2026-02-27T07:51:17Z packages/beacon-node/src/db/flatFileStore/dcolFormat.ts:137
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r2863028730
  use `offsetTableSize()`?
- #2863028211 twoeths 2026-02-27T07:51:07Z packages/beacon-node/src/db/flatFileStore/dcolFormat.ts:156
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r2863028211
  use `offsetTableSize()`?
- #2863027168 twoeths 2026-02-27T07:50:46Z packages/beacon-node/src/db/flatFileStore/dcolFormat.ts:191
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r2863027168
  use `offsetTableSize()`?
- #2801370204 chatgpt-codex-connector[bot] 2026-02-12T22:31:35Z packages/beacon-node/src/chain/chain.ts:809
  https://github.com/ChainSafe/lodestar/pull/8899#discussion_r2801370204
  **<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub> Add LevelDB fallback when flat file lookup misses**
  When `flatFileStore` is enabled, this path returns early and never falls back to `blobSidecars`/`blobSidecarsArchive` (and the same pattern is used for data columns), so upgraded nodes with pre-existing sidecars in Le...

Review bodies
- #3852766177 twoeths 2026-02-25T08:54:08Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/8899#pullrequestreview-3852766177
  with the current approach, we store all DataColumnSidecars per block
  this is against https://github.com/ChainSafe/lodestar/issues/8114 so we need to reconsider should we store DataColumnSidecar separately vs store all DataColumnSidecars per file like in this approach
- #3794043709 chatgpt-codex-connector[bot] 2026-02-12T22:31:34Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/8899#pullrequestreview-3794043709
  ### 💡 Codex Review
  Here are some automated review suggestions for this pull request.
- #3794032679 gemini-code-assist[bot] 2026-02-12T22:28:34Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/8899#pullrequestreview-3794032679
  ## Code Review
  This pull request introduces a major feature: flat file storage for blob sidecars and data columns, moving away from LevelDB for this data. The changes are extensive, including a detailed design document, the core imp...
