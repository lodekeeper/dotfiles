# Heze #5713 / #5655 implementation tracker

## Goal
Two independent, ready-for-review Lodestar PRs against `unstable`; implement exact spec changes and preserve earlier forks. Nico requested GPT Sol implementation and parent self-review, overriding separate review-agent workflow.

## Baselines
- Lodestar: `fc618d94e9f` (`origin/unstable`). Main checkout left untouched.
- #5713: `68702a5b201ef974817830fc358baf8fd6035c7b`; local `/home/openclaw/consensus-specs-eip8365-5713` (independent old Heze schema).
- #5655: merged `a5ab894edd2c22494dfe46dc880946d636f5cdf7`; current master `c489a99077c16bad7d75053257c50633d12d314d` at `/home/openclaw/consensus-specs-heze-5713-5655`.
- Worktrees: `/home/openclaw/lodestar-heze-eip8365` and `/home/openclaw/lodestar-heze-eip8015`.

## Progress
- [x] Task registered, upstream diffs captured, acting GitHub user lodekeeper verified.
- [x] No existing open PR matching either EIP found in complete open PR title inventory.
- [x] Isolated worktrees and existing dependency store linked; pinned native2.0/Fastify validation dependencies installed separately after finding stale inherited cache; no tracked dependency/lock changes.
- [x] GPT-6.1 Sol bounded implementers, one per independent change; parent owns self-review. EIP-8015 completing final test-type/gossip gates.
- [x] Generate targeted upstream reftests from exact appropriate spec baselines;6 EIP-8365,180 EIP-8015,186 combined cases passed in Lodestar.
- [x] Independently validate lint, types, build and relevant tests; both full root gates passed; EIP-8015 additionally26 upstream gossip boundary cases passed using temporary local-only suite unskip.
- [x] Self-review each entire diff + spec compliance; both verdicts faithful, final test-type regressions reviewed.
- [x] Sign/push commits and create two PRs as lodekeeper; both ready-for-review OPEN against unstable, signed canonical identity, exact heads and metadata verified.

## Spec Compliance Artifacts
- `notes/heze-5713-5655/spec-compliance-eip8365.md` — faithful, parent self-review +6 upstream /11unit tests passed.

- `notes/heze-5713-5655/spec-compliance-eip8015.md` — faithful; source reviewed against all four changed spec documents, root gates and206 standalone upstream cases passed (92Heze+88Gloas+26networking).

Validated #5713 `apply_pending_deposit`, #5655 SSZ active-field maps, upgrade, block/epoch processing, production/serialization consumers and gossip operation limits. Local archived vectors are v1.7.0-beta.0 while CI pin is beta.2, so they are not valid evidence for new Heze changes. Generate exact upstream targeted vectors instead; do not depend on broken upstream nightly packaging.

## First PR
- https://github.com/ChainSafe/lodestar/pull/10292 — EIP-8365, ready for review, base unstable, author lodekeeper, signed head c822cc7315a (follow-up preserves helper signature for clean sibling integration).
- Parent full repository build/typecheck/lint all pass after isolated validation dependency repair.

## Second PR and final verification
- https://github.com/ChainSafe/lodestar/pull/10293 — EIP-8015, ready for review, base unstable, author lodekeeper; signed commit `716dd88a5f62a15dc5a1c8504cdb7c50198b18c6`, worktree clean.
- First PR signed final head `c822cc7315a9e69a961922faa508a0f906caaea4`. Both PR titles/bodies verified against actual diff; sibling links and combined-test evidence included.
- Final EIP-8015 root build/check-types/lint passed;68 files,951 insertions,182 deletions. Includes actual field removal and necessary consumers/test typing, no tracked dependency or fixture artifacts.
-206 standalone upstream cases passed (92Heze,88Gloas,26gossip); combined snapshot186 unique cases +11 deposit units passed. Unit gates117core/106gossip-layout-archive-statebytes/18legacy helpers/38API-production-signing/24V3/3proposal passed in separate overlapping runs.
- Completed2026-10-07 08:12UTC. Main checkout untouched; temporary local gossip runner removed, archived in notes for reproducibility. Existing trunk block-gossip skip policy unchanged.

## PR #10292 explicit-fork review follow-up (2026-10-07)
- Source: nflaig https://github.com/ChainSafe/lodestar/pull/10292#discussion_r4204379754, routed topic50.
- Convention verified against applyDeposit/processDeposit and fork-aware epoch helpers. Private applyPendingDeposit now accepts fork first; both callers pass the existing computed fork. Public signature unchanged; no fork-boundary behavior change.
- Completed 2026-10-07 08:23 UTC: signed `1bd4bef654f` pushed and exact live PR head verified. Advisor final review and bug review approved; lint, full types, state-transition build, 20 unit +6 exact upstream Heze cases passed. Reply: https://github.com/ChainSafe/lodestar/pull/10292#discussion_r4204652469. No topic/DM completion notification; PR title/body still match scope.

