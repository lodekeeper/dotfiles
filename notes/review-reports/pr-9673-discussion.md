PR discussion coverage for ChainSafe/lodestar#9673
Fetched counts:
- Issue comments: 1
- Inline review comments: 16
- Review bodies: 1
Display limit: latest 20 per surface

Issue comments
- #5005593153 gemini-code-assist[bot] 2026-07-17T17:03:32Z
  https://github.com/ChainSafe/lodestar/pull/9673#issuecomment-5005593153
  > [!CAUTION]
  > The consumer version of Gemini Code Assist on GitHub has been sunset. All code review activity has officially ceased.

Inline review comments
- #3605234712 lodekeeper 2026-07-17T18:12:01Z packages/beacon-node/src/api/rest/base.ts:64 reply-to=3605117327
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3605234712
  Done — updated the title to `fix: raise query string arrayLimit to NUMBER_OF_COLUMNS`. The body already referenced `NUMBER_OF_COLUMNS`, so only the title was stale. Will keep the title in sync when a change moves the ...
- #3605201604 nflaig 2026-07-17T18:06:23Z packages/beacon-node/src/api/rest/base.ts:64 reply-to=3605117327
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3605201604
  @lodekeeper next time, please make sure to update the pr title if you do code changes that affect it, the title says 64 which is no longer true since we change to `NUMBER_OF_COLUMNS`
- #3605155296 lodekeeper 2026-07-17T17:57:56Z packages/beacon-node/src/api/rest/base.ts:64 reply-to=3605117327
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3605155296
  Leaving the `qs` note in and not re-triggering CI on the approved PR. matthewkeil's reasoning is what tips it for me — the note is tied to the `qs` dep (and the version floor now pinned in `package.json`), so it's the...
- #3605144091 nflaig 2026-07-17T17:56:09Z packages/beacon-node/src/api/rest/base.ts:64 reply-to=3605117327
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3605144091
  agree, not sure it's worth re-triggering the CI for this though, the `qs` note might be useful if someone tries to query or larger values again, it's definitely strange behavior from `qs` to do this... I am wondering ...
- #3605136081 matthewkeil 2026-07-17T17:54:26Z packages/beacon-node/src/api/rest/base.ts:64 reply-to=3605117327
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3605136081
  open to removing though if you feel strongly about it or others do
- #3605133371 matthewkeil 2026-07-17T17:53:58Z packages/beacon-node/src/api/rest/base.ts:64 reply-to=3605117327
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3605133371
  I actually kinda think that might be worth leaving because its specific to that dep so if we remove the dep we can remove the value.
- #3605125653 spiral-ladder 2026-07-17T17:52:32Z packages/beacon-node/src/api/rest/base.ts:64 reply-to=3605117327
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3605125653
  but dont let this block a release, we can trim it after if ppl agree.
- #3605117327 spiral-ladder 2026-07-17T17:51:00Z packages/beacon-node/src/api/rest/base.ts:64
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3605117327
  nit: not sure if this overexplanation is necessary too, don't need to know `qs` implementation details + this lacks context for newer readers who dont know about the breaking change
  ```suggestion
- #3604995282 lodekeeper 2026-07-17T17:28:32Z packages/beacon-node/src/api/rest/base.ts:93 reply-to=3604877656
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3604995282
  Good catch — raised the cap to `NUMBER_OF_COLUMNS` (128) in c1fa18ec1b so a full-custody `getDebugDataColumnSidecars` request (columns 0..127) parses as an array. Kept it a single global limit rather than route-specif...
- #3604900368 lodekeeper 2026-07-17T17:11:03Z packages/api/test/utils/utils.ts:13 reply-to=3604868459
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3604900368
  Removed; kept only the `arrayLimit: 64` parity change.
- #3604900238 lodekeeper 2026-07-17T17:11:01Z packages/beacon-node/src/api/rest/base.ts:69 reply-to=3604866505
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3604900238
  Trimmed — the doc now just states 64 = largest beacon-API `maxItems` (the `id` lists on `validators` / `validator_balances`), and dropped the qs/CVE/#9399 backstory. Also removed the redundant inline comment at the `a...
- #3604900108 lodekeeper 2026-07-17T17:11:00Z packages/beacon-node/test/unit/api/rest/base.test.ts:32 reply-to=3604861541
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3604900108
  Removed the test file.
- #3604877656 chatgpt-codex-connector[bot] 2026-07-17T17:06:44Z packages/beacon-node/src/api/rest/base.ts:93
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3604877656
  **<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub> Raise the query array limit for data column indices**
  This global cap is still too low for the Fulu debug data-column endpoint: `getDebugDataColumnSidecars` accepts an `indices?: number[]` query array and filters by those indices, while Fulu `DataColumnSidecars` is bound...
- #3604861541 nflaig 2026-07-17T17:05:07Z packages/beacon-node/test/unit/api/rest/base.test.ts:32
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3604861541
  please remove this slop tests
- #3604866505 nflaig 2026-07-17T17:05:07Z packages/beacon-node/src/api/rest/base.ts:69
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3604866505
  no reason to overexplain this.... please trim, later nobody will care about the `qs` situation, just explain why the limit is 64, pretty sure this is even part of the beacon-api spec
- #3604868459 nflaig 2026-07-17T17:05:07Z packages/api/test/utils/utils.ts:13
  https://github.com/ChainSafe/lodestar/pull/9673#discussion_r3604868459
  stop adding this dumb comments everywhere, we got why you did the change here

Review bodies
- #4724644230 chatgpt-codex-connector[bot] 2026-07-17T17:06:44Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9673#pullrequestreview-4724644230
  ### 💡 Codex Review
  Here are some automated review suggestions for this pull request.
