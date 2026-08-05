# Review Findings - review-devils-advocate - PR 9687

Reviewer: review-devils-advocate
Reviewed commit: 9face9a4872302e03cd0804a7a85ad261572f43a
Generated at: 2026-08-05 09:01 UTC

## Objections

1. [Medium] `bootstrap.ssz_snappy` is still decoded with the suite fork, not `bootstrap_fork_digest`.

In `packages/beacon-node/test/spec/presets/light_client/sync.ts:207`, the runner selects `sszTypesFor(fork).LightClientBootstrap` before `testFunction` can inspect `meta.bootstrap_fork_digest`. That undercuts the new format handling at `packages/beacon-node/test/spec/presets/light_client/sync.ts:101`: the consensus test format says the bootstrap SSZ type is determined from `bootstrap_fork_digest`, and that it may need upgrading before store initialization. A Gloas sync case with a pre-Gloas bootstrap can therefore fail during fixture loading, or worse, force the vectors to be shaped around Lodestar's static suite fork rather than the spec metadata. Spec reference: https://github.com/ethereum/consensus-specs/blob/ca22f9c268d460afaf17ab51d01514fc545adaa5/tests/formats/light_client/sync.md#bootstrapszz_snappy

Counter-proposal: Treat `bootstrap` exactly like updates. Deserialize it as raw bytes, or use `getSszTypes(meta)` to pick `sszTypesFor(bootstrapFork).LightClientBootstrap` from `meta.bootstrap_fork_digest`, then upgrade to `storeFork` only after decoding.

2. [Low] Non-finality update creation now allocates a full default update just to read two zero fields.

In `packages/beacon-node/src/chain/lightClient/index.ts:681`, `maybeStoreNewBestUpdate()` calls `LightClientUpdate.defaultValue()` on every non-finality best-update write only to copy `finalityBranch` and `finalizedHeader`. That default object also includes the sync committee, sync aggregate, and other fields that are immediately discarded. The old cached zero avoided this allocation, and Gloas adds another large zero layout to churn through on a path that can run repeatedly during normal block import.

Counter-proposal: Keep the fork-specific behavior, but cache only `{finalityBranch, finalizedHeader}` per `ForkName`, or add a small helper that reads those field defaults directly from the fork type. That preserves the Gloas fix without allocating an entire `LightClientUpdate` each time.
