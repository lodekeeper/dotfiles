## Summary
Fix the [unstable type-check failure](https://github.com/ChainSafe/lodestar/actions/runs/39576553124) after #10022 made the execution envelope repositories explicit mocked properties.

Reuse the isolated repository provided by `getMockedBeaconDb()` instead of assigning plain repository instances in two archiver tests. Preserve the explicit null response and all existing assertions. No production code changes.

## Validation
- Reproduced both original TS2322 errors locally before the fix.
- `pnpm build`
- `pnpm lint`
- `pnpm check-types`
- `pnpm vitest run --project unit packages/beacon-node/test/unit/chain/archiveStore/` (44 tests passed across 7 files)

## Spec Compliance
- Artifact: N/A
- Reason: test fixture typing only; no production or spec behavior changes.