## PR #10293 Gloas-pattern simplification (2026-10-07)
- Source: Nico/nflaig Discord message1557310056855375975, 08:34 UTC; simplify removals following Gloas.
- Removed exported PreHeze aliases and restored legacy helpers using local concrete-fork casts; preserved nonoptional state facade with unsupported-fork throw. Reused existing SSZ operation bounds, removed duplicate gossip checks/errors/tests. Explicit actual fork required by raw-byte picker.
- PR diff 68→55 files, 951→753 insertions. All current full build/types/lint passed;159 units+92Heze+88Gloas+26wire-gossip cases passed.
- Parent self-review complete; independent review APPROVE in simplify-independent-review.md, exact working diff SHA256 recorded. Publishing incremental signed follow-up to existing PR; no force-push.

- Simplified #10293 published: signed `b814619e3921b5bac9ed07e6ef333d71c7134533`; GitHub exact head/state/author/base/body verified.
- Latest sibling fork-first signature follow-up caused one merge conflict. Minimal type-only adjustment in #10292 broadens the private helper and its pure isValidatorKnown utility to the already-existing Heze type. Initial two-line attempt failed due SSZ ViewDU bid-type invariance; corrected four-line/two-file type declarations pass package types and full lint, executable statements unchanged. Final independent review pending before signing/push.

## Final published simplification and sibling alignment
- #10293 signed head95577761f36b0192bbef006848ae35ffbef0501c; #10292 type-only headad44c7ba71eded74ea182e9f2a4cf51ec53564ef. Both live OPEN/non-draft on unstable, authorlodekeeper, metadata matches currentdiff; both worktrees clean. No force-push.
- Fork-first helper alignment required matching both the stateunion and insertedforkparam. Actual post-Electra fork preserves registry branch behavior. Final source/design review APPROVE in simplify-integration-review.md; sibling type review APPROVE in simplify-sibling-review.md.
- Final #10293 diff55files,757insertions,170deletions vs original68files,951insertions,182deletions. Root full build/types/lint passed again after final alignment; all206generatedspec cases passed together,11affectedHeze units rerun.159focusedunit gate remains green. #10292 type-only gate: full lint/state-transition types pass.
- Merge-tree in bothdirections returns clean treefd77858b205b7b6b99a4a87ff4301f29ca3bae7a. Earlier combined186case result is historical, not claimed as a fresh combined execution.

## PR #10292 common-state lookup types (2026-10-07)
- Source: nflaig review4204961114. Both fork-independent lookup predicates now use the existing CachedBeaconStateAllForks type, imported from cache/stateCache.js following util/shuffling.ts. No aliases/casts/runtime changes.
- Mirrored the same two predicate signatures in sibling #10293; its mutating helpers retain post-Electra state unions. Three-way file merge now clean; full merge-tree verification follows signed commits.
- Completed 2026-10-07 09:17 UTC: both exact diffs independently approved; full lint/types and state-transition builds pass;21/10 focused unit cases pass. Signed commits02524c9b2fa/7079b042fa5 pushed without force. Full bidirectional merge-tree clean8d95e36f95b3; PR metadata verified. Reply https://github.com/ChainSafe/lodestar/pull/10292#discussion_r4205136028. No topic/DM completion ping.

## PR #10293 block-service mock typing (2026-10-07)
- Source: nflaig review4204969241. Completed 2026-10-07 09:45 UTC.
- Diagnosis: removing3 casts reproduced3 TS2322 failures. Callback mocks constructed an envelope around an all-forks message union, while signed aliases retain exact per-fork envelopes. Heze field removal exposed the lost union correlation.
- Rejected experiment: aggregate signed aliases + removal of existing production assertion passed source review/lint/types-package build but failed global types with7 SSZ API boundary errors. Never committed/pushed; fully discarded. Initial source-only approvals and stale draft pass claims were not used for acceptance or posted.
- Final solution: only block.test.ts changed. Three concrete signed fixture mocks plus one-call/signing-input identity checks; publishing assertions preserved. Exported SSZ aliases and production signing unchanged.
- Fresh gates pass: full build/types/lint;6 block-service/Heze SSZ tests plus8 targeted signing tests,11 unrelated signing tests excluded by filter. No broad spec rerun claimed.
- Exact diff and response explanation independently approved by advisor and bug reviewer; reports review-block-fixtures-{advisor,bugs}.md. Logs review-block-fixtures-{build,global-types,lint,unit,signing}.log.
- Signed incremental lodekeeper commit `48123ba414230df3d03fa14b724bb93eede40efd` pushed without force. Live #10293 head/title/body verified;55changed files/766insertions. #10292 remains02524c9b2fa; bidirectional merge-tree clean `e42c9e5f7d90362447e804ee077699c8b7917eee`.
- Posted reply: https://github.com/ChainSafe/lodestar/pull/10293#discussion_r4205405107. Metadata/result artifacts review-block-fixtures-pr10293.md, review-block-fixtures-pr-live-final.json, review-block-fixtures-reply-result.json. Checklist handled; notifications marked done. No topic/DM completion ping.
