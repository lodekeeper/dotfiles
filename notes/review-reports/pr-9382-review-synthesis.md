# PR #9382 Review Synthesis

Reviewed commit: 3534a7aa12cbe756a6deef878b8c1c3c59d2dc0b
Posted review: https://github.com/ChainSafe/lodestar/pull/9382#pullrequestreview-4797546595
Posted at: 2026-07-28 13:09 UTC

## Result

Submitted a `CHANGES_REQUESTED` review as `lodekeeper`.

Inline comments posted:

- https://github.com/ChainSafe/lodestar/pull/9382#discussion_r3665747587 — SSZ `getBlobsV1` compact responses cannot preserve mid-list missing blobs, but Lodestar maps the compact response back by request index.
- https://github.com/ChainSafe/lodestar/pull/9382#discussion_r3665747591 — SSZ network-error fallback is outside the serialized queue item, allowing a later Engine call to overtake the JSON-RPC retry of an earlier failed SSZ call.

The review body also records agreement with the already-existing comments on:

- `PayloadStatusV1` / `ForkchoiceUpdatedResponseV1` wire shape drift versus the current EIP-8178 text.
- Missing `INVALID_BLOCK_HASH` status byte `4` handling in SSZ response decoding.

## Verification

- PR head was still `3534a7aa12cbe756a6deef878b8c1c3c59d2dc0b`.
- Artifact freshness check passed for `review-bugs`, `review-security`, `review-linter`, `review-defender`, `review-devils-advocate`, `review-wisdom`, and `reviewer-architect`.
- Changed-file scope matched the PR file list.
- Existing GitHub discussion was checked to avoid duplicating the already-posted status/container comments.
- `gh auth status` confirmed the acting account was `lodekeeper` before posting.

## Sources Checked

- Current EIP-8178 draft: https://eips.ethereum.org/EIPS/eip-8178
- Historical execution-apis SSZ transport PR #764: https://github.com/ethereum/execution-apis/pull/764
- Current JSON-RPC `engine_getBlobsV1` text: https://github.com/ethereum/execution-apis/blob/main/src/engine/cancun.md#engine_getblobsv1
