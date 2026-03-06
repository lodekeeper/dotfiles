# EIP-7782 (6-Second Slots) — Architecture Spec for Lodestar

## Overview

Implement EIP-7782 as a new fork on top of Fulu. The core challenge is **changing slot duration at runtime at the fork boundary** — not just running at 6s (which already works).

## Fork Ordering

```
phase0 → altair → bellatrix → capella → deneb → electra → fulu → eip7782
```

- EIP-7782 builds on top of **Fulu** (confirmed by Nico)
- Follows the focil (EIP-7805) insertion pattern exactly
- ForkSeq: `eip7782 = 7` (same slot as eip7805 in focil, displacing gloas)
- For this PoC, Gloas is not included in the fork chain

## Implementation Phases

### Phase 1: Fork Scaffolding (params, config, types)

**`packages/params/src/forkName.ts`**
- Add `eip7782 = "eip7782"` to `ForkName` enum
- Add `eip7782 = 7` to `ForkSeq` enum  
- Add `ForkPreEip7782`, `ForkPostEip7782` types and guards
- Update `forkAll`, `forkPostEip7782` arrays

**`packages/params/src/index.ts`**
- Add EIP-7782 constants:
  - `BASE_REWARD_FACTOR_EIP7782 = 32`
  - `EPOCHS_PER_SYNC_COMMITTEE_PERIOD_EIP7782 = 512`
  - `MIN_PER_EPOCH_CHURN_LIMIT_EIP7782 = 64_000_000_000`
  - `MAX_PER_EPOCH_ACTIVATION_EXIT_CHURN_LIMIT_EIP7782 = 128_000_000_000`

**`packages/config/src/chainConfig/types.ts`**
- Add `EIP7782_FORK_VERSION: Uint8Array`, `EIP7782_FORK_EPOCH: number`
- Add `SLOT_DURATION_MS_EIP7782: number`
- Add all BPS timing params: `ATTESTATION_DUE_BPS_EIP7782`, `AGGREGRATE_DUE_BPS_EIP7782`, etc.

**`packages/config/src/chainConfig/configs/mainnet.ts`**
- `EIP7782_FORK_VERSION: b("0x0b000000")`
- `EIP7782_FORK_EPOCH: Infinity`
- `SLOT_DURATION_MS_EIP7782: 6000`
- All BPS values per spec

**`packages/config/src/chainConfig/configs/minimal.ts`**
- Same but with minimal values (e.g. `EIP7782_FORK_EPOCH: Infinity`)

**`packages/config/src/forkConfig/index.ts`**
- Add `eip7782` ForkInfo entry (prevVersion: FULU, prevForkName: fulu)
- Add fork-aware `getSlotDurationMs(epoch)` method:
  ```ts
  getSlotDurationMs(epoch: Epoch): number {
    return epoch >= config.EIP7782_FORK_EPOCH 
      ? config.SLOT_DURATION_MS_EIP7782 
      : config.SLOT_DURATION_MS;
  }
  ```
- Update `getSlotComponentDurationMs` to use fork-aware slot duration

### Phase 2: Clock Redesign (THE HARD PART)

**`packages/state-transition/src/util/slot.ts`** — Core slot/time conversion

The current functions assume constant slot duration:
```ts
// CURRENT (broken post-fork):
slot = Math.floor(diffInSeconds / (config.SLOT_DURATION_MS / 1000))
time = genesisTime + slot * (config.SLOT_DURATION_MS / 1000)
```

