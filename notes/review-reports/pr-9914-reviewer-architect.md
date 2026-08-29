Reviewer: reviewer-architect
Reviewed commit: 83a43eb9198c1ae535e7c1665565050d990397ce

# PR #9914 Architecture Review

Scope reviewed:

- `packages/beacon-node/package.json`
- `packages/beacon-node/src/api/impl/beacon/blocks/index.ts`
- `packages/beacon-node/src/chain/regen/interface.ts`
- `packages/beacon-node/src/chain/validation/executionPayloadBid.ts`
- `packages/beacon-node/src/network/network.ts`
- `packages/beacon-node/test/unit/api/impl/beacon/blocks/publishExecutionPayloadBid.test.ts`
- `packages/beacon-node/test/unit/chain/validation/executionPayloadBid.test.ts`
- `pnpm-lock.yaml`

Sources checked:

- Local `~/lodestar` object `83a43eb9198c1ae535e7c1665565050d990397ce`
- Review context at `~/.openclaw/workspace/notes/review-reports/pr-9914-context.md`
- Gloas `execution_payload_bid` gossip validation in consensus-specs: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md#new-execution_payload_bid
- libp2p gossipsub releases:
  - https://github.com/libp2p/js-libp2p/releases/tag/gossipsub-v17.0.0
  - https://github.com/libp2p/js-libp2p/releases/tag/gossipsub-v17.0.1
  - https://github.com/libp2p/js-libp2p/releases/tag/gossipsub-v17.1.0
- `@libp2p/gossipsub@17.1.0` npm package source for `PublishOpts.floodPublish`

## Findings

### 🟡 `packages/beacon-node/src/api/impl/beacon/blocks/index.ts:1073` - API-only bids can enter the local proposer pool without the local proposer-safety checks

`publishExecutionPayloadBid` now runs only `validateApiExecutionPayloadBid(...)` and then unconditionally inserts the bid into `chain.executionPayloadBidPool.add(...)` before flood-publishing it. The API validator intentionally skips all gossip IGNORE checks, including proposer preferences, parent payload hash/gas-limit compatibility, bid value increment, and builder balance coverage.

Skipping those checks can be reasonable for propagation, because peers classify them as IGNORE and will make their own forwarding decisions. It is not equally safe for local proposer selection. The proposer path later selects a p2p bid only by `(slot, parentBlockHash, parentBlockRoot)` and pushes the candidate into `chain.produceBlock({...builderBid})` without re-running proposer-preference checks.

Refinement of area A:

- Head compatibility is mostly enforced by the tuple lookup in the proposer path.
- `canBuilderCoverBid` is eventually enforced by `processExecutionPayloadBid` during `computeNewStateRoot`; an uncoverable bid should make the builder-block branch fail and fall back to the engine block if the engine block is available.
- Fee recipient and gas-limit preference mismatches are not consensus transition checks. A co-located validator can therefore select an API-inserted bid that peers would not forward and that does not honor the local proposer's advertised preferences.

Concrete recommendation:

- Separate "safe to publish" from "safe to use for local proposal."
- Keep REJECT-only validation before flood publish, but add to `executionPayloadBidPool` only after the local proposer-use checks pass, or revalidate p2p candidates before `candidates.push(...)` in block production.
- At minimum, gate API pool insertion on the tuple-independent local policy checks that block production will not catch: proposer preferences fee recipient and gas-limit compatibility. Coverage can also be checked here to avoid wasting the builder-block branch.

### 🟡 `packages/beacon-node/src/chain/validation/executionPayloadBid.ts:94` - REJECT parity is copy-pasted, so future gossip changes can silently make flood-published API bids self-penalizing

At this commit, REJECT parity holds: the API path includes the same REJECT-class checks as the gossip path for parent slot, execution payment, blob KZG commitment count, builder index, builder active status, builder version, prev_randao, and signature.

The architecture is fragile because those checks are implemented twice: once in `validateApiExecutionPayloadBid` and again in `validateExecutionPayloadBid`. The safety claim for this PR depends on those sets staying identical. If a later spec update or bug fix adds a new gossip REJECT check and only touches `validateExecutionPayloadBid`, Lodestar will still flood-publish locally submitted bids that well-behaved peers reject and penalize.

This is not just a theoretical style preference: Lodestar's nearby validation modules generally use small exported API/gossip wrappers around a shared internal validator, with options for the API-specific differences. That pattern is visible in `aggregateAndProof.ts`, `executionPayloadEnvelope.ts`, and `payloadAttestationMessage.ts`.

Concrete recommendation:

- Extract a shared helper for the REJECT-class bid checks, e.g. `assertExecutionPayloadBidRejectChecks(chain, signedBid, parentBlock, state, caller)`.
- Let the API path do parent lookup/regen and call that helper.
- Let the gossip path retain its cheaper IGNORE/anti-spam ordering, then call the same helper once the required state is available.
- If the helper shape is too intrusive for this PR, add a prominent cross-reference comment plus a unit test that enumerates the expected REJECT codes for both paths. I would still prefer the helper because this file already has enough ordering complexity.

