Reviewer: review-bugs
Reviewed commit: 83a43eb9198c1ae535e7c1665565050d990397ce

## Findings

### 🟡 should-fix - API bids can poison the local proposer bid pool without local-commit validation

`packages/beacon-node/src/api/impl/beacon/blocks/index.ts:1073`

The final handler validates an API-submitted bid with `validateApiExecutionPayloadBid()` and then always inserts it into `executionPayloadBidPool`:

- `packages/beacon-node/src/api/impl/beacon/blocks/index.ts:1068` calls the new API validator.
- `packages/beacon-node/src/api/impl/beacon/blocks/index.ts:1073` adds the same bid to the local pool.
- `packages/beacon-node/src/chain/validation/executionPayloadBid.ts:81` documents that this validator intentionally skips the IGNORE-class checks, including proposer preferences and balance coverage.

Concrete failing scenarios:

1. A local builder submits a high-value bid for the proposer's exact `(slot, parentBlockRoot, parentBlockHash)` tuple, but `value > builder excess balance`. This passes all API REJECT checks and is inserted. The proposer later reads it with `executionPayloadBidPool.getBestBid(slot, bidParentBlockHash, parentBlockRootHex)` and uses it as a p2p candidate without re-running `canBuilderCoverBid`. It is caught only when `chain.produceBlock({...builderBid})` reaches `computeNewStateRoot() -> stateTransition() -> processExecutionPayloadBid()`, where `canBuilderCoverBid()` throws `Invalid execution payload bid: builder ... has insufficient balance`. So the node should not sign an invalid block, but the builder branch fails late. Because the pool stores only the highest bid per tuple, this bad high bid can also cause otherwise valid lower gossip bids for the same tuple to be ignored as `BID_TOO_LOW`, leaving the proposer with no valid p2p bid to fall back to.

2. A local builder submits a high-value bid for the proposer's exact tuple with the wrong `feeRecipient` or incompatible `gasLimit`. The API validator skips those proposer-preference checks, the pool accepts it, and the proposer uses it as the p2p candidate. Unlike balance coverage, these preferences are not checked by the block state transition, so `chain.produceBlock({...builderBid})` can return a block that honors the bid's fee recipient / gas limit rather than the proposer's signed preferences or strict fee-recipient intent.

Fix: keep the REJECT-only validator as the publish gate, but do not feed those bids into the local production pool unless they also pass the local-commit checks used for gossip/selection: head tuple compatibility, proposer preferences, parent payload variant/gas-limit compatibility, min increment, and `canBuilderCoverBid`. Another viable shape is to revalidate the selected p2p bid before ranking/production and keep enough candidates to fall back to the next best valid bid.

## Areas Checked

### A. Local pool insertion without full gossip validation

Confirmed as the main issue above. There is no validation between `getBestBid()` selection and `chain.produceBlock({...builderBid})` for proposer preferences or balance coverage. Balance coverage is caught during state transition before a block is returned, so the concrete outcome is a rejected builder branch / possible missed valid p2p opportunity, not a signed invalid block. Proposer-preference mismatches are not consensus-state-transition checks and can make it into a produced block.

### B. gossipsub 16 -> 17 and `PublishOpts.floodPublish`

No functional issue found. `@libp2p/gossipsub@17.1.0` exports `PublishOpts.floodPublish?: boolean` from `@libp2p/gossipsub/types`, and the implementation passes the per-publish value into `selectPeersToPublish(topic, opts?.floodPublish)`. libp2p/js-libp2p#3610 describes this as an additive per-message option. The PR comments say it was tested with a local package patch; I did not find devnet evidence in the PR metadata.

### C. Thrown IGNORE from API validation

Partly refuted. `validateApiExecutionPayloadBid()` now throws `ExecutionPayloadBidError(GossipAction.IGNORE)` for unknown parent / regen failure and the bid is not published, but the REST layer maps `GossipActionError` to HTTP 400, not HTTP 500. I do not see an actual correctness bug there given the API path cannot check REJECT parity without the parent state.

### D. Regen failures collapsed to `UNKNOWN_BLOCK_ROOT`

Confirmed but diagnostic-only. This mirrors the gossip path and can obscure the true regen cause, but I do not see broken behavior from it in this PR.

### E. REJECT-parity drift risk

Confirmed as a maintainability risk, not a current functional bug. The API and gossip REJECT checks match at this commit: not-later-than-parent, builder index bounds/active, builder version, zero execution payment, KZG commitment limit, prev_randao, and signature.

### F. Bare `throw new Error(...)` for non-gloas state

Confirmed as pre-existing/copied behavior from the gossip path. Not introduced by the PR and not flagged.

### G. Test coverage gaps

Confirmed, but not a functional finding. The new API validator tests do not cover `TOO_MANY_KZG_COMMITMENTS`, `INVALID_BUILDER_VERSION`, or the out-of-bounds builder-index branch, and there is no direct test that `publishSignedExecutionPayloadBid()` passes `{floodPublish: true}`.

## Additional Checks

- Return-type change: `git grep` at the reviewed commit found no production caller that reads a return value from `validateApiExecutionPayloadBid`; the only production call is the awaited call in `publishExecutionPayloadBid`.
- Handler ordering: I did not find a separate correctness issue in `validate -> pool.add -> publish` or in the `try/catch` around `pool.add` only. The correctness problem is specifically that the pool insertion uses the REJECT-only publish validator as if it were a local-production validator.
- Prev_randao: no off-by-epoch issue found. Both API and gossip validation regenerate the parent branch to `bid.slot` and compare against `state.getRandaoMix(computeEpochAtSlot(state.slot))`, matching the self-build bid creation and the state-transition check.
