Reviewer: review-devils-advocate
Reviewed commit: 83a43eb9198c1ae535e7c1665565050d990397ce

# PR #9914 — Devil's Advocate review (premise & necessity lens)

PR: feat: flood publish execution payload bids (ChainSafe/lodestar, base `unstable`).
Two orthogonal changes: (1) flood-publish own bids over gossip via gossipsub 16→17 + `{floodPublish: true}`; (2) new bespoke REJECT-only `validateApiExecutionPayloadBid`.

I verified the surrounding code at head (not just the diff): the p2p-bid selection path in
`api/impl/validator/index.ts`, the block-processing state transition in
`state-transition/src/block/processExecutionPayloadBid.ts`, the third bid-validation copy in
`execution/builder/validateBid.ts`, and the full PR commit history (7 commits).

---

## 🔴 1. Dropping commit-1's pool-insert guard IS a real liveness regression (for co-located builder+proposer)

**This is the one finding I'd hold merge on.** Steelmanning the removed guard — and it holds up.

Commit `c1a501b68f` deleted, and the final commit did not restore, this guard on local pool insertion:

```ts
// Only add the bid to the local pool if it passes full gossip validation, a local proposer must
// never commit to a bid that peers would not accept
await validateGossipExecutionPayloadBid(chain, signedExecutionPayloadBid);
const insertOutcome = chain.executionPayloadBidPool.add(...);
```

At head, the handler adds to the pool gated only by the **REJECT-only** `validateApiExecutionPayloadBid`, which deliberately skips `canBuilderCoverBid` (the `BID_TOO_HIGH` IGNORE check).

Now trace what happens to that pooled own-bid — I confirmed all three legs:

1. **Selection does not re-validate.** `api/impl/validator/index.ts:990` pulls the p2p bid with
   `executionPayloadBidPool.getBestBid(...)` and only checks it against `builderConfig.minBid`.
   Unlike builder-API bids (which go through `validateBuilderApiExecutionPayloadBid`, incl. coverage
   at `validateBid.ts:110`), the **p2p pool bid gets no coverage / preference re-check**. It trusts
   pool-insertion-time validation — which just dropped the coverage check.
2. **The state transition DOES enforce coverage.** `processExecutionPayloadBid.ts:55`:
   `if (!canBuilderCoverBid(state, builderIndex, amount)) throw ...insufficient balance`.
3. Therefore: operator's own builder submits (via the beacon `publishExecutionPayloadBid` API) a bid
   with `value >` its excess balance → passes REJECT-only validation → lands in the local pool under
   the proposer's exact head tuple → selected as best p2p bid → `computeNewStateRoot` runs
   `processExecutionPayloadBid` → **throws → block production fails → missed proposal.**

Gossip would `IGNORE` such a bid (`BID_TOO_HIGH`), so peers never propagate it and a *remote* proposer
never sees it. The regression is specifically the **co-located own-builder + own-proposer** case, where
the local pool is populated by the un-coverage-checked API path. It's not a chain-safety issue (the
invalid block never leaves the node — production fails first), but it is a self-inflicted liveness hit
on your own slot, which is exactly what commit-1's guard existed to prevent.

Note the asymmetry that makes this subtle: `canBuilderCoverBid` is classified IGNORE **for forwarding**
(peers just don't relay), but for *your own* proposer it has REJECT-grade consequences. It is the one
skipped IGNORE check whose omission bites locally.

**What resolves it (pick one):**
- Re-validate coverage at p2p bid *selection* in `validator/index.ts` (symmetric with the builder-API
  path), OR
- Keep `canBuilderCoverBid` (and only that) in `validateApiExecutionPayloadBid`, OR
- Author confirms this is intentional: own builder is trusted to self-limit `value ≤ excess balance`,
  and a missed slot on a misbehaving own builder is an accepted failure mode — then at minimum add a
  metric/loud log so operators can see *why* their block production threw.
- A regression test: own bid with `value > excess balance` published via API must not cause block
  production to throw (or must be filtered at selection).

---

## 🟡 2. Is flooding even the right mechanism? — Yes, but the premise deserves an explicit answer

I pushed on the alternatives and they're worse, so I'll say so plainly:

- **Direct-send to the proposer's peer** is not feasible: the proposer is a *validator*, its beacon node
  is an unknown peer. You cannot address "the proposer's node." Gossip exists precisely because the
  recipient is unknown. So targeted send is out.
- **Global mesh-parameter tuning** (D, D_lazy, heartbeat) is *less* surgical than this change, not more:
  it perturbs scoring/propagation for *every* topic. A per-publish `floodPublish` on the single
  `execution_payload_bid` topic, for *own* messages only, is the narrowest possible lever.
- **Plain mesh gossip** adds per-hop latency for a sub-slot-critical message whose recipient may not be
  in your mesh or on your head — the code comment's rationale is sound.

So the premise holds. `floodPublish` is a standard gossipsub v1.1 concept (not a Lodestar hack), and the
bids are tiny so amplification cost is bounded. **But** this is a Lodestar-specific latency optimization,
not a spec/interop requirement — the network sees identical messages, just sooner. Two things I could
*not* verify and the author should supply:
- **The 16→17 changelog.** Empty PR description; installed tree here is gossipsub 15, and public release
  notes for `@libp2p/gossipsub` 17.x weren't indexable. Confirm `PublishOpts.floodPublish` is the
  sanctioned 17.x per-publish API and that **nothing else changed in 16→17 that touches scoring / mesh
  maintenance / pruning defaults** — those are the changes that silently degrade a consensus client.
- **Devnet evidence**: measured latency win and duplicate/bandwidth amplification on a topology with
  real proposer↔builder separation. Otherwise this is an unmeasured optimization.

---

## 🟡 3. There are now THREE hand-maintained copies of the REJECT checks — extract a shared helper

The safety argument for the whole feature ("if it passes REJECT locally, peers won't penalize it")
rests on REJECT-parity, which is currently guaranteed only by copy-paste. At head the same builder
eligibility / version / prev_randao / KZG / signature block exists in **three** places:
`validateExecutionPayloadBid` (gossip), the new `validateApiExecutionPayloadBid` (API), and
`validateBuilderApiExecutionPayloadBid` (`execution/builder/validateBid.ts`). Add a REJECT check to
gossip validation and forget one of the other two → flood-publish silently self-penalizes (P4 gossip
score), or a builder-API bid is under-validated.

I considered the alternative the task raised — reuse `validateExecutionPayloadBid` with a documented
skip-set — and it's the *wrong* fix: the gossip function interleaves IGNORE lookups (proposer
preferences, dependent-root, seen-cache) with REJECT checks and depends on them for ordering, so a
skip-flag would be a maze of conditionals. The right move is to extract the REJECT set into one
`assertBidRejectChecks(state, bid, ...)` (or similar) called by all three. That keeps the bespoke
API function (justified) while making drift structurally impossible. **Resolution:** shared REJECT
helper, or at minimum a prominent cross-reference comment tying the three lists together.

