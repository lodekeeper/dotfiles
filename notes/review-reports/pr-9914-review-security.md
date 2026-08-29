Reviewer: review-security
Reviewed commit: 83a43eb9198c1ae535e7c1665565050d990397ce

# Security Review - PR #9914

Scope: only the changed files listed in the task. I used the provided context, the PR net diff, local source at the reviewed commit, and the npm tarballs for `@libp2p/gossipsub` 16.1.1 and 17.1.0.

## Findings

### 🔴 Pooling API-submitted bids after REJECT-only validation lets a builder steer local proposals

File: `packages/beacon-node/src/api/impl/beacon/blocks/index.ts:1068`
File: `packages/beacon-node/src/api/impl/beacon/blocks/index.ts:1073`
File: `packages/beacon-node/src/chain/validation/executionPayloadBid.ts:81`

The new `validateApiExecutionPayloadBid()` deliberately skips all IGNORE-class checks, and the API handler then unconditionally inserts the same bid into `executionPayloadBidPool`. That is safe for gossip peer scoring, but not safe for the local proposer candidate pool.

Concrete scenario:

1. A builder with a valid active builder key submits a bid over `/eth/v1/beacon/execution_payload_bids`.
2. The bid uses the local proposer's exact `(slot, parentBlockRoot, parentBlockHash)` so the proposer-side pool lookup can find it.
3. The bid passes every REJECT check, but fails proposer-policy checks that gossip would IGNORE: for example `feeRecipient` does not match proposer preferences, `gasLimit` is outside the requested target, or `value` is above the builder's coverable balance.
4. The API path stores it in `executionPayloadBidPool` anyway.
5. The local proposer later treats the pooled bid as a p2p candidate. It does not run the direct builder API validator on p2p candidates.

Impact:

- For `feeRecipient` mismatch, state transition does not reject the block; `processExecutionPayloadBid()` stores the pending builder payment to `bid.feeRecipient`. A malicious or buggy builder can therefore cause the validator to sign a valid block that pays the bid value to the wrong execution address.
- For `gasLimit` mismatch, the local proposer can sign a block that violates its own signed preferences, even if it remains consensus-valid.
- For insufficient builder balance, `processExecutionPayloadBid()` / `computeNewStateRoot()` rejects before the invalid block is returned, so I did not find an invalid-block broadcast. It can still burn the builder-block branch during proposal, and if the local engine branch is pending or failed, this can turn into a missed proposal.

This confirms area A as a real local proposer safety issue, with one refinement: balance coverage is rechecked by state transition before broadcast, but proposer preferences are not consensus checks and can still be violated.

Fix:

- Separate "publish this own bid" from "eligible for my local proposal pool"; or
- Before adding API-submitted bids to `executionPayloadBidPool`, run the local proposer acceptability checks that are skipped for gossip: exact current/next slot, known parent payload hash for this node, proposer preferences fee recipient, proposer preferences gas limit, bid increment/known tuple policy, and `canBuilderCoverBid`; or
- Revalidate p2p pool candidates at selection time with a helper equivalent to `validateBuilderApiExecutionPayloadBid()` for the selected parent tuple before passing `builderBid` into block production.

### 🟡 REJECT-only API validation makes flood-publish and regen work unbounded for reachable API callers

File: `packages/beacon-node/src/chain/validation/executionPayloadBid.ts:101`
File: `packages/beacon-node/src/chain/validation/executionPayloadBid.ts:135`
File: `packages/beacon-node/src/api/impl/beacon/blocks/index.ts:1083`
File: `packages/beacon-node/src/network/network.ts:517`

The API path removed the gossip `INVALID_SLOT`, `UNKNOWN_PARENT_BLOCK_HASH`, `BID_ALREADY_KNOWN`, and `BID_TOO_LOW` gates before the new flood publish call. That means the expensive and amplified path is not bounded to "one useful tuple per slot".

Concrete scenarios:

