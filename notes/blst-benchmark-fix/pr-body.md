## Summary

- align processBlock perf deposit pubkeys with their future validator indices
- give loadState synthetic new validators distinct interop pubkeys
- read only the appended loadState pubkeys instead of caching another large pubkey array
- keep the fix scoped to benchmark fixtures; no production cache behavior changed

## Root Cause

After the blst-z merge, `@chainsafe/lodestar-z` uses a process-wide append-only pubkey cache. The benchmark fixtures still generated synthetic "new" validators with pubkeys that were not valid for their intended validator indices:

- processBlock worstcase deposits used arbitrary `SecretKey.fromBytes(Buffer.alloc(32, i + 1))` keys, which can conflict with restored interop pubkey snapshots at `depositCount + i`
- loadState cloned validator 0 for 2000 synthetic new validators, so each appended validator reused the same pubkey and hit `DuplicatePubkey`

The loadState fix reads only those 2000 appended pubkeys directly from the native cache so the benchmark does not retain another ~1.5M-entry JavaScript pubkey array.

## Verification

- `pnpm benchmark:files packages/state-transition/test/perf/block/processBlockPhase0.test.ts packages/state-transition/test/perf/block/processBlockAltair.test.ts packages/state-transition/test/perf/util/loadState/loadState.test.ts`
- `pnpm lint`
- `pnpm check-types`
- `pnpm build`

AI-assisted.
