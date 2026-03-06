# Teku + Lodestar interop rerun (PTC previous-epoch fix)

## Setup
- Repo: `~/lodestar-epbs-devnet-0`
- Branch: `fix/epbs-teku-ptc-committee`
- Commit: `ba3fb81f10`
- Lodestar image: `lodestar:epbs-devnet-0-teku-ptc-fix`
- Kurtosis config: `notes/epbs-devnet-0/kurtosis-configs/epbs-devnet-0-teku-lodestar-fixed.yaml`
- Topology: 2x Teku + 2x Lodestar, Geth EL, `gloas_fork_epoch: 1`, Dora enabled

## Root cause addressed
`EpochCache.getPayloadTimelinessCommittee(slot)` only served committees for `epochCtx.epoch`.
At epoch boundary, payload attestations in block `N` reference slot `N-1`, which can be in the previous epoch (e.g. slot 48 block referencing slot 47).
This caused `Payload Timeliness Committee is not available for slot=<prevSlot>` when processing those attestations.

## Code change
- Cache previous-epoch payload timeliness committees in epoch cache.
- Shift current -> previous on epoch transition.
- `getPayloadTimelinessCommittee(slot)` now serves:
  - current epoch committees
  - previous epoch committees (when available)
  - throws for older slots only.
- Added unit tests in `packages/state-transition/test/unit/cache/epochCache.test.ts`.

## Validation
### Local checks
- `pnpm --filter @lodestar/state-transition lint` ✅
- `pnpm --filter @lodestar/state-transition test:unit -- test/unit/cache/epochCache.test.ts` ✅

### Devnet rerun observations
From logs in this directory:
- Lodestar CL:
  - `Payload Timeliness Committee is not available for slot` = **0** occurrences
  - `Error processing block from unknown parent sync` = **0** occurrences
- Lodestar VC:
  - no warn/error lines
  - no `miss` strings
  - ongoing attestation and block publications observed

### Remaining network issues (not this fix)
- Finalization stayed at epoch 0 (all CLs).
- Peer health degraded (Lodestar peers dropped 3 -> 2).
- Teku logs showed repeated validator production failures and `No peers for message topics` warnings.
- Lodestar `cl-3` showed repeated `BLOCK_ERROR_PRESTATE_MISSING` for an old slot-75 unknown block sync item.

## Status
- Reported PTC epoch-boundary bug is fixed in code + covered by tests.
- Full acceptance criteria (`stable peering + finalization`) are **not met yet** in this mixed-client run due additional interop/gossip instability not caused by this patch.
