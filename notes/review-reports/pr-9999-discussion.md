PR discussion coverage for ChainSafe/lodestar#9999
Fetched counts:
- Issue comments: 2
- Inline review comments: 8
- Review bodies: 3
Display limit: latest 20 per surface

Issue comments
- #5532201999 github-actions[bot] 2026-09-03T21:34:47Z
  https://github.com/ChainSafe/lodestar/pull/9999#issuecomment-5532201999
  ## Performance Report
  ✔️ no performance regression detected
- #5532000130 chatgpt-codex-connector[bot] 2026-09-03T20:59:40Z
  https://github.com/ChainSafe/lodestar/pull/9999#issuecomment-5532000130
  <!-- codex-pull-request-review-summary -->
  <!-- codex-security-review:v1 {"blockingSeverityThreshold":"P0","headSha":"090158476d0aecc9cedd6293f0492b3fbb0fa069","mergeGateEnabled":false,"pullRequestNumber":9999,"repository":"ChainSafe/lodestar","status":"comple...

Inline review comments
- #3967140950 lodekeeper 2026-09-09T10:08:30Z packages/validator/test/unit/slashingProtection/attestation.test.ts:21 reply-to=3967018651
  https://github.com/ChainSafe/lodestar/pull/9999#discussion_r3967140950
  Ran this against latest `origin/unstable` (`858e7b16e9`) by overlaying only this PR test file onto a fresh unstable worktree.
  Command after build:
- #3967140968 lodekeeper 2026-09-09T10:08:30Z packages/validator/src/slashingProtection/attestation/attestationByTargetRepository.ts:48 reply-to=3967045303
  https://github.com/ChainSafe/lodestar/pull/9999#discussion_r3967140968
  Double checked. This does cover the full target-epoch range for that validator pubkey, but not the whole slashing DB/bucket.
  The keys are encoded as bucket + pubkey + targetEpoch, and `getLatest()` uses:
- #3967045303 nflaig 2026-09-09T09:58:21Z packages/validator/src/slashingProtection/attestation/attestationByTargetRepository.ts:48
  https://github.com/ChainSafe/lodestar/pull/9999#discussion_r3967045303
  this covers the whole db range? I don't think this is a perf issue but slashing db can be quite large for really old validators
  ah but it also should return on first fin, and does reverse search, so I think this is fine, @lodekeeper double check please
- #3967018651 nflaig 2026-09-09T09:55:14Z packages/validator/test/unit/slashingProtection/attestation.test.ts:21
  https://github.com/ChainSafe/lodestar/pull/9999#discussion_r3967018651
  @lodekeeper can you run these tests against latest unstable branch and tell me which ones are failing
- #3928784815 wemeetagain 2026-09-03T21:16:10Z packages/validator/src/slashingProtection/attestation/index.ts:169 reply-to=3928644396
  https://github.com/ChainSafe/lodestar/pull/9999#discussion_r3928784815
  Pre-existing: the previous write order left the rows as well as the spans. Reverted the reorder in ad3ad0fbc3 to keep this PR to the invariant check, import atomicity is tracked in #10001.
- #3928784460 wemeetagain 2026-09-03T21:16:07Z packages/validator/src/slashingProtection/attestation/index.ts:85 reply-to=3928644411
  https://github.com/ChainSafe/lodestar/pull/9999#discussion_r3928784460
  Addressed in ad3ad0fbc3: import now requires the resulting highest target attestation to have the highest source epoch and rejects the file with `NEW_SURROUNDS_PREV` otherwise, before anything is written.
- #3928644396 chatgpt-codex-connector[bot] 2026-09-03T20:56:33Z packages/validator/src/slashingProtection/attestation/index.ts:169
  https://github.com/ChainSafe/lodestar/pull/9999#discussion_r3928644396
  **<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub> Keep failed imports from leaving span records**
  When an earlier attestation in this loop succeeds but a later one is rejected, `insertAttestation` has already persisted the earlier min/max spans even though none of the corresponding attestation rows are stored. Tho...
- #3928644411 chatgpt-codex-connector[bot] 2026-09-03T20:56:33Z packages/validator/src/slashingProtection/attestation/index.ts:85
  https://github.com/ChainSafe/lodestar/pull/9999#discussion_r3928644411
  **<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub> Base the cutoff on the maximum recorded source epoch**
  The highest-target attestation is not guaranteed to have the highest source epoch because interchange imports can contain slashable pairs that min-max checking itself misses outside the lookback window. For example, i...

Review bodies
- #5152884165 nflaig 2026-09-09T10:16:50Z state=APPROVED
  https://github.com/ChainSafe/lodestar/pull/9999#pullrequestreview-5152884165
  looks good, leaving up for @lodekeeper to give a final approval 😁
- #5152125597 twoeths 2026-09-09T09:05:19Z state=APPROVED
  https://github.com/ChainSafe/lodestar/pull/9999#pullrequestreview-5152125597
  looks good to me, prefer @nflaig to have another look
- #5106747555 chatgpt-codex-connector[bot] 2026-09-03T20:56:32Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9999#pullrequestreview-5106747555
  ### 💡 Codex Review
  Here are some automated review suggestions for this pull request.
