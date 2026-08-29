# PR #9914 — flood publish execution payload bids — CONSOLIDATED REVIEW

- **Author:** markolazic01 (Marko L), curated from nflaig/lodestar#4
- **Requested by:** Marko in Discord #lodestar-builder › "BN Bid Publishing" (2026-08-29)
- **Head reviewed:** 83a43eb9198c1ae535e7c1665565050d990397ce · base unstable · +301/−12, 8 files
- **Reviewers:** wisdom, devils-advocate, architect, security, bugs (all 5 done) + my own source re-verification

## VERDICT: No hard blockers. Design is sound.

The core safety argument holds: locally flood-published own bids go through REJECT-only API
validation, and every REJECT check present in the gossip path is present in the API path, so a
flood-published bid cannot emit anything peers would REJECT (no peer-score self-penalty). The
gossipsub 16→17 major bump was cleared as non-blocking by two reviewers.

## Corrections I made to my own earlier review (both overstatements, caught by reading source)

1. **RETRACTED: "pubkey type blocker."** I earlier claimed `createSingleSignatureSetFromComponents(builder.pubkey, …)`
   passes raw bytes where a `PublicKey` is expected (TS2345). **Wrong.** The helper signature is
   `createSingleSignatureSetFromComponents(pubkey: Uint8Array, …)` (`state-transition/src/util/signatureSets.ts:93`).
   Raw 48-byte `builder.pubkey` is exactly right; the API (`:182`) and gossip (`:454`) call sites are identical.
   No type error, no runtime break.

2. **DOWNGRADED: "missed slot" → value-degradation.** The coverage skip is real (see 🟡 #1), but block
   production races a local self-build against the bid block (`api/impl/validator/index.ts` ~1113). If the
   uncoverable bid's block throws in the state transition, the proposer falls back to the local self-build
   block (`EngineBlockSelectionReason.BuilderError`, ~1204). So it is **not a missed slot** — the harm is
   losing the value of the valid lower p2p bid that would otherwise have been used.

## Should-fix (🟡)

1. **API path skips IGNORE-class checks (coverage + proposer preferences).**
   `validateApiExecutionPayloadBid` is REJECT-only and, per its own docstring (lines 86-90), intentionally
   omits `canBuilderCoverBid`, proposer-preference match, head-compat, first-bid-per-tuple, value-increment.
   Rationale in the docstring: those only limit *forwarding of peers'* bids. Gap: for a **co-located
   builder+proposer**, the API path also `pool.add`s the bid locally (`blocks/index.ts:1074`), and selection
   (`getBestBid`) does not re-check coverage (`canBuilderCoverBid` is used only in the gossip validator and
   the builder-API validator — not the pool, not selection). So a buggy/misconfigured own builder submitting
   an uncoverable bid can win selection over a valid lower p2p bid; the bid block then fails the state
   transition and the proposer self-builds — forgoing the legitimate bid. Fee-recipient / gas-limit
   preference mismatches are *not* caught by the state transition at all, so a locally-submitted mismatched
   bid can produce a **valid** block that violates the operator's own proposer preferences.
   → Re-check coverage + preferences at selection, or don't skip them in the API validator.

2. **REJECT-check parity enforced only by copy-paste.** The REJECT checks (not-later-than-parent,
   builder-bounds, builder-active, builder-version, non-zero-payment, too-many-KZG, prev-randao, signature)
   are hand-duplicated across three validators (API path, gossip shared path, builder-API `validateBid.ts`)
   and are already ordered differently (API hoists cheap payment/KZG above regen). Parity is the feature's
   whole safety basis. → Extract each REJECT check into a small throwing helper the paths call in their own
   order; minimum is a "keep in sync" cross-reference comment.

3. **Test gap on the headline behavior.** `{floodPublish: true}` is wired at `network.ts:174`, but the
   handler unit tests mock `publishSignedExecutionPayloadBid`, so nothing asserts the flag is actually
   passed to the gossip publish. No cases for TOO_MANY_KZG, INVALID_BUILDER_VERSION, or the builder
   out-of-bounds branch. (NB: no deleted `floodPublish.test.ts` exists in this diff, contra one reviewer's
   summary.)

## Nits (🟢)

- Empty PR description ("To be added.").
- `// TODO: skip validation for timely publishing once the builder is proven reliable` (`blocks/index.ts:1067`)
  is a footgun — skipping REJECT checks would penalize *your* node regardless of builder trust. Should
  reference a tracking issue and scope to non-REJECT checks only.
- API-path regen `.catch(() => throw IGNORE UNKNOWN_BLOCK_ROOT)` (~`:138`) drops the underlying cause and
  mislabels every regen failure as `UNKNOWN_BLOCK_ROOT`.
- Own bids are silently dropped (IGNORE) on a transient parent-import race; for a timeliness feature, a
  metric on that drop would help.
- gossipsub 16→17: per-publish floodPublish, IDONTWANT handling, protocol feature gating, topic memory cap;
  no scoring/mesh weakening found. Non-blocking, but a changelog note + devnet numbers would strengthen the PR.

## Source-verified facts (head 83a43eb)
- `createSingleSignatureSetFromComponents(pubkey: Uint8Array, …)` — signatureSets.ts:93
- API validator REJECT-only, skips coverage — executionPayloadBid.ts:94-195 (docstring 86-90)
- gossip validator enforces `canBuilderCoverBid` as IGNORE — executionPayloadBid.ts:433
- API handler pools + flood-publishes after REJECT-only validation — blocks/index.ts:1057-1083
- selection `getBestBid`, no coverage re-check — validator/index.ts:983,990
- self-build fallback on bid-block error — validator/index.ts ~1204 (EngineBlockSelectionReason.BuilderError)
