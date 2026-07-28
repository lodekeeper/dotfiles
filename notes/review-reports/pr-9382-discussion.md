PR discussion coverage for ChainSafe/lodestar#9382
Fetched counts:
- Issue comments: 2
- Inline review comments: 9
- Review bodies: 2
Display limit: latest 20 per surface

Issue comments
- #4515557022 codecov[bot] 2026-05-22T05:55:51Z
  https://github.com/ChainSafe/lodestar/pull/9382#issuecomment-4515557022
  ## [Codecov](https://app.codecov.io/gh/ChainSafe/lodestar/pull/9382?dropdown=coverage&src=pr&el=h1&utm_medium=referral&utm_source=github&utm_content=comment&utm_campaign=pr+comments&utm_term=ChainSafe) Report
  :white_check_mark: All modified and coverable lines are covered by tests.
- #4487177480 github-actions[bot] 2026-05-20T16:32:00Z
  https://github.com/ChainSafe/lodestar/pull/9382#issuecomment-4487177480
  ## :warning: **Performance Alert** :warning:
  Possible performance regression was detected for some benchmarks.

Inline review comments
- #3286193225 chatgpt-codex-connector[bot] 2026-05-22T06:02:43Z packages/beacon-node/src/execution/engine/sszRestEncoding.ts:58
  https://github.com/ChainSafe/lodestar/pull/9382#discussion_r3286193225
  **<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub> Encode PayloadStatus with spec field shapes**
  This container uses `latestValidHash` as `List[Bytes32, 1]`, but the SSZ-REST Engine schema defines `PayloadStatusV1.latest_valid_hash` as fixed `Bytes32` (zero-hash sentinel for absence), and `ForkchoiceUpdatedRespon...
- #3286193229 chatgpt-codex-connector[bot] 2026-05-22T06:02:43Z packages/beacon-node/src/execution/engine/sszRestEncoding.ts:474
  https://github.com/ChainSafe/lodestar/pull/9382#discussion_r3286193229
  **<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub> Handle INVALID_BLOCK_HASH status byte**
  `statusByteToEnum` maps only values 0-3 and throws on any other byte, but `PayloadStatusV1` also includes `INVALID_BLOCK_HASH` (value 4). When an EL returns that valid status for `newPayload`, the SSZ path will throw ...
- #3265734588 gemini-code-assist[bot] 2026-05-19T10:59:59Z packages/beacon-node/src/execution/engine/sszRestEncoding.ts:287
  https://github.com/ChainSafe/lodestar/pull/9382#discussion_r3265734588
  ![critical](https://www.gstatic.com/codereviewagent/critical.svg)
  The SSZ encoding for the `getBlobs` request is incorrect. According to EIP-8161, the request body for `engine_getBlobsV1` is a `List[Hash32, 128]`. Since `Hash32` is a fixed-size type, the SSZ encoding of the list is ...
- #3265734600 gemini-code-assist[bot] 2026-05-19T10:59:59Z packages/beacon-node/src/execution/engine/sszRestEncoding.ts:519
  https://github.com/ChainSafe/lodestar/pull/9382#discussion_r3265734600
  ![critical](https://www.gstatic.com/codereviewagent/critical.svg)
  The `getBlobs` response decoding incorrectly expects a `list_offset`. As `BlobAndProof` is a fixed-size type, the `List[BlobAndProof]` is encoded as a simple concatenation of items. The current logic will fail to deco...
- #3265734609 gemini-code-assist[bot] 2026-05-19T10:59:59Z packages/beacon-node/src/execution/engine/http.ts:201
  https://github.com/ChainSafe/lodestar/pull/9382#discussion_r3265734609
  ![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)
  The `SszRestClient` is initialized using only the first URL from `opts.urls`. While the fallback to JSON-RPC (which handles multiple URLs) ensures correctness, this implementation will cause a timeout or connection er...
- #3265734615 gemini-code-assist[bot] 2026-05-19T10:59:59Z packages/beacon-node/src/execution/engine/http.ts:252
  https://github.com/ChainSafe/lodestar/pull/9382#discussion_r3265734615
  ![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)
  The logic for determining the Engine API version based on the fork is repeated in `notifyNewPayload`, `notifyForkchoiceUpdate` (line 421), and `getPayload` (line 555). This duplication increases the risk of inconsiste...
- #3265734617 gemini-code-assist[bot] 2026-05-19T10:59:59Z packages/beacon-node/src/execution/engine/sszRestClient.ts:150
  https://github.com/ChainSafe/lodestar/pull/9382#discussion_r3265734617
  ![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)
  This manual hex-to-bytes conversion is redundant. The `@lodestar/utils` package already provides a robust `fromHex` function which is more efficient and handles edge cases like the '0x' prefix correctly. It is recomme...
- #3265733834 github-advanced-security[bot] 2026-05-19T10:59:51Z packages/beacon-node/src/execution/engine/http.ts:192
  https://github.com/ChainSafe/lodestar/pull/9382#discussion_r3265733834
  ## CodeQL / Polynomial regular expression used on uncontrolled data
  This [regular expression](1) that depends on [library input](2) may run slow on strings with many repetitions of '/'.
- #3265733855 github-advanced-security[bot] 2026-05-19T10:59:51Z packages/beacon-node/src/execution/engine/sszRestClient.ts:70
  https://github.com/ChainSafe/lodestar/pull/9382#discussion_r3265733855
  ## CodeQL / Polynomial regular expression used on uncontrolled data
  This [regular expression](1) that depends on [library input](2) may run slow on strings with many repetitions of '/'.

Review bodies
- #4342910717 chatgpt-codex-connector[bot] 2026-05-22T06:02:43Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9382#pullrequestreview-4342910717
  ### 💡 Codex Review
  Here are some automated review suggestions for this pull request.
- #4318276722 gemini-code-assist[bot] 2026-05-19T10:59:58Z state=COMMENTED
  https://github.com/ChainSafe/lodestar/pull/9382#pullrequestreview-4318276722
  ## Code Review
  This pull request implements EIP-8161, introducing an SSZ-REST transport for the Engine API to improve communication efficiency. It adds a new `SszRestClient` and specialized encoding/decoding logic, updating the `Exe...
