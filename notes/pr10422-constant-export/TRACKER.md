# #10422 requested stacked export refactor

- Source: Nico4330293014, reply under Marko4330019829; routed2026-10-20T21:18Z. Only this thread+diff read, explicit restriction respected; no broad discussion/history guards.
- Base: ChainSafe/lodestar:nflaig/builder-bid-deadline at6c49831117e19c4a38ad52950e0efaf49f203c33. This is NOT a branch in nflaig's fork and NOT unstable.
- Worktree: /home/openclaw/lodestar-bid-cutoff-export, branchrefactor/builder-bid-cutoff-export.
- Scope: node/options.ts re-exports original BLOCK_PRODUCTION_RACE_CUTOFF_GLOAS_BPS next to lag buffer; CLI imports both from root. Definition/value/behavior unchanged, existing /api export preserved. Exactly2files,+8/-2 after formatting.
- Design and two independent source reviews approve; public PR/reply text approved. Reports design.md,review-{advisor,bugs}.md,public-text-review.md.
- Validation: root lint passed; fresh API/BN/CLI build passed after initial environment failures. Cached donor had missing package links and wrong native/Fastify links despite matching lockfile blobs. Corrected worktree-only links to declared native2.0.0 and Fastify5.12.5 with plugins; no install/shared-cache mutation.
- Pending gates: BN+CLI check-types and public root/API import smoke. No new unit tests for export-only refactor. Then signed canonical identity commit, fork push, PR base exactlyNico's branch, in-thread reply underroot4330019829 (contains requestchild4330293014), verify metadata/head/diff and update tracking.
- Spec compliance: N/A, no behavior or protocol changes.

## Completed 2026-10-20 21:31 UTC
- All final gates passed: root lint, fresh API/BN/CLI build,BN+CLIcheck-types, public-import smoke (root cutoff1667/APIbindingequality and lag250). Two source reviews and public-text QA approved.
- Initial type-check's missing @ethereumjs/rlp test dependency linked from cached declared4.0.1; no code/manifest changes. No new unit tests for simple export-only change.
- Signed canonical lodekeeper commit `fbea950520b7cb919a9696fff71e1af07d5a8979` pushed normally. https://github.com/ChainSafe/lodestar/pull/10448 is OPEN/non-draft against `nflaig/builder-bid-deadline`, not unstable. Live head/title/body/base and2files/+8/-2/onecommit verified; clean worktree.
- Reply https://github.com/ChainSafe/lodestar/pull/10422#discussion_r4330534479 under root4330019829 containing Nicochild4330293014. No duplicate reply/PR; interruption reconciled before publishing. Metadata and receipts pr-live*.json,reply-result.json,pr-created.txt.
- Guarded BACKLOG update passed; Nico request checklist includes final reply/PR outcome, notification26402193577 deleted. No merge, Nico-branch push, DM or topic completion ping.

## Duplicate notification reconciliation
- Live verification: PR10448 merged by nflaig at2026-10-20T21:38:14Z into nflaig/builder-bid-deadline, merge ab51d68f7797a4c24f9a77dc4d32c002e3d3afcd.
- Nico confirmation: https://github.com/ChainSafe/lodestar/pull/10422#discussion_r4330616649
- Review5591884853 fulfilled by the existing merged nit PR. No duplicate reply or code. Parent10422 remains open.