Related note: the new TODO at `packages/beacon-node/src/api/impl/beacon/blocks/index.ts:1067` says to "skip validation for timely publishing once the builder is proven reliable." That should be narrowed or removed. Under flood publish, REJECT validation is the part that protects the node's peer score; only local-use or IGNORE-class gating should be optional.

### 🟢 `packages/beacon-node/test/unit/chain/validation/executionPayloadBid.test.ts:54` - The new API validator tests do not cover every duplicated REJECT branch or the flood-publish wiring

The test file covers valid, unknown parent, regen failure, not-later-than-parent, non-zero payment, inactive builder, wrong randao, and invalid signature. Missing REJECT branches:

- `TOO_MANY_KZG_COMMITMENTS`
- `INVALID_BUILDER_VERSION`
- out-of-bounds `builderIndex >= state.getBuildersLength()`; the current builder-not-eligible test exercises only the inactive-builder branch

There is also no direct regression test that `Network.publishSignedExecutionPayloadBid` passes `{floodPublish: true}` through to `core.publishGossip`.

Concrete recommendation:

- Add the missing API validator branch tests if the duplication remains.
- Add a focused network unit test or thin mock test that verifies only `execution_payload_bid` publishes with `floodPublish: true`.
- If the REJECT helper is extracted, test the helper once and keep API/gossip wrapper tests around the policy differences.

## A-G Verification

### A. Local pool insertion no longer gated by full gossip validation

Confirmed as a local proposer-selection risk, with nuance.

The API bid is inserted into the local pool after REJECT-only validation. Block production will catch consensus invalidity such as insufficient builder coverage during `processExecutionPayloadBid`, but fee-recipient and gas-limit preference mismatches are not enforced by the state transition. Because the proposer selects p2p bids directly from the pool by tuple, those skipped policy checks can still affect a local proposal.

### B. Major gossipsub bump 16 -> 17

Refuted as a blocker.

Using upstream `PublishOpts.floodPublish` is the right architectural layer and is much better than carrying a Lodestar monkeypatch of `selectPeersToPublish`. The 17.1.0 package exposes `PublishOpts.floodPublish` and its implementation explicitly gives the per-publish option precedence over the global `floodPublish` option while preserving `false`.

The 16 -> 17 breaking release note is the new `maxTopicBytesPerPeer` cap, defaulting to 1 MiB of subscribed topic strings per peer. That does not look dangerous for Lodestar's expected topic counts, and Lodestar already supplies an `allowedTopics` set. The 17.1.0 changes also include IDONTWANT enforcement and the per-message flood-publish option; I did not find a scoring/mesh/pruning default change that makes the PR architecturally unsound. A PR description should still call out these release notes because this is a major gossip dependency in a consensus client.

The PR threads the option cleanly: `network.publishSignedExecutionPayloadBid(...)` passes `{floodPublish: true}` to `publishGossip`, and `publishGossip` spreads it into the `PublishOpts` sent to `core.publishGossip`.

### C. Thrown IGNORE surfaces to the builder API caller

Mostly refuted as a correctness issue.

For unknown parent or unavailable state, dropping the API bid is consistent with the PR's self-penalty argument: without the parent branch state Lodestar cannot prove builder eligibility, prev_randao, or signature validity. Publishing anyway could lead to REJECT by peers that do have the parent.

There is still an API ergonomics issue: raw `ExecutionPayloadBidError` will likely escape the method as a generic server error instead of a clear 4xx/404 style response. I did not treat that as a primary architecture finding for this PR.

### D. Regen catch collapses failures to UNKNOWN_BLOCK_ROOT

Confirmed low priority.

This mirrors the existing gossip path and preserves the gossip action contract, but it will be misleading during debugging if regen failed for a reason other than an unknown/pruned block. I would not block this PR on it.

### E. Maintainability / drift risk

Confirmed.

See the second finding above. Given Lodestar's local house style, I recommend a shared helper over a comment-only fix.

### F. Bare `throw new Error(...)` for non-gloas state

Note-only.

It is present in both paths and is inherited from existing code. I would not flag it against this PR.

### G. Test coverage gaps

Confirmed.

See the third finding above. The most important extra tests are the missing duplicated REJECT branches and the `floodPublish: true` network plumbing.

## Spec Classification Cross-Check

Against current consensus-specs Gloas `validate_execution_payload_bid_gossip`:

- Lodestar's REJECT classifications match the spec for non-zero `execution_payment`, too many blob KZG commitments, bid slot not higher than parent, incorrect prev_randao, builder index out of range, inactive builder, wrong builder version, and invalid bid signature.
- Lodestar's IGNORE classifications match the spec for duplicate bid, bid not sufficiently higher than current best, unknown parent block root/state, missing proposer preferences, fee recipient mismatch, unknown parent execution payload hash, gas-limit target mismatch, head incompatibility, and `can_builder_cover_bid`.
- The spec has an explicit IGNORE check that the bid slot is within the parent's proposer lookahead. Lodestar does not spell that out separately in the shown path; it appears to degrade through the dependent-root/proposer-preferences lookup. Since that check is IGNORE-class and the PR's API path intentionally skips IGNORE checks, it does not change the REJECT-parity assessment.