- Regen DoS without a builder key: any caller that can reach the endpoint can submit a bid with a known `parentBlockRoot`, an arbitrarily far-future `slot`, and any signature. `validateApiExecutionPayloadBid()` checks the parent root and then calls `getBlockSlotState(parentBlock, bid.slot, ...)` before the randao/signature rejection. Regen processes empty slots and epoch transitions up to the requested slot on the queued regen path, so a far-future slot can tie up state regeneration before the request is rejected.
- Flood-publish amplification with a valid builder key: a buggy or compromised builder can submit many distinct signed bids for the same slot by varying `parentBlockHash`, `blockHash`, `value`, or other signed fields. Because the API path skips known-tuple, parent-payload, and min-increment checks, each successful call reaches `network.publishSignedExecutionPayloadBid()`, which now sets `{floodPublish: true}`. In Lodestar defaults, non-flood publish targets roughly `GOSSIP_D = 8` mesh/fanout peers, while flood publish sends to every subscribed peer above `publishThreshold`, roughly up to the node's target/max peer set (`targetPeers = 200`, `maxPeers = 210`) on this core topic. Peers should IGNORE many of these messages cheaply, but the local node still serializes and sends them to the whole subscriber set.
- Local pool growth: `executionPayloadBidPool` is keyed by `(slot, parentBlockRoot, parentBlockHash)` and only prunes old slots. Future slots and arbitrary parent hashes can create many entries until those slots become old.

Peers cannot trigger this through gossip relay: the only caller of `publishSignedExecutionPayloadBid()` in the reviewed source is the API handler, and peer gossip goes through `validateGossipExecutionPayloadBid()` plus normal forwarding, not this flood-publish API. The attack surface is therefore "reachable beacon API" or "misbehaving own builder", not arbitrary remote gossip peers.

Fix:

- Add a cheap current-or-next-slot bound before regen on the API path.
- Require `parentBlockHash` to resolve to a known fork-choice payload variant before flood publishing, or at minimum before local pool insertion.
- Do not flood publish or pool bids when `executionPayloadBidPool.add()` returns `Old`, `AlreadyKnown`, or `NotBetterThan`.
- Add a small per-builder/per-slot publication budget for this API route, since the builder controls signed message uniqueness.

## REJECT-Parity and Area Checks

- Self-penalization: current REJECT parity holds. I found the same eight REJECT checks in gossip and API validation at this commit: not-later-than-parent, builder index bounds, active builder, builder version, zero execution payment, max blob commitments, prev_randao, and BLS signature. With this exact code, I do not see a peer-score self-penalization path from a bid accepted by `validateApiExecutionPayloadBid()`.
- Blast radius if this parity drifts later: because `network.ts:517-520` forces flood publish for bids, any future missing REJECT check would broadcast a penalizable message to every subscribed peer above `publishThreshold` in one call, roughly order 200 peers by default instead of the normal mesh/fanout order of 8 to 12.
- Flood-publish source: confirmed limited to the node's own API-submitted bids in changed code. I did not find a peer-gossip path that reuses `publishSignedExecutionPayloadBid()`.
- Area A: confirmed as above for local pool/proposer safety. Coverage is rechecked before returning a block, but proposer preferences are not.
- Area B: no concrete gossipsub 17 security regression found. The 16.1.1 to 17.1.0 package diff adds the per-publish `PublishOpts.floodPublish`, IDONTWANT skip handling, protocol feature gating, and a per-peer topic subscription memory cap. I did not see peer scoring or mesh threshold weakening, and `pnpm-lock.yaml` only changes the gossipsub package version/integrity/snapshot, not transitive resolved versions.
- Area C: refuted the HTTP 500 concern. `ExecutionPayloadBidError` extends `GossipActionError`, and the REST error handler maps that to HTTP 400. The API still drops unknown-parent or regen-failure bids; that is a timeliness/product tradeoff rather than a security finding.
- Area D: confirmed but note-only. Collapsing all regen failures to `UNKNOWN_BLOCK_ROOT` mirrors the gossip path and mainly hurts debugging.
- Area E: confirmed maintainability risk. The security invariant depends on copy-pasted REJECT checks between API and gossip validation. A shared helper or an explicit parity test would materially reduce future self-penalization risk.
- Area F: note-only and pre-existing pattern.
- Area G: confirmed test gaps. The new tests miss `TOO_MANY_KZG_COMMITMENTS`, `INVALID_BUILDER_VERSION`, builder index out-of-bounds, per-publish `floodPublish: true`, far-future slot rejection/regen avoidance, and "API-published but not local-proposer-eligible" cases.

