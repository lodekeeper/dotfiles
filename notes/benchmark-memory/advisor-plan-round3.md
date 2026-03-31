# gpt-advisor Benchmark Optimization Plan — Round 3 (2026-03-31)

## Phase 1 Changes (immediate)

### Memory stability fixes:

1. **Release 4 remaining module-scoped big-state files** — convert to `beforeValue()` or add explicit `afterAll(() => state = undefined)`:
   - `packages/beacon-node/test/perf/api/impl/validator/attester.test.ts`
   - `packages/state-transition/test/perf/util/epochContext.test.ts`
   - `packages/state-transition/test/perf/util/shufflings.test.ts`
   - `packages/state-transition/test/perf/hashing.test.ts`
   - Est: ~1.5-2GB retained memory freed

2. **Drop standalone base-state singletons** once cached slot states exist:
   - In `packages/state-transition/src/testUtils/util.ts`:
   - After `*CachedState23637`/`*CachedState23638` are built, set `phase0State = null`, `altairState = null`, `electraState = null`
   - Est: ~1.5GB

3. **Stop creating unused clones on warm cache**:
   - In `generatePerfTestCachedStateAltair()`: move `origState = generatePerformanceStateAltair(pubkeys)` inside `if (!cachedState23637)` block
   - Same for `generatePerfTestCachedStateElectra()`
   - Est: ~500MB transient peak per call

4. **Enable CI GC** (`--expose-gc` + `triggerGC: true`):
   - `package.json`: add `--expose-gc` to NODE_OPTIONS
   - `.benchrc.yaml`: set `triggerGC: true`
   - Est: ~0.3-0.8GB practical headroom

### Time reduction fixes:

5. **Gate epoch step-breakdown benches off CI**:
   - `epochPhase0.test.ts`, `epochAltair.test.ts`, `epochCapella.test.ts`
   - Wrap step-breakdown describe blocks in `if (!process.env.CI || process.env.BENCHMARK_FULL === "1")`
   - Keep end-to-end `processEpoch` benchmark
   - Est: ~70-90s saved

6. **Reduce loadState CI scale** (1.5M → 500k):
   - `packages/state-transition/test/perf/util/loadState/loadState.test.ts`
   - CI: 500k seed validators; full/nightly/local: 1.5M
   - Est: ~70-110s saved + lower peak memory

7. **BLS: keep 10k only in CI**:
   - `packages/beacon-node/test/perf/bls/bls.test.ts`
   - CI: `[10_000]`; full/nightly/local: `[10_000, 100_000]`
   - Est: ~45-55s saved

## Phase 2 (only if still needed)

- Trim `bytes.test.ts` browser/deprecated cases
- Reduce `aggregatedAttestationPool` 1.5M → 750k CI-only
- Reduce `findModifiedValidators` 1M → 500k CI-only
- Split into `benchmark:ci` vs `benchmark:full` scripts

## Decision: Do NOT drop Altair
Risk too high — different SSZ tree shape, clone/hash costs, fork-specific code paths. Only partial consolidation in Phase 2 if absolutely necessary.
