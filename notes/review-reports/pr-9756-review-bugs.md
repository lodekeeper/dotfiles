Reviewer: review-bugs
Reviewed commit: 9acfe6c9e7835f32ffd0ccd0631745ff36d0fba2

# PR #9756 Bug Review

## Findings

### Medium: Direct-parent compatibility still accepts bids for slots where Lodestar cannot reorg to the parent

`packages/beacon-node/src/chain/validation/executionPayloadBid.ts:63-66` treats any bid that builds on `head.parentRoot` / `head.parentBlockHash` as compatible whenever `bid.slot` is not an epoch start. That is broader than Lodestar's proposer-boost block-production path. A parent-of-head bid is only usable when `getProposerHead(slot)` can reorg from `head` to `head.parent`, and that path requires `headBlock.slot + 1 === slot` before returning the parent (`packages/fork-choice/src/forkChoice/forkChoice.ts:487-491`).

Because the compatibility branch does not check `bid.slot === head.slot + 1`, a bid can pass validation and be pooled/propagated while keyed to `head.parentRoot` even when block production will never ask for that tuple. Examples include a stale head after skipped slots (`head.slot = 32`, `bid.slot = 35`) or a current-slot bid that arrives after a same-slot head is already cached (`head.slot = bid.slot`). In both cases, `produceBlockV4` retrieves bids for the parent returned by `chain.getProposerHead(slot)` and the selected parent payload hash (`packages/beacon-node/src/api/impl/validator/index.ts:870` and `packages/beacon-node/src/api/impl/validator/index.ts:883-893`), which is not `head.parent` when `head.slot + 1 !== bid.slot`.

The direct-parent exception should also require `bid.slot === head.slot + 1`, alongside `!isStartSlotOfEpoch(bid.slot)`, to match the only parent-bid case Lodestar block production can actually use.

## Question Answers

1. No evidence that #9756's epoch-boundary rejection drops a direct-parent bid Lodestar block production can use. Lodestar's proposer-boost reorg path returns the current head at an epoch-boundary proposal slot.
2. No for the epoch-boundary case: a direct-parent bid where `isStartSlotOfEpoch(bid.slot)` is true now fails compatibility before state regeneration.
3. Yes. Outside epoch boundaries, the direct-parent branch is missing the `bid.slot === head.slot + 1` adjacency check, so current-slot or stale-head parent bids can pass even though block production cannot select them.
