# alpha4-ptc — implementation spec draft

## Problem
`consensus-specs#4979` adds `ptc_window` to Gloas state and changes `get_ptc()` / `process_epoch()` / fork initialization behavior around cached payload-timeliness committees. Lodestar currently computes PTCs eagerly inside `epochCtx`, but it does not persist the spec-mandated state field and still targets alpha.3 spec refs/tests.

We need the minimal alpha.4 delta needed to pass the relevant spec tests while preserving Lodestar’s preferred runtime pattern: hot-path PTC reads should continue to come from `epochCtx`, not repeated tree access into the state view.

## Proposed approach
1. **Add the canonical spec field**
   - Add `ptcWindow` to Gloas SSZ types using a nested vector shape equivalent to spec `ptc_window`.
   - Do not add new public runtime APIs unless required by existing code.

2. **Hydrate cache from state, similar to proposer lookahead**
   - Keep `epochCtx.getPayloadTimelinessCommittee(slot)` as the hot-path accessor.
   - Change `EpochCache.createFromState()` and `finalProcessEpoch()` to copy the previous/current epoch slices from `state.ptcWindow` into `previousPayloadTimelinessCommittees` / `payloadTimelinessCommittees`.
   - This mirrors `state.proposerLookahead` -> `epochCtx.proposers`.

3. **Maintain `ptcWindow` during epoch processing**
   - Add `processPtcWindow()` in epoch processing for Gloas+.
   - Shift the state window by one epoch and append the newly computed trailing epoch.
   - Reuse `EpochTransitionCache.nextShuffling` when available so we do not recompute the same future shuffling twice.

4. **Initialize `ptcWindow` on Gloas fork and genesis-at-gloas**
   - Add helper `initializePtcWindow()` that returns `[empty previous epoch] + [current/lookahead epochs]`.
   - Use it in `upgradeStateToGloas()`.
   - Also use it in `initializeBeaconStateFromEth1()` for genesis-at-gloas if the alpha.4 tests require it.

5. **Update alpha.4 spec/test metadata**
   - Bump `spec-tests-version.json` and `specrefs/.ethspecify.yml` to `v1.7.0-alpha.4`.
   - Run `ethspecify process` so `specrefs` matches the release.
   - Unskip `gloas/operations/voluntary_exit/pyspec_tests/builder_voluntary_exit__success`.

## Likely files
- `packages/types/src/gloas/sszTypes.ts`
- `packages/types/src/gloas/types.ts`
- `packages/state-transition/src/util/gloas.ts`
- `packages/state-transition/src/epoch/index.ts`
- `packages/state-transition/src/slot/upgradeStateToGloas.ts`
- `packages/state-transition/src/cache/epochCache.ts`
- `packages/state-transition/src/util/genesis.ts` (only if needed for tests)
- `packages/beacon-node/test/spec/utils/specTestIterator.ts`
- `spec-tests-version.json`
- `specrefs/.ethspecify.yml`
- generated `specrefs/*` changes from `ethspecify process`

## Key pitfalls to watch
- Off-by-one window semantics at epoch boundaries.
- Fork-upgrade alignment: after `processPtcWindow()` runs at the end of epoch N, `state.ptcWindow` must be valid for epoch N+1.
- Genesis-at-gloas / tests that mutate balances directly and need the cached window refreshed.
- Avoiding accidental hot-path regressions by reading `state.ptcWindow[...]` directly in validation/state-view methods.
