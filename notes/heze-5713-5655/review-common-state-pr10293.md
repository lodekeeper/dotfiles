## Summary

Implement [consensus-specs #5655](https://github.com/ethereum/consensus-specs/pull/5655), EIP-8015, for Heze.

- Remove legacy Eth1 state/body fields with progressive-container gaps, preserving surviving generalized indices.
- Require the legacy deposit mechanism to be disabled before upgrade; skip removed-field processing at Heze.
- Follow existing Gloas patterns: local fork guards/casts, unchanged legacy-helper signatures and state-view interfaces. No extra PreHeze type aliases.
- Adapt production, API/signing shapes, serialized-block offsets and archive indexing for Heze while preserving earlier forks.
- Reuse existing Gloas SSZ list limits for gossip operation bounds; no duplicate count validation or new gossip error code.
- Preserve schema-correct genesis defaults and reject legacy proof-genesis processing at Heze.

Simplified following maintainer feedback: **68 to 55 changed files, 951 to 757 insertions**. Required schema/consumer changes and behavioral regressions remain.

The private pending-deposit helper also follows the fork-first convention used in the sibling PR; passing the actual post-Electra fork preserves registry behavior.

Independent of [EIP-8365 (#10292)](https://github.com/ChainSafe/lodestar/pull/10292); this PR does not add its new BLS-validator rejection.

## Testing

- Shared lookup-type cleanup: full lint/types, state-transition build and **10 focused deposit/consolidation unit tests passed**. The two PRs still merge cleanly in both directions.

Latest simplified snapshot:
- `pnpm build`, `pnpm check-types`, `pnpm lint`: passed.
- **159 focused unit tests** covering Heze SSZ/transition, Gloas SSZ, state loading, deposits, block production and serialized offsets: passed.
- Manually generated upstream minimal fixtures from consensus-specs `c489a99077c16bad7d75053257c50633d12d314d` (includes merged #5655): **92 Heze + 88 Gloas cases passed** in Lodestar.
- **26 generated upstream gossip boundaries passed** through the wire-decoding harness after removing redundant gossip checks. Temporary local-only suite unskip; tracked skip policy unchanged.

Original implementation also passed API/signing/archive and V3/proposal tests, and a combined EIP-8015/EIP-8365 snapshot passed 186 upstream cases. Those earlier results are not claimed as reruns on this simplified head.

Validation uses isolated dependencies matching trunk's pins; no dependency or lockfile changes. Relevant fixtures were generated directly because upstream nightly packaging was unavailable.

## Spec Compliance

- Artifact: `notes/heze-5713-5655/spec-compliance-eip8015.md` (local self-review record).
- Verdict: faithful.
- References: `heze/beacon-chain.md`, `heze/fork.md`, `heze/p2p-interface.md`, `heze/validator.md` from #5655.

Implemented with GPT-6.1 Sol and self-reviewed against the spec and full diff, as requested.
