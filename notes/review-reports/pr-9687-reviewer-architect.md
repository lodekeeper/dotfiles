# Review Findings - reviewer-architect - 9687

Reviewer: reviewer-architect
Reviewed commit: 9face9a4872302e03cd0804a7a85ad261572f43a
Generated at: 2026-08-05 09:07 UTC

## Findings

### 1. Bootstrap decoding still ignores the vector fork digest

File: `packages/beacon-node/test/spec/presets/light_client/sync.ts:206`

**Scope** - Multi-fork light-client sync spec harness, especially the newly unskipped Gloas fork vectors.

**Issue** - The sync test format says `bootstrap.ssz_snappy` is a `LightClientBootstrap` whose SSZ type is determined from `meta.bootstrap_fork_digest`, and then it may need to be upgraded to `store_fork_version`. This runner still registers a static `bootstrap` SSZ type from the directory fork. For `gloas/light_client/sync` cases where the trusted bootstrap is pre-Gloas, the file is decoded as a Gloas bootstrap before lines 102-105 can look at `bootstrap_fork_digest` and upgrade it.

**Impact** - Valid cross-fork vectors can fail during fixture loading or be decoded under the wrong container shape, so removing the `gloas/light_client/sync` skip does not actually give a robust spec-alignment signal for the Gloas store upgrade path.

**Recommendation** - Make bootstrap decoding fork-aware before deserialization, either with `getSszTypes(meta)` or by loading `bootstrap` as raw bytes like updates. Resolve `bootstrapFork` from `meta.bootstrap_fork_digest`, deserialize with `sszTypesFor(bootstrapFork).LightClientBootstrap`, and only then call `upgradeLightClientBootstrap` when `bootstrapFork < storeFork`.

## Architectural Summary

Production beacon-node changes keep the dependency direction intact and the Gloas execution proof helper matches the consensus-spec Gloas light-client shape. The main architecture gap I found is in the multi-fork spec harness: updates are decoded by their fork digest, but bootstraps are still decoded by path fork.
