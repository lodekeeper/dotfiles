# Bounded bug review: #10422 constant-export follow-up

## Verdict
APPROVED, conditional on root's lint/build/types/import-smoke gates passing. No actionable bug found in the two-file diff against6c49831117e19c4a38ad52950e0efaf49f203c33.

## Verified
- Authoritative working-tree diff changes only packages/beacon-node/src/node/options.ts and packages/cli/src/cmds/beacon/handler.ts. The saved refactor.diff predates multiline import formatting, but actual working-tree diff remains semantically identical.
- node/options.ts imports original BLOCK_PRODUCTION_RACE_CUTOFF_GLOAS_BPS binding from api/impl/validator/index.js and includes that binding beside BUILDER_BID_LAG_BUFFER_MS in its existing export block. No copied value, changed constant, or changed deadline logic.
- Barrel propagation exists: src/index.ts exports node/index.ts, which exports node/nodejs.ts, which exports options.ts at line34. Thus CLI root import is supported without another barrel or package export change.
- CLI removes only the separate @lodestar/beacon-node/api constant import and combines it into existing @lodestar/beacon-node import. Existing references at handler.ts252–255 and their inequality remain unchanged.
- Cycle consideration: node/nodejs.ts already imports ../api/index.js at line20, which re-exports impl/index.js and reaches validator implementation. The new options edge reaches the same validator implementation; constant is only re-exported as a live binding, not read during options default object initialization. No new top-level access of that binding or evident temporal-dead-zone failure introduced. Runtime import smoke remains appropriate to establish delivered graph evaluation.
- Original constant remains exported at api/impl/validator/index.ts133 with value1667, preserving existing API-subpath consumers. Main export addition is additive.

Scope matches requested tiny follow-up. No related PR history fetched, code modified, or external actions performed by reviewer. No recommendation to retarget unstable; requested stack base is Nico's actual ChainSafe branch head.
