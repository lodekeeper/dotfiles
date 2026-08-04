Reviewer: review-devils-advocate
Reviewed commit: 9acfe6c9e7835f32ffd0ccd0631745ff36d0fba2

# PR #9756 Devil's Advocate Review

## Summary

The performance motivation is real: a direct-parent bid at an epoch boundary cannot be selected by Lodestar's proposer-head logic because the single-slot proposer-boost reorg branch is disabled at epoch boundaries. Dropping it before `regen.getBlockSlotState(parentBlock, bid.slot, ...)` avoids an expensive parent-state epoch transition for a bid Lodestar will not locally use.

I still have objections to the current framing and placement. They are not necessarily blockers if the team accepts the propagation divergence, but they should be made explicit.

## Objection 1: local uselessness is not the same as gossip invalidity

At `packages/beacon-node/src/chain/validation/executionPayloadBid.ts:63`, Lodestar now treats the direct-parent path as incompatible when `bid.slot` is an epoch start. That is aligned with Lodestar's own `get_proposer_head` outcome, but it is still a gossip propagation divergence from the stated compatibility rule.

The concrete risk is not that Lodestar would build an invalid block. The risk is suppressing a bid that is unusable from our local head view but may still be useful to peers with a different head view. For example, a peer that has not accepted the last-slot head may see the bid parent as its actual head, not as a proposer-boost reorg target. Gossip rules usually avoid turning "I won't use this" into "the network should not see this" unless the spec deliberately says so.

Counter-proposal: keep gossip validation spec-compatible unless this has an explicit upstream/spec decision. If the divergence is desired, open or reference the consensus-specs change that adds `not_epoch_boundary` to the bid-compatibility rule itself. In Lodestar, make the peer outcome clearly `IGNORE` without peer penalty and add a metric/log label for this exact policy drop so it is visible during Gloas interop.

## Objection 2: the check is in a helper whose name still reads as the spec rule

`isBidCompatibleWithHead()` is introduced by a comment that mirrors the gossip validation rule ("compatible with the current head branch"), but lines 63-66 now include an additional Lodestar production policy. That makes the helper harder to reason about and causes both `validateGossipExecutionPayloadBid()` and `validateApiExecutionPayloadBid()` to reject this case through the generic `INCOMPATIBLE_WITH_HEAD` path at lines 116-125.

This is a subtle contract change: the bid is not actually incompatible with the branch under the prior #9739 interpretation; it is compatible but intentionally not worth validating/propagating at this slot.

Counter-proposal: keep `isBidCompatibleWithHead()` spec-shaped and add a separate predicate such as `isUnusableDirectParentBidAtEpochBoundary()` or `shouldSkipDirectParentBidForLocalPolicy()`. Place it in `validateExecutionPayloadBid()` immediately after the cheap parent lookup / `NOT_LATER_THAN_PARENT` checks and before state regeneration. That keeps the expensive work avoided while preserving a precise reason, and it leaves room to apply different policy to API vs gossip if needed.

A network-processor prequeue filter could be added later as an optimization, but I would not make it the canonical check. It would duplicate head-dependent validation based on serialized fields and would not cover the API publish path at `packages/beacon-node/src/api/impl/beacon/blocks/index.ts:994`.

## Objection 3: the comment does not fully describe the tradeoff

The new comment at lines 64-65 is helpful, but it compresses several important facts into "Lodestar does not propagate these bids." It does not say that this is an intentional spec divergence for propagation, that the API path rejects it too, or that the consensus-specs `get_proposer_head` rationale is the epoch-boundary `not_epoch_boundary` condition rather than bid validity itself.

Counter-proposal: expand the comment enough to name the tradeoff:

```ts
// Spec bid compatibility still admits this direct-parent branch, but Lodestar's
// proposer-head logic cannot select it at epoch boundaries because single-slot
// proposer-boost reorgs require is_not_epoch_boundary(slot). We intentionally
// IGNORE instead of validating/forwarding to avoid regenerating the parent state
// through the epoch transition for a locally unreachable bid.
```

That would make future reviewers less likely to "fix" this back to spec compatibility or miss the propagation cost being accepted.

## Answers To The Prompt

1. Rejecting these bids is defensible as a Lodestar-local DoS/performance policy, but I would not call it a clean spec-compliant propagation rule without an upstream spec clarification. The safer default for gossip is spec compliance; if Lodestar diverges, it should be intentionally labeled as local policy and measured.

2. The safer placement is not the network processor as the source of truth. Put an explicit skip after parent lookup / parent-slot validation and before state regeneration. A network-processor fast path can exist later, but only as an optimization that mirrors validation.

3. The comment is directionally correct but too terse. It should name `get_proposer_head` / `is_not_epoch_boundary`, the fact that this is a propagation/API rejection rather than consensus invalidity, and the performance tradeoff being accepted.
