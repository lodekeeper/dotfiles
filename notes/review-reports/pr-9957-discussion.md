PR discussion coverage for ChainSafe/lodestar#9957
Fetched counts:
- Issue comments: 11
- Inline review comments: 29
- Review bodies: 6
Display limit: latest 20 per surface

Issue comments
- #6802751013 ensi321 2026-11-11T17:31:22Z
  https://github.com/ChainSafe/lodestar/pull/9957#issuecomment-6802751013
  @lodekeeper I like [4161c5d](https://github.com/ChainSafe/lodestar/pull/9957/commits/4161c5d563c59241460c8a86c22b6609fcf7c953) more than #10600
- #6802189315 lodekeeper 2026-11-11T17:07:42Z
  https://github.com/ChainSafe/lodestar/pull/9957#issuecomment-6802189315
  The genesis lookahead fix is #10600. Multifork fails for the same reason: its Lighthouse node (node-5) logs 18 `IncorrectBlockProposer { block: 0, ... }` rejections. With #10600 merged into this branch, both sims at f...
- #6798916735 nflaig 2026-11-11T14:45:47Z
  https://github.com/ChainSafe/lodestar/pull/9957#issuecomment-6798916735
  > > I think we can get this in, its super close
  >
- #6797005451 wemeetagain 2026-11-11T13:23:38Z
  https://github.com/ChainSafe/lodestar/pull/9957#issuecomment-6797005451
  Merge conflicts
- #6788329070 ensi321 2026-11-11T05:56:52Z
  https://github.com/ChainSafe/lodestar/pull/9957#issuecomment-6788329070
  > I think we can get this in, its super close
  Don't see anything blocking this at the moment
- #6778222870 wemeetagain 2026-11-10T20:17:28Z
  https://github.com/ChainSafe/lodestar/pull/9957#issuecomment-6778222870
  I think we can get this in, its super close
- #5487006980 github-actions[bot] 2026-11-05T11:53:28Z
  https://github.com/ChainSafe/lodestar/pull/9957#issuecomment-5487006980
  ## :warning: **Performance Alert** :warning:
  Possible performance regression was detected for some benchmarks.
- #6181672220 lodekeeper 2026-10-15T00:39:36Z
  https://github.com/ChainSafe/lodestar/pull/9957#issuecomment-6181672220
  I don't see any regression from this PR. feat1-sas has been running 4c98359 since Oct 13 08:29 UTC. I compared it with unstable-sas over the last 7h, since unstable restarted Oct 14 16:00:
  - Both stayed synced the whole window, with the same head lag, 201 peers each and 6 reorgs each.
- #6181487698 ensi321 2026-10-15T00:25:05Z
  https://github.com/ChainSafe/lodestar/pull/9957#issuecomment-6181487698
  @lodekeeper can you verify the soak result for this PR? It's deployed on feat1-sas on Hoodi since Oct 13. Check if there is any regression or error compared to unstable-sas.
- #6021069235 wemeetagain 2026-10-06T16:48:00Z
  https://github.com/ChainSafe/lodestar/pull/9957#issuecomment-6021069235
  I like this PR, hoping to get this in eventually
- #5868840311 codecov[bot] 2026-10-05T09:26:29Z
  https://github.com/ChainSafe/lodestar/pull/9957#issuecomment-5868840311
  ## [Codecov](https://app.codecov.io/gh/ChainSafe/lodestar/pull/9957?dropdown=coverage&src=pr&el=h1&utm_medium=referral&utm_source=github&utm_content=comment&utm_campaign=pr+comments&utm_term=ChainSafe) Report
  :white_check_mark: All modified and coverable lines are covered by tests.

Inline review comments
- #4539287056 nflaig 2026-11-11T14:44:48Z packages/beacon-node/src/api/impl/beacon/blocks/index.ts:119 reply-to=4480655180
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4539287056
  @ensi321 we can do this now with 10558 merged
- #4480806631 ensi321 2026-11-05T13:07:55Z packages/beacon-node/src/api/impl/beacon/blocks/index.ts:119 reply-to=4480655180
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4480806631
  Agreed. The sims (multiFork, mixedClient) still publish electra blocks, so a plain reject needs them on fulu first. Opened #10558 to move them post-fulu. Once that lands I'll merge unstable here and switch this to a p...
- #4480655180 nflaig 2026-11-05T12:52:15Z packages/beacon-node/src/api/impl/beacon/blocks/index.ts:119
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4480655180
  should just plain reject for pre-fulu
- #4479924873 ensi321 2026-11-05T11:34:51Z packages/beacon-node/src/sync/utils/downloadByRange.ts:163 reply-to=4478098687
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4479924873
  Replaced in 165e7335c6.
- #4479924277 ensi321 2026-11-05T11:34:49Z packages/beacon-node/test/utils/blocksAndData.ts:142 reply-to=4478098673
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4479924277
  Removed in 165e7335c6.
- #4479923601 ensi321 2026-11-05T11:34:46Z packages/beacon-node/src/chain/blocks/verifyBlocksExecutionPayloads.ts:173 reply-to=4478098654
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4479923601
  Applied in 165e7335c6.
- #4479922905 ensi321 2026-11-05T11:34:43Z packages/beacon-node/src/chain/GetBlobsTracker.ts:76 reply-to=4478098632
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4479922905
  Done in 165e7335c6: the guard is the first statement of triggerGetBlobs and the comment now sits on the engine call.
- #4479922319 ensi321 2026-11-05T11:34:40Z specrefs/.ethspecify.yml:127 reply-to=4477920470
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4479922319
  Shortened to one line in 165e7335c6, electra pointer dropped.
- #4479921792 ensi321 2026-11-05T11:34:38Z packages/cli/test/utils/crucible/utils/syncing.ts:121 reply-to=4477913418
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4479921792
  Switched to getBlobs in 7322e2da4d. Since fulu publishBlockV2 slices kzgProofs as NUMBER_OF_COLUMNS per blob, the util now computes cell proofs with kzg.computeCellsAndKzgProofs instead of passing one blob proof per b...
- #4479921194 ensi321 2026-11-05T11:34:35Z packages/cli/test/utils/crucible/utils/syncing.ts:122 reply-to=4477910743
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4479921194
  multiFork still runs electra heads (FULU_FORK_EPOCH: Infinity) and calls assertUnknownBlockSync, and pre-fulu blobs are no longer in the DB, so the API would 404 without the guard. Kept it with a one-line comment. It ...
- #4479920581 ensi321 2026-11-05T11:34:32Z packages/beacon-node/src/api/impl/beacon/blocks/index.ts:134 reply-to=4477861146
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4479920581
  Comment dropped and replaced by an explicit throw at the top of the function, see 7322e2da4d. It keys on the block's blob commitments rather than the supplied blobs, so an electra block with commitments but an empty b...
- #4479920058 ensi321 2026-11-05T11:34:29Z packages/beacon-node/src/api/impl/beacon/blocks/index.ts:138 reply-to=4165413847
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4479920058
  Done in 7322e2da4d. publishBlockV2 now throws 400 for any pre-fulu block whose blob commitments are non-empty, before anything is cached. Blob-free pre-fulu blocks still publish, which keeps multiFork/mixedClient (FUL...
- #4478102857 lodekeeper 2026-11-05T08:19:36Z specrefs/.ethspecify.yml:127 reply-to=4477920470
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4478102857
  Agree. One line is enough, for example `# Pre-fulu blob sidecar functions, replaced by data columns in fulu` above the deneb entries. The electra comment pointing back to it can then go.
- #4478102592 lodekeeper 2026-11-05T08:19:34Z packages/cli/test/utils/crucible/utils/syncing.ts:121 reply-to=4477913418
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4478102592
  Agree. That change also needs proofs: `getBlobs` returns blobs without them, and fulu `publishBlockV2` reads `kzgProofs` as 128 cell proofs per blob. The current `currentSidecars.map((b) => b.kzgProof)` passes one blo...
- #4478102353 lodekeeper 2026-11-05T08:19:32Z packages/cli/test/utils/crucible/utils/syncing.ts:122 reply-to=4477910743
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4478102353
  Not yet. `multiFork.test.ts` sets `FULU_FORK_EPOCH: Infinity` and calls `assertUnknownBlockSync` (L158), so the head here is an electra block. With this PR, pre-fulu `getBlobSidecars` reads the blob DB, which nothing ...
- #4478102106 lodekeeper 2026-11-05T08:19:30Z packages/beacon-node/src/api/impl/beacon/blocks/index.ts:134 reply-to=4477861146
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4478102106
  Agree. One constraint: `multiFork.test.ts` and `mixedClient.test.ts` still run with `FULU_FORK_EPOCH: Infinity`, and their Lodestar validators publish electra blocks through `publishBlockV2`, so a plain pre-fulu throw...
- #4478098632 lodekeeper 2026-11-05T08:19:05Z packages/beacon-node/src/chain/GetBlobsTracker.ts:76
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4478098632
  🟢 This restates the guard. The comment above it, about sending the request before newPayload, now sits on an early return that sends nothing. I'd make the guard the first statement of `triggerGetBlobs` and move that c...
  ```suggestion
- #4478098654 lodekeeper 2026-11-05T08:19:05Z packages/beacon-node/src/chain/blocks/verifyBlocksExecutionPayloads.ts:173
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4478098654
  🟢 The `deneb.BeaconBlockBody` cast is only safe because of the `isBlockInputNoData` return above. `getBlobKzgCommitments` from `util/dataColumns.ts` already knows where commitments live per fork, including the gloas bid:
  ```suggestion
- #4478098673 lodekeeper 2026-11-05T08:19:05Z packages/beacon-node/test/utils/blocksAndData.ts:142
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4478098673
  🟢 Restates the function name. AGENTS.md defaults to no comment here.
  ```suggestion
- #4478098687 lodekeeper 2026-11-05T08:19:05Z packages/beacon-node/src/sync/utils/downloadByRange.ts:163
  https://github.com/ChainSafe/lodestar/pull/9957#discussion_r4478098687
  🟢 This PR rewrites this line but keeps the em dash, which AGENTS.md rules out.
  ```suggestion

Review bodies
- #5862458757 lodekeeper 2026-11-11T17:03:13Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9957#pullrequestreview-5862458757
  The plain pre-fulu reject in 788f6be2af looks right, and moving the sims and e2e configs to fulu at genesis is what it needs.
  The failing Mixed clients sim is real, but the cause isn't in this PR's code. Moving the sim to `FULU_FORK_EPOCH: 0` exposes a genesis bug: Lodestar's `initializeBeaconStateFromEth1` never sets `proposer_lookahead`, s...
- #5793729479 lodekeeper 2026-11-05T23:45:12Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9957#pullrequestreview-5793729479
  Rechecked at 165e7335c6. 7322e2da4d and 165e7335c6 address my four comments. The commitment-keyed pre-fulu reject, the `getBlobs` switch with computed cell proofs, and the two new publish tests look right, and the fix...
- #5781766611 lodekeeper 2026-11-05T08:19:04Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9957#pullrequestreview-5781766611
  No regression found for post-fulu (current mainnet) or gloas. What I checked on 258d7d1:
  - Fulu block inputs are still `BlockInputColumns`, and gloas still uses `BlockInputNoData` plus `PayloadEnvelopeInput`. The new `PreData` to `NotRequired` mapping in `verifyBlocksDataAvailability` only applies to dene...
- #5781450446 nflaig 2026-11-05T07:57:33Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9957#pullrequestreview-5781450446
  @lodekeeper can you please review this code to see if it causes any regression for post-fulu (ie. current mainnet) or gloas, also check comments added in the pr against our agent.md policy
- #5391411421 nflaig 2026-10-02T11:50:28Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9957#pullrequestreview-5391411421
  I feel like this PR just needs to be deployed to a devnet node and a feat group and let AI check if there are issues with it before we review it
- #5337844623 chatgpt-codex-connector[bot] 2026-09-28T11:24:05Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9957#pullrequestreview-5337844623
  ### 💡 Codex Review
  Here are some automated review suggestions for this pull request.
