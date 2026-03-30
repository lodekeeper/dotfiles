# Coding Context — Fix Benchmark Failures

## Problem
After bumping `@chainsafe/benchmark` from 1.2.3 to 2.0.2, benchmark CI now properly reports errors that were previously silently swallowed. 5 benchmark test files are failing:

### Failing files and errors:

1. **`packages/beacon-node/test/perf/chain/opPools/aggregatedAttestationPool.test.ts`**
   - Error: `Does not support producing blocks for pre-electra forks anymore`
   - Cause: Uses `generatePerfTestCachedStateAltair` which creates an Altair-era state, but `getAttestationsForBlock()` at line 216 of `aggregatedAttestationPool.ts` now rejects forks before Electra
   - Fix needed: Update to use Electra state (need `generatePerfTestCachedStateElectra` or equivalent)

2. **`packages/beacon-node/test/perf/chain/produceBlock/produceBlockBody.test.ts`**
   - Error: `REGEN_ERROR_NO_SEED_STATE`
   - Cause: Uses `generatePerfTestCachedStateAltair` to create a BeaconChain — state is incompatible with current chain initialization
   - Fix needed: Update to use Electra state

3. **`packages/state-transition/test/perf/block/processAttestation.test.ts`**
   - Error: `BitArray set bitIndex 31 beyond bitLen 31` (flaky, may pass locally but fails in CI)
   - Cause: `getAggregationBits(len, participants)` in `util.ts` uses 0-based indexing — `bits.set(participants-1)` is fine but `bits.set(participants)` when participants==len is out of bounds
   - Fix: Check `util.ts` line ~258-264 for off-by-one in BitArray creation

4. **`packages/state-transition/test/perf/block/processBlockAltair.test.ts`**
   - Same BitArray error as #3

5. **`packages/state-transition/test/perf/block/processEth1Data.test.ts`**
   - Same BitArray error as #3

## Key Files
- `packages/state-transition/src/testUtils/util.ts` — contains `generatePerfTestCachedStateAltair`, `generatePerfTestCachedStatePhase0`
- `packages/state-transition/test/perf/block/util.ts` — contains `getBlockAltair`, `getAggregationBits`
- `packages/beacon-node/src/chain/opPools/aggregatedAttestationPool.ts` — line 216: pre-electra rejection

## Constraints
- Branch: `fix/benchmark-failures` on `~/lodestar`
- Run `pnpm lint` before committing
- Run `pnpm benchmark:files <file>` to verify each fix
- Keep changes minimal — fix the test setup, don't change production code
- Node 24: `source ~/.nvm/nvm.sh && nvm use 24`
- Project convention: no scopes in commit messages (e.g. `test: fix benchmark failures` not `test(perf): ...`)
- If creating `generatePerfTestCachedStateElectra`, export it from `test-utils` like the existing ones

## Verification
Run each failing benchmark file individually:
```
pnpm benchmark:files packages/beacon-node/test/perf/chain/opPools/aggregatedAttestationPool.test.ts
pnpm benchmark:files packages/beacon-node/test/perf/chain/produceBlock/produceBlockBody.test.ts
pnpm benchmark:files packages/state-transition/test/perf/block/processAttestation.test.ts
pnpm benchmark:files packages/state-transition/test/perf/block/processBlockAltair.test.ts
pnpm benchmark:files packages/state-transition/test/perf/block/processEth1Data.test.ts
```
