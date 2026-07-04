# Gloas builder constants drift — 2026-07-03 re-verification pass

Re-verified Lodestar Gloas builder constants against `consensus-specs` `origin/master`
(local checkout is on my own `proposal/fcr-monotonic-confirmed` branch, 81 behind master —
so all comparisons are against fetched `origin/master`, not the stale local tree).

Trigger: `git log origin/master --since=2026-06-19 -- specs/gloas/` surfaced a batch of
constant changes, **all merged 2026-07-03** (same day as this pass).

## Findings — 3 stale constants on Lodestar `unstable`

| Constant | Lodestar `unstable` | Spec `master` | Spec PR |
|---|---|---|---|
| `BUILDER_WITHDRAWAL_PREFIX` | `0x03` | `0xB0` | #5416 |
| `MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD` (mainnet **and** minimal preset) | `256` (`2**8`) | `64` (`2**6`) | #5420 |
| `MIN_BUILDER_WITHDRAWABILITY_DELAY` (mainnet config) | `8192` | `64` | #5426 |
| `MIN_BUILDER_WITHDRAWABILITY_DELAY` (minimal config) | `2` | `2` | ✅ in sync |

### Lodestar source locations
- `packages/params/src/index.ts:149` — `export const BUILDER_WITHDRAWAL_PREFIX = 0x03;`
  - consumed by `packages/state-transition/src/util/gloas.ts:31` (`hasBuilderWithdrawalCredential`)
- `packages/params/src/presets/mainnet.ts:148` and `.../minimal.ts:149` —
  `MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD: 256`
- `packages/config/src/chainConfig/configs/mainnet.ts:74` —
  `MIN_BUILDER_WITHDRAWABILITY_DELAY: 8192`
  - consumed by `processBuilderDepositRequest.ts:41` and `util/gloas.ts:173`

### Spec anchors (origin/master)
- #5416 `Set BUILDER_WITHDRAWAL_PREFIX to 0xB0` — `specs/gloas/beacon-chain.md`
  (`Bytes1('0x03')` → `Bytes1('0xB0')`). Temporary constant, only used for the fork-time
  builder-deposit credential form `BUILDER_WITHDRAWAL_PREFIX + b"\x00"*11 + execution_address`.
- #5420 `Reduce MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD to 64` — `presets/{mainnet,minimal}/gloas.yaml`
  (`uint64(2**6)`). Bounds the `builder_deposits: List[BuilderDepositRequest, MAX_...]` in the payload.
- #5426 `Reduce MIN_BUILDER_WITHDRAWABILITY_DELAY to 64 epochs` — `configs/mainnet.yaml`
  (drives `builder.withdrawable_epoch = epoch + MIN_BUILDER_WITHDRAWABILITY_DELAY`).

## Impact assessment
- These are **fresh (same-day) spec constant reductions** in the Gloas/EPBS builder path —
  Nico's active area, still churning. No live devnet break: glamsterdam-devnet-N pin a
  fixed spec version, so today's master reductions aren't on the wire yet; this is
  forward-alignment work, not an interop regression.
- `MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD` and `BUILDER_WITHDRAWAL_PREFIX` are the
  interop-relevant ones once a devnet bumps to a post-2026-07-03 spec: the prefix change
  (`0x03`→`0xB0`) alters which withdrawal credentials are recognized as builder credentials,
  and the list bound changes SSZ limits.

## Decision
Per the 2026-06-19 precedent (documented Gloas fork-choice gap, no autonomous PR in Nico's
active area), **document + flag, do not open a PR autonomously**. A batched constant-sync PR
is low-risk and uncontroversial, but Nico owns the Gloas alignment cadence and may prefer to
bump these together with the next devnet spec pin. Captured in BACKLOG for the next
main-session sweep (cron-event context is cross-context-blocked from posting to #347);
open the sync PR only on Nico's go.
