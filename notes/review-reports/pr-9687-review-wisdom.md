# Review Findings - review-wisdom - 9687

Reviewer: review-wisdom
Reviewed commit: 9face9a4872302e03cd0804a7a85ad261572f43a
Generated at: 2026-08-05 08:56 UTC

## Findings

- [P2] Centralize the execution-branch layout used for Gloas upgrades and reconstruction. `getLcExecutionRoot()` reconstructs pre-Gloas execution roots from a normalized Gloas branch by slicing off `BLOCK_BODY_EXECUTION_PAYLOAD_GINDEX` depth, then choosing capella or deneb `blockHash` gindices (`packages/state-transition/src/lightClient/spec/utils.ts:231`). `upgradeLightClientHeaderToGloas()` independently constructs the same composite branch with its own capella/deneb split (`packages/state-transition/src/lightClient/spec/utils.ts:514`). That invariant is now spread across two places, and future fork changes to execution header fields or gindices will require keeping them in lockstep. A small fork-aware helper/table for the execution header SSZ type, block-hash gindex, and body proof split, used by both paths and directly round-trip tested, would make this easier to extend without hidden drift.

- [P2] Exercise the Gloas zero-update path through a supported test surface. The new server test reaches into the private `maybeStoreNewBestUpdate()` method and builds a partial `LightClientServer` with several `as never` and `as unknown as IBeaconDb` stubs (`packages/beacon-node/test/unit/chain/lightclient/server.test.ts:65`, `packages/beacon-node/test/unit/chain/lightclient/server.test.ts:90`). That makes the coverage brittle to private refactors and leaves the production import path around sync aggregates, emitted events, and DB interactions untested. Please drive this through the public block/import path or factor the zero-value update construction into a small exported helper that can be tested directly without a half-constructed server.
