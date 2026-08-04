# Review Findings — reviewer-architect — 9505

Reviewer: reviewer-architect
Reviewed commit: 350d13c7c384b379eab3934d0de7b8cd494f5a4d
Generated at: 2026-08-04 09:29 UTC

Reviewer: reviewer-architect
Reviewed commit: 350d13c7c384b379eab3934d0de7b8cd494f5a4d

## Findings

### 1. Heze spec mappings remain marked unimplemented after implementation

Scope: `specrefs/.ethspecify.yml`, `packages/state-transition/src/slot/upgradeStateToHeze.ts`, `packages/types/src/heze/sszTypes.ts`.

Issue: The PR adds source implementations for `upgrade_to_heze` and Heze `PayloadAttributes`, but `.ethspecify.yml` still keeps `PayloadAttributes#heze` under dataclass exceptions and `upgrade_to_heze#heze` under the `# heze (not implemented)` function exceptions. That breaks Lodestar's spec-reference contract: implemented fork logic is no longer checked as a 1:1 mapping to the pinned consensus spec.

Impact: Future Heze spec changes can drift silently because ethspecify will continue treating these implemented surfaces as intentionally unmapped. It also leaves the implementation status ambiguous for reviewers and future fork work.

Recommendation: Remove only the implemented Heze entries from the exception list and add source mappings in `specrefs/dataclasses.yml` for `PayloadAttributes#heze` and `specrefs/functions.yml` for `upgrade_to_heze#heze`. Keep the genuinely unimplemented FOCIL store/fork-choice functions excepted.

References: `specrefs/.ethspecify.yml:100`, `specrefs/.ethspecify.yml:357`, `packages/state-transition/src/slot/upgradeStateToHeze.ts:9`, `packages/types/src/heze/sszTypes.ts:121`.

### 2. Heze block production encodes FOCIL placeholders instead of a boundary for inclusion-list data

Scope: `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts`, Heze fork-choice / inclusion-list integration.

Issue: The Heze production path hard-codes `inclusionListBits` to an empty bitvector and `inclusionListTransactions` to an empty list. The pinned Heze spec derives these from the inclusion-list store via `get_inclusion_list_bits` / `get_inclusion_list_transactions`, which are still listed as unimplemented. This makes the runtime Heze path look like a Gloas extension with zero FOCIL data instead of establishing the required inclusion-list store/pool boundary.

Impact: If a testnet or spec test activates Heze before that boundary exists, produced bids and payload attributes will claim no local inclusion-list obligations regardless of observed lists. Longer term, this bakes a misleading abstraction into block production that later FOCIL work has to unwind.

Recommendation: Keep Heze block production explicitly unsupported until the inclusion-list store/pool abstraction is available, or introduce that boundary now and derive both fields from it. The placeholder values should not be the active Heze production behavior.

References: `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts:359`, `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts:937`, `specrefs/functions.yml:4420`, `specrefs/functions.yml:8957`.