---

## 🟡 4. The final version silently drops own bids on a transient parent race — reversing the earlier intent

Evolution across commits: v0 warned-and-published-anyway when it couldn't validate ("Publishing …
skipped validation"); commit `c1a501b68f`/final removed that and now `validateApiExecutionPayloadBid`
**throws IGNORE** (`UNKNOWN_BLOCK_ROOT`) when the parent block/state isn't available. The handler has
no try/catch around it → propagates to the API layer → HTTP 500 to the operator's own builder, bid not
published.

For safety this is actually the *better* default (you can't confirm REJECT-cleanliness against a branch
you can't load, so don't broadcast). I won't argue to restore blind-publish. **But** for a feature whose
entire justification is timeliness, silently dropping your own bid because the parent block landed a few
ms late (slot-boundary import race) is a real cost. Ask: is dropping correct here, and if so add a
distinct metric/log for "own bid dropped, parent not yet imported" so it's diagnosable rather than a bare
500. (Overlaps context items C + D — D's `.catch()` collapsing every regen failure to
`UNKNOWN_BLOCK_ROOT` compounds the diagnosability problem.)

---

## 🟢 5. The TODO "skip validation for timely publishing once the builder is proven reliable" is a footgun

`// TODO: skip validation for timely publishing once the builder is proven reliable`

"Proven reliable" is not a safe basis to skip the **REJECT** checks. The IGNORE checks are already
skipped and that's defensible. But skipping REJECT checks means publishing bids that well-behaved peers
will REJECT and **penalize your node's gossip score for** — a bad signature or wrong-randao bid from a
"trusted" builder still gets *you* scored down, regardless of the builder's reputation. Builder
reliability and REJECT-cleanliness are orthogonal: a reliable builder can still have a bug, a clock skew,
or a stale randao. Recommend narrowing the TODO to explicitly mean "the IGNORE-class local checks may be
skipped; the REJECT set must always run" — or dropping it. As written it invites a future change that
trades a bounded latency gain for peer-scoring / peering damage.

---

## 🟢 6. Test-coverage gaps (confirms context G)

Missing REJECT-branch tests: `TOO_MANY_KZG_COMMITMENTS`, `INVALID_BUILDER_VERSION`, and the
out-of-bounds `builderIndex >= getBuildersLength()` branch (only the `isActiveBuilder` branch of
`BUILDER_NOT_ELIGIBLE` is exercised). No test asserts `network.publishSignedExecutionPayloadBid` sets
`floodPublish: true` (the old `floodPublish.test.ts` was deleted with the reverted monkeypatch) — given
that flooding is the headline feature, a one-line assertion that the opt is passed is cheap insurance.
Low priority, but #1 above specifically warrants a new test.

---

## Verdict

The two mechanisms are individually defensible: flooding is the right (and most surgical) tool for a
sub-slot own-message, and a bespoke REJECT-only API validator is a reasonable design. My one blocking
concern is **#1** — dropping commit-1's guard removes the only thing preventing a co-located proposer
from committing to its own uncoverable bid, and nothing downstream re-checks coverage before the state
transition throws. Everything else is "answer before merge": the empty description + unaudited major dep
bump (#2), the three-way REJECT duplication (#3), and the timeliness-vs-drop tension (#4). The TODO (#5)
is a latent footgun worth rewording now while the context is fresh.
