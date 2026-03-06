## Summary
Fixes an epoch-boundary bug in payload timeliness committee lookup.

`EpochCache.getPayloadTimelinessCommittee(slot)` previously only served committees for `epochCtx.epoch`.
At epoch boundaries, payload attestation validation can reference `slot - 1` (previous epoch), which caused:

```
Payload Timeliness Committee is not available for slot=<prevEpochSlot>
```

This patch:
- caches previous-epoch payload timeliness committees in epoch cache,
- shifts current -> previous on epoch transition,
- serves committees for current or previous epoch slots,
- still throws for slots older than previous epoch.

## Changes
- `packages/state-transition/src/cache/epochCache.ts`
  - add previous-epoch PTC cache handling
  - update `getPayloadTimelinessCommittee(slot)` lookup logic
- `packages/state-transition/test/unit/cache/epochCache.test.ts`
  - add coverage for previous/current/too-old slot behavior

## Validation
### Local
- `pnpm --filter @lodestar/state-transition lint`
- `pnpm --filter @lodestar/state-transition test:unit -- test/unit/cache/epochCache.test.ts`

### Devnet evidence (local)
- Mixed Teku+Lodestar rerun with fixed image: original PTC error is gone in Lodestar logs.
- Lodestar-only control run with this image reaches justification/finalization (justified=3, finalized=2 by slot 130), with no PTC errors and no VC misses.

## Notes on remaining mixed-client instability
In my local mixed-client and Teku-only control runs, finalization remained unstable/absent due separate interop/topology behavior (outside this patch scope). This PR is scoped to the PTC root-cause fix only.

---
AI-assisted: drafted and validated with OpenClaw; final patch and test assertions reviewed by me.
