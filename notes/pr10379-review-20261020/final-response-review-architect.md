# Final response QA — architect

Reviewed all 12 replies in draft-replies.json against exact head `119fda5f3bbe03e0b2d26b6e6bd3ce4b4ccebe4b`, focusing on reply4329523765. Technical response QA only; no formal PR approval and no code/source/metadata mutations.

## Result

**Ready from an architecture standpoint. No blocking factual correction found.**

Head-tracker reply correctly:
- Uses existing head_v2, not a speculative API.
- Maps current/next dependent roots to the event head-block epoch and following epoch.
- Keeps roots distinct from actual payloadAttributes parent root/hash.
- Handles skipped slots by not keying against clock epoch.
- Retains startup/reconnect/uncovered-epoch fallback, with age ordering against streamed state.
- Limits stale-build discard to relevant branch changes; does not say every head event is a reorg or require canceling every in-flight build.
- Correctly distinguishes legacy head from head_v2 on same-block payload-status changes.

Sources: packages/api/src/beacon/routes/events.ts108–116; packages/beacon-node/src/chain/chain.ts1437–1473; packages/builder/src/services/bidder.ts62–87,103–119,147–160; packages/builder/src/builder.ts240–255; packages/validator/src/services/blockDuties.ts189–219. Read via git show at exact ref.

## One optional precision edit

To make intentional parent/proposer-boost or payload variants explicitly safe, replace:

“On relevant branch changes, discard obsolete in-flight work and recheck its captured parent/preferences before publishing.”

with:

“On relevant branch changes, recheck the captured preferences and whether that parent/variant is still a valid build target before publishing; discard only obsolete work.”

Current wording is not incorrect: “relevant” and “obsolete” already bound it. The proposed wording makes clearer that head != build parent is not, by itself, a reason to discard a build. Do not require equality to the latest canonical head. Preserve payload-attributes targets; do not derive execution hash from beacon root or duty-dependent root.

## Remaining drafts

No blocking architecture/factual error found in the other 11 drafts. Confirmed defaults9500bps/9000share/zero fixed cost/minimum1.1ETH; coverable amount subtracts MIN_DEPOSIT_AMOUNT and unsettled exposure; revealer cutoff is checked before constructing/publishing, not an enforced completion deadline; identity reads head and waits next slot while unresolved. References: defaults.ts6–15, bidder.ts137–140, bidPolicy.ts52–63, revealer.ts55–71, identity.ts76–105,116–119.

9500bps reply's -0.6s is appropriately approximate and conditional on12s slots; retrieval/publication latency can shift actual logs. 10000 share description assumes default limits and zero fixed cost, which context supplies. CLI naming/doc suggestions are recommendations, not assertions of already-applied changes. No new promises about pushing, changing Marko's metadata, or modifying code are made.
