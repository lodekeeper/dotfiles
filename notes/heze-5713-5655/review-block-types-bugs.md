# Signed block envelope bug review

Reviewer: review-bugs
Reviewed base: 7079b042fa5 (PR #10293, working three-file diff)
Scope:
- packages/types/src/types.ts
- packages/validator/src/services/validatorStore.ts
- packages/validator/test/unit/services/block.test.ts

No functional bugs found. Approved.

All inspected fork-specific signed block SSZ containers contain exactly message and signature, with the corresponding unsigned block message and the common BLSSignature. For a concrete F, the rewritten aliases retain those exact field types. The cross-fork envelope preserves the unsigned message union without introducing independently varying fork-specific metadata or signature formats. Existing blinded mappings, including the Electra aliases for later forks, remain unchanged.

Removing the signBlock assertion and three mock message casts changes no executed operations or returned object fields. The signing root, slashing-protection insertion, signature generation, and block message remain unchanged. No introduced API safety failure found within the allowlist.

Compile/build gates and focused runtime tests are handled by the parent; this report is the independent source review.
