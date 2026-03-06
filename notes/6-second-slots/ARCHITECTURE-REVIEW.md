# Review: EIP-7782 (6s slots) architecture spec for Lodestar

## TL;DR
Your core direction is right, but the current spec underestimates how many places assume **slot duration is globally constant**.  
The piecewise `getCurrentSlot` / `computeTimeAtSlot` approach is correct in principle, but you need a broader refactor to avoid subtle post-fork timing bugs.

---

## 1) Missed edge cases in the clock redesign

### A. You have **multiple clock implementations**, not one
You called out beacon-node clock (`packages/beacon-node/src/util/clock.ts`), but there are at least two more clock paths that still assume fixed slot duration:

- `packages/validator/src/util/clock.ts`
  - `timeUntilNext()` uses modulo with `config.SLOT_DURATION_MS`
  - `getCurrentSlotAround()` uses static `config.SLOT_DURATION_MS`
- `packages/light-client/src/utils/clock.ts`
  - `getCurrentSlot()` and `timeUntilNextEpoch()` assume one slot duration forever

If only state-transition clock math is fixed, validator and light-client behavior can drift at fork.

### B. Epoch timing helpers still use `genesis + epoch * secPerEpoch`
Example: `packages/beacon-node/src/api/impl/validator/index.ts` (`msToNextEpoch`).  
Post-fork this becomes wrong because epoch wall-clock duration changed.

Use:
- `computeTimeAtSlot(config, computeStartSlotAtEpoch(epoch), genesisTime)`
instead of direct `epoch * SLOTS_PER_EPOCH * SLOT_DURATION_MS`.

### C. Precomputed timer values become stale across fork
Some values are computed once at startup with old slot duration and then reused:

- gossipsub `seenTTL`, score decay windows (`scoringParameters.ts`, `gossipsub.ts`)
- notifier half-slot timing (`node/notifier.ts`)
- various delayed callbacks using `config.SLOT_DURATION_MS`

These should be either:
1) fork-aware by slot/fork at use time, or
2) explicitly recomputed when fork boundary is crossed.

### D. Pre-genesis behavior should be explicitly defined
Current formulas can return negative slots before genesis. That may be accepted today, but with more piecewise complexity it’s worth making behavior explicit (clamp or keep as-is consistently).

### E. Use millisecond arithmetic to avoid boundary jitter
Your formulas are logically sound, but using fractional seconds (`Date.now()/1000`) can introduce tiny boundary jitter. Prefer integer ms arithmetic for fork boundary comparisons and slot math.

---

## 2) Is the fork-aware slot/time conversion correct?

Short answer: **yes, conceptually correct**.

Your piecewise forms preserve continuity at the fork boundary:

- `computeTimeAtSlot(forkSlot)` equals `forkTime`
- `getCurrentSlot` switches at `now >= forkTime`
- no off-by-one at exact boundary

So mathematically this is the right model.

### Suggested hardening
- Compute in ms internally:
  - `forkTimeMs = genesisTime*1000 + forkSlot*oldSlotMs`
  - compare with `nowMs`
- Add invariants/tests around boundary:
  - `computeTimeAtSlot(s) <= now < computeTimeAtSlot(s+1)` where `s = getCurrentSlot(...)`
  - continuity test at `forkSlot-1`, `forkSlot`, `forkSlot+1`
  - startup both pre- and post-fork

---

## 3) Additional major risks not fully accounted for

## A. Static `@lodestar/params` constants conflict with fork-time parameter changes
You listed state-transition parameter updates, but several are currently hard-imported constants, not config/fork-aware values.

### Examples:
- `BASE_REWARD_FACTOR` imported in:
  - `state-transition/src/util/altair.ts`
  - `state-transition/src/util/syncCommittee.ts`
  - `state-transition/src/epoch/getAttestationDeltas.ts`
- `EPOCHS_PER_SYNC_COMMITTEE_PERIOD` imported in:
  - `state-transition/src/util/epoch.ts`
  - `state-transition/src/epoch/processSyncCommitteeUpdates.ts`
  - validator/light-client duty logic

If EIP-7782 changes these at a fork, you need fork-aware getters, not compile-time constants.

## B. Light-client SSZ type limits may be wrong after sync-period change
`types/src/*/sszTypes.ts` defines `LightClientStore.validUpdates` max length using `EPOCHS_PER_SYNC_COMMITTEE_PERIOD * SLOTS_PER_EPOCH`.  
If sync period doubles at EIP-7782, this bound likely needs an EIP-7782 fork type update.

## C. ForkConfig due-time helpers still use one global `SLOT_DURATION_MS`
`config/src/forkConfig/index.ts` `getSlotComponentDurationMs()` multiplies BPS by static `config.SLOT_DURATION_MS`.  
All due-time helpers (`getAttestationDueMs`, `getAggregateDueMs`, etc.) therefore remain 12s-derived unless redesigned.

This impacts:
- proposer reorg cutoff
- attestation/sync due windows
- validator duty scheduling

## D. Hardcoded 12s assumptions are broader than listed
You found several already; also include gossipsub scoring windows and followup window:
- `meshMessageDeliveriesWindow = 12 * 1000`
- `gossipsubIWantFollowupMs = 12 * 1000`

## E. Existing fork ordering may conflict with current codebase
Current Lodestar includes `gloas` after `fulu`. If adding `eip7782` “on top of fulu”, clarify whether it is:
- `fulu -> gloas -> eip7782`, or
- replacing/bypassing gloas

This affects fork enum ordering, type resolution, and gossip topic boundaries.

---

## 4) Is implementation order right?

Current order is understandable but I’d change it to reduce rework/risk:

1. **Fork scaffolding first**
   - add fork enum/version/epoch wiring, fork ordering, config schema fields
2. **Introduce fork-aware timing abstraction**
   - canonical helpers for:
     - slot duration at slot/epoch/fork
     - `computeTimeAtSlot`, `getCurrentSlot`, time-to-next-slot/epoch
3. **Migrate all clocks/schedulers to abstraction**
   - beacon-node, validator, light-client, notifier, API epoch wait helpers
4. **Migrate due-time and scoring/time-window logic**
   - forkConfig due windows
   - gossipsub/reqresp windows that are slot-relative
5. **State-transition parameter forking**
   - base reward factor, churn constants, sync committee period, blob limits
   - remove hard dependency on static `@lodestar/params` for fork-changing values
6. **Types + light-client constraints**
   - SSZ bounds and light-client update windows that depend on sync period
7. **Only then sweep hardcoded constants + tune operational timeouts**
8. **Comprehensive transition testing**
   - boundary slot tests, startup pre/post-fork, long-run duty scheduling, gossip scoring behavior

---

## Final assessment
- **Clock piecewise logic:** good foundation, mostly correct.
- **Biggest gap:** treating this as a small clock patch instead of a system-wide “constant-to-fork-aware” migration.
- **Main risk:** consensus-correct slot math with non-consensus subsystems (validator, gossip, light-client, scheduling) still running 12s assumptions, causing missed duties / poor scoring / flaky behavior around and after fork.
