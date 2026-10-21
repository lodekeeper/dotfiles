PR discussion coverage for ChainSafe/lodestar#10379
Fetched counts:
- Issue comments: 7
- Inline review comments: 30
- Review bodies: 1
Display limit: latest 20 per surface

Issue comments
- #6223540554 markolazic01 2026-10-16T19:55:05Z
  https://github.com/ChainSafe/lodestar/pull/10379#issuecomment-6223540554
  Good catch guys, fixed it. The error check can be improved later, for now just matching the specific BN error. Settlement limitation is now documented on the constant and in the README.
- #6218096681 lodekeeper 2026-10-16T14:49:46Z
  https://github.com/ChainSafe/lodestar/pull/10379#issuecomment-6218096681
  Confirmed at f6069d7c041. `notifyForkchoiceUpdate` updates the state from the response status before it throws ([http.ts#L355](https://github.com/ChainSafe/lodestar/blob/f6069d7c041f4d66cafd0a3f0831555fff7e2be2/packag...
  JSON-RPC error responses do the same thing. The client `ERROR` event maps `ErrorJsonRpcResponse` and `HttpRpcError` to `SYNCING` ([utils.ts#L200-L207](https://github.com/ChainSafe/lodestar/blob/f6069d7c041f4d66cafd0a3...
- #6217598696 krisoshea-eth 2026-10-16T14:24:19Z
  https://github.com/ChainSafe/lodestar/pull/10379#issuecomment-6217598696
  Thanks Marko, appreciate you tightening the retries. I checked the new adapter and noticed the BN also sets `engine.state` to `SYNCING` after an `INVALID` response, so the catch can still turn that into a retry. Could...
  On settlement, the delayed-withdrawal test in #10351 is the case I meant. Queueing a payment doesn't debit the balance, so it can remain payable beyond three epochs. I agree that keeping an already-paid bid reserved f...
- #6190285666 lodekeeper 2026-10-15T10:48:23Z
  https://github.com/ChainSafe/lodestar/pull/10379#issuecomment-6190285666
  One nuance for that follow-up: at the end of the epoch after the bid, a payment that met quorum moves to `builder_pending_withdrawals`. The balance is only debited once a payload processes that withdrawal, so with a r...
- #6180079709 markolazic01 2026-10-14T22:38:33Z
  https://github.com/ChainSafe/lodestar/pull/10379#issuecomment-6180079709
  Thanks for the feedback @krisoshea-eth!
  Agreed on `SYNCING`, I'll keep retrying only while the EL is syncing and let other errors fail the build. No engine changes needed for that.
- #6170879724 krisoshea-eth 2026-10-14T14:36:30Z
  https://github.com/ChainSafe/lodestar/pull/10379#issuecomment-6170879724
  Thanks Marko, appreciate you getting the basic wiring together. I’m happy to build on this and trim the overlapping parts of my PRs.
  There are two things I’d like to check before it goes in. The three-epoch cutoff clears a win without checking whether its payment is reflected in the balance we’re using. I reproduced the reservation being released a...
- #6154291890 chatgpt-codex-connector[bot] 2026-10-13T20:26:15Z
  https://github.com/ChainSafe/lodestar/pull/10379#issuecomment-6154291890
  <!-- codex-pull-request-review-summary -->
  ## Codex Review Summary

Inline review comments
- #4330028816 nflaig 2026-10-20T21:00:22Z packages/builder/src/identity.ts:102
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330028816
  this meant we discover builder 1 epoch too late but could be optimized by polling at slot 1 of the epoch with the head state advanced, polling each slot as done right now isn't needed but also not too big of a deal I ...
- #4330006169 nflaig 2026-10-20T20:59:50Z packages/builder/src/defaults.ts:15
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330006169
  not sure this makes too much sense, we could just let balance drain to 1 ETH, there is no reason to keep the extra 0.1 ETH around and do nothing
- #4330114390 nflaig 2026-10-20T20:56:15Z packages/builder/README.md:24 reply-to=4330106988
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330114390
  > Reconciling against the pending payments and withdrawals of the state is a follow-up.
  should have read the last part, literally says it here
- #4330153831 nflaig 2026-10-20T20:56:15Z packages/cli/src/cmds/builder/options.ts:160
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330153831
  ~~describtion doesn't really explain what the flag does?~~ nvm, re-read and it seems fine
- #4330182333 nflaig 2026-10-20T20:56:15Z packages/cli/src/cmds/builder/options.ts:115
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330182333
  would be better to namespace this, ie. `execution.jwtSecret`
- #4330209534 nflaig 2026-10-20T20:56:15Z scripts/kurtosis/builder-dev.yaml:24
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330209534
  🚀
- #4329488280 nflaig 2026-10-20T20:56:14Z packages/builder/src/services/bidder.ts:172
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4329488280
  why `- 1`? this should probably print out a negative value if we published before the proposer slot or a positive value if we published in the slot
- #4329523765 nflaig 2026-10-20T20:56:14Z packages/builder/src/services/bidder.ts:189
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4329523765
  this is not ideal and a bit hacky, ideally the builder should keep track of their canonical branch via the head event, cc @lodekeeper maybe has anohter idea, but if we just fetch duties to get the root it's definitely...
- #4329974378 nflaig 2026-10-20T20:56:14Z packages/builder/src/builder.ts:56
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4329974378
  > Execution client
  is too specific, this could be any payload construction software
- #4330011481 nflaig 2026-10-20T20:56:14Z packages/builder/src/defaults.ts:8
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330011481
  might be better to make the default 0 profit/loss, ie. 10000
- #4330036023 nflaig 2026-10-20T20:56:14Z packages/builder/src/services/revealer.ts:14
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330036023
  ~~what's the default of this @lodekeeper~~ ah it's `PAYLOAD_ATTESTATION_DUE_BPS` might wanna make that more explicit
- #4330072517 nflaig 2026-10-20T20:56:14Z packages/builder/test/unit/services/payloadOrchestrator.test.ts:327
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330072517
  not sure what that even means based on the test description, so likely fine to delete it
- #4330106988 nflaig 2026-10-20T20:56:14Z packages/builder/README.md:24
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330106988
  might able to optimize this by using apis from https://github.com/ethereum/beacon-APIs/pull/655
- #4330126819 nflaig 2026-10-20T20:56:14Z packages/cli/src/cmds/builder/options.ts:46
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330126819
  > otherwise the builder only bids on slots the beacon node itself proposes
  this doesn't need to be explicitly noted
- #4330132833 nflaig 2026-10-20T20:56:14Z packages/cli/src/cmds/builder/options.ts:46
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330132833
  > Url to a trusted beacon node
  "trusted" is that how it documented for the validator client? i think this is mostly assumed in all cases
- #4330139287 nflaig 2026-10-20T20:56:14Z packages/cli/src/cmds/builder/options.ts:127
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330139287
  do we need this? seems useless
- #4329397138 lodekeeper 2026-10-20T19:34:08Z .github/workflows/nightly-builder-smoke.yml:109 reply-to=4329223795
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4329397138
  Confirmed, local value doesn't matter here. The validators run with `--builder.selection=builderalways` ([builder-dev.yaml#L20](https://github.com/ChainSafe/lodestar/blob/119fda5f3bbe03e0b2d26b6e6bd3ce4b4ccebe4b/scrip...
  Local can still win if the circuit breaker is active, the EL sets `shouldOverrideBuilder`, or no bid arrives before the bid deadline. That's why the check only needs at least one win over ~3 epochs. The comment could ...
- #4329381940 markolazic01 2026-10-20T19:32:45Z .github/workflows/nightly-builder-smoke.yml:109 reply-to=4329223795
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4329381940
  We use `builderalways` in `builder-dev.yaml`, so the bid is picked whenever one is available without comparing values. Without it the local payload wins every slot on the devnet since the builder bids with value 0.
- #4329223795 nflaig 2026-10-20T19:18:03Z .github/workflows/nightly-builder-smoke.yml:109
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4329223795
  > the builder is the only bidder, it must have won bids and revealed their payloads
  hmm what if local payload is more valuable or are we setting `builderalways` cc @lodekeeper can maybe confirm or deny
- #4272194399 krisoshea-eth 2026-10-14T14:36:33Z packages/builder/src/builder.ts:243 reply-to=4263645834
  https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4272194399
  Thanks Marko, happy to pick that up. I’ve added it to LOD-111. I’ll keep it on the Builder side and check that the source is actually active before warning about missing payload attributes, so startup or a disconnect ...

Review bodies
- #5509528604 chatgpt-codex-connector[bot] 2026-10-13T20:26:10Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/10379#pullrequestreview-5509528604
  ### 💡 Codex Review
  Here are some automated review suggestions for this pull request.
