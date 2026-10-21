# #10422 constant re-export — bounded design consult

Verified live ref `origin/nflaig/builder-bid-deadline` resolves to `6c49831117e19c4a38ad52950e0efaf49f203c33`. Read only requested parent/request comment snapshots and targeted source via git show at this ref. No history/unrelated comment fetching; no edits to source.

## Conclusion: proceed with exactly two files

1. `packages/beacon-node/src/node/options.ts`: import `BLOCK_PRODUCTION_RACE_CUTOFF_GLOAS_BPS` from `../api/impl/validator/index.js`, and add it to the existing “Re-export to use as default values and for validation in CLI args” export block alongside `BUILDER_BID_LAG_BUFFER_MS`. This best matches Marko's explicit request/pattern. A direct named re-export from that module is functionally equivalent and also acceptable, but the existing block is clearer for this nit.
2. `packages/cli/src/cmds/beacon/handler.ts`: merge the cutoff constant into the existing root `@lodestar/beacon-node` named import; remove the now-unnecessary `@lodestar/beacon-node/api` import. No usage or default-value changes.

Do not move the constant definition or change the /api export surface. It stays defined once as1667 in api/impl/validator/index.ts; both exported bindings refer to that same constant.

## Barrel / module risks

Root already exports transitively: `src/index.ts` -> `node/index.ts` -> `node/nodejs.ts` -> `node/options.ts`. Thus no third-file index.ts edit is required.

The new re-export/import is a real runtime dependency on the validator API module (not a type-only import). However, root already imports that implementation through node/nodejs.ts -> api/index.ts -> api/impl/api.ts -> validator/index.ts. CLI already imports both root and /api. This does not introduce a previously unloaded implementation into the existing CLI handler's graph, and native ESM caches the same underlying module rather than duplicating the constant/module execution.

Targeted scan found no direct import of node/options.ts or node/nodejs.ts from api implementation; validator/index.ts reads no node-options binding at module initialization. Its cutoff constant is a plain numeric initialization. No concrete new temporal-dead-zone/cycle hazard was identified that would justify broadening scope to relocating constants. Existing broader package cycles are not evidence that this simple additional export is unsafe.

Static analysis is not a runtime proof. Appropriate verification: standard required lint; type/build checks that resolve the new root export; if practical, a built-artifact import smoke check asserting the root and /api named exports are equal to1667. No new unit-test framework/file is warranted for a pure barrel move. Root should run checks in the implementation worktree, not edit/rebuild the main clean repository.

No values, deadline calculations, validation conditions, options, or behavior should change. Keep stacked PR base on `nflaig/builder-bid-deadline`, not unstable.
