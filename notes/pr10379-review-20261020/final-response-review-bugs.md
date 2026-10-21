# Final response QA — bug/behavior claims

Reviewed all12 drafts in draft-replies.json against exact PR head119fda5f3bbe03e0b2d26b6e6bd3ce4b4ccebe4b. Read-only; no posts, pushes, or code changes.

## Verdict
Approved subject to the following two small precision corrections. No substantive bug in reveal/identity replies.

1.4329488280: replace “it would normally log about -0.6s ... logs about +11.4s” with “the retrieval target is -0.6s ... +11.4s ...; the actual publication log will be later by retrieval/publication latency.” Source bidder.ts:95–119 calculates getPayloadAt, publication awaited:160, log:163–172. Suggested complete sentence: “With the current9500-bps deadline, the ideal retrieval target for a12s slot is -0.6s relative to the proposal slot, or +11.4s relative to its preceding slot; actual publication is later by retrieval/publication latency.” Keep last sentence about deadline calculation using preceding slot.
2.4330011481: qualify full-value offer to avoid implying affordability/max constraints disappear. Suggested: “10000 makes sense as the neutral default: with zero fixed cost, it uses100% of the reported payload value as the proportional bid, rather than reserving a10% margin. Affordability/configured limits still apply. Operators can opt into a smaller share or a fixed cost.” Source bidPolicy.ts:52–63 computes proportional amount, optional max clamp, and declines bids exceeding coverableGwei. No universal zero-PnL accounting assertion should be added.

## Other drafts

-4330036023 reveal: approved. Fallback exactly builder.ts:211; public doc:64–65, CLI:180–182. Immediate block-driven trigger, last-start cutoff, not completion bound.
-4330028816 identity: approved. Explicit head at identity.ts:116–118; per-slot wait:105,151–152; head post-state from state/utils.ts:70–79; slot1 caveat correctly retained.
-4330006169 admission/floor: approved.1.1ETH admission gate bidder.ts:127–135; affordability preserves MIN_DEPOSIT_AMOUNT plus unsettled bids:137–138. Wording makes no sweeping guarantee against other balance changes.
-4330072517 removed test: accurate to provided old diff-hunk case name; current tests separately cover permanent error first-attempt propagation:259–268 and missing-ID retries:271–289. Does not incorrectly call mixed retry/permanent test redundant or identical coverage.
-4330139287 jwtId: approved. handler.ts:100 forwards optional value; engine jsonRpcHttpClient.ts:266 and restHttpClient.ts:184 include it in token id claim. Adapter has no further builder-specific use. It may be externally consumed, and draft explicitly allows that case.
-4330132833 VC wording: exact quote matches validator/options.ts:201–202; no security-trust claim added.
-4330182333 rename: reasonable technical discussion; options argument type:24–25 and handler:99–100 need matching rename.
-4330126819 short URL description: retains emitPayloadAttributes setup requirement and intentionally omits fallback; fine for requested shortening (not assertion that no fallback exists).
-4329974378 abstraction wording: correct: PayloadSource is interface; Engine-specific adapter implementation does not constrain all implementations.
-4329523765 head_v2: source event contract lines108–114 supports current/next roots keyed to epoch from event head block slot, and empty-to-full same-block update. Draft correctly distinguishes build parent root/hash from dependent root. No new blocking claim found; specialized head agent can validate cache design details.
