# Concrete signed fixture bug review

Reviewer: review-bugs
Reviewed base: 7079b042fa5 (PR #10293, working one-file diff)
Scope: packages/validator/test/unit/services/block.test.ts

No functional bugs found. Approved.

Each fixed signed fixture shares its message object with the corresponding produceBlockV3/V4 response. The new once-only and reference-identity signing assertions verify that the produced message reaches signBlock, closing the coverage gap a constant mock response otherwise creates. Existing full/blinded publish assertions and production-argument assertions remain intact. The Gloas test retains its original fee-recipient-focused coverage and gains the same signing-input checks. No production signing or shared type changes remain in the working diff.

Draft explanation approved: Casts hid the cross-fork union correlation lost by mock reconstruction; Heze removes eth1Data/deposits, exposing it. Concrete signed fixtures plus signing-input identity checks remove the assertions. Shared per-fork SSZ types and production signing remain unchanged.

Full compile/build checks and focused runtime tests are handled by the parent.
