Reviewer: review-security
Reviewed commit: 9acfe6c9e7835f32ffd0ccd0631745ff36d0fba2

# PR #9756 Security Review

## Scope

Reviewed `packages/beacon-node/src/chain/validation/executionPayloadBid.ts` for adversarial gossip and DoS implications of ignoring direct-parent execution payload bids at epoch boundaries.

## Findings

No concrete security findings.

## Answers

1. This does reduce the stated DoS path. The new `isBidCompatibleWithHead()` branch returns false for bids that build on `head.parentRoot` and `head.parentBlockHash` when `isStartSlotOfEpoch(bidSlot)` is true. That check runs immediately after the slot check and before `seenExecutionPayloadBids`, parent block lookup, proposer preference lookup, `regen.getBlockSlotState(...)`, builder checks, and BLS verification. For the targeted known direct-parent epoch-boundary bid, the expensive parent-state epoch transition is avoided.

   Residual work remains only in the cheap/pre-validation layers: SSZ deserialization, head lookup, and NetworkProcessor's bounded unknown block/envelope prequeue for bids whose serialized parent tuple is not already resolved. I did not find a remaining path where the targeted direct-parent epoch-boundary bid reaches `regen.getBlockSlotState(...)`.

2. I do not see a propagation or validation bypass. The change narrows acceptance and does not mark `seenExecutionPayloadBids`, update the bid pool, or emit bid events before returning `GossipAction.IGNORE`. A later compatible bid for the head branch is still eligible for normal validation. The behavior is head-dependent, but that was already true for the #9739 compatibility filter, and this branch only suppresses forwarding of a locally unusable/spec-divergent direct-parent bid.

3. `IGNORE` is appropriate. The condition is local-head and Lodestar-policy dependent, and the bid may be spec-valid or useful to a peer with a different view. `REJECT` would create peer-score risk for a message that is not intrinsically invalid. Mapping it through the existing `INCOMPATIBLE_WITH_HEAD` ignore path is safe, though a more specific metric/error reason would improve observability rather than security.

## Notes

- The PR intentionally diverges from the current Gloas p2p helper, which accepts the direct-parent compatibility path. The new inline comment documents that tradeoff.
- I did not run tests; this was a focused static security review of the changed validation path and the surrounding gossip prequeue behavior.
