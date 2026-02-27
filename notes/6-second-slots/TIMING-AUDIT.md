# EIP-7782 Timing Audit — Hard-coded 12s Assumptions in Lodestar

## Critical: Clock (must change)

### `packages/state-transition/src/util/slot.ts`
- `getSlotsSinceGenesis()` — uses `config.SLOT_DURATION_MS / 1000` as constant divisor
  - **MUST** become piecewise: pre-fork slots at 12s, post-fork at 6s
- `computeTimeAtSlot()` — `genesisTime + slot * (config.SLOT_DURATION_MS / 1000)`
  - **MUST** become piecewise: slot→time mapping changes at fork epoch

### `packages/beacon-node/src/util/clock.ts`
- `msUntilNextSlot()` — `config.SLOT_DURATION_MS - (diffInMilliSeconds % milliSecondsPerSlot)`
  - **MUST** use fork-aware slot duration. Simple modular arithmetic won't work at fork boundary.
  - After fork boundary, need to use 6s slot duration. The modular approach breaks because
    pre-fork slots were 12s-aligned.
  - **Fix:** Use `computeTimeAtSlot(currentSlot + 1) - now` instead of modular arithmetic
- `onNextSlot()` — relies on `msUntilNextSlot()`, transitive fix
- `currentSlotWithGossipDisparity` — uses `computeTimeAtSlot`, transitive fix

## Hard-coded 12_000 values (likely need fork-awareness)

### `packages/beacon-node/src/api/impl/validator/index.ts:122`
- `BLOCK_PRODUCTION_RACE_TIMEOUT_MS = 12_000` — timeout for block production race
  - Should be `config.SLOT_DURATION_MS` (or fork-aware)

### `packages/beacon-node/src/chain/blocks/verifyBlocksDataAvailability.ts:6`
- `BLOB_AVAILABILITY_TIMEOUT = 12_000` — timeout waiting for blobs
  - Should be `config.SLOT_DURATION_MS` (or fork-aware)

### `packages/beacon-node/src/network/reqresp/rateLimit.ts:88,93`
- `quotaTimeMs: 12_000` — rate limiting per-slot
  - Should be slot-duration-aware

### `packages/beacon-node/src/execution/builder/http.ts:42`
- `timeout: 12000` — builder API timeout
  - Should be slot-duration-aware

### `packages/beacon-node/src/execution/engine/http.ts:94`
- `timeout: 12000` — engine API timeout
  - Should be slot-duration-aware

## SLOT_DURATION_MS usages (all need to be fork-aware after EIP-7782)

### Already using config.SLOT_DURATION_MS (single value — needs to become fork-aware):
1. `beacon-node/src/api/impl/lodestar/index.ts:32` — profiling duration
2. `beacon-node/src/api/impl/validator/index.ts:191` — half-slot timeout
3. `beacon-node/src/api/impl/validator/index.ts:256` — sec per epoch calculation
4. `beacon-node/src/api/impl/validator/index.ts:1095` — prepare next slot timing
5. `beacon-node/src/chain/blocks/importBlock.ts:269` — delay threshold
6. `beacon-node/src/chain/chain.ts:1341` — sleep half slot
7. `beacon-node/src/chain/validatorMonitor.ts:291` — retain duration
8. `beacon-node/src/node/notifier.ts:144` — ms per slot
9. `beacon-node/src/network/subnets/attnetsService.ts:168` — half-slot timer
10. `beacon-node/src/network/gossip/scoringParameters.ts` — multiple scoring params
11. `beacon-node/src/network/gossip/gossipsub.ts:153` — seenTTL

### `packages/config/src/forkConfig/index.ts:233`
- `getSlotComponentDurationMs()` — BPS-based timing
  - Already uses fork-aware BPS values, but multiplies by `config.SLOT_DURATION_MS`
  - Needs to use fork-aware SLOT_DURATION_MS

### `packages/validator/src/genesis.ts:6`
- `WAITING_FOR_GENESIS_POLL_MS = 12 * 1000` — genesis polling interval
  - Low priority, only used at startup

## Cache Expirations (may assume 12s slot duration)

Need to audit:
- `seenAttestationData` TTL
- `reprocess` queue timeouts
- Gossip seenTTL (`SLOT_DURATION_MS * SLOTS_PER_EPOCH * 2`)
- Op pool pruning intervals

## Approach

The key question: **should `config.SLOT_DURATION_MS` become dynamic, or add `config.SLOT_DURATION_MS_EIP7782`?**

**Option A: Dynamic SLOT_DURATION_MS** — config value changes at fork epoch. Requires `config.getSlotDurationMs(epoch)` method.
- Pro: Minimal changes at call sites
- Con: Config is supposed to be static

**Option B: Fork-aware slot/time functions** — Keep config static, make `getCurrentSlot`/`computeTimeAtSlot` handle the transition.
- Pro: Config stays immutable, follows spec pattern
- Con: More complex slot/time math

**Recommended: Option B** — follows the spec pattern where `get_*_due_ms()` functions take epoch and branch. The core slot/time functions become piecewise.
