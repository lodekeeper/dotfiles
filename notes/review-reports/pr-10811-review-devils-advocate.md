# PR #10811 — Devil's Advocate Review

Reviewer: review-devils-advocate
Reviewed commit: 6387e428684ab1e2f584fac30afce616c4b03efc

## Overall Assessment

The fail-fast CLI validation is a sound, narrowly scoped response to the current gossip timing rule; it uses the network configuration rather than hard-coding a mainnet deadline.

## Objections

None. I found no substantive approach objection with a simpler, equally useful counter-proposal.

## Spec interpretation and necessity checked

Fetched the local consensus-specs clone's upstream master into `refs/remotes/origin/master` without checking out or touching its working tree. The reviewed upstream reference is **36888ee87b0faa6ad7804b017a0184e8e6e6a1c6**, dated **2026-11-26**.

At `specs/gloas/p2p-interface.md:1162–1166`, `validate_execution_payload_bid_gossip` derives the earliest receipt time from the start of `bid.slot - 1` plus `get_payload_attestation_due_ms()` and raises `GossipIgnore` when `current_time_ms` is strictly below it. The rule's brief description is: “The bid is received after the payload attestation deadline of the previous slot.” Equality is accepted by the actual comparison.

Primary reference: https://github.com/ethereum/consensus-specs/blob/36888ee87b0faa6ad7804b017a0184e8e6e6a1c6/specs/gloas/p2p-interface.md#new-execution_payload_bid

- The builder's existing bidder schedules payload retrieval using `deadlineBps` in the slot before the proposal slot, then creates/publishes the bid. Rejecting a configured retrieval deadline below the earliest useful publication time avoids a builder silently producing bids that peers ignore. Retrieval latency can occasionally carry an early retrieval past the threshold, but relying on that incidental latency is not a useful configuration contract.
- The existing beacon-node validation enforces the same preceding-slot deadline. Consequently this is not speculative validation for an unimplemented rule.
- Comparing with `config.PAYLOAD_ATTESTATION_DUE_BPS` preserves custom-network timing. Fresh upstream mainnet uses 7500, while the builder's existing 9500 default remains unaffected.
- The strict `<` check and equality test match the spec's non-strict acceptance boundary. No clock-disparity allowance belongs in this lower bound: the spec's current/next-slot eligibility helper is a distinct check, and this particular early-bid check compares the receipt time directly.
- Logging a warning instead would leave a misconfigured unattended builder running without reliable useful bids. Silently clamping would obscure the configured schedule. A startup error before loading the key is the smaller and more explicit alternative.

## Verification scope

Reviewed the saved exact-head diff, PR description and saved feedback, builder handler, bidder scheduling path, existing beacon-node bid timing check and fresh upstream specification. The parent owns exact-head execution and reported the focused tests passing 17/17; I did not run tests or modify source.

## Verdict

**SOUND — no fundamental issues.**
