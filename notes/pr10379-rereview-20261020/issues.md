# issues

## 6154291890 chatgpt-codex-connector[bot]  parent=None 2026-10-13T20:13:56Z
<!-- codex-pull-request-review-summary -->

## Codex Review Summary

This comment shows the latest Codex review activity on this pull request.

| Review | Status | Commit | Review trigger |
| --- | --- | --- | --- |
| 📝 **Code Review** | ✅ **Completed** <relative-time datetime="2026-10-13T20:26:14.430536Z">2026-10-13T20:26:14.430536Z</relative-time> | `725efef` | Draft marked ready |



<details> <summary>ℹ️ About Codex in GitHub</summary>
<br/>

[Your team has set up Codex to review pull requests in this repo](https://chatgpt.com/codex/cloud/settings/general). Reviews are triggered when you
- Open a pull request for review
- Mark a draft as ready
- Comment "@codex review" or "@codex security review".

Codex reacts with 👀 while any review is running, comments if it has suggestions, and reacts with 👍 once all reviews finish with no findings.

</details>

## 6170879724 krisoshea-eth  parent=None 2026-10-14T14:36:30Z
Thanks Marko, appreciate you getting the basic wiring together. I’m happy to build on this and trim the overlapping parts of my PRs.

There are two things I’d like to check before it goes in. The three-epoch cutoff clears a win without checking whether its payment is reflected in the balance we’re using. I reproduced the reservation being released and pruned without any payment or balance update. Could we leave those wins reserved for now while I finish the accounting follow-up? That can reduce the bidding budget, but avoids assuming the payment has happened.

I also see why preparation needs to retry while the EL is syncing. The BN wrapper throws for `SYNCING`, but retrying every exception also retries permanent failures and turns them into a timeout. Could we keep `SYNCING` retryable and let permanent errors through? #10234 already makes that distinction, so we should be able to reuse it.

I’ll keep the reveal retries and request cancellation as focused follow-ups rather than ask you to bring all my runtime changes into this PR. Thanks again.

## 6180079709 markolazic01  parent=None 2026-10-14T22:38:33Z
Thanks for the feedback @krisoshea-eth!

Agreed on `SYNCING`, I'll keep retrying only while the EL is syncing and let other errors fail the build. No engine changes needed for that.

For the balance I think we're fine with the three epochs. The payment is either deducted or dropped at the end of the epoch after the bid, so by the time we release the reservation the balance we poll already includes it. Holding it longer would count the payment twice. Reconciling against the pending payments endpoint instead of a timer sounds like a good follow-up though.

## 6190285666 lodekeeper  parent=None 2026-10-15T10:48:23Z
One nuance for that follow-up: at the end of the epoch after the bid, a payment that met quorum moves to `builder_pending_withdrawals`. The balance is only debited once a payload processes that withdrawal, so with a run of empty payloads (or a full withdrawal queue) the debit can land after the 3 epoch release. The fallout is limited to rejected bids, since `can_builder_cover_bid` subtracts the pending amounts. Reconciling against both pending payments and pending withdrawals, the same as `get_pending_balance_to_withdraw_for_builder`, would remove the timer entirely.


## 6217598696 krisoshea-eth  parent=None 2026-10-16T14:24:19Z
Thanks Marko, appreciate you tightening the retries. I checked the new adapter and noticed the BN also sets `engine.state` to `SYNCING` after an `INVALID` response, so the catch can still turn that into a retry. Could we check the result of that specific request instead? #10234 already keeps those responses separate.

On settlement, the delayed-withdrawal test in #10351 is the case I meant. Queueing a payment doesn't debit the balance, so it can remain payable beyond three epochs. I agree that keeping an already-paid bid reserved forever is wrong too. I'm continuing LOD-112 to distinguish those cases using both pending queues. Could we keep that limitation explicit until it's wired in?


## 6218096681 lodekeeper  parent=None 2026-10-16T14:49:46Z
Confirmed at f6069d7c041. `notifyForkchoiceUpdate` updates the state from the response status before it throws ([http.ts#L355](https://github.com/ChainSafe/lodestar/blob/f6069d7c041f4d66cafd0a3f0831555fff7e2be2/packages/beacon-node/src/execution/engine/http.ts#L355)), and `getExecutionEngineStateForPayloadStatus` maps `INVALID`, `INVALID_BLOCK_HASH` and `ELERROR` to `SYNCING` ([utils.ts#L171-L175](https://github.com/ChainSafe/lodestar/blob/f6069d7c041f4d66cafd0a3f0831555fff7e2be2/packages/beacon-node/src/execution/engine/utils.ts#L171-L175)). So an `INVALID` fcU passes the check at [handler.ts#L119](https://github.com/ChainSafe/lodestar/blob/f6069d7c041f4d66cafd0a3f0831555fff7e2be2/packages/cli/src/cmds/builder/handler.ts#L119) and gets retried until the deadline.

JSON-RPC error responses do the same thing. The client `ERROR` event maps `ErrorJsonRpcResponse` and `HttpRpcError` to `SYNCING` ([utils.ts#L200-L207](https://github.com/ChainSafe/lodestar/blob/f6069d7c041f4d66cafd0a3f0831555fff7e2be2/packages/beacon-node/src/execution/engine/utils.ts#L200-L207)), so a permanent `-38003 Invalid payload attributes` would be retried as well. Only the `SYNCING` status branch throws `Execution Layer Syncing`, so checking the response itself like #10234 does is the reliable way.


## 6223540554 markolazic01  parent=None 2026-10-16T19:55:05Z
Good catch guys, fixed it. The error check can be improved later, for now just matching the specific BN error. Settlement limitation is now documented on the constant and in the README.

## 6302417784 markolazic01  parent=None 2026-10-20T21:50:14Z
@lodekeeper [352a400](https://github.com/ChainSafe/lodestar/pull/10379/commits/352a400e0664ad910adc486826379c743d014522) should address every point except for 2 mentioned follow-ups, can you double check?
