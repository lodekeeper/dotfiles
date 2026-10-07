# EIP-8015 self-review and spec compliance

Verdict: faithful (parent self-review requested by Nico).

Reference: ethereum/consensus-specs#5655; merged head `a5ab894edd2c22494dfe46dc880946d636f5cdf7`; targeted vectors generated from master `c489a99077c16bad7d75053257c50633d12d314d`.

## Layout and transition
- Heze state has width46 active fields with gaps8,9,10,28; no eth1Data,eth1DataVotes,eth1DepositIndex,depositRequestsStartIndex.
- Heze body has width13 active fields with gaps1,6; no eth1Data,deposits. Surviving field order/generalized indices remain unchanged; checked for every field against Gloas and explicit light-client indices735,2945,2946.
- upgradeStateToHeze checks legacy deposit-index equality before changing/committing prestate and copies only surviving fields. Newly added inclusion-list bits remain zero as previous Heze upgrade required.
- Block processing skips Eth1 voting at Heze; epoch skips Eth1 vote-reset; operation processing does not access removed deposits or enforce obsolete empty-deposits condition.
- Pre-Heze validation remains unchanged; Fulu/Gloas reject nonempty legacy deposit bodies.
- Deposit-request start-index writes remain limited to Electra, and post-Heze requests continue queuing properly.

## Consumers
- Heze block production does not include removed body fields; pre-Heze production still includes them.
- State-view Eth1 accessor throws at Heze before accessing the field; native facade follows the same contract. The existing nonoptional interface is preserved, matching the Gloas execution-header accessor.
- Raw signed-block parent payload-hash picker uses correct Heze bid-offset pointer492 instead of Gloas568. Network processor passes actual fork; unit test uses nonempty operation section to exercise offset navigation.
- Existing state-byte loaders calculate offsets by field name and continue working with compact Heze serialization; regression covers state load, modified-validator migration and pubkey/count extraction.
- Genesis defaults preserve RANDAO entropy without adding legacy fields. Legacy proof/index genesis processors explicitly reject Heze.
- API codecs and block-content/signing types use each fork's actual block shape rather than relying on structural inheritance from Phase0/Fulu. Heze local and external signing tests verify real signing roots and header serialization.
- Archive removal computes the root through the supplied actual-fork SSZ view; Gloas/Heze binary put/remove regressions cover root and parent-root indexes.
- Inherited Gloas progressive-list SSZ limits enforce all six body operation bounds and Gloas deposits==0 during wire decoding. Heze omits deposits entirely. Redundant gossip validation loops/errors removed after confirming the SSZ decoder rejects oversized lists before gossip validation; all 26 upstream wire-level boundary cases still pass.
- Legacy V3 engine production/reconstruction is accurately limited to pre-Gloas shapes; supported post-Gloas V4 paths are unchanged.

## Validation
- Exact upstream Heze reftests:92passed across fork(7),pending-deposits(43),sanity(42).
- Standalone EIP-8015 intentionally does not implement EIP-8365's new BLS-validator rejection (independent PR#10292); those six distinct vectors are tested on that PR.
- Exact upstream Gloas compatibility:88passed; targeted unit gates recorded in separate logs.
- Parent independent unit validation:14newSSZ/STF regressions passed;38API/proposal/signing tests passed.
- Parent identified and fixed sibling helper-signature merge conflict by keeping EIP-8365 guard local; current three-way source merge is clean.
- No review-agent verdict used; user explicitly requested self-review. Parent reviewed complete production changes and regression fixtures against formal spec.

## Combined integration and latest independent gates
- Clean three-way source merge, combined snapshot:186 unique upstream cases passed (Gloas88 + Heze98, including six EIP-8365 cases), plus11 deposit unit tests. Initial nested symlink case directories were excluded by the fixture loader; materialized43 cases and verified all93 pending-deposit cases separately.
- Parent V3 production24tests + validator proposal3tests passed. Gossip/state-byte79tests passed. Validator and CLI type checks passed. Final full repository build/check-types/lint all passed. Final test-type changes reviewed: old-fork fixtures remain accurately typed, state-byte writes and legacy runners guarded, SSZ equality uses actual fork types, and gossip fixtures construct real fork-specific block inputs.

## Final operation-limit upstream gate
- Generated26 exact upstream boundary vectors (14pytest tests) for Gloas/Heze operation counts. All26 passed through Lodestar's actual networking harness under a temporary local-only removal of the suite skip. The temporary runner was removed and archived locally; tracked skip policy unchanged.
- Sol implementation gates:117 core regressions,106 gossip/layout/archive/state-byte tests,18 affected legacy helper tests,38 production/API/signing tests passed in separate runs with overlapping coverage.
- Full source and final regression/type diffs self-reviewed by parent; no unresolved implementation issue. No dependency/lockfile changes.

## Simplification requested by Nico, 2026-10-07 08:34 UTC
- Compared the existing Gloas removed execution-header/field patterns; restored established public legacy-helper signatures with local concrete-fork casts and removed all exported PreHeze aliases. Restored eight alias/signature-only files plus two spec runner files and three redundant gossip files to the exact trunk baseline.
- Native/JS Eth1 access now throws for unsupported Heze access without widening interfaces; actual production access remains fork-guarded. Raw-byte picker now requires the actual fork explicitly.
- Reduction: 68 to 55 changed files, 951 to 753 insertions (full PR diff); 198 avoided insertions. Field gaps, transition invariant, fork-specific API/signing/archive correctness and runtime regressions retained.
- Current simplified snapshot: full build, types and lint pass; 159 focused units, 92 generated Heze cases, 88 generated Gloas cases and 26 generated wire-gossip boundaries pass. Initial pre-build types invocation consumed stale declarations and failed; post-build full rerun passed. Local gossip harness archived outside the checkout; skip policy unchanged.
- Parent self-review checked production and regression diff against exact spec source; independent Sol source/design review also approved the exact working diff (SHA256 recorded in simplify-independent-review.md).

## Final published simplification and sibling alignment
- #10293 signed head95577761f36b0192bbef006848ae35ffbef0501c; #10292 type-only headad44c7ba71eded74ea182e9f2a4cf51ec53564ef. Both live OPEN/non-draft on unstable, authorlodekeeper, metadata matches currentdiff; both worktrees clean. No force-push.
- Fork-first helper alignment required matching both the stateunion and insertedforkparam. Actual post-Electra fork preserves registry branch behavior. Final source/design review APPROVE in simplify-integration-review.md; sibling type review APPROVE in simplify-sibling-review.md.
- Final #10293 diff55files,757insertions,170deletions vs original68files,951insertions,182deletions. Root full build/types/lint passed again after final alignment; all206generatedspec cases passed together,11affectedHeze units rerun.159focusedunit gate remains green. #10292 type-only gate: full lint/state-transition types pass.
- Merge-tree in bothdirections returns clean treefd77858b205b7b6b99a4a87ff4301f29ca3bae7a. Earlier combined186case result is historical, not claimed as a fresh combined execution.