Must become piecewise:
```ts
// NEW: Fork-aware slot calculation
function getCurrentSlot(config, genesisTime): Slot {
  const now = Date.now() / 1000;
  const forkSlot = computeStartSlotAtEpoch(config.EIP7782_FORK_EPOCH);
  const forkTime = genesisTime + forkSlot * (config.SLOT_DURATION_MS / 1000);
  
  if (now < forkTime || config.EIP7782_FORK_EPOCH === Infinity) {
    // Pre-fork: normal 12s calculation
    return GENESIS_SLOT + Math.floor((now - genesisTime) / (config.SLOT_DURATION_MS / 1000));
  }
  
  // Post-fork: forkSlot + time-since-fork at 6s rate
  return forkSlot + Math.floor((now - forkTime) / (config.SLOT_DURATION_MS_EIP7782 / 1000));
}

function computeTimeAtSlot(config, slot, genesisTime): TimeSeconds {
  const forkSlot = computeStartSlotAtEpoch(config.EIP7782_FORK_EPOCH);
  
  if (slot < forkSlot || config.EIP7782_FORK_EPOCH === Infinity) {
    return genesisTime + slot * (config.SLOT_DURATION_MS / 1000);
  }
  
  // Time to reach fork + remaining slots at 6s
  const forkTime = genesisTime + forkSlot * (config.SLOT_DURATION_MS / 1000);
  return forkTime + (slot - forkSlot) * (config.SLOT_DURATION_MS_EIP7782 / 1000);
}
```

**`packages/beacon-node/src/util/clock.ts`** — Clock timer

`msUntilNextSlot()` uses modular arithmetic that breaks at fork boundary:
```ts
// CURRENT (broken):
milliSecondsPerSlot - (diffInMilliSeconds % milliSecondsPerSlot)

// NEW: Use computeTimeAtSlot directly
private msUntilNextSlot(): number {
  const nextSlotTime = computeTimeAtSlot(this.config, this._currentSlot + 1, this.genesisTime) * 1000;
  return Math.max(0, nextSlotTime - Date.now());
}
```

This is cleaner AND handles the fork boundary correctly because `computeTimeAtSlot` is already fork-aware.

### Phase 3: State Transition

**`packages/state-transition/src/slot/upgradeStateToEip7782.ts`** (NEW)
- Copy pattern from focil's `upgradeStateToEip7805.ts`
- Commit Fulu state node → create EIP7782 view
- Set fork version: `config.EIP7782_FORK_VERSION`
- No new state fields (EIP-7782 only changes timing/rewards)

**`packages/state-transition/src/epoch/` modifications:**
- `getBaseRewardPerIncrement()` — use `BASE_REWARD_FACTOR_EIP7782` post-fork
- `getBalanceChurnLimit()` — use `MIN_PER_EPOCH_CHURN_LIMIT_EIP7782` post-fork
- `getActivationExitChurnLimit()` — use halved max post-fork
- `getSyncCommitteePeriod()` — use `EPOCHS_PER_SYNC_COMMITTEE_PERIOD_EIP7782` post-fork

### Phase 4: Hard-coded 12s Assumptions (Codebase Audit)

These must all become fork-aware (see TIMING-AUDIT.md for full list):

| File | Value | Fix |
|------|-------|-----|
| `validator/index.ts:122` | `BLOCK_PRODUCTION_RACE_TIMEOUT_MS = 12_000` | Use `config.getSlotDurationMs(epoch)` |
| `verifyBlocksDataAvailability.ts:6` | `BLOB_AVAILABILITY_TIMEOUT = 12_000` | Use slot duration |
| `rateLimit.ts:88,93` | `quotaTimeMs: 12_000` | Use slot duration |
| `execution/builder/http.ts:42` | `timeout: 12000` | Use slot duration |
| `execution/engine/http.ts:94` | `timeout: 12000` | Use slot duration |
| `gossipsub.ts:153` | `seenTTL: SLOT_DURATION_MS * ...` | Already config-based, OK |
| `scoringParameters.ts` | Multiple | Already config-based, OK if slot duration updated |

### Phase 5: Validator Client Timing

BPS-based timing is already fork-aware in `forkConfig/index.ts:233`:
```ts
getSlotComponentDurationMs(bps) = Math.round((bps * config.SLOT_DURATION_MS) / BASIS_POINTS)
```

This needs to use `getSlotDurationMs(epoch)` instead of `config.SLOT_DURATION_MS`.

