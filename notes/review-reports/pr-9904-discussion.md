PR discussion coverage for ChainSafe/lodestar#9904
Fetched counts:
- Issue comments: 2
- Inline review comments: 4
- Review bodies: 1
Display limit: latest 20 per surface

Issue comments
- #5393757961 twoeths 2026-08-24T10:11:04Z
  https://github.com/ChainSafe/lodestar/pull/9904#issuecomment-5393757961
  @lodekeeper please review, given the last error that you know https://github.com/ChainSafe/lodestar/pull/9489#issuecomment-4706589676
- #5392894001 github-actions[bot] 2026-08-24T08:55:33Z
  https://github.com/ChainSafe/lodestar/pull/9904#issuecomment-5392894001
  ## Performance Report
  ✔️ no performance regression detected

Inline review comments
- #3842487344 twoeths 2026-08-24T10:10:00Z packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:240 reply-to=3841895722
  https://github.com/ChainSafe/lodestar/pull/9904#discussion_r3842487344
  should not happen too, when the block comes again at either source it will be ignored due to forkchoice check
- #3841958634 twoeths 2026-08-24T08:52:46Z packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:296 reply-to=3841895710
  https://github.com/ChainSafe/lodestar/pull/9904#discussion_r3841958634
  this should not happen, the seen cache contains 96 items while gossip only accept messages in the last recent 32 slots, given `DEFAULT_EARLIEST_PERMISSIBLE_SLOT_DISTANCE = 32`
  even if gossip fails due to this, this is by design, because it will fallback to UnknownBlockInput` which calls `getOrReload()`
- #3841895710 chatgpt-codex-connector[bot] 2026-08-24T08:43:22Z packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:296
  https://github.com/ChainSafe/lodestar/pull/9904#discussion_r3841895710
  **<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub> Preserve active payload inputs when enforcing the cap**
  When range sync fills the 96-entry cap and another block is inserted, insertion-order eviction can remove an older-inserted canonical input even if it is recent and still awaiting its envelope or columns. The gossip e...
- #3841895722 chatgpt-codex-connector[bot] 2026-08-24T08:43:22Z packages/beacon-node/src/chain/seenCache/seenPayloadEnvelopeInput.ts:240
  https://github.com/ChainSafe/lodestar/pull/9904#discussion_r3841895722
  **<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub> Recheck the cache after the asynchronous DB read**
  On the DB path, `reloadFromDb()` yields while awaiting `db.block.get()`. A concurrent gossip, API, by-root, or range call can then add the same root and attach an envelope or columns, but this unconditional `set()` ov...

Review bodies
- #5006006783 chatgpt-codex-connector[bot] 2026-08-24T08:43:22Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9904#pullrequestreview-5006006783
  ### 💡 Codex Review
  Here are some automated review suggestions for this pull request.
