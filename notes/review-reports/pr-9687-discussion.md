PR discussion coverage for ChainSafe/lodestar#9687
Fetched counts:
- Issue comments: 2
- Inline review comments: 5
- Review bodies: 1
Display limit: latest 20 per surface

Issue comments
- #5034863465 github-actions[bot] 2026-08-05T08:23:25Z
  https://github.com/ChainSafe/lodestar/pull/9687#issuecomment-5034863465
  ## Performance Report
  ✔️ no performance regression detected
- #5188800283 spiral-ladder 2026-08-05T07:21:17Z
  https://github.com/ChainSafe/lodestar/pull/9687#issuecomment-5188800283
  @lodekeeper review

Inline review comments
- #3714027857 spiral-ladder 2026-08-04T15:43:10Z packages/state-transition/src/lightClient/spec/utils.ts:498 reply-to=3622589405
  https://github.com/ChainSafe/lodestar/pull/9687#discussion_r3714027857
  couldn't hurt to add a check, done in [575528a](https://github.com/ChainSafe/lodestar/pull/9687/commits/575528a7f44228eaf1c3e308717bfda8f125125b)
- #3714002387 spiral-ladder 2026-08-04T15:39:41Z packages/beacon-node/src/chain/lightClient/index.ts:775 reply-to=3622589400
  https://github.com/ChainSafe/lodestar/pull/9687#discussion_r3714002387
  this doesn't seem valid, we do `hashTreeRoot(block.body)` before in `blockToLightClientHeader()` so if the bid is undefined that should already fail
- #3713925661 spiral-ladder 2026-08-04T15:29:22Z packages/state-transition/src/lightClient/spec/utils.ts:471
  https://github.com/ChainSafe/lodestar/pull/9687#discussion_r3713925661
  so this change is because we cache up to `MAX_SYNC_PERIODS_CACHE` (= 2) of `bestValidUpdate`. The concern is if the store is upgraded but an old cached update remains in a pre-gloas state, causing the headers to have ...
- #3622589400 gemini-code-assist[bot] 2026-07-21T13:35:16Z packages/beacon-node/src/chain/lightClient/index.ts:775
  https://github.com/ChainSafe/lodestar/pull/9687#discussion_r3622589400
  ![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)
  In `blockToLightClientHeader`, accessing `blockBody.signedExecutionPayloadBid.message.parentBlockHash` directly can cause a runtime crash (`TypeError: Cannot read properties of undefined`) if `signedExecutionPayloadBi...
- #3622589405 gemini-code-assist[bot] 2026-07-21T13:35:16Z packages/state-transition/src/lightClient/spec/utils.ts:498
  https://github.com/ChainSafe/lodestar/pull/9687#discussion_r3622589405
  ![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)
  In `computeBranchRoot`, if the `branch` parameter is shorter than the expected `depth` (for example, due to a malformed or truncated `executionBranch` in a light client header), `proof.length` will be less than `depth...

Review bodies
- #4745159997 gemini-code-assist[bot] 2026-07-21T13:35:16Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9687#pullrequestreview-4745159997
  ## Code Review
  This pull request introduces support for the Gloas fork in the light client, including block-to-header conversion, proof generation for the execution block hash, and upgrades to the light client sync spec tests to han...