Key timing changes post-fork:
- Attestation due: 5000 BPS × 6000ms / 10000 = 3000ms (was 4000ms)
- Aggregate due: 7500 BPS × 6000ms / 10000 = 4500ms (was 8000ms)
- Sync message due: 3333 BPS × 6000ms / 10000 = 2000ms (was 4000ms)

### Phase 6: SSZ Types

EIP-7782 doesn't add new BeaconState fields — same SSZ layout as Fulu.
But we still need:
- `packages/types/src/eip7782/` — re-export Fulu types (same state/block)
- `packages/types/src/ssz/eip7782.ts` — SSZ type definitions
- Register in type index

### Phase 7: Kurtosis Testing

**Custom network params:**
```yaml
participants:
  - el_type: geth
    cl_type: lodestar
    count: 2
    cl_extra_params:
      - "--params.EIP7782_FORK_EPOCH=10"

network_params:
  genesis_delay: 30
  seconds_per_slot: 12
  
additional_services: []
```

**Acceptance criteria (from Nico):**
- No missed blocks or attestations
- Stable peering
- Finalization continuing
- Smooth fork transition at epoch boundary
- "A perfect run"

## Risk Areas

1. **Clock transition at fork boundary** — The exact slot when we switch from 12s→6s. Timer must fire correctly for the first 6s slot. Off-by-one here breaks everything.

2. **Epoch boundary alignment** — Fork happens at epoch boundary. First EIP-7782 slot = `EIP7782_FORK_EPOCH * SLOTS_PER_EPOCH`. The state upgrade runs, then immediately slots start at 6s pace.

3. **Validator duties timing** — Validators subscribed to duties for the fork epoch may have scheduled timers at 12s-based offsets. These need to be recalculated.

4. **Gossip scoring** — `decayIntervalMs` and other scoring params use `config.SLOT_DURATION_MS`. If not updated at fork, gossip scores will be wrong.

5. **EL interaction** — Block timestamps in EL assume 12s between blocks. With 6s slots, the timestamp delta changes. Need to verify engine API handles this.

6. **Sync committee transition** — Period doubles at fork. Need to handle the transition where the current sync committee period length changes.

## Suggested Implementation Order (revised per review)

1. **Fork scaffolding** — enum, version, epoch, config schema, fork ordering
2. **Fork-aware timing abstraction** — canonical helpers: `getSlotDurationMs(epoch)`, piecewise `getCurrentSlot`/`computeTimeAtSlot`, ms-based arithmetic
3. **Migrate ALL clocks** — beacon-node, validator (`packages/validator/src/util/clock.ts`), light-client (`packages/light-client/src/utils/clock.ts`)
4. **Migrate due-time and scoring** — forkConfig `getSlotComponentDurationMs`, gossipsub scoring params, reqresp windows
5. **State-transition parameter forking** — base reward factor, churn, sync committee period, blob limits. Replace static `@lodestar/params` imports with fork-aware getters.
6. **Types + light-client constraints** — SSZ bounds depending on sync committee period
7. **Hard-coded 12s sweep** — all remaining operational timeouts
8. **State upgrade function** — `upgradeStateToEip7782`
9. **Build & type-check** — fix all compilation errors
10. **Kurtosis config + test** — devnet, verify acceptance criteria

## Review Findings (from gpt-advisor)

Key additions to address:
- **3 clock implementations** (beacon-node, validator, light-client) — ALL need migration
- **Static @lodestar/params constants** — `BASE_REWARD_FACTOR`, `EPOCHS_PER_SYNC_COMMITTEE_PERIOD` are compile-time imports, need fork-aware getters
- **Light-client SSZ bounds** — `LightClientStore.validUpdates` max length depends on sync period
- **ms arithmetic** — use integer ms internally, avoid fractional second boundary jitter
- **Fork ordering clarity** — EIP-7782 on Fulu, bypassing Gloas for this PoC
- **Additional hard-coded 12s** — gossipsub `meshMessageDeliveriesWindow`, `gossipsubIWantFollowupMs`
